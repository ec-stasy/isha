import os
import sys
from pathlib import Path

APP_NAME = "Isha"

# Track A4 security fix: os.chmod(0o600) (used elsewhere, e.g. config_store's
# save) is effectively a no-op on NTFS — it doesn't translate to a real ACL.
# This locks %APPDATA%\Isha down to the owning user only, once per process,
# raising the bar from "any local process can read/write it" to "a process
# already running as this user" — the honest trust boundary for a
# single-user desktop app (see THREAT_MODEL.md).
_dacl_locked = False


def _lock_down_windows_dir(path: Path) -> None:
    if sys.platform != "win32":
        return
    try:
        import subprocess
        username = os.environ.get("USERNAME", "")
        if not username:
            return
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(OI)(CI)F"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass  # best-effort only; never block startup on ACL failures


def app_data_dir() -> Path:
    """
    Returns the per-user application data directory for Isha, creating it if needed.

    Windows: %APPDATA%\\Isha
    Other OSes (dev/test only — Isha ships for Windows): ~/.isha
    """
    global _dacl_locked

    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if not base:
            base = str(Path.home() / "AppData" / "Roaming")
        root = Path(base) / APP_NAME
    else:
        root = Path.home() / ".isha"

    root.mkdir(parents=True, exist_ok=True)

    if not _dacl_locked:
        _lock_down_windows_dir(root)
        _dacl_locked = True

    return root


def logs_dir() -> Path:
    d = app_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_file() -> Path:
    return app_data_dir() / "config.json"


def app_registry_cache_file() -> Path:
    return app_data_dir() / "app_registry_cache.json"
