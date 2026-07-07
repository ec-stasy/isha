"""
Async command runner — the core perf fix of Cycle 4 (§3.2). One worker
thread owns a queue of (command_text, source) jobs and calls
main.process_command_safe off the UI thread, so no surface ever blocks
(the ~3 s mode website-open wait stops mattering). Every surface —
dashboard bar, quick-input overlay, quick-action buttons, sidebar pages —
submits through this runner, so behavior can't diverge between them, same
principle as process_command_safe itself.

Security: confirmation requests are marshaled to the UI thread and shown as
a quiet prompt; the answer resolves a per-request event. This changes the
chrome, not the gate — a declined/timed-out request is a decline, and
callers that must never confirm (schedulers) don't go through this runner's
confirm path at all.
"""
import queue
import threading

from PySide6.QtCore import QObject, Signal

_SENTINEL = object()


class ConfirmRequest:
    """Carries one confirmation across threads: the worker blocks on `event`
    until the UI thread calls resolve()."""

    def __init__(self, resolved_ir):
        self.resolved_ir = resolved_ir
        self.event = threading.Event()
        self.answer = False

    def resolve(self, answer: bool) -> None:
        self.answer = bool(answer)
        self.event.set()


class CommandRunner(QObject):
    # All emitted from the worker thread — Qt auto-queues them onto the UI thread.
    started = Signal(str, str)              # command_text, source
    finished = Signal(str, str, list)       # command_text, source, outcomes
    confirmation_needed = Signal(object)    # ConfirmRequest

    CONFIRM_TIMEOUT_S = 300  # an unanswered prompt is a decline, never a hang

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._jobs = queue.Queue()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="isha-command-runner")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._jobs.put(_SENTINEL)

    def submit(self, command_text: str, source: str = "ui") -> None:
        text = (command_text or "").strip()
        if text:
            self._jobs.put((text, source))

    # -- worker side ----------------------------------------------------
    def _confirm(self, resolved_ir) -> bool:
        request = ConfirmRequest(resolved_ir)
        self.confirmation_needed.emit(request)
        if not request.event.wait(self.CONFIRM_TIMEOUT_S):
            return False  # fail closed
        return request.answer

    def _loop(self) -> None:
        from main import process_command_safe
        while True:
            job = self._jobs.get()
            if job is _SENTINEL:
                return
            command_text, source = job
            self.started.emit(command_text, source)
            outcomes = process_command_safe(command_text, self._config, confirm_callback=self._confirm)
            self.finished.emit(command_text, source, outcomes)
