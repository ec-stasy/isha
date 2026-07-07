"""
Global hotkey listener — Windows-only, ctypes-only (no extra dependency, keeps
the stack lightweight per the roadmap). Runs its own message loop on a
dedicated background thread and calls back into the app when the combo fires.

Security note: RegisterHotKey only ever *receives* a keypress notification for
the exact combo it registered; it cannot observe or log other keystrokes.
"""
import sys
import threading

IS_WINDOWS = sys.platform == "win32"

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODIFIER_NAMES = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
}

DEFAULT_HOTKEY = "ctrl+alt+space"


def parse_hotkey(combo: str):
    """
    Parses a "ctrl+alt+space" style string into (modifiers_bitmask, vk_code).
    Raises ValueError on anything it can't recognize — callers should fall
    back to DEFAULT_HOTKEY rather than silently registering the wrong combo.
    """
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")

    modifiers = 0
    key_part = parts[-1]
    for part in parts[:-1]:
        if part not in _MODIFIER_NAMES:
            raise ValueError(f"unknown modifier '{part}'")
        modifiers |= _MODIFIER_NAMES[part]

    vk = _vk_from_name(key_part)
    if vk is None:
        raise ValueError(f"unknown key '{key_part}'")

    return modifiers | MOD_NOREPEAT, vk


def _vk_from_name(name: str):
    name = name.lower()
    single_char_specials = {
        "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    }
    if name in single_char_specials:
        return single_char_specials[name]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit():
        n = int(name[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)  # VK_F1..VK_F24
    return None


class HotkeyListener:
    """
    on_trigger is called from the listener's own thread — callers that touch
    a GUI toolkit (Tkinter isn't thread-safe) must hand off via a queue rather
    than acting directly inside the callback.
    """

    def __init__(self, on_trigger, combo: str = DEFAULT_HOTKEY):
        self._on_trigger = on_trigger
        self._combo = combo
        self._thread = None
        self._stop_flag = threading.Event()
        self._thread_id = None
        self.error = None

        if not IS_WINDOWS:
            self.error = "Global hotkeys need Windows; use the tray menu instead."

    def start(self) -> None:
        if not IS_WINDOWS:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="isha-hotkey-listener")
        self._thread.start()

    def stop(self) -> None:
        if not IS_WINDOWS or self._thread_id is None:
            return
        import ctypes
        # WM_QUIT posted to our own message-loop thread to unblock GetMessageW
        ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        try:
            modifiers, vk = parse_hotkey(self._combo)
        except ValueError as e:
            try:
                modifiers, vk = parse_hotkey(DEFAULT_HOTKEY)
                self.error = f"Hotkey '{self._combo}' invalid ({e}); using default {DEFAULT_HOTKEY} instead."
            except ValueError:
                self.error = f"Could not register any hotkey: {e}"
                return

        HOTKEY_ID = 1
        if not user32.RegisterHotKey(None, HOTKEY_ID, modifiers, vk):
            self.error = f"Could not register hotkey '{self._combo}' (already in use by another app?)."
            return

        try:
            msg = wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break  # WM_QUIT or error
                if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:  # WM_HOTKEY
                    try:
                        self._on_trigger()
                    except Exception:
                        pass  # a broken callback must never kill the listener thread
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)


class MultiHotkeyListener:
    """
    Registers many (combo -> callback) pairs on a single message-loop thread.
    This is what backs user-customizable command hotkeys: each bound command
    gets its own combo, but Windows RegisterHotKey calls all need to live on
    the same thread that pumps their messages, so one listener multiplexes
    them all instead of spinning up a thread per binding.

    bindings: dict of combo -> zero-arg callback, called from the listener's
    own thread (same threading contract as HotkeyListener).
    """

    def __init__(self, bindings: dict):
        self._bindings = dict(bindings)
        self._thread = None
        self._thread_id = None
        self.errors = []  # list of str, one per combo that failed to register/parse

        if not IS_WINDOWS:
            self.errors = ["Global hotkeys need Windows; use the tray menu or palette instead."]

    def start(self) -> None:
        if not IS_WINDOWS or not self._bindings:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="isha-multi-hotkey-listener")
        self._thread.start()

    def stop(self) -> None:
        if not IS_WINDOWS or self._thread_id is None:
            return
        import ctypes
        ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        id_to_callback = {}
        next_id = 1
        for combo, callback in self._bindings.items():
            try:
                modifiers, vk = parse_hotkey(combo)
            except ValueError as e:
                self.errors.append(f"Hotkey '{combo}' invalid ({e}) — skipped.")
                continue
            if not user32.RegisterHotKey(None, next_id, modifiers, vk):
                self.errors.append(f"Could not register hotkey '{combo}' (already in use by another app?).")
                continue
            id_to_callback[next_id] = callback
            next_id += 1

        if not id_to_callback:
            return

        try:
            msg = wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break  # WM_QUIT or error
                if msg.message == 0x0312 and msg.wParam in id_to_callback:  # WM_HOTKEY
                    try:
                        id_to_callback[msg.wParam]()
                    except Exception:
                        pass  # a broken callback must never kill the listener thread
        finally:
            for hotkey_id in id_to_callback:
                user32.UnregisterHotKey(None, hotkey_id)
