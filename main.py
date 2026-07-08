import sys
import traceback

import undo_manager
from input_processor import input_processor
from command_splitter import command_splitter
from command_parser import command_parser
from c_resolver_validator import resolve_and_validate
from executor import execute, set_confirm_callback
from config_store import load_config, save_config
from logger import log_command, log_crash

# recent records kept in memory only for crash reports — never written unless a crash happens
_recent_records = []
_MAX_RECENT_RECORDS = 50


def _record_recent(command_id: str, command_input: str) -> None:
    _recent_records.append({"command_id": command_id, "input": command_input})
    if len(_recent_records) > _MAX_RECENT_RECORDS:
        _recent_records.pop(0)


def process_command(command_input: str, config: dict, confirm_callback=None) -> list:
    """
    Runs one line of input through the full pipeline and returns a structured
    outcome per split sub-command, instead of printing — so any front end
    (CLI loop, command palette, future voice input) can present it however
    fits that surface (text, toast, screen-reader announcement, ...).

    confirm_callback, if given, is called with the resolved CommandIR for any
    action flagged requires_confirmation, and must return a bool. Front ends
    that don't pass one (e.g. mode_scheduler's auto-triggers) get the old,
    safe-by-default behavior: destructive actions simply refuse and say why —
    scheduled triggers must never silently confirm a destructive action.

    Each item: {"result": ExecutionResult, "warnings": [str, ...]}
    """
    tokens = input_processor(command_input)
    commands = command_splitter(tokens)

    outcomes = []
    for command_tokens in commands:
        ir = command_parser(command_tokens)
        resolved_ir = resolve_and_validate(ir, config)

        if resolved_ir.params.get("requires_confirmation") and confirm_callback and not resolved_ir.params.get("confirmed"):
            resolved_ir.params["confirmed"] = bool(confirm_callback(resolved_ir))

        undo_snapshot = undo_manager.snapshot_before(resolved_ir, config)
        # Threaded per-call (not just per-process) so a mode script's own
        # confirmation (executor._run_mode_script, Track A1) always uses
        # *this* call's confirm_callback — None for callers like
        # mode_scheduler's auto-trigger thread, which must never confirm on
        # the user's behalf.
        set_confirm_callback(confirm_callback)
        result = execute(resolved_ir, config)
        undo_manager.record(resolved_ir, result, config, undo_snapshot)

        command_id = log_command(command_input, command_tokens, ir, resolved_ir, vars(result))
        _record_recent(command_id, command_input)

        outcomes.append({"result": result, "warnings": list(resolved_ir.warnings)})

    return outcomes


def process_command_safe(command_input: str, config: dict, confirm_callback=None) -> list:
    """
    Same as process_command, but never raises — any front end that isn't the
    CLI loop below (tray icon, palette, hotkey callback) needs a call that
    can't take the whole process down. Crashes are still logged and surfaced
    as a single failed outcome with a report ID.
    """
    try:
        return process_command(command_input, config, confirm_callback)
    except Exception as e:
        crash_id = log_crash(_recent_records, e)
        from execution_result import ExecutionResult
        return [{
            "result": ExecutionResult(False, f"Something went wrong (report ID: {crash_id}).", error="crash"),
            "warnings": [],
        }]


def _cli_confirm(resolved_ir) -> bool:
    if resolved_ir.action == "open_unlisted_url":
        prompt = f"{resolved_ir.target} isn't on your allow list — open it anyway? [y/N]: "
    elif resolved_ir.action in ("run_mode_script", "run_script"):
        prompt = f"Isha is about to run this script:\n  {resolved_ir.target}\nAllow? [y/N]: "
    else:
        name = resolved_ir.target if isinstance(resolved_ir.target, str) else (resolved_ir.target or {}).get("name") or resolved_ir.action
        prompt = f"'{resolved_ir.action}' on '{name}' can't be easily undone — proceed? [y/N]: "
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def run_command(command_input: str, config: dict) -> None:
    """CLI presentation: print each outcome, prompting for real confirmation on destructive actions."""
    for outcome in process_command(command_input, config, confirm_callback=_cli_confirm):
        result = outcome["result"]
        status = "OK" if result.success else "FAILED"
        print(f"[{status}] {result.message}")
        for warning in outcome["warnings"]:
            print(f"  warning: {warning}")


def _show_onboarding_if_first_run(config: dict) -> None:
    if config.get("settings", {}).get("onboarded"):
        return
    print(
        "\nWelcome to Isha! A few things to know:\n"
        "  - Type a command in plain English (or Hinglish), e.g. 'open chrome' or 'create study mode chrome and youtube'.\n"
        "  - Type 'help' any time for a full cheat sheet of commands.\n"
        "  - Destructive actions (shutdown, delete mode, ...) always ask you to confirm first.\n"
        "  - Made a mistake? Type 'undo' to reverse your last action.\n"
        "  - Nothing you type ever leaves this machine unless you explicitly ask to report an issue.\n"
    )
    config.setdefault("settings", {})["onboarded"] = True
    save_config(config)


def main() -> None:
    config = load_config()
    import a_updater
    a_updater.cleanup_stale_update_dirs()
    _show_onboarding_if_first_run(config)

    while True:
        try:
            command_input = input("Enter command (blank to quit): ").strip()
        except EOFError:
            break

        if not command_input:
            break

        try:
            run_command(command_input, config)
        except Exception as e:
            crash_id = log_crash(_recent_records, e)
            print(f"Something went wrong (report ID: {crash_id}).", file=sys.stderr)
            traceback.print_exc()


if __name__ == "__main__":
    main()
