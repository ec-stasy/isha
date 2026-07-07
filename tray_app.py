"""
Phase 2 entry point: the actual shipped app. Runs Isha as a system-tray
process with a global hotkey and a command-palette window — the three input
paths (hotkey, typed text, and later voice) all feed the same pipeline used
by main.py's CLI, so behavior never diverges between them.

Kept intentionally thin: no business logic lives here, only wiring between
the tray icon, the hotkey listener, and the palette window. Every one of
those three degrades independently and explains itself if its optional
dependency (pystray/Pillow) or platform requirement (Windows, for the
hotkey) isn't available, rather than crashing the whole process.

Phase 5 adds three tray menu items (check for updates, install update,
report an issue) that all delegate to a_updater.py/a_issue_reporter.py
through the same process_command_safe pipeline — "Install update" is the
only one that needs a real confirmation dialog, so it's the only one routed
through the UI queue to run on the Tk thread; the other two are safe to run
directly on a background thread since they never touch Tkinter.

Phase 6 adds a one-time-per-run toast pointing unactivated installs at
'activate license <key>' (typed, not a tray menu item — a license key is a
long pasted string, better suited to the palette than a menu click). It's
informational only; see a_licensing.py for why enforcement is deliberately
soft.
"""
import queue
import sys
import threading

from a_clipboard_history import get_instance as get_clipboard_history
from config_store import load_config
from hotkey_listener import HotkeyListener, MultiHotkeyListener, DEFAULT_HOTKEY
from mode_scheduler import ModeScheduler

SHOW_PALETTE = "show_palette"
QUIT = "quit"
INSTALL_UPDATE = "install_update"
OPEN_SETTINGS = "open_settings"
OPEN_DASHBOARD = "open_dashboard"

DEFAULT_VOICE_HOTKEY = "ctrl+alt+v"

_ui_queue = queue.Queue()


def _build_tray_icon(on_show, on_quit, on_check_updates, on_report_issue, on_install_update, on_open_settings, on_open_dashboard):
    try:
        import pystray
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print(
            "Tray icon needs the optional 'pystray' and 'Pillow' packages (not installed) — "
            "continuing without a tray icon. The hotkey (Windows only) still opens the palette."
        )
        return None

    def _make_image():
        # A calm, Japan-inspired mark: a single ink ring (ensō-style, deliberately
        # not quite closed) around the glyph, rather than a flat filled disc.
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        margin = 4
        ring_color = (58, 139, 255, 255)
        draw.arc((margin, margin, size - margin, size - margin), start=18, end=342, fill=ring_color, width=5)
        try:
            font = ImageFont.truetype("segoeui.ttf", 30)
        except Exception:
            font = None
        text = "I"
        if font is not None:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((size / 2 - tw / 2 - bbox[0], size / 2 - th / 2 - bbox[1]), text, fill=(236, 238, 242, 255), font=font)
        else:
            draw.text((size // 2 - 5, size // 2 - 11), text, fill=(236, 238, 242, 255))
        return img

    menu = pystray.Menu(
        pystray.MenuItem("Open Isha (command palette)", lambda icon, item: on_show(), default=True),
        pystray.MenuItem("Dashboard...", lambda icon, item: on_open_dashboard()),
        pystray.MenuItem("Settings...", lambda icon, item: on_open_settings()),
        pystray.MenuItem("Check for updates", lambda icon, item: on_check_updates()),
        pystray.MenuItem("Install update...", lambda icon, item: on_install_update()),
        pystray.MenuItem("Report an issue", lambda icon, item: on_report_issue()),
        pystray.MenuItem("Quit", lambda icon, item: on_quit()),
    )
    return pystray.Icon("isha", _make_image(), "Isha", menu)


def _notify_license_status_if_unlicensed(config: dict) -> None:
    """
    One-time-per-process-start toast, not a blocking dialog — Isha never
    locks features behind a license (see ROADMAP.md Section 6 and
    a_licensing.py's module docstring for why), so this only ever informs.
    """
    import a_licensing
    from a_notifications import notify

    if not a_licensing.is_licensed(config):
        notify(
            "Isha",
            "Not activated yet — Isha works the same either way. Open the palette and "
            "type 'activate license <key>' if you have a purchase email.",
        )


def _run_check_for_updates(config: dict) -> None:
    """Read-only network check — safe to run on the tray's own thread, no Tk involved."""
    from a_notifications import notify
    from main import process_command_safe

    outcomes = process_command_safe("check updates", config)
    for outcome in outcomes:
        result = outcome["result"]
        notify("Isha — updates", result.message, sound=not result.success)
        if result.success and result.data.get("update_available"):
            notify("Isha — updates", "Use tray > 'Install update...' or type 'install update' to install it.")


def _run_report_issue(config: dict) -> None:
    """Builds a local report zip only — no network call, safe off the Tk thread."""
    from a_notifications import notify
    from main import process_command_safe

    outcomes = process_command_safe("report issue", config)
    for outcome in outcomes:
        result = outcome["result"]
        notify("Isha — report", result.message, sound=not result.success)


def _run_voice_command(config: dict) -> None:
    """
    Voice as an optional module (per the roadmap): imported here, not at
    module load, so a plain hotkey/palette-only install never pays for vosk
    or sounddevice even being probed unless the voice hotkey is actually used.
    """
    from a_notifications import notify
    import a_voice_input

    if not a_voice_input.is_available():
        notify(
            "Isha — voice",
            "Voice input needs the optional 'vosk' + 'sounddevice' packages and a "
            "downloaded Vosk model (not set up) — use the hotkey or palette instead.",
        )
        return

    notify("Isha — voice", "Listening...")
    transcript = a_voice_input.listen_and_transcribe()
    if not transcript:
        notify("Isha — voice", "Didn't catch that — try again.")
        return

    from main import process_command_safe
    outcomes = process_command_safe(transcript, config)
    for outcome in outcomes:
        result = outcome["result"]
        notify("Isha — voice", f"\"{transcript}\" -> {result.message}", sound=not result.success)


def _install_update_on_ui_thread(config: dict) -> None:
    """
    Must only run on the Tk main thread — the confirmation dialog is a real
    tkinter.messagebox prompt, and Tkinter isn't thread-safe. This is why
    request_install_update() posts to the queue instead of calling this
    directly from a pystray callback thread.
    """
    from tkinter import messagebox

    from a_notifications import notify
    from main import process_command_safe

    def confirm(resolved_ir):
        return messagebox.askyesno(
            "Isha — confirm update",
            "Download the update and launch its installer now?\n\n"
            "The installer will open separately; follow its prompts to finish.",
        )

    outcomes = process_command_safe("install update", config, confirm_callback=confirm)
    for outcome in outcomes:
        result = outcome["result"]
        notify("Isha — updates", result.message, sound=not result.success)


def _open_settings_on_ui_thread(config: dict, palette) -> None:
    """Must run on the Tk main thread, like _install_update_on_ui_thread —
    it's a real Toplevel window, and Tkinter isn't thread-safe."""
    from settings_window import SettingsWindow
    SettingsWindow(config, palette.root)


def _open_dashboard_on_ui_thread(config: dict, palette) -> None:
    """Must run on the Tk main thread, like _open_settings_on_ui_thread."""
    from dashboard_window import DashboardWindow
    DashboardWindow(config, palette.root)


def _run_custom_hotkey_command(config: dict, command_text: str, combo: str) -> None:
    """
    Fires a user-bound hotkey -> command text. Runs on the hotkey listener's
    own background thread, same threading contract as _run_voice_command, so
    any confirmation for a destructive action is refused by default rather
    than touching Tkinter off-thread — matching main.process_command's
    documented behavior for callers that pass no confirm_callback (e.g.
    mode_scheduler's auto-triggers). A hotkey firing unattended must never
    silently confirm a destructive action on the user's behalf.
    """
    from a_notifications import notify
    from main import process_command_safe

    outcomes = process_command_safe(command_text, config)
    for outcome in outcomes:
        result = outcome["result"]
        notify(f"Isha — {combo}", result.message, sound=not result.success)


def main() -> None:
    try:
        import tkinter  # noqa: F401 — presence check only; used inside command_palette
    except ImportError:
        print(
            "Isha's command palette needs Tk (python3-tk on Linux; bundled with the "
            "official Windows Python installer). Install it, or run main.py for CLI-only use.",
            file=sys.stderr,
        )
        return

    from command_palette import CommandPalette

    config = load_config()

    import a_updater
    a_updater.cleanup_stale_update_dirs()

    def request_open_settings():
        _ui_queue.put(OPEN_SETTINGS)

    def request_open_dashboard():
        _ui_queue.put(OPEN_DASHBOARD)

    palette = CommandPalette(
        config, on_open_settings=request_open_settings, on_open_dashboard=request_open_dashboard,
    )

    def request_show():
        _ui_queue.put(SHOW_PALETTE)

    def request_quit():
        _ui_queue.put(QUIT)

    def request_check_updates():
        threading.Thread(target=_run_check_for_updates, args=(config,), daemon=True, name="isha-check-updates").start()

    def request_report_issue():
        threading.Thread(target=_run_report_issue, args=(config,), daemon=True, name="isha-report-issue").start()

    def request_install_update():
        # Applying an update needs a real yes/no confirmation dialog, which
        # means touching Tkinter — routed through the UI queue so it runs on
        # the Tk main thread like SHOW_PALETTE/QUIT, never on pystray's own
        # callback thread.
        _ui_queue.put(INSTALL_UPDATE)

    hotkey_combo = config.get("settings", {}).get("hotkey", DEFAULT_HOTKEY)
    listener = HotkeyListener(on_trigger=request_show, combo=hotkey_combo)
    listener.start()
    if listener.error:
        print(f"[hotkey] {listener.error}")

    def request_voice_command():
        threading.Thread(target=_run_voice_command, args=(config,), daemon=True, name="isha-voice-input").start()

    voice_combo = config.get("settings", {}).get("voice_hotkey", DEFAULT_VOICE_HOTKEY)
    voice_listener = HotkeyListener(on_trigger=request_voice_command, combo=voice_combo)
    voice_listener.start()
    if voice_listener.error:
        print(f"[voice hotkey] {voice_listener.error}")

    # User-customizable command hotkeys (config["hotkeys"]: combo -> command
    # text) — a third, user-defined input path alongside the palette and
    # voice hotkeys above. Reserved combos (palette/voice) are skipped so a
    # user rebinding can't silently shadow either built-in listener.
    reserved_combos = {hotkey_combo, voice_combo}
    command_hotkeys = {
        combo: text for combo, text in config.get("hotkeys", {}).items()
        if combo not in reserved_combos and text
    }

    def _make_command_hotkey_callback(command_text, combo):
        def _trigger():
            threading.Thread(
                target=_run_custom_hotkey_command, args=(config, command_text, combo),
                daemon=True, name="isha-command-hotkey",
            ).start()
        return _trigger

    command_hotkey_listener = MultiHotkeyListener({
        combo: _make_command_hotkey_callback(text, combo) for combo, text in command_hotkeys.items()
    })
    command_hotkey_listener.start()
    for error in command_hotkey_listener.errors:
        print(f"[command hotkey] {error}")

    scheduler = ModeScheduler(config)
    scheduler.start()

    # Bug fix (audit, Phase 5): the clipboard-history poller existed but was
    # never started anywhere, so "show clipboard history" always reported
    # empty. The tray app is the long-running process, so it — not the CLI —
    # owns this background thread, same as ModeScheduler.
    clipboard_history = get_clipboard_history()
    clipboard_history.start()

    _notify_license_status_if_unlicensed(config)

    icon = _build_tray_icon(
        request_show, request_quit, request_check_updates, request_report_issue,
        request_install_update, request_open_settings, request_open_dashboard,
    )
    if icon is not None:
        threading.Thread(target=icon.run, daemon=True, name="isha-tray-icon").start()
        from a_notifications import register_tray_icon
        register_tray_icon(icon)

    def poll_queue():
        try:
            while True:
                message = _ui_queue.get_nowait()
                if message == SHOW_PALETTE:
                    palette.show()
                elif message == INSTALL_UPDATE:
                    _install_update_on_ui_thread(config)
                elif message == OPEN_SETTINGS:
                    _open_settings_on_ui_thread(config, palette)
                elif message == OPEN_DASHBOARD:
                    _open_dashboard_on_ui_thread(config, palette)
                elif message == QUIT:
                    listener.stop()
                    voice_listener.stop()
                    command_hotkey_listener.stop()
                    scheduler.stop()
                    clipboard_history.stop()
                    if icon is not None:
                        icon.stop()
                    palette.destroy()
                    return
        except queue.Empty:
            pass
        palette.root.after(100, poll_queue)

    palette.root.after(100, poll_queue)

    if not config.get("settings", {}).get("onboarded"):
        # Track C3: a short guided wizard replaces the old single printed
        # message. Scheduled via after() rather than shown inline so it
        # opens once the Tk mainloop is actually pumping events.
        from onboarding_wizard import OnboardingWizard
        palette.root.after(200, lambda: OnboardingWizard(config, palette.root))

    print(
        f"Isha is running in the tray. Hotkey: {hotkey_combo} (palette), {voice_combo} (voice, optional module) "
        "— both Windows only; tray menu also opens the palette."
    )
    palette.root.mainloop()


if __name__ == "__main__":
    main()
