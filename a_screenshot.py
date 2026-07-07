"""
Screenshot utility — captures the full desktop and saves it locally under
Pictures\\Isha Screenshots. Nothing is uploaded or sent anywhere; this is a
local file write only, consistent with the "no data leaves the machine"
promise unless the user explicitly triggers issue reporting.
"""
import datetime
from pathlib import Path

from execution_result import ExecutionResult


def _screenshots_dir() -> Path:
    d = Path.home() / "Pictures" / "Isha Screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def take_screenshot(ir=None, config: dict = None) -> ExecutionResult:
    try:
        from PIL import ImageGrab
    except ImportError:
        return ExecutionResult(
            False,
            "Screenshots need the optional 'Pillow' module (not installed).",
            error="missing_dependency",
        )

    try:
        image = ImageGrab.grab()
    except Exception as e:
        return ExecutionResult(False, f"Couldn't capture the screen: {e}", error="capture_failed")

    filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = _screenshots_dir() / filename
    try:
        image.save(path)
    except OSError as e:
        return ExecutionResult(False, f"Couldn't save screenshot: {e}", error="save_failed")

    return ExecutionResult(True, f"Screenshot saved to {path}.", data={"path": str(path)})
