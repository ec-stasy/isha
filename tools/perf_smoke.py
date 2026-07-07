"""
Perf smoke (§7 P5 — measurement, not vibes). Times three things against the
Cycle 4 targets and prints a small table:

  cold construct+show of the main window   target < 2000 ms
  overlay show (already-built, the hotkey path)  target < 50 ms
  20 sequential pipeline commands (headless)     just recorded

Run:  python tools/perf_smoke.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    t_import = time.perf_counter()
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    from config_store import _default_config
    config = _default_config()
    config["settings"]["onboarded"] = True

    from services.command_runner import CommandRunner
    from services.notifier import Notifier
    from shell.main_window import MainWindow

    t0 = time.perf_counter()
    runner = CommandRunner(config)
    notifier = Notifier(config)
    window = MainWindow(config, runner, notifier)
    window.apply_theme()
    window.show()
    app.processEvents()
    cold_ms = (time.perf_counter() - t0) * 1000
    with_imports_ms = (time.perf_counter() - t_import) * 1000

    from pages.overlay import get_overlay
    overlay = get_overlay(config, runner)
    overlay.show_overlay()
    overlay.hide()
    app.processEvents()
    t0 = time.perf_counter()
    overlay.show_overlay()
    app.processEvents()
    overlay_ms = (time.perf_counter() - t0) * 1000

    # 20 headless pipeline commands (no Qt involved)
    from main import process_command_safe
    commands = ["help", "show allow list", "show reminders", "show scripts",
                "check disk space", "license status", "show clipboard history",
                "allow website example.com", "disallow example.com", "undo"] * 2
    t0 = time.perf_counter()
    for command in commands:
        process_command_safe(command, config)
    pipeline_ms = (time.perf_counter() - t0) * 1000

    print(f"window construct+show : {cold_ms:8.0f} ms   (target < 2000; excl. imports)")
    print(f"  incl. Qt imports    : {with_imports_ms:8.0f} ms")
    print(f"overlay re-show       : {overlay_ms:8.0f} ms   (target < 50)")
    print(f"20 pipeline commands  : {pipeline_ms:8.0f} ms   ({pipeline_ms/20:.1f} ms each)")


if __name__ == "__main__":
    main()
