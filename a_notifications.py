"""
Toast + optional-sound notifications — a thin, lightweight layer with no new
required dependency. Prefers the tray icon's own balloon/toast (pystray,
already optional for Phase 2's tray) when the tray app registered one;
otherwise falls back to a console print plus an optional system beep so
background events (pomodoro phase changes, auto-triggers) are never
completely silent, even headless (CLI-only) or before the tray icon exists.
"""
import sys

IS_WINDOWS = sys.platform == "win32"

_tray_icon = None  # set by tray_app.py once its pystray icon exists


def register_tray_icon(icon) -> None:
    global _tray_icon
    _tray_icon = icon


def notify(title: str, message: str, sound: bool = False) -> None:
    if _tray_icon is not None:
        try:
            _tray_icon.notify(message, title)
        except Exception:
            print(f"[{title}] {message}")
    else:
        print(f"[{title}] {message}")

    if sound and IS_WINDOWS:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
