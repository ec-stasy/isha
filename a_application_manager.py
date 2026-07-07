"""
Application-manager utility: read-only queries over installed/running apps,
layered on top of app_registry.py's scan. Used by the executor's clean-switching
logic in activate_mode (Modes 2.0) and exposed as a direct user query.
"""
import subprocess
import sys

from app_registry import get_app_registry
from execution_result import ExecutionResult

IS_WINDOWS = sys.platform == "win32"


def list_installed_apps(config: dict = None) -> ExecutionResult:
    apps = sorted(get_app_registry().keys())
    if not apps:
        return ExecutionResult(False, "No installed apps found in the registry scan.", error="empty_registry")
    return ExecutionResult(True, f"{len(apps)} installed app(s) found.", data={"apps": apps})


def is_app_running(image_name: str) -> bool:
    """
    Windows-only process check via tasklist; used to decide whether an app
    needs (re)launching during a mode switch. Returns False (not True) on any
    platform/parsing failure — a false negative just re-launches an already
    running app, which is harmless; a false positive would skip launching one.
    """
    if not IS_WINDOWS:
        return False
    if not image_name:
        return False
    if not image_name.lower().endswith(".exe"):
        image_name = f"{image_name}.exe"

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
            capture_output=True, text=True, shell=False, timeout=5,
        )
        return image_name.lower() in result.stdout.lower()
    except (OSError, subprocess.TimeoutExpired):
        return False
