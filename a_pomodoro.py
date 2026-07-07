"""
Focus/Pomodoro timer tied to a mode — activates the mode for the work
interval, deactivates it for the break interval, and repeats until stopped.
Runs on its own background thread; phase changes are announced via
a_notifications (toast if the tray icon is running, console print otherwise).
"""
import sys
import threading
import time

from a_notifications import notify
from execution_result import ExecutionResult

DEFAULT_WORK_MINUTES = 25
DEFAULT_BREAK_MINUTES = 5


class PomodoroTimer:
    def __init__(self):
        self._thread = None
        self._stop_flag = threading.Event()
        self.running = False
        self.mode_name = None

    def start(self, mode_name: str, work_minutes: int, break_minutes: int, config: dict) -> None:
        self.mode_name = mode_name
        self.running = True
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._run, args=(mode_name, work_minutes, break_minutes, config),
            daemon=True, name="isha-pomodoro",
        )
        self._thread.start()

    def stop(self, config: dict = None) -> None:
        self._stop_flag.set()
        self.running = False
        if self.mode_name and config is not None:
            from main import process_command_safe
            process_command_safe(f"deactivate {self.mode_name} mode", config)

    def _run(self, mode_name: str, work_minutes: int, break_minutes: int, config: dict) -> None:
        from main import process_command_safe
        while not self._stop_flag.is_set():
            if mode_name:
                process_command_safe(f"activate {mode_name} mode", config)
            notify("Isha — Focus", f"Focus for {work_minutes} minute(s)." + (f" ({mode_name})" if mode_name else ""), sound=True)
            if self._stop_flag.wait(work_minutes * 60):
                break

            if mode_name:
                process_command_safe(f"deactivate {mode_name} mode", config)
            notify("Isha — Break", f"Break for {break_minutes} minute(s).", sound=True)
            if self._stop_flag.wait(break_minutes * 60):
                break

        self.running = False


_instance = None


def get_instance() -> PomodoroTimer:
    global _instance
    if _instance is None:
        _instance = PomodoroTimer()
    return _instance


def start_pomodoro(ir, config: dict) -> ExecutionResult:
    timer = get_instance()
    if timer.running:
        return ExecutionResult(False, "A pomodoro timer is already running.", error="already_running")

    settings = config.get("settings", {})
    work_minutes = settings.get("pomodoro_work_minutes", DEFAULT_WORK_MINUTES)
    break_minutes = settings.get("pomodoro_break_minutes", DEFAULT_BREAK_MINUTES)
    mode_name = ir.target if getattr(ir, "target", None) else None

    timer.start(mode_name, work_minutes, break_minutes, config)
    message = f"Started a {work_minutes}/{break_minutes} minute pomodoro timer"
    message += f" tied to mode '{mode_name}'." if mode_name else " (no mode tied — timer only)."
    return ExecutionResult(True, message, data={"mode": mode_name, "work_minutes": work_minutes, "break_minutes": break_minutes})


def stop_pomodoro(ir, config: dict) -> ExecutionResult:
    timer = get_instance()
    if not timer.running:
        return ExecutionResult(False, "No pomodoro timer is running.", error="not_running")
    timer.stop(config)
    return ExecutionResult(True, "Stopped the pomodoro timer.")
