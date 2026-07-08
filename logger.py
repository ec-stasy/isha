import json
import logging
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from platform_paths import logs_dir

# Actions whose target/params may contain content the user typed for themselves
# (reminder bodies, search text, etc.) rather than an app/system name — redact
# these before writing to disk, per the "no user data collected" promise.
SENSITIVE_ACTIONS = {
    "set_reminder",
    "schedule_task",
    "add_task",
    "search",
    "open_url",
    "show_clipboard_history",   # clipboard contents can be anything, including secrets
    "expand_snippet",           # snippet body is user-authored free text
}

_LOGGER_NAME = "isha.commands"
_logger = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = RotatingFileHandler(
            logs_dir() / "commands.jsonl",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        # raw formatter — each record IS a complete JSON line, nothing to add
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    _logger = logger
    return logger


def _redact(action, value):
    if value is None:
        return None
    if action not in SENSITIVE_ACTIONS:
        return value
    text = str(value)
    return f"<redacted:{len(text)} chars>"


def _ir_to_dict(ir) -> dict:
    if ir is None:
        return {}
    data = asdict(ir) if is_dataclass(ir) else dict(ir)
    action = data.get("action")
    data["target"] = _redact(action, data.get("target"))
    if isinstance(data.get("params"), dict):
        data["params"] = {k: _redact(action, v) for k, v in data["params"].items()}
    return data


def log_command(raw_input: str, tokens: list, ir, resolved_ir=None, execution_result=None) -> str:
    """
    Writes one JSON-lines record capturing the full pipeline for a single command:
    raw input -> tokens -> CommandIR -> resolution -> execution result.

    Deterministic CommandIR + this log means any parse or execution bug can be
    replayed exactly from a single line, without needing the user's machine.

    Returns the generated command_id so callers (e.g. crash handlers, issue
    reports) can cross-reference it.
    """
    command_id = str(uuid.uuid4())
    action = getattr(ir, "action", None) if ir is not None else None

    # Security audit fix (Phase 6): this used to redact raw_input and the
    # structured command_ir/resolved_ir/execution_result.data fields for a
    # sensitive action, but not the token list or the execution result's
    # *message* string — both can carry the exact same content in the clear
    # right next to the redacted fields, defeating the redaction entirely
    # (e.g. a search query surviving verbatim in "tokens"). Both are now
    # redacted the same way as everything else.
    redacted_result = None
    if execution_result is not None:
        redacted_result = dict(execution_result)
        if action in SENSITIVE_ACTIONS:
            if isinstance(redacted_result.get("data"), dict):
                redacted_result["data"] = {k: _redact(action, v) for k, v in redacted_result["data"].items()}
            redacted_result["message"] = _redact(action, redacted_result.get("message"))

    logged_tokens = _redact(action, tokens) if action in SENSITIVE_ACTIONS else tokens

    record = {
        "command_id": command_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_input": _redact(action, raw_input),
        "tokens": logged_tokens,
        "command_ir": _ir_to_dict(ir),
        "resolved_ir": _ir_to_dict(resolved_ir) if resolved_ir is not None else None,
        "execution_result": redacted_result,
    }

    _get_logger().info(json.dumps(record, default=str))
    return command_id


def log_crash(last_records: list, error: Exception) -> str:
    """Writes a crash record with the last N command records for issue reports."""
    crash_id = str(uuid.uuid4())
    record = {
        "crash_id": crash_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "recent_commands": last_records,
    }
    _get_logger().error(json.dumps(record, default=str))
    return crash_id
