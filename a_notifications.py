"""
Notification fan-out — the stable public notify() every background module
(pomodoro, mode_scheduler, reminders) calls. Cycle 4: when the Qt app is
running it registers a GUI notifier (services/notifier.py — calm top-right
toast cards, silent by default); headless/CLI use falls back to a console
print. The old pystray-balloon path is gone with pystray itself.
"""
import sys

IS_WINDOWS = sys.platform == "win32"

_gui_notify = None  # set by app.py once the Qt notifier exists


def register_gui_notifier(fn) -> None:
    """fn(title, message, sound=False, actions=None) — must be thread-safe."""
    global _gui_notify
    _gui_notify = fn


def register_tray_icon(icon) -> None:  # legacy no-op shim (pystray path removed)
    pass


def notify(title: str, message: str, sound: bool = False, actions=None) -> None:
    if _gui_notify is not None:
        try:
            _gui_notify(title, message, sound=sound, actions=actions)
            return
        except Exception:
            pass
    print(f"[{title}] {message}")
