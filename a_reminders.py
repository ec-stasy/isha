"""
Reminders engine (F5 — closes Cycle 2 C1: reminders used to persist but
never fire). Pure logic, no UI and no thread of its own: mode_scheduler's
existing 20 s poll calls due_reminders(); the executor handlers write the v2
record shape. Records are minimal, flat, human-readable JSON:

  {"id", "text", "at": ISO local, "repeat": "none"|"daily"|"weekly",
   "enabled": bool, "last_fired": ISO|null}

Missed-while-off reminders fire once at startup, marked "(missed)", rather
than being dropped silently.
"""
import uuid
from datetime import datetime, timedelta

from command_ir import CommandIR
from execution_result import ExecutionResult
from config_store import save_config

_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6,
             "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_DAY_PARTS = {"morning": 9, "afternoon": 15, "evening": 18, "night": 21}
_UNIT_SECONDS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
}


def _parse_clock(token: str):
    """'5pm' / '17:00' / '9:30am' -> (hour, minute) or None."""
    token = token.lower().strip()
    suffix = None
    if token.endswith(("am", "pm")):
        suffix = token[-2:]
        token = token[:-2]
    try:
        if ":" in token:
            hour_s, minute_s = token.split(":", 1)
            hour, minute = int(hour_s), int(minute_s)
        else:
            hour, minute = int(token), 0
    except ValueError:
        return None
    if suffix == "pm" and hour < 12:
        hour += 12
    elif suffix == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def parse_time_tokens(tokens, now: datetime = None):
    """
    Turns the parser's raw time token list (e.g. ['at','5pm'], ['in',20,
    'minutes'], ['tomorrow','9am'], ['daily','at','8am']) into
    (at: datetime|None, repeat: str). A past clock time rolls to the next
    occurrence rather than firing immediately.
    """
    now = now or datetime.now()
    tokens = [t for t in (tokens or []) if t not in ("at", "on", "by", "before", "after", "every")]

    repeat = "none"
    clock = None
    day_offset = 0
    weekday = None
    relative_seconds = None

    i = 0
    while i < len(tokens):
        token = tokens[i]
        text = str(token).lower()
        if text in ("daily", "everyday"):
            repeat = "daily"
        elif text == "weekly":
            repeat = "weekly"
        elif text == "tomorrow":
            day_offset = 1
        elif text == "today":
            day_offset = 0
        elif text in _WEEKDAYS:
            weekday = _WEEKDAYS[text]
        elif text in _DAY_PARTS:
            clock = (_DAY_PARTS[text], 0)
        elif isinstance(token, int) and i + 1 < len(tokens) and str(tokens[i + 1]).lower() in _UNIT_SECONDS:
            relative_seconds = token * _UNIT_SECONDS[str(tokens[i + 1]).lower()]
            i += 1
        else:
            parsed = _parse_clock(text)
            if parsed:
                clock = parsed
        i += 1

    if relative_seconds is not None:
        return now + timedelta(seconds=relative_seconds), repeat

    if clock is None and weekday is None and day_offset == 0 and repeat == "none":
        return None, repeat

    hour, minute = clock if clock else (9, 0)  # a day with no time means 9am
    at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    at += timedelta(days=day_offset)
    if weekday is not None:
        days_ahead = (weekday - at.weekday()) % 7
        if days_ahead == 0 and at <= now:
            days_ahead = 7
        at += timedelta(days=days_ahead)
        if repeat == "none":
            pass  # a bare weekday is one-shot; "every friday" arrives as weekly
    elif at <= now and day_offset == 0:
        at += timedelta(days=1)  # past clock time rolls to tomorrow
    return at, repeat


def next_occurrence(at: datetime, repeat: str, after: datetime) -> datetime:
    """First occurrence strictly after `after` for a repeating reminder."""
    step = timedelta(days=1) if repeat == "daily" else timedelta(days=7)
    while at <= after:
        at += step
    return at


def due_reminders(config: dict, now: datetime = None, startup: bool = False) -> list:
    """
    Returns [(record, missed: bool), ...] for reminders due now, updating each
    record in place (last_fired; disable one-shots; advance repeats) and
    saving the config once if anything fired. The caller shows the toasts.
    """
    now = now or datetime.now()
    fired = []
    for record in config.get("reminders", []) or []:
        if not record.get("enabled") or not record.get("at"):
            continue
        try:
            at = datetime.fromisoformat(record["at"])
        except (ValueError, TypeError):
            continue
        if at > now:
            continue
        missed = (now - at) > timedelta(minutes=2)
        fired.append((record, missed))
        record["last_fired"] = now.isoformat(timespec="seconds")
        if record.get("repeat") in ("daily", "weekly"):
            record["at"] = next_occurrence(at, record["repeat"], now).isoformat(timespec="seconds")
        else:
            record["enabled"] = False
    if fired:
        save_config(config)
    return fired


def snooze(config: dict, reminder_id: str, minutes: int = 10) -> None:
    for record in config.get("reminders", []) or []:
        if record.get("id") == reminder_id:
            record["at"] = (datetime.now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")
            record["enabled"] = True
            save_config(config)
            return


# ---------------------------------------------------------------------------
# executor handlers

def set_reminder(ir: CommandIR, config: dict) -> ExecutionResult:
    at, repeat = parse_time_tokens(ir.params.get("time"))
    record = {
        "id": uuid.uuid4().hex[:8],
        "text": str(ir.target),
        "at": at.isoformat(timespec="seconds") if at else None,
        "repeat": repeat,
        "enabled": at is not None,
        "last_fired": None,
    }
    config.setdefault("reminders", []).append(record)
    save_config(config)
    if at is None:
        return ExecutionResult(True, f"Saved “{ir.target}” — but I couldn't read a time, so it won't "
                               "alert you. Try “remind me to {0} at 5pm”.".format(ir.target))
    friendly = at.strftime("%a %d %b, %H:%M")
    extra = f", repeating {repeat}" if repeat != "none" else ""
    return ExecutionResult(True, f"I'll remind you to {ir.target} at {friendly}{extra}.",
                           data={"id": record["id"], "at": record["at"], "repeat": repeat})


def show_reminders(ir: CommandIR, config: dict) -> ExecutionResult:
    records = [r for r in config.get("reminders", []) or [] if isinstance(r, dict)]
    if not records:
        return ExecutionResult(True, "No reminders set. Try “remind me to stretch at 4pm”.")
    lines = []
    for record in sorted(records, key=lambda r: r.get("at") or "9999"):
        state = "" if record.get("enabled") else " (off)"
        repeat = f" · {record['repeat']}" if record.get("repeat") not in (None, "none") else ""
        lines.append(f"• {record.get('text')} — {record.get('at') or 'no time'}{repeat}{state}")
    return ExecutionResult(True, "\n".join(lines), data={"count": len(records)})


def delete_reminder(ir: CommandIR, config: dict) -> ExecutionResult:
    needle = str(ir.target or "").lower()
    records = config.get("reminders", []) or []
    keep = [r for r in records
            if needle not in str(r.get("text", "")).lower() and r.get("id") != needle]
    removed = len(records) - len(keep)
    if not removed:
        return ExecutionResult(False, f"No reminder matching '{ir.target}'.", error="not_found")
    config["reminders"] = keep
    save_config(config)
    return ExecutionResult(True, f"Deleted {removed} reminder(s) matching '{ir.target}'.")
