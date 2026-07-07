"""
Disk-space check — a cheap, cross-platform utility handler (stdlib only, no
Windows-specific API needed) that reports free/used/total space on a drive.
"""
from pathlib import Path

from execution_result import ExecutionResult


def check_disk_space(path: str = None) -> ExecutionResult:
    target = Path(path) if path else Path.home().anchor or Path("/")
    try:
        import shutil
        total, used, free = shutil.disk_usage(str(target))
    except OSError as e:
        return ExecutionResult(False, f"Couldn't read disk space for '{target}': {e}", error="disk_read_failed")

    gb = 1024 ** 3
    percent_free = (free / total * 100) if total else 0
    message = (
        f"{target}: {free / gb:.1f} GB free of {total / gb:.1f} GB "
        f"({percent_free:.0f}% free)."
    )
    return ExecutionResult(
        True, message,
        data={"path": str(target), "total_bytes": total, "used_bytes": used, "free_bytes": free},
    )
