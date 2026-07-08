"""
Isha 2.0 entry point — the packaged .exe starts here. Creates the Qt app,
enforces a single instance, builds the main window + tray + hotkeys +
schedulers + the async command runner. main.py stays the Qt-free CLI/test
entry; no business logic lives here, only wiring (same rule tray_app.py
followed, now retired).
"""
import ctypes
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

MUTEX_NAME = "IshaSingleInstanceMutex"
ERROR_ALREADY_EXISTS = 183

DEFAULT_VOICE_HOTKEY = "ctrl+alt+v"


def _acquire_single_instance():
    """Named mutex — a second launch exits after nudging the first (two
    instances would fight over RegisterHotKey and the config file)."""
    if sys.platform != "win32":
        return object()
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return None
    return handle


class HotkeyBridge(QObject):
    """Hotkey callbacks fire on the listener's thread; these signals queue
    them onto the UI thread."""
    show_overlay = Signal()
    start_voice = Signal()
    prtscr = Signal()


def _app_icon() -> QIcon:
    for candidate in (APP_DIR / "isha.ico", APP_DIR / "packaging" / "isha.ico",
                      APP_DIR / "assets" / "sprig.svg"):
        if candidate.exists():
            return QIcon(str(candidate))
    return QIcon()


def _build_tray(app, window, runner, config):
    icon = _app_icon()
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Isha")

    menu = QMenu()
    open_action = QAction("Open Isha", menu)
    open_action.triggered.connect(window.bring_to_front)
    menu.addAction(open_action)

    quick_action = QAction("Quick input", menu)

    def _show_overlay():
        from pages.overlay import get_overlay
        get_overlay(config, runner).show_overlay()
    quick_action.triggered.connect(_show_overlay)
    menu.addAction(quick_action)

    screenshot_action = QAction("Take screenshot", menu)
    screenshot_action.triggered.connect(lambda: runner.submit("take screenshot", source="tray"))
    menu.addAction(screenshot_action)

    menu.addSeparator()
    exit_action = QAction("Exit", menu)
    exit_action.triggered.connect(window.force_quit)
    menu.addAction(exit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.bring_to_front() if reason == QSystemTrayIcon.Trigger else None)
    tray.show()
    return tray


def main() -> None:
    mutex = _acquire_single_instance()
    if mutex is None:
        print("Isha is already running — check the tray.")
        return

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Isha")
    app.setQuitOnLastWindowClosed(False)  # close-to-tray; force_quit() exits

    from config_store import load_config
    config = load_config()

    import a_updater
    a_updater.cleanup_stale_update_dirs()

    # warm the app registry off-thread so the first keystroke never pays the scan (P1)
    def _warm_registry():
        try:
            from app_registry import get_app_registry
            get_app_registry()
        except Exception:
            pass
    threading.Thread(target=_warm_registry, daemon=True, name="isha-registry-warmup").start()

    from services.command_runner import CommandRunner
    from services.notifier import Notifier
    from shell.main_window import MainWindow

    runner = CommandRunner(config)
    notifier = Notifier(config)

    import a_notifications
    a_notifications.register_gui_notifier(notifier.notify)

    window = MainWindow(config, runner, notifier)
    window.setWindowIcon(_app_icon())
    window.apply_theme()

    # confirmations: runner (worker thread) -> quiet prompt on the UI thread
    from widgets.quiet_prompt import QuietPrompt

    def _on_confirmation_needed(request):
        parent = window if window.isVisible() else None
        ir = request.resolved_ir
        if getattr(ir, "action", "") == "open_unlisted_url":
            # F1: Open once / Always allow / Not now — always-allow persists the host
            host = (ir.params or {}).get("host") or ir.target
            prompt = QuietPrompt(
                f"Open {host}?", str(ir.target),
                yes_label="Open once", no_label="Not now",
                parent=parent, extra_buttons=[("always", "Always allow")])
            prompt.exec()
            if prompt.choice == "always":
                import a_allow_list
                a_allow_list.add_host(host, config)
            request.resolve(prompt.choice in ("yes", "always"))
            return
        request.resolve(QuietPrompt.ask_for_ir(ir, parent=parent))
    runner.confirmation_needed.connect(_on_confirmation_needed, Qt.QueuedConnection)
    runner.start()

    tray = _build_tray(app, window, runner, config)
    app.isha_tray = tray  # notifier's optional native-toast route

    # -- global hotkeys ---------------------------------------------------
    from hotkey_listener import HotkeyListener, MultiHotkeyListener, DEFAULT_HOTKEY

    bridge = HotkeyBridge()

    def _show_overlay():
        from pages.overlay import get_overlay
        get_overlay(config, runner).show_overlay()
    bridge.show_overlay.connect(_show_overlay, Qt.QueuedConnection)

    def _voice_overlay():
        from pages.overlay import get_overlay
        get_overlay(config, runner).show_overlay(start_listening=True)
    bridge.start_voice.connect(_voice_overlay, Qt.QueuedConnection)
    bridge.prtscr.connect(lambda: runner.submit("take screenshot", source="prtscr"), Qt.QueuedConnection)

    settings = config.get("settings", {})
    hotkey_combo = settings.get("hotkey", DEFAULT_HOTKEY)
    listener = HotkeyListener(on_trigger=bridge.show_overlay.emit, combo=hotkey_combo)
    listener.start()
    if listener.error:
        print(f"[hotkey] {listener.error}")

    voice_combo = settings.get("voice_hotkey") or DEFAULT_VOICE_HOTKEY
    voice_listener = HotkeyListener(on_trigger=bridge.start_voice.emit, combo=voice_combo)
    voice_listener.start()

    # PrtScr capture — off by default; fail-closed (F4)
    prtscr_listener = None
    if (settings.get("screenshot", {}) or {}).get("prtscr") == "isha":
        prtscr_listener = HotkeyListener(on_trigger=bridge.prtscr.emit, combo="printscreen")
        prtscr_listener.start()
        if prtscr_listener.error:
            notifier.notify("Isha", "Couldn't claim the Print Screen key (another app or "
                            "Windows' Snipping Tool holds it) — the option was turned back off.")
            settings.setdefault("screenshot", {})["prtscr"] = "off"
            from config_store import save_config
            save_config(config)

    # live hotkey rebinding for the Shortcuts page (§6.3): swap the listener,
    # fail closed — a RegisterHotKey conflict keeps the old binding running
    listeners = {"hotkey": listener, "voice_hotkey": voice_listener}

    def _rebind_hotkey(settings_key: str, combo: str):
        old = listeners.get(settings_key)
        trigger = bridge.show_overlay.emit if settings_key == "hotkey" else bridge.start_voice.emit
        if old is not None:
            old.stop()
        new = HotkeyListener(on_trigger=trigger, combo=combo)
        new.start()
        import time as _time
        _time.sleep(0.3)  # listener thread reports registration errors asynchronously
        if new.error:
            new.stop()
            if old is not None:
                revert = HotkeyListener(on_trigger=trigger, combo=old.combo if hasattr(old, "combo") else
                                        settings.get(settings_key, DEFAULT_HOTKEY))
                revert.start()
                listeners[settings_key] = revert
            return False, "that key combination is held by another app."
        listeners[settings_key] = new
        return True, "ok"
    app.isha_rebind_hotkey = _rebind_hotkey

    # user-defined command hotkeys — no confirm callback: a hotkey firing
    # unattended must never silently confirm a destructive action
    reserved = {hotkey_combo, voice_combo}
    command_hotkeys = {c: t for c, t in config.get("hotkeys", {}).items() if c not in reserved and t}
    multi = MultiHotkeyListener({
        combo: (lambda t=text, c=combo: runner.submit(t, source=f"hotkey:{c}"))
        for combo, text in command_hotkeys.items()
    })
    multi.start()

    # -- background services ----------------------------------------------
    from mode_scheduler import ModeScheduler
    scheduler = ModeScheduler(config)
    scheduler.start()

    from a_clipboard_history import get_instance as get_clipboard_history
    clipboard = get_clipboard_history()
    clipboard.start()

    window.show()

    if not settings.get("onboarded"):
        from pages.onboarding import show_onboarding
        show_onboarding(window, config)

    exit_code = app.exec()

    listener.stop()
    voice_listener.stop()
    if prtscr_listener is not None:
        prtscr_listener.stop()
    multi.stop()
    scheduler.stop()
    clipboard.stop()
    runner.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
