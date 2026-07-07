"""
Undo last action — an in-memory-only stack of reversible records (nothing
persisted to disk; undo across an app restart isn't a meaningful concept for
most of these actions). Only a single level is exposed to the user ("undo"),
but a small stack is kept so multiple undos in a row make sense.

Deliberately scoped to actions that are safe and cheap to reverse:
open/close app, activate/deactivate mode, create/delete mode, mute/unmute.
Destructive, hard-to-reverse actions (shutdown, empty_recycle_bin, uninstall)
are never recorded here — there is nothing safe to undo them with.
"""
import collections

from command_ir import CommandIR

_MAX_UNDO_DEPTH = 10
_stack = collections.deque(maxlen=_MAX_UNDO_DEPTH)

# actions whose successful execution gets an undo record pushed
_UNDO_BUILDERS = {}


def _register(action):
    def decorator(fn):
        _UNDO_BUILDERS[action] = fn
        return fn
    return decorator


@_register("open_app")
def _undo_open_app(ir, result, config, snapshot):
    return {"description": f"close {_target_name(ir.target)}", "kind": "execute",
            "action": "close_app", "target": ir.target, "params": {}}


@_register("close_app")
def _undo_close_app(ir, result, config, snapshot):
    return {"description": f"reopen {_target_name(ir.target)}", "kind": "execute",
            "action": "open_app", "target": ir.target, "params": {}}


@_register("activate_mode")
def _undo_activate_mode(ir, result, config, snapshot):
    prior_active = snapshot.get("prior_active_mode")
    if prior_active:
        return {"description": f"reactivate '{prior_active}' mode", "kind": "execute",
                "action": "activate_mode", "target": prior_active, "params": {}}
    return {"description": f"deactivate '{ir.target}' mode", "kind": "execute",
            "action": "deactivate_mode", "target": ir.target, "params": {}}


@_register("deactivate_mode")
def _undo_deactivate_mode(ir, result, config, snapshot):
    return {"description": f"reactivate '{ir.target}' mode", "kind": "execute",
            "action": "activate_mode", "target": ir.target, "params": {}}


@_register("create_mode")
def _undo_create_mode(ir, result, config, snapshot):
    return {"description": f"delete '{ir.target}' mode", "kind": "execute",
            "action": "delete_mode", "target": ir.target, "params": {}}


@_register("delete_mode")
def _undo_delete_mode(ir, result, config, snapshot):
    mode_data = snapshot.get("prior_mode_data")
    if mode_data is None:
        return None  # nothing captured to restore
    return {"description": f"restore '{ir.target}' mode", "kind": "restore_mode",
            "mode_name": str(ir.target).lower(), "mode_data": mode_data}


@_register("mute_volume")
def _undo_mute_volume(ir, result, config, snapshot):
    return {"description": "unmute volume", "kind": "execute",
            "action": "unmute_volume", "target": None, "params": {}}


def _target_name(target) -> str:
    if isinstance(target, dict):
        return target.get("name") or "?"
    return str(target) if target else "?"


def snapshot_before(ir: CommandIR, config: dict) -> dict:
    """Captures whatever pre-execution state a given action's undo record might
    need (e.g. the active mode before switching, a mode's data before deleting
    it) — cheap dict lookups done unconditionally before every execute() call."""
    snap = {"prior_active_mode": config.get("active_mode")}
    if ir.action == "delete_mode" and ir.target:
        snap["prior_mode_data"] = config.get("modes", {}).get(str(ir.target).lower())
    return snap


def record(ir: CommandIR, result, config: dict, snapshot: dict) -> None:
    if not result.success:
        return
    builder = _UNDO_BUILDERS.get(ir.action)
    if not builder:
        return
    undo_record = builder(ir, result, config, snapshot)
    if undo_record:
        _stack.append(undo_record)


def peek_description():
    return _stack[-1]["description"] if _stack else None


def perform_undo(config: dict):
    from execution_result import ExecutionResult

    if not _stack:
        return ExecutionResult(False, "Nothing to undo.", error="nothing_to_undo")

    undo_record = _stack.pop()

    if undo_record["kind"] == "restore_mode":
        from config_store import save_config
        config["modes"][undo_record["mode_name"]] = undo_record["mode_data"]
        save_config(config)
        return ExecutionResult(True, f"Undid: restored '{undo_record['mode_name']}' mode.")

    from executor import execute
    ir = CommandIR(action=undo_record["action"], target=undo_record["target"], params=dict(undo_record["params"]))
    result = execute(ir, config)
    result.message = f"Undid ({undo_record['description']}): {result.message}"
    return result
