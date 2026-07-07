"""
One-click issue reporting (Phase 5) — builds a local zip of exactly what the
roadmap promises and nothing more: the last ~50 already-redacted command log
records, basic OS/version info, and an optional user-typed description. It is
never uploaded automatically; sending is a separate, explicitly-confirmed
step gated on an opt-in intake URL, per the "we take no data" promise.
"""
import json
import platform
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

from execution_result import ExecutionResult
from platform_paths import app_data_dir, logs_dir
from version import VERSION

MAX_LOG_RECORDS = 50
_REPORTS_DIRNAME = "reports"


def _reports_dir() -> Path:
    d = app_data_dir() / _REPORTS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tail_log_records(limit: int = MAX_LOG_RECORDS) -> list:
    """
    Last `limit` lines of the current command log. Records are already
    redacted at write time (logger.py), so nothing further needs scrubbing
    here — this only ever reads the log Isha itself wrote.
    """
    log_path = logs_dir() / "commands.jsonl"
    if not log_path.exists():
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return []
    return [line.rstrip("\n") for line in lines[-limit:] if line.strip()]


def _system_info() -> dict:
    return {
        "isha_version": VERSION,
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
    }


def latest_report_path():
    """Most recently built report zip, or None if none exist yet."""
    d = _reports_dir()
    zips = sorted(d.glob("report_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


def build_report(config: dict, description: str = "") -> ExecutionResult:
    """
    Writes a report zip to disk and returns a manifest of exactly what's in
    it, so the caller (tray/palette/CLI) can show the user before offering
    to send it. Never makes a network call.
    """
    report_id = uuid.uuid4().hex[:12]
    records = _tail_log_records()
    info = _system_info()
    description = (description or "").strip()

    manifest_lines = [
        f"Isha issue report {report_id}",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "This zip contains, and ONLY contains:",
        f"  - system_info.json ({', '.join(info.keys())})",
        f"  - commands_log.jsonl ({len(records)} of your most recent command records, already redacted)",
    ]
    if description:
        manifest_lines.append("  - description.txt (what you typed)")
    manifest_lines += ["", "Nothing here is uploaded unless you explicitly choose to send it."]

    zip_path = _reports_dir() / f"report_{report_id}.zip"
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.txt", "\n".join(manifest_lines))
            zf.writestr("system_info.json", json.dumps(info, indent=2))
            zf.writestr("commands_log.jsonl", "\n".join(records))
            if description:
                zf.writestr("description.txt", description)
    except OSError as e:
        return ExecutionResult(False, f"Couldn't write the report zip: {e}", error="io_error")

    included = ["manifest.txt", "system_info.json", "commands_log.jsonl"]
    if description:
        included.append("description.txt")

    return ExecutionResult(
        True,
        f"Report {report_id} saved to {zip_path}. Nothing has been sent — "
        "review the file, then run 'send report' if you want to submit it.",
        data={
            "report_id": report_id,
            "path": str(zip_path),
            "included_files": included,
            "record_count": len(records),
        },
    )


def send_report(config: dict, zip_path: str) -> ExecutionResult:
    """
    Uploads a previously-built report zip — opt-in only. If
    config["settings"]["report_intake_url"] isn't set, this refuses outright
    rather than guessing an endpoint; this is the one Isha action that sends
    data off the machine without the user directly asking for that specific
    URL (unlike open_url/search), so it's kept as its own confirmed step,
    separate from building the report.
    """
    url = (config.get("settings", {}) or {}).get("report_intake_url")
    if not url:
        return ExecutionResult(
            False,
            "No report intake URL is configured — the report stays local only. "
            "Set settings.report_intake_url in config.json to enable sending, or "
            "attach the zip to an email yourself.",
            error="not_configured",
        )
    if not str(url).lower().startswith("https://"):
        return ExecutionResult(False, "Refusing to send a report over a non-HTTPS URL.", error="insecure_url")

    path = Path(zip_path)
    if not path.is_file():
        return ExecutionResult(False, f"Report file not found: {zip_path}", error="not_found")

    try:
        with open(path, "rb") as f:
            payload = f.read()
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/zip",
                "X-Isha-Report-Id": path.stem.replace("report_", ""),
                "X-Isha-Version": VERSION,
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
    except Exception as e:
        return ExecutionResult(False, f"Couldn't send the report: {e}", error="send_failed")

    if 200 <= status < 300:
        return ExecutionResult(True, f"Report sent (server responded {status}).")
    return ExecutionResult(False, f"Report upload failed (server responded {status}).", error="send_failed")
