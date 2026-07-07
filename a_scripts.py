"""
Named scripts (F6) — save a command line under a name, run it later with
"run <name>", or reference it from a mode's script field (one level of
indirection, resolved at activation, never nested — a script's command is
not re-parsed for further script references, which bounds the audit
surface).

Security: execution inherits Track A1 wholesale via executor._run_mode_script
— the settings.allow_scripts opt-in gates all script execution, the literal
command text is confirmed verbatim on run, and non-interactive triggers can
never execute one. Saving never runs anything.
"""
from datetime import datetime

from command_ir import CommandIR
from execution_result import ExecutionResult
from config_store import save_config


def resolve_script_reference(script: str, config: dict) -> str:
    """If a mode's script field names a saved script, return its command
    (one level only); otherwise return the text unchanged."""
    if not script:
        return script
    saved = (config.get("scripts") or {}).get(str(script).strip().lower())
    if isinstance(saved, dict) and saved.get("command"):
        return saved["command"]
    return script


def save_script(ir: CommandIR, config: dict) -> ExecutionResult:
    name = str(ir.params.get("name") or "").strip().lower()
    command = str(ir.params.get("command") or "").strip()
    if not name or " " in name:
        return ExecutionResult(False, "Script names are a single word — e.g. "
                               "'save script backup as robocopy …'.", error="bad_name")
    if not command:
        return ExecutionResult(False, "No command to save.", error="missing_param")
    scripts = config.setdefault("scripts", {})
    existed = name in scripts
    scripts[name] = {"command": command, "created": datetime.now().isoformat(timespec="seconds")}
    save_config(config)
    note = "Updated" if existed else "Saved"
    return ExecutionResult(True, f"{note} script '{name}'. It runs with your permissions — "
                           f"say 'run {name}' to use it (you'll see the exact command first).",
                           data={"name": name})


def run_script(ir: CommandIR, config: dict) -> ExecutionResult:
    name = str(ir.target or "").strip().lower()
    saved = (config.get("scripts") or {}).get(name)
    if not isinstance(saved, dict) or not saved.get("command"):
        return ExecutionResult(False, f"No saved script named '{name}'. "
                               "'show scripts' lists what you have.", error="not_found")
    # Same three gates as mode scripts: allow_scripts opt-in, a live confirm
    # callback, and verbatim approval of this exact command text.
    from executor import _run_mode_script
    return _run_mode_script(saved["command"], config)


def delete_script(ir: CommandIR, config: dict) -> ExecutionResult:
    name = str(ir.target or "").strip().lower()
    scripts = config.get("scripts") or {}
    if name not in scripts:
        return ExecutionResult(False, f"No saved script named '{name}'.", error="not_found")
    del scripts[name]
    save_config(config)
    return ExecutionResult(True, f"Deleted script '{name}'.")


def show_scripts(ir: CommandIR, config: dict) -> ExecutionResult:
    scripts = config.get("scripts") or {}
    if not scripts:
        return ExecutionResult(True, "No saved scripts. Try 'save script <name> as <command>'.")
    lines = [f"• {name}: {record.get('command')}" for name, record in sorted(scripts.items())]
    return ExecutionResult(True, "\n".join(lines), data={"count": len(scripts)})
