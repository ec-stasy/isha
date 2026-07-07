"""
Auto-triggers for Modes 2.0 — a lightweight background poller, not a full
scheduler daemon: time-based ("Work mode at 9am"), on-battery, app-launch,
and idle triggers stored in config["triggers"]. Fires through
main.process_command_safe so a trigger goes through the exact same pipeline
(and gets logged the same way) as typed input, the hotkey, or the palette —
one brain, four input paths now.

Trigger records (config-editable, like hotkey rebinding in Phase 2):
  {"mode": "study", "type": "time", "at": "09:00", "days": ["mon", ...]}   # days omitted/empty = every day
  {"mode": "power_saver", "type": "battery", "state": "on_battery"}
  {"mode": "gaming", "type": "app_launch", "app": "steam.exe"}
  {"mode": "power_saver", "type": "idle", "minutes": 10}
"""
import datetime
import sys
import threading
import time

IS_WINDOWS = sys.platform == "win32"

POLL_SECONDS = 20
_DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _get_idle_seconds():
    """Seconds since the last keyboard/mouse input, or None if unavailable."""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        millis_since = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return millis_since / 1000.0
    except Exception:
        return None


def _get_on_battery() -> bool:
    """True if on battery power, False if on AC or if the check isn't available."""
    if not IS_WINDOWS:
        return False
    try:
        import ctypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("Reserved1", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]

        status = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return False
        return status.ACLineStatus == 0
    except Exception:
        return False


class ModeScheduler:
    """
    Runs on its own daemon thread; never touches Tkinter or any GUI toolkit
    directly, so it's safe to start alongside the hotkey listener and tray icon.
    """

    def __init__(self, config: dict, poll_seconds: int = POLL_SECONDS):
        self._config = config
        self._poll_seconds = poll_seconds
        self._stop_flag = threading.Event()
        self._thread = None
        self._fired_today = {}       # trigger index -> date last fired (time triggers)
        self._was_on_battery = None  # None = unknown yet, avoids a false edge on first poll
        self._app_was_running = {}   # trigger index -> bool, for app_launch edge detection
        self._idle_fired = set()     # trigger indices already fired for the current idle stretch

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="isha-mode-scheduler")
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()

    def _fire(self, mode_name: str) -> None:
        from main import process_command_safe
        from a_notifications import notify
        try:
            process_command_safe(f"activate {mode_name} mode", self._config)
            notify("Isha — auto-trigger", f"Activated '{mode_name}' mode automatically.")
        except Exception:
            pass  # a broken trigger must never kill the scheduler thread

    def _check_time_trigger(self, index: int, trigger: dict, now: datetime.datetime) -> None:
        at = trigger.get("at")
        if not at:
            return
        days = [d.lower()[:3] for d in trigger.get("days", [])]
        if days and _DAY_NAMES[now.weekday()] not in days:
            return

        try:
            hour, minute = (int(p) for p in at.split(":"))
        except (ValueError, AttributeError):
            return

        today = now.date()
        if now.hour == hour and now.minute == minute and self._fired_today.get(index) != today:
            self._fired_today[index] = today
            self._fire(trigger.get("mode"))

    def _check_battery_trigger(self, trigger: dict, on_battery: bool) -> None:
        if trigger.get("state") != "on_battery":
            return
        # edge-triggered: fire only on the AC → battery transition, not every poll
        if on_battery and self._was_on_battery is False:
            self._fire(trigger.get("mode"))

    def _check_app_launch_trigger(self, index: int, trigger: dict) -> None:
        app = trigger.get("app")
        if not app:
            return
        from a_application_manager import is_app_running
        running = is_app_running(app)
        was_running = self._app_was_running.get(index, False)
        self._app_was_running[index] = running
        # edge-triggered: fire only on the not-running -> running transition
        if running and not was_running:
            self._fire(trigger.get("mode"))

    def _check_idle_trigger(self, index: int, trigger: dict, idle_seconds) -> None:
        minutes = trigger.get("minutes")
        if not minutes or idle_seconds is None:
            return
        threshold = minutes * 60
        if idle_seconds >= threshold:
            if index not in self._idle_fired:
                self._idle_fired.add(index)
                self._fire(trigger.get("mode"))
        else:
            # user is active again — allow this trigger to fire next time idle recurs
            self._idle_fired.discard(index)

    def _tick(self) -> None:
        now = datetime.datetime.now()
        on_battery = _get_on_battery()
        idle_seconds = _get_idle_seconds()

        for index, trigger in enumerate(self._config.get("triggers", [])):
            if not trigger.get("mode"):
                continue
            trigger_type = trigger.get("type")
            if trigger_type == "time":
                self._check_time_trigger(index, trigger, now)
            elif trigger_type == "battery":
                self._check_battery_trigger(trigger, on_battery)
            elif trigger_type == "app_launch":
                self._check_app_launch_trigger(index, trigger)
            elif trigger_type == "idle":
                self._check_idle_trigger(index, trigger, idle_seconds)

        self._was_on_battery = on_battery

    def _run(self) -> None:
        while not self._stop_flag.is_set():
            try:
                self._tick()
            except Exception:
                pass  # one bad tick must never stop future ticks
            self._stop_flag.wait(self._poll_seconds)
