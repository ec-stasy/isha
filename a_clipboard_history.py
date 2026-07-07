"""
Clipboard history — small, capped, local-only, in-memory (never written to
disk, since clipboard content routinely includes passwords/sensitive text).
Windows-only (win32clipboard); degrades explicitly everywhere else.

Security note: this only ever reads the clipboard the user already put data
into voluntarily; it never sends it anywhere, and history-viewing actions are
redacted in the log the same way reminders/search/open_url already are
(see logger.py's REDACTED_ACTIONS).
"""
import sys
import threading
from collections import deque

from execution_result import ExecutionResult

IS_WINDOWS = sys.platform == "win32"
DEFAULT_MAX_ITEMS = 50
DEFAULT_POLL_SECONDS = 1.0


class ClipboardHistory:
    def __init__(self, max_items: int = DEFAULT_MAX_ITEMS, poll_seconds: float = DEFAULT_POLL_SECONDS):
        self._history = deque(maxlen=max_items)
        self._poll_seconds = poll_seconds
        self._stop_flag = threading.Event()
        self._thread = None
        self._last_seen = None
        self.error = None

        if not IS_WINDOWS:
            self.error = "Clipboard history needs Windows (win32clipboard)."

    def start(self) -> None:
        if not IS_WINDOWS:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="isha-clipboard-history")
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()

    def get_history(self) -> list:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()

    def _run(self) -> None:
        try:
            import win32clipboard
        except ImportError:
            self.error = "Clipboard history needs the optional 'pywin32' module (not installed)."
            return

        while not self._stop_flag.is_set():
            try:
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                        text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                        if text and text != self._last_seen:
                            self._last_seen = text
                            self._history.appendleft(text)
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                pass  # a transient clipboard-access failure must never kill the poller
            self._stop_flag.wait(self._poll_seconds)


_instance = None


def get_instance() -> ClipboardHistory:
    global _instance
    if _instance is None:
        _instance = ClipboardHistory()
    return _instance


def show_clipboard_history(ir=None, config: dict = None) -> ExecutionResult:
    history = get_instance()
    if history.error:
        return ExecutionResult(False, history.error, error="missing_dependency")
    items = history.get_history()
    if not items:
        return ExecutionResult(True, "Clipboard history is empty.", data={"items": []})
    return ExecutionResult(True, f"{len(items)} clipboard item(s).", data={"items": items})


def clear_clipboard_history(ir=None, config: dict = None) -> ExecutionResult:
    get_instance().clear_history()
    return ExecutionResult(True, "Clipboard history cleared.")
