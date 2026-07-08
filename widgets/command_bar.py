"""
The command bar (§4.1/§4.3, reworked in Cycle 6) — one widget class reused by
the dashboard and the quick-input overlay so typing and voice behave
identically everywhere. Large rounded input, a modern SVG mic flush right
inside it (no clear-✕ — Esc or Ctrl+A already do that), and a smarter
"did you mean" list underneath:

  * verb-aware: after "open"/"close"/... it completes against real installed
    apps (showing each one's actual .exe), system utilities, modes, aliases
    and known websites — never the raw PATH junk drawer (Cycle 6 A16);
  * first-word typing completes whole command templates;
  * suggestions never appear while voice is capturing.

Voice (Cycle 6 A14): the mic uses the online pipeline — one-time notice on
first ever use, then click-to-talk with silence-terminated capture. The
transcript lands in the input for review; voice never auto-executes.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

ASSETS = Path(__file__).resolve().parent.parent / "assets"

SUGGEST_DEBOUNCE_MS = 120
MAX_SUGGESTIONS = 6

# verbs whose object is an app/mode/site — completion kicks in after them
_TARGET_VERBS = {
    "open", "close", "launch", "start", "run", "quit", "kill", "stop",
    "activate", "deactivate", "focus", "maximize", "minimize", "uninstall",
}

_COMMAND_TEMPLATES = [
    "open chrome",
    "open settings",
    "open camera",
    "open recycle bin",
    "close chrome",
    "set volume to 50",
    "volume 70",
    "mute",
    "unmute",
    "take screenshot",
    "delete last screenshot",
    "open last screenshot",
    "check internet",
    "check disk space",
    "empty recycle bin",
    "lock screen",
    "create study mode chrome and youtube",
    "activate study mode",
    "deactivate study mode",
    "remind me to stretch at 4pm",
    "show reminders",
    "show clipboard history",
    "start pomodoro",
    "search the weather",
    "undo",
    "help",
]


class CommandBar(QWidget):
    submitted = Signal(str)

    def __init__(self, config: dict, placeholder: str = "Ask Isha anything…", parent=None):
        super().__init__(parent)
        self._config = config
        self._listening = False
        self._placeholder = placeholder

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.input = QLineEdit()
        self.input.setObjectName("commandBar")
        self.input.setPlaceholderText(placeholder)
        self.input.setMinimumHeight(52)
        self.input.setClearButtonEnabled(False)  # Cycle 6 UI-1: no ✕ behind the mic
        self.input.returnPressed.connect(self._submit)
        self.input.textEdited.connect(self._schedule_suggest)
        layout.addWidget(self.input)

        self._mic_icon = QIcon(str(ASSETS / "mic.svg"))
        self._mic_icon_active = QIcon(str(ASSETS / "mic_active.svg"))
        self.mic = QPushButton(self.input)
        self.mic.setObjectName("micButton")
        self.mic.setIcon(self._mic_icon)
        self.mic.setIconSize(QSize(20, 20))
        self.mic.setFixedSize(36, 36)
        self.mic.setCursor(Qt.PointingHandCursor)
        self.mic.setToolTip("Speak a command (needs internet)")
        self.mic.clicked.connect(self._toggle_voice)

        self.suggestions = QListWidget()
        self.suggestions.setVisible(False)
        self.suggestions.setMaximumHeight(190)
        self.suggestions.setFocusPolicy(Qt.NoFocus)
        self.suggestions.itemClicked.connect(self._pick_suggestion)
        layout.addWidget(self.suggestions)

        self._suggest_timer = QTimer(self)
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(SUGGEST_DEBOUNCE_MS)
        self._suggest_timer.timeout.connect(self._suggest_now)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.mic.move(self.input.width() - self.mic.width() - 8,
                      (self.input.height() - self.mic.height()) // 2)

    # -- typing / suggestions --------------------------------------------
    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.suggestions.setVisible(False)
        self.submitted.emit(text)

    def _schedule_suggest(self, _text: str) -> None:
        if self._listening:
            return  # Cycle 6 issue 26: no suggestion popups during voice input
        self._suggest_timer.start()

    def _target_candidates(self) -> list:
        """[(insert_text, display_text), ...] — curated sources only."""
        rows = []
        try:
            from app_registry import curated_apps
            for name, entry in sorted(curated_apps().items()):
                exe = Path(entry.get("path") or "").name
                kind = "web app" if entry.get("web_app") else exe
                rows.append((name, f"{name}    ·  {kind}"))
        except Exception:
            pass
        try:
            from c_resolver_validator import SYSTEM_UTILITIES, DEFAULT_URL_TARGETS
            for name in SYSTEM_UTILITIES:
                rows.append((name, f"{name}    ·  system"))
            for name in DEFAULT_URL_TARGETS:
                rows.append((name, f"{name}    ·  website"))
        except Exception:
            pass
        for name in (self._config.get("modes", {}) or {}):
            rows.append((name, f"{name}    ·  mode"))
        for name in (self._config.get("aliases", {}) or {}):
            rows.append((name, f"{name}    ·  alias"))
        return rows

    def _suggest_now(self) -> None:
        if self._listening:
            self.suggestions.setVisible(False)
            return
        text = self.input.text()
        stripped = text.strip().lower()
        if len(stripped) < 2:
            self.suggestions.setVisible(False)
            return

        words = stripped.split()
        matches = []  # (insert_full_text, display)

        if len(words) >= 2 and words[0] in _TARGET_VERBS:
            # completing the *target* of an open/close/... command
            query = " ".join(words[1:])
            seen = set()
            starts, contains = [], []
            for name, display in self._target_candidates():
                if name in seen:
                    continue
                seen.add(name)
                full = f"{words[0]} {name}"
                if name.startswith(query):
                    starts.append((full, display))
                elif query in name:
                    contains.append((full, display))
            matches = starts + contains
        else:
            # completing a whole command template
            starts = [(t, t) for t in _COMMAND_TEMPLATES if t.startswith(stripped)]
            contains = [(t, t) for t in _COMMAND_TEMPLATES if stripped in t and not t.startswith(stripped)]
            matches = starts + contains

        self.suggestions.clear()
        for full, display in matches[:MAX_SUGGESTIONS]:
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, full)
            self.suggestions.addItem(item)
        self.suggestions.setVisible(bool(matches))

    def _pick_suggestion(self, item) -> None:
        full = item.data(Qt.UserRole) or item.text()
        self.input.setText(full)
        self.suggestions.setVisible(False)
        self.input.setFocus()
        self.input.end(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.suggestions.isVisible():
            self.suggestions.setVisible(False)
        else:
            super().keyPressEvent(event)

    # -- voice ------------------------------------------------------------
    def _first_use_notice_ok(self) -> bool:
        """One-time heads-up that voice audio goes to an online service."""
        voice = self._config.setdefault("settings", {}).setdefault("voice", {})
        if voice.get("online_notice_shown"):
            return True
        from widgets.quiet_prompt import QuietPrompt
        agreed = QuietPrompt.ask(
            "Voice input uses the internet",
            "To turn speech into text, Isha sends the audio of your voice command to an "
            "online speech service. Only the audio is sent — never your files, settings "
            "or history — and only while the mic is on. You'll only see this notice once.",
            yes_label="Got it, continue", no_label="Not now",
            parent=self.window())
        if agreed:
            voice["online_notice_shown"] = True
            from config_store import save_config
            save_config(self._config)
        return agreed

    def _toggle_voice(self) -> None:
        from services.voice_controller import get_voice_controller
        controller = get_voice_controller()
        if controller.listening:
            controller.stop()
            return
        if not self._first_use_notice_ok():
            return
        self._set_listening(True)
        controller.status.connect(self._on_status)
        controller.final.connect(self._on_final)
        controller.stopped.connect(self._on_voice_stopped)
        controller.unavailable.connect(self._on_voice_unavailable)
        controller.start()

    def start_listening(self) -> None:
        if not (self._voice_active()):
            self._toggle_voice()

    def _voice_active(self) -> bool:
        try:
            from services.voice_controller import get_voice_controller
            return get_voice_controller().listening
        except Exception:
            return False

    def _set_listening(self, on: bool) -> None:
        self._listening = on
        self.suggestions.setVisible(False)
        self.mic.setIcon(self._mic_icon_active if on else self._mic_icon)
        self.mic.setProperty("listening", "true" if on else "false")
        self.mic.style().unpolish(self.mic)
        self.mic.style().polish(self.mic)
        if on:
            self.input.clear()
            self.input.setPlaceholderText("Listening… speak now (click the mic again to finish)")
        else:
            self.input.setPlaceholderText(self._placeholder)

    def _on_status(self, phase: str) -> None:
        if phase == "transcribing":
            self.input.setPlaceholderText("Transcribing…")

    def _on_final(self, text: str) -> None:
        self.input.setText(text)
        self.input.setFocus()
        self.input.end(False)  # user reviews and presses Enter — voice never auto-executes

    def _on_voice_stopped(self) -> None:
        self._set_listening(False)
        self._disconnect_voice()

    def _on_voice_unavailable(self, reason: str) -> None:
        self._set_listening(False)
        self.input.setPlaceholderText(reason)
        self._disconnect_voice()

    def _disconnect_voice(self) -> None:
        try:
            from services.voice_controller import get_voice_controller
            controller = get_voice_controller()
            controller.status.disconnect(self._on_status)
            controller.final.disconnect(self._on_final)
            controller.stopped.disconnect(self._on_voice_stopped)
            controller.unavailable.disconnect(self._on_voice_unavailable)
        except (RuntimeError, TypeError):
            pass
