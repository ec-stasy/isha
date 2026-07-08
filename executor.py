import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import a_mode_manager
from a_check_disk_space import check_disk_space as _check_disk_space
from a_check_internet import check_internet as _check_internet
from a_screenshot import take_screenshot as _take_screenshot
from a_clipboard_history import show_clipboard_history as _show_clipboard_history
from a_clipboard_history import clear_clipboard_history as _clear_clipboard_history
from a_pomodoro import start_pomodoro as _start_pomodoro
from a_pomodoro import stop_pomodoro as _stop_pomodoro
from command_ir import CommandIR
from execution_result import ExecutionResult

IS_WINDOWS = sys.platform == "win32"

# Track A1 security fix: a mode's free-text `script` field is an arbitrary-
# process-launch primitive (config.json is plaintext and user-editable), so
# running it must never be silent. The confirm callback each front end passes
# into main.process_command is threaded down here per-thread (not a plain
# global — mode_scheduler's poller thread and the Tk thread can call execute()
# concurrently) so _run_mode_script can ask before running, and so a caller
# that never supplies one (mode_scheduler's auto-triggers) gets a callback of
# None, which means "refuse" — never "run anyway".
_confirm_state = threading.local()


def set_confirm_callback(callback) -> None:
    _confirm_state.callback = callback


def _get_confirm_callback():
    return getattr(_confirm_state, "callback", None)


def _unsupported_platform(action: str) -> ExecutionResult:
    return ExecutionResult(
        False,
        f"'{action}' needs Windows to run; this platform isn't supported.",
        error="unsupported_platform",
    )


def _not_yet_implemented(action: str) -> ExecutionResult:
    return ExecutionResult(False, f"'{action}' isn't implemented yet.", error="not_implemented")


def _app_path(target) -> str:
    """target is a dict resolved by c_resolver_validator ({'name', 'path'}); tolerate a bare string too."""
    if isinstance(target, dict):
        return target.get("path")
    return None


def _app_name(target) -> str:
    if isinstance(target, dict):
        return target.get("name")
    return str(target) if target else None


# ---------------------------------------------------------------------------------------
# apps

def _is_path_trustworthy(path: str) -> bool:
    """
    Track A4 security fix: app_registry_cache.json is a convenience index, not
    an authority — it's plain JSON, writable by any process running as this
    user, and open_app used to launch whatever path was in it with no further
    checks. Poisoning the cache used to be enough to make "open chrome" launch
    an attacker's binary. This re-validates the path at launch time instead of
    trusting the cache blindly: it must actually exist, and (on Windows) it
    must live somewhere a legitimately-installed or PATH-reachable program
    would — not just anywhere on disk a planted file could sit.
    """
    try:
        candidate = Path(path)
        if not candidate.is_file():
            return False
        resolved = candidate.resolve()
    except OSError:
        return False

    if not IS_WINDOWS:
        return True  # dev/non-Windows: existence is all we can meaningfully assert here

    allowed_roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramW6432"),
        os.environ.get("LocalAppData"),
        os.environ.get("APPDATA"),
        os.environ.get("WinDir"),
    ]
    # %TEMP% lives *inside* LocalAppData on Windows, but a planted file in a
    # world-of-this-user-writable temp dir is exactly the poisoning scenario
    # this check exists for — carve it out before the root allow-list runs.
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir:
        try:
            if str(resolved).lower().startswith(str(Path(temp_dir).resolve()).lower() + os.sep):
                return False
        except OSError:
            pass

    for root in filter(None, allowed_roots):
        try:
            root_resolved = Path(root).resolve()
        except OSError:
            continue
        if str(resolved).lower().startswith(str(root_resolved).lower()):
            return True

    # Also allow anything actually reachable on PATH *right now* — re-derived
    # live, not trusted from the cache — which covers portable/dev tools
    # installed outside the usual roots without trusting the cache blindly.
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        try:
            if Path(directory).resolve() == resolved.parent:
                return True
        except OSError:
            continue

    return False


def open_app(ir: CommandIR, config: dict) -> ExecutionResult:
    path = _app_path(ir.target)
    name = _app_name(ir.target)
    if not path:
        return ExecutionResult(False, f"Don't know how to launch '{name or ir.target}' — no resolved path.", error="unresolved_target")

    if not _is_path_trustworthy(path):
        return ExecutionResult(
            False,
            f"Refusing to launch '{name}': its cached path no longer looks valid or safe "
            f"({path}). Try again after Isha rescans installed apps.",
            error="untrusted_path",
        )

    try:
        # list form, never shell=True: the resolved path came from our own trusted
        # registry scan, but we still don't want to hand a string to a shell
        subprocess.Popen([path], shell=False)
        return ExecutionResult(True, f"Opened {name}.", data={"path": path})
    except OSError as e:
        return ExecutionResult(False, f"Couldn't open {name}: {e}", error="launch_failed")


def close_app(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("close_app")

    path = _app_path(ir.target)
    name = _app_name(ir.target)
    image_name = Path(path).name if path else f"{name}.exe"

    try:
        result = subprocess.run(
            ["taskkill", "/IM", image_name],
            capture_output=True, text=True, shell=False,
        )
        if result.returncode == 0:
            return ExecutionResult(True, f"Closed {name}.", data={"image_name": image_name})
        return ExecutionResult(False, f"Couldn't close {name}: {result.stderr.strip()}", error="close_failed")
    except OSError as e:
        return ExecutionResult(False, f"Couldn't close {name}: {e}", error="close_failed")


def uninstall_app(ir: CommandIR, config: dict) -> ExecutionResult:
    # Deliberately not automated: uninstall strings are inconsistent and risky to
    # invoke blindly. Send the user to the native, confirmable Windows UI instead.
    name = _app_name(ir.target)
    if not IS_WINDOWS:
        return _unsupported_platform("uninstall_app")
    try:
        os.startfile("ms-settings:appsfeatures")
        return ExecutionResult(
            True,
            f"Opened Windows Settings > Apps — search for '{name}' to uninstall it safely.",
            data={"name": name},
        )
    except OSError as e:
        return ExecutionResult(False, f"Couldn't open Settings: {e}", error="open_settings_failed")


# ---------------------------------------------------------------------------------------
# system value controls (volume/brightness/...)

def _volume_key(vk_code: int) -> ExecutionResult:
    import ctypes
    KEYEVENTF_EXTENDEDKEY = 0x1
    KEYEVENTF_KEYUP = 0x2
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
    return ExecutionResult(True, "Done.")


def _set_volume_level(level: int) -> ExecutionResult:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError:
        return ExecutionResult(
            False,
            "Setting an exact volume level needs the optional 'pycaw' module (not installed).",
            error="missing_dependency",
        )

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
    return ExecutionResult(True, f"Set volume to {level}%.", data={"level": level})


def increase_value(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("increase_value")
    if ir.target == "volume":
        return _volume_key(0xAF)  # VK_VOLUME_UP
    return _not_yet_implemented(f"increase {ir.target}")


def decrease_value(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("decrease_value")
    if ir.target == "volume":
        return _volume_key(0xAE)  # VK_VOLUME_DOWN
    return _not_yet_implemented(f"decrease {ir.target}")


def set_value(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("set_value")

    level = ir.params.get("level")
    if level is None:
        return ExecutionResult(False, "No level given to set.", error="missing_param")

    if ir.target == "volume":
        return _set_volume_level(level)
    if ir.target in ("dark_mode", "light_mode"):
        return _set_theme(ir.target == "dark_mode")
    return _not_yet_implemented(f"set {ir.target}")


def toggle_value(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("toggle_value")
    if ir.target in ("dark_mode", "light_mode"):
        return _set_theme(ir.target == "dark_mode")
    return _not_yet_implemented(f"toggle {ir.target}")


def _set_theme(dark: bool) -> ExecutionResult:
    import winreg
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            value = 0 if dark else 1
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
        return ExecutionResult(True, f"Switched to {'dark' if dark else 'light'} mode.")
    except OSError as e:
        return ExecutionResult(False, f"Couldn't change theme: {e}", error="registry_write_failed")


def mute_volume(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("mute_volume")
    # F3: multi-device-aware — behavior chosen by settings.audio.mute_behavior
    # (default halve_all); degrades to the old media-key toggle without pycaw.
    import a_audio
    return a_audio.mute(config)


def unmute_volume(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("unmute_volume")
    import a_audio
    return a_audio.unmute(config)


# ---------------------------------------------------------------------------------------
# power / session actions — shutdown/restart/hibernate are gated behind
# requires_confirmation upstream in execute(); sleep/lock/refresh are reversible enough to run directly

def shutdown(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("shutdown")
    subprocess.run(["shutdown", "/s", "/t", "0"], shell=False)
    return ExecutionResult(True, "Shutting down.")


def restart(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("restart")
    subprocess.run(["shutdown", "/r", "/t", "0"], shell=False)
    return ExecutionResult(True, "Restarting.")


def hibernate(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("hibernate")
    subprocess.run(["shutdown", "/h"], shell=False)
    return ExecutionResult(True, "Hibernating.")


def sleep(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("sleep")
    import ctypes
    ctypes.windll.powrprof.SetSuspendState(False, True, True)
    return ExecutionResult(True, "Going to sleep.")


def lock_screen(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("lock_screen")
    import ctypes
    ctypes.windll.user32.LockWorkStation()
    return ExecutionResult(True, "Locked.")


def refresh(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("refresh")
    import ctypes
    VK_F5 = 0x74
    ctypes.windll.user32.keybd_event(VK_F5, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_F5, 0, 2, 0)
    return ExecutionResult(True, "Refreshed.")


# ---------------------------------------------------------------------------------------
# browser / search

def _allow_list_gate(url: str, config: dict) -> ExecutionResult:
    """
    F1: allow-listed hosts pass silently; anything else needs an explicit
    affirmative from this call's confirm callback (shown as a quiet prompt,
    never an alarm). Callers with no callback — schedulers, triggers — get a
    calm skip, consistent with Track A's rule that background paths never
    confirm on the user's behalf. Returns None when the open may proceed.
    """
    import a_allow_list
    if a_allow_list.is_allowed(url, config):
        return None
    host = a_allow_list.normalize_host(url) or url
    confirm = _get_confirm_callback()
    if confirm is None:
        return ExecutionResult(
            True,
            f"Skipped {host} — it's not on your allow list. Open Isha and say "
            f"'allow website {host}' to let it open automatically.",
            data={"skipped": "not_allow_listed", "url": url},
        )
    if not confirm(CommandIR(action="open_unlisted_url", target=url, params={"host": host})):
        return ExecutionResult(True, f"Didn't open {host} (not on your allow list, not confirmed).",
                               data={"skipped": "declined", "url": url})
    return None


def open_url(ir: CommandIR, config: dict) -> ExecutionResult:
    if not ir.target:
        return ExecutionResult(False, "No URL to open.", error="unresolved_target")
    gate = _allow_list_gate(ir.target, config)
    if gate is not None:
        return gate
    opened = webbrowser.open(ir.target)
    if not opened:
        return ExecutionResult(False, f"No browser available to open {ir.target}.", error="no_browser")
    return ExecutionResult(True, f"Opened {ir.target}.", data={"url": ir.target})


def search(ir: CommandIR, config: dict) -> ExecutionResult:
    return open_url(ir, config)


# ---------------------------------------------------------------------------------------
# window management

def _find_window_by_title(substring: str):
    import win32gui

    matches = []

    def _callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and substring.lower() in title.lower():
                matches.append(hwnd)

    win32gui.EnumWindows(_callback, None)
    return matches[0] if matches else None


def _window_action(ir: CommandIR, action_name: str, win32_call) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform(action_name)
    try:
        import win32gui
    except ImportError:
        return ExecutionResult(False, "Window management needs the optional 'pywin32' module (not installed).", error="missing_dependency")

    name = _app_name(ir.target)
    if not name:
        return ExecutionResult(False, "No window to act on.", error="unresolved_target")

    hwnd = _find_window_by_title(name)
    if not hwnd:
        return ExecutionResult(False, f"No open window matching '{name}'.", error="window_not_found")

    win32_call(win32gui, hwnd)
    return ExecutionResult(True, f"{action_name.replace('_', ' ').title()}: {name}.", data={"window": name})


def focus_window(ir: CommandIR, config: dict) -> ExecutionResult:
    return _window_action(ir, "focus_window", lambda g, h: g.SetForegroundWindow(h))


def maximize_window(ir: CommandIR, config: dict) -> ExecutionResult:
    return _window_action(ir, "maximize_window", lambda g, h: g.ShowWindow(h, 3))  # SW_MAXIMIZE


def minimize_window(ir: CommandIR, config: dict) -> ExecutionResult:
    return _window_action(ir, "minimize_window", lambda g, h: g.ShowWindow(h, 6))  # SW_MINIMIZE


def show_window(ir: CommandIR, config: dict) -> ExecutionResult:
    return _window_action(ir, "show_window", lambda g, h: g.ShowWindow(h, 5))  # SW_SHOW


def hide_window(ir: CommandIR, config: dict) -> ExecutionResult:
    return _window_action(ir, "hide_window", lambda g, h: g.ShowWindow(h, 0))  # SW_HIDE


def snap_window(ir: CommandIR, config: dict) -> ExecutionResult:
    # Precise snap-zone geometry is Phase 3 (Modes 2.0); the window is at least
    # brought into focus now rather than doing nothing.
    return _not_yet_implemented("snap_window")


def resize_window(ir: CommandIR, config: dict) -> ExecutionResult:
    return _not_yet_implemented("resize_window")


def move_window(ir: CommandIR, config: dict) -> ExecutionResult:
    return _not_yet_implemented("move_window")


# ---------------------------------------------------------------------------------------
# reminders / tasks — Phase 1 persists them; a background scheduler is a later phase

def set_reminder(ir: CommandIR, config: dict) -> ExecutionResult:
    # F5: real records, parsed times, and a scheduler pass that fires them.
    import a_reminders
    return a_reminders.set_reminder(ir, config)


def schedule_task(ir: CommandIR, config: dict) -> ExecutionResult:
    from config_store import save_config
    config["reminders"].append({"type": "task", "target": ir.target, "time": ir.params.get("time")})
    save_config(config)
    return ExecutionResult(True, "Task saved (no background scheduler yet, so it won't run automatically).", data={"target": ir.target})


def add_task(ir: CommandIR, config: dict) -> ExecutionResult:
    from config_store import save_config
    config["reminders"].append({"type": "task", "target": ir.target, "time": None})
    save_config(config)
    return ExecutionResult(True, f"Added task: {ir.target}.", data={"target": ir.target})


def cancel_task(ir: CommandIR, config: dict) -> ExecutionResult:
    import a_reminders
    return a_reminders.delete_reminder(ir, config)


# ---------------------------------------------------------------------------------------
# file operations — not automated: the parser gives free text, not validated
# source/destination paths, and guessing wrong here means lost or overwritten files

def copy_item(ir: CommandIR, config: dict) -> ExecutionResult:
    return _not_yet_implemented("copy_item")


def rename_item(ir: CommandIR, config: dict) -> ExecutionResult:
    return _not_yet_implemented("rename_item")


# ---------------------------------------------------------------------------------------
# utilities — disk/internet checks, screenshot, recycle bin, clipboard history,
# text snippets, focus/pomodoro timer

def check_disk_space(ir: CommandIR, config: dict) -> ExecutionResult:
    return _check_disk_space(ir.target if ir.target else None)


def check_internet(ir: CommandIR, config: dict) -> ExecutionResult:
    return _check_internet()


def take_screenshot(ir: CommandIR, config: dict) -> ExecutionResult:
    return _take_screenshot(ir, config)


def empty_recycle_bin(ir: CommandIR, config: dict) -> ExecutionResult:
    if not IS_WINDOWS:
        return _unsupported_platform("empty_recycle_bin")
    import ctypes
    SHERB_NOCONFIRMATION, SHERB_NOPROGRESSUI, SHERB_NOSOUND = 0x00000001, 0x00000002, 0x00000004
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    result_code = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    # 0 = success; -2147418113 (0x8000FFFF) is also returned when the bin is already empty
    if result_code in (0, -2147418113):
        return ExecutionResult(True, "Recycle bin emptied.")
    return ExecutionResult(False, f"Couldn't empty recycle bin (error code {result_code}).", error="recycle_bin_failed")


def show_clipboard_history(ir: CommandIR, config: dict) -> ExecutionResult:
    return _show_clipboard_history(ir, config)


def clear_clipboard_history(ir: CommandIR, config: dict) -> ExecutionResult:
    return _clear_clipboard_history(ir, config)


def _type_text(text: str) -> ExecutionResult:
    if not IS_WINDOWS:
        return ExecutionResult(
            False,
            f"Can't type text automatically outside Windows; here it is to copy: {text}",
            error="unsupported_platform", data={"text": text},
        )
    import ctypes
    from ctypes import wintypes

    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT)]

    for char in text:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(0, ord(char), flags, 0, None))
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    return ExecutionResult(True, "Snippet typed.", data={"text": text})


def expand_snippet(ir: CommandIR, config: dict) -> ExecutionResult:
    name = str(ir.target).lower() if ir.target else None
    if not name:
        return ExecutionResult(False, "No snippet name given.", error="missing_param")

    text = config.get("snippets", {}).get(name)
    if text is None:
        return ExecutionResult(False, f"No snippet named '{name}' (add one to config.json's 'snippets').", error="not_found")

    return _type_text(text)


def start_pomodoro(ir: CommandIR, config: dict) -> ExecutionResult:
    return _start_pomodoro(ir, config)


def stop_pomodoro(ir: CommandIR, config: dict) -> ExecutionResult:
    return _stop_pomodoro(ir, config)


# ---------------------------------------------------------------------------------------
# modes — Modes 2.0: mixed apps/websites, script-on-activate, per-mode system
# state, best-effort window layout, and clean switching (A→B closes only A's
# apps not needed by B, opens only B's delta)

def _mode_item_key(item) -> str:
    if isinstance(item, dict):
        if item.get("type") == "website":
            return f"website:{item.get('url')}"
        return f"app:{(item.get('name') or '').lower()}"
    return f"app:{str(item).lower()}"


def _mode_item_name(item) -> str:
    return item.get("name") if isinstance(item, dict) else str(item)


# In-session-only tracking of the window a website item was opened in, so
# deactivate can close that exact window (Phase 4 fix for Phase 3's "can't
# close a website tab" limitation). Resets on restart — there's no stable
# cross-session handle to a browser window, so this is best-effort, not a
# full fix: it only works for websites opened in their own dedicated window
# (via the default browser's --new-window flag), not a tab in an existing one.
_website_windows = {}  # mode_name -> {url: hwnd}

_BROWSER_NEW_WINDOW_ARGS = {
    "chrome.exe": ["--new-window"],
    "msedge.exe": ["--new-window"],
    "brave.exe": ["--new-window"],
    "firefox.exe": ["-new-window"],
}


def _default_browser_path():
    if not IS_WINDOWS:
        return None
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\shell\open\command") as key:
            command, _ = winreg.QueryValueEx(key, "")
        import shlex
        parts = shlex.split(command)
        return parts[0] if parts else None
    except OSError:
        return None


def _visible_window_handles() -> set:
    import win32gui
    handles = set()
    win32gui.EnumWindows(lambda hwnd, _: handles.add(hwnd) if win32gui.IsWindowVisible(hwnd) else None, None)
    return handles


def _wait_for_new_window(before: set, timeout: float = 3.0):
    import time as _time
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        new = _visible_window_handles() - before
        if new:
            return next(iter(new))
        _time.sleep(0.2)
    return None


def _open_website_item(item: dict, config: dict, mode_name: str) -> ExecutionResult:
    url = item.get("url")
    # F1 gate applies to mode websites too; the dedicated-window fast path
    # below bypasses open_url, so the check must happen here as well.
    gate = _allow_list_gate(url, config)
    if gate is not None:
        return gate
    if not IS_WINDOWS:
        return open_url(CommandIR(action="open_url", target=url), config)

    browser_path = _default_browser_path()
    if not browser_path:
        return open_url(CommandIR(action="open_url", target=url), config)

    try:
        import win32gui  # noqa: F401 — presence check for the window-tracking helpers above
    except ImportError:
        return open_url(CommandIR(action="open_url", target=url), config)

    exe_name = Path(browser_path).name.lower()
    extra_args = _BROWSER_NEW_WINDOW_ARGS.get(exe_name, [])
    before = _visible_window_handles()
    try:
        subprocess.Popen([browser_path, *extra_args, url], shell=False)
    except OSError:
        return open_url(CommandIR(action="open_url", target=url), config)

    hwnd = _wait_for_new_window(before)
    if hwnd and mode_name:
        _website_windows.setdefault(mode_name, {})[url] = hwnd
    return ExecutionResult(True, f"Opened {url}.", data={"url": url, "tracked_window": bool(hwnd)})


def _open_mode_item(item, config: dict, mode_name: str = None) -> ExecutionResult:
    if isinstance(item, dict) and item.get("type") == "website":
        return _open_website_item(item, config, mode_name)
    return open_app(CommandIR(action="open_app", target=item), config)


def _close_mode_item(item, config: dict, mode_name: str = None) -> ExecutionResult:
    if isinstance(item, dict) and item.get("type") == "website":
        url = item.get("url")
        hwnd = _website_windows.get(mode_name, {}).pop(url, None) if mode_name else None
        if hwnd and IS_WINDOWS:
            try:
                import win32gui
                import win32con
                if win32gui.IsWindow(hwnd):
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    return ExecutionResult(True, f"Closed website window '{_mode_item_name(item)}'.")
            except Exception:
                pass
        return ExecutionResult(
            True,
            f"Skipped closing website '{_mode_item_name(item)}' "
            "(no tracked dedicated window this session — it may share a window with other tabs).",
        )
    return close_app(CommandIR(action="close_app", target=item), config)


def _run_mode_script(script: str, config: dict) -> ExecutionResult:
    """
    Track A1 fix: mode scripts are an arbitrary-process-launch primitive
    (config.json is plaintext and user-editable), so this never runs one
    silently. Three gates, all of which must pass:
      1. settings.allow_scripts must be explicitly on (default off) —
         most users never need this, so nobody is exposed by default.
      2. A confirm callback must exist for the calling thread — the CLI and
         palette set one; mode_scheduler's auto-trigger thread never does, so
         a scheduled activation always skips the script step, never runs it.
      3. The user must explicitly approve THIS script's literal text — a
         config edit can't smuggle a command past someone who thinks they're
         just switching modes.
    The mode's apps/websites/system-state still apply either way; only this
    one step is ever skipped.
    """
    if not script:
        return ExecutionResult(True, "No script to run.")

    # F6: a mode's script field may name a saved script — one level of
    # indirection, resolved here so the verbatim confirmation below always
    # shows the real command that would run, never just the name.
    import a_scripts
    script = a_scripts.resolve_script_reference(script, config)

    settings = config.get("settings", {}) or {}
    # v2 key with the v1 name accepted for un-migrated configs handed in directly
    if not settings.get("allow_scripts", settings.get("allow_mode_scripts", False)):
        return ExecutionResult(
            True,
            "Script skipped (scripts are disabled by default — turn on "
            "'allow scripts' in Isha's settings to enable them).",
            data={"skipped": "disabled"},
        )

    confirm = _get_confirm_callback()
    if confirm is None:
        return ExecutionResult(
            True,
            "Mode script skipped (no one was available to confirm it — automatic "
            "triggers never run mode scripts).",
            data={"skipped": "no_confirm"},
        )

    allowed = bool(confirm(CommandIR(action="run_mode_script", target=script)))
    if not allowed:
        return ExecutionResult(True, "Mode script skipped (not confirmed).", data={"skipped": "declined"})

    import shlex
    try:
        subprocess.Popen(shlex.split(script, posix=not IS_WINDOWS), shell=False)
        return ExecutionResult(True, f"Ran script: {script}")
    except (OSError, ValueError) as e:
        return ExecutionResult(False, f"Mode script failed: {e}", error="script_failed")


def _apply_mode_system_state(system_state: dict, config: dict) -> list:
    """Best-effort: applies volume/theme for a mode; failures are collected, not fatal."""
    problems = []
    if "volume" in system_state:
        result = set_value(CommandIR(action="set_value", target="volume", params={"level": system_state["volume"]}), config)
        if not result.success:
            problems.append(result.message)
    if "theme" in system_state and system_state["theme"] in ("dark", "light"):
        result = _set_theme(system_state["theme"] == "dark") if IS_WINDOWS else _unsupported_platform("set theme")
        if not result.success:
            problems.append(result.message)
    return problems


def _apply_mode_window_layout(window_layout: dict) -> list:
    """
    Best-effort geometry restore (Modes 2.0's "restore window layout"). Runs
    right after launch, so a just-started app's window may not exist yet —
    that's a known limitation, not silently swallowed: misses are reported.
    """
    if not window_layout:
        return []
    if not IS_WINDOWS:
        return [f"Window layout needs Windows to apply ({len(window_layout)} entr(y/ies) skipped)."]
    try:
        import win32gui
        import win32con
    except ImportError:
        return ["Window layout needs the optional 'pywin32' module (not installed)."]

    problems = []
    for name, geometry in window_layout.items():
        hwnd = _find_window_by_title(name)
        if not hwnd:
            problems.append(f"'{name}' has no open window yet to position.")
            continue
        try:
            win32gui.SetWindowPos(
                hwnd, None,
                geometry.get("x", 0), geometry.get("y", 0),
                geometry.get("w", 800), geometry.get("h", 600),
                win32con.SWP_NOZORDER,
            )
        except Exception as e:
            problems.append(f"Couldn't position '{name}': {e}")
    return problems


def activate_mode(ir: CommandIR, config: dict) -> ExecutionResult:
    new_items = a_mode_manager.get_mode_apps(config, ir.target)
    if not new_items:
        return ExecutionResult(False, f"Mode '{ir.target}' has no apps to open.", error="empty_mode")

    old_name = config.get("active_mode")
    old_items = a_mode_manager.get_mode_apps(config, old_name) if old_name and old_name != ir.target else []

    new_by_key = {_mode_item_key(i): i for i in new_items}
    old_by_key = {_mode_item_key(i): i for i in old_items}

    # clean switching: only close what the new mode doesn't need, only open what wasn't already running
    to_close = [item for key, item in old_by_key.items() if key not in new_by_key]
    to_open = [item for key, item in new_by_key.items() if key not in old_by_key]

    closed, close_failed = [], []
    for item in to_close:
        result = _close_mode_item(item, config, old_name)
        (closed if result.success else close_failed).append(_mode_item_name(item))

    opened, failed = [], []
    for item in to_open:
        result = _open_mode_item(item, config, ir.target)
        (opened if result.success else failed).append(_mode_item_name(item))

    problems = []
    problems += _apply_mode_system_state(a_mode_manager.get_mode_system_state(config, ir.target), config)
    script_result = _run_mode_script(a_mode_manager.get_mode_script(config, ir.target), config)
    if not script_result.success or (script_result.data or {}).get("skipped"):
        problems.append(script_result.message)
    problems += _apply_mode_window_layout(a_mode_manager.get_mode_window_layout(config, ir.target))

    a_mode_manager.set_active_mode(config, ir.target)

    message = f"Activated '{ir.target}': opened {len(opened)} item(s)"
    if closed:
        message += f", closed {len(closed)} from '{old_name}'"
    message += "."
    if failed:
        message += f" Couldn't open: {', '.join(failed)}."
    if close_failed:
        message += f" Couldn't close: {', '.join(close_failed)}."
    if problems:
        message += " " + " ".join(problems)

    return ExecutionResult(
        not failed or bool(opened), message,
        data={"opened": opened, "failed": failed, "closed": closed, "close_failed": close_failed},
    )


def deactivate_mode(ir: CommandIR, config: dict) -> ExecutionResult:
    items = a_mode_manager.get_mode_apps(config, ir.target)
    if not items:
        return ExecutionResult(False, f"Mode '{ir.target}' has no apps to close.", error="empty_mode")

    closed, failed = [], []
    for item in items:
        result = _close_mode_item(item, config, ir.target)
        (closed if result.success else failed).append(_mode_item_name(item))

    if config.get("active_mode") == ir.target:
        a_mode_manager.set_active_mode(config, None)

    message = f"Deactivated '{ir.target}': closed {len(closed)} item(s)."
    if failed:
        message += f" Couldn't close: {', '.join(failed)}."
    return ExecutionResult(not failed or bool(closed), message, data={"closed": closed, "failed": failed})


def set_mode_script(ir: CommandIR, config: dict) -> ExecutionResult:
    return a_mode_manager.set_mode_script(config, ir.target, ir.params.get("script"))


def set_mode_volume(ir: CommandIR, config: dict) -> ExecutionResult:
    return a_mode_manager.set_mode_volume(config, ir.target, ir.params.get("level"))


def set_mode_theme(ir: CommandIR, config: dict) -> ExecutionResult:
    return a_mode_manager.set_mode_theme(config, ir.target, ir.params.get("theme"))


def capture_mode_layout(ir: CommandIR, config: dict) -> ExecutionResult:
    """Typed shorthand for Phase 3's config-editable-only window_layout field:
    snapshots the current position/size of each of the mode's already-open app
    windows, so a later activation can restore them via _apply_mode_window_layout."""
    if not IS_WINDOWS:
        return _unsupported_platform("capture_mode_layout")
    try:
        import win32gui
    except ImportError:
        return ExecutionResult(False, "Needs the optional 'pywin32' module (not installed).", error="missing_dependency")

    items = a_mode_manager.get_mode_apps(config, ir.target)
    layout = {}
    missing = []
    for item in items:
        if isinstance(item, dict) and item.get("type") == "website":
            continue
        name = _mode_item_name(item)
        hwnd = _find_window_by_title(name)
        if not hwnd:
            missing.append(name)
            continue
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        layout[name] = {"x": left, "y": top, "w": right - left, "h": bottom - top}

    if not layout:
        return ExecutionResult(False, f"No open windows found for mode '{ir.target}' to capture.", error="nothing_to_capture")

    result = a_mode_manager.set_mode_window_layout(config, ir.target, layout)
    if missing:
        result.message += f" (no open window for: {', '.join(missing)})"
    return result


def create_mode(ir: CommandIR, config: dict) -> ExecutionResult:
    return a_mode_manager.create_mode(config, ir.target, ir.params.get("new", []))


def update_mode(ir: CommandIR, config: dict) -> ExecutionResult:
    return a_mode_manager.update_mode(config, ir.target, ir.params.get("add"), ir.params.get("remove"))


def delete_mode(ir: CommandIR, config: dict) -> ExecutionResult:
    return a_mode_manager.delete_mode(config, ir.target)


# ---------------------------------------------------------------------------------------
# Phase 4 — custom aliases, undo, and comfort/onboarding

def add_alias(ir: CommandIR, config: dict) -> ExecutionResult:
    from config_store import save_config
    word = str(ir.params.get("alias", "")).lower()
    canonical = str(ir.target).lower() if ir.target else None
    if not word or not canonical:
        return ExecutionResult(False, "Need both an alias word and its target.", error="missing_param")
    config["aliases"][word] = canonical
    save_config(config)
    return ExecutionResult(True, f"'{word}' now means '{canonical}'.", data={"alias": word, "target": canonical})


def remove_alias(ir: CommandIR, config: dict) -> ExecutionResult:
    from config_store import save_config
    word = str(ir.target).lower() if ir.target else None
    if not word or word not in config.get("aliases", {}):
        return ExecutionResult(False, f"No alias named '{ir.target}'.", error="not_found")
    del config["aliases"][word]
    save_config(config)
    return ExecutionResult(True, f"Removed alias '{word}'.")


def undo_last_action(ir: CommandIR, config: dict) -> ExecutionResult:
    import undo_manager
    return undo_manager.perform_undo(config)


HELP_TEXT = """Isha — quick reference
Apps: "open chrome", "close notepad"
Web: "go to youtube", "search python tutorials"
Modes: "create study mode chrome and youtube", "activate study mode",
       "update study mode add spotify", "delete study mode"
Mode fields: "study mode script <command>", "study mode vol <0-100>",
       "study mode theme dark|light", "study mode layout" (capture current)
       (mode scripts are disabled by default — turn on "allow mode scripts" in
       Settings, and Isha will still show you the exact command before running
       it; auto-triggers never run a mode script even when enabled)
System: "mute", "set volume to 50", "lock screen", "shutdown" (asks to confirm)
Utilities: "screenshot", "check disk space", "check internet", "empty recycle bin",
       "show clipboard history", "start pomodoro <mode>", "stop pomodoro"
Aliases: "alias browser as chrome", "remove alias browser"
Comfort: "undo" (reverses your last action), "help" (this list)
Support: "report issue <optional description>" (saves a local zip, asks before
       sending), "send report" (sends the most recent one), "check updates",
       "install update" (asks to confirm before running an installer)
Hotkey: opens the command palette (default ctrl+alt+space)."""


def show_help(ir: CommandIR, config: dict) -> ExecutionResult:
    return ExecutionResult(True, HELP_TEXT)


# ---------------------------------------------------------------------------------------
# Phase 5 — issue reporting and update checking. Both are network-touching by
# nature, so both go through the same "opt-in, explicit, never silent" rules
# as the rest of Isha: reporting only builds a local zip until a separate
# 'send report' is explicitly confirmed, and update checks/applies never run
# unless the user asks and are refused outright if unsigned.

def report_issue(ir: CommandIR, config: dict) -> ExecutionResult:
    import a_issue_reporter
    description = ir.params.get("description") or ""
    return a_issue_reporter.build_report(config, description)


def send_report(ir: CommandIR, config: dict) -> ExecutionResult:
    import a_issue_reporter
    path = ir.target or ir.params.get("path")
    if not path:
        latest = a_issue_reporter.latest_report_path()
        if latest is None:
            return ExecutionResult(
                False, "No report has been built yet — run 'report issue' first.", error="not_found"
            )
        path = str(latest)
    return a_issue_reporter.send_report(config, path)


def check_for_updates(ir: CommandIR, config: dict) -> ExecutionResult:
    import a_updater
    return a_updater.check_for_update(config)


def apply_update(ir: CommandIR, config: dict) -> ExecutionResult:
    import a_updater
    check_result = a_updater.check_for_update(config)
    if not check_result.success:
        return check_result
    if not check_result.data.get("update_available"):
        return ExecutionResult(True, check_result.message)

    dl_result = a_updater.download_and_verify(check_result.data)
    if not dl_result.success:
        return dl_result

    installer_path = dl_result.data["installer_path"]
    if not IS_WINDOWS:
        return ExecutionResult(
            True,
            f"Update downloaded and verified to {installer_path}. Launching installers "
            "is Windows-only here; run it manually to apply.",
            data=dl_result.data,
        )

    # Track A2 fix: re-verify the checksum right before Popen, not only at
    # download time, to close the TOCTOU window where a local process could
    # have swapped the file after the earlier check.
    reverify = a_updater.verify_installer_before_launch(installer_path, dl_result.data["sha256"])
    if not reverify.success:
        return reverify

    try:
        subprocess.Popen([installer_path], shell=False)
    except OSError as e:
        return ExecutionResult(False, f"Downloaded the update but couldn't launch it: {e}", error="launch_failed")
    return ExecutionResult(True, "Update verified and installer launched — follow its prompts to finish.")


# ---------------------------------------------------------------------------------------

ACTION_HANDLER_MAP = {
    "open_app": open_app,
    "close_app": close_app,
    "uninstall_app": uninstall_app,

    "increase_value": increase_value,
    "decrease_value": decrease_value,
    "set_value": set_value,
    "toggle_value": toggle_value,

    "mute_volume": mute_volume,
    "unmute_volume": unmute_volume,

    "shutdown": shutdown,
    "restart": restart,
    "lock_screen": lock_screen,
    "sleep": sleep,
    "hibernate": hibernate,
    "refresh": refresh,

    "open_url": open_url,
    "search": search,

    "activate_mode": activate_mode,
    "deactivate_mode": deactivate_mode,
    "create_mode": create_mode,
    "delete_mode": delete_mode,
    "update_mode": update_mode,

    "focus_window": focus_window,
    "maximize_window": maximize_window,
    "minimize_window": minimize_window,
    "show_window": show_window,
    "hide_window": hide_window,
    "snap_window": snap_window,
    "resize_window": resize_window,
    "move_window": move_window,

    "set_reminder": set_reminder,
    "schedule_task": schedule_task,
    "add_task": add_task,
    "cancel_task": cancel_task,

    "copy_item": copy_item,
    "rename_item": rename_item,

    "check_disk_space": check_disk_space,
    "check_internet": check_internet,
    "take_screenshot": take_screenshot,
    "empty_recycle_bin": empty_recycle_bin,
    "show_clipboard_history": show_clipboard_history,
    "clear_clipboard_history": clear_clipboard_history,
    "expand_snippet": expand_snippet,
    "start_pomodoro": start_pomodoro,
    "stop_pomodoro": stop_pomodoro,

    "set_mode_script": set_mode_script,
    "set_mode_volume": set_mode_volume,
    "set_mode_theme": set_mode_theme,
    "capture_mode_layout": capture_mode_layout,

    "add_alias": add_alias,
    "remove_alias": remove_alias,
    "undo_last_action": undo_last_action,
    "show_help": show_help,

    "report_issue": report_issue,
    "send_report": send_report,
    "check_for_updates": check_for_updates,
    "apply_update": apply_update,
}


def _lazy_handler(module_name, function_name):
    def _handler(ir, config):
        import importlib
        return getattr(importlib.import_module(module_name), function_name)(ir, config)
    return _handler


# Cycle 4 feature actions — lazy so the modules only load when used
ACTION_HANDLER_MAP.update({
    "add_allow_site": _lazy_handler("a_allow_list", "add_allow_site"),      # F1
    "remove_allow_site": _lazy_handler("a_allow_list", "remove_allow_site"),
    "show_allow_list": _lazy_handler("a_allow_list", "show_allow_list"),
    "show_reminders": _lazy_handler("a_reminders", "show_reminders"),       # F5
    "save_script": _lazy_handler("a_scripts", "save_script"),               # F6
    "run_script": _lazy_handler("a_scripts", "run_script"),
    "delete_script": _lazy_handler("a_scripts", "delete_script"),
    "show_scripts": _lazy_handler("a_scripts", "show_scripts"),
})


def execute(ir: CommandIR, config: dict) -> ExecutionResult:
    """
    Dispatches a resolved+validated CommandIR to its handler. Every path returns
    a structured ExecutionResult — nothing here fails silently.
    """
    if ir.errors:
        return ExecutionResult(False, "; ".join(ir.errors), error="unresolved")

    if ir.params.get("requires_confirmation") and not ir.params.get("confirmed"):
        return ExecutionResult(
            False,
            f"'{ir.action}' needs explicit confirmation before it runs.",
            error="confirmation_required",
        )

    handler = ACTION_HANDLER_MAP.get(ir.action)
    if handler is None:
        return ExecutionResult(False, f"Unknown action '{ir.action}'.", error="unknown_action")

    try:
        return handler(ir, config)
    except Exception as e:
        return ExecutionResult(False, f"'{ir.action}' failed unexpectedly: {e}", error="handler_exception")
