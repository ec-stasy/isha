"""
Screenshot utility (F4) — captures the desktop (or the foreground window)
and saves it locally. Default folder is the system-standard
Pictures\\Screenshots (resolved via SHGetKnownFolderPath so a OneDrive-
redirected Pictures is respected — the same folder Win+PrtScr uses);
settings.screenshot.dir overrides it. settings.screenshot.after ==
"save_and_open" opens the PNG in the default viewer after saving. Nothing
is uploaded anywhere; this is a local file write only.
"""
import datetime
import os
import sys
from pathlib import Path

from execution_result import ExecutionResult

IS_WINDOWS = sys.platform == "win32"


def _system_pictures_dir() -> Path:
    """The user's real Pictures folder — known-folder API first (handles
    OneDrive redirection), plain home fallback otherwise."""
    if IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes
            # FOLDERID_Pictures = {33E28130-4E1E-4676-835A-98395C3BC3BB}
            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]
            guid = GUID(0x33E28130, 0x4E1E, 0x4676,
                        (ctypes.c_ubyte * 8)(0x83, 0x5A, 0x98, 0x39, 0x5C, 0x3B, 0xC3, 0xBB))
            path_ptr = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(
                    ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)) == 0:
                result = Path(path_ptr.value)
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
                return result
        except Exception:
            pass
    return Path.home() / "Pictures"


def screenshots_dir(config: dict = None) -> Path:
    configured = ((config or {}).get("settings", {}).get("screenshot", {}) or {}).get("dir")
    directory = Path(configured) if configured else _system_pictures_dir() / "Screenshots"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _foreground_window_bbox():
    """The foreground window's rectangle, or None to fall back to full screen."""
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None
        return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        return None


def take_screenshot(ir=None, config: dict = None) -> ExecutionResult:
    try:
        from PIL import ImageGrab
    except ImportError:
        return ExecutionResult(
            False,
            "Screenshots need the optional 'Pillow' module (not installed).",
            error="missing_dependency",
        )

    settings = ((config or {}).get("settings", {}).get("screenshot", {}) or {})
    bbox = None
    if settings.get("capture") == "window" and IS_WINDOWS:
        bbox = _foreground_window_bbox()

    try:
        image = ImageGrab.grab(bbox=bbox, all_screens=(bbox is not None))
    except Exception as e:
        return ExecutionResult(False, f"Couldn't capture the screen: {e}", error="capture_failed")

    filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    try:
        path = screenshots_dir(config) / filename
        image.save(path)
    except OSError as e:
        return ExecutionResult(False, f"Couldn't save screenshot: {e}", error="save_failed")

    opened = False
    if settings.get("after") == "save_and_open" and IS_WINDOWS:
        try:
            os.startfile(str(path))  # default image viewer
            opened = True
        except OSError:
            pass

    suffix = " and opened it" if opened else ""
    return ExecutionResult(True, f"Screenshot saved to {path}{suffix}.",
                           data={"path": str(path), "opened": opened})
