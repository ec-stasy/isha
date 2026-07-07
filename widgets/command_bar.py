"""
The command bar (§4.1/§4.3) — one widget class reused by the dashboard and
the quick-input overlay so typing and voice behave identically everywhere.
Large rounded input, mic button flush right inside it, debounced "did you
mean" suggestions underneath, and live streaming voice partials rendered
into the same input (muted while partial, normal when final). Voice never
auto-executes — the user always presses Enter.
"""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

SUGGEST_DEBOUNCE_MS = 120
MAX_SUGGESTIONS = 5


class CommandBar(QWidget):
    submitted = Signal(str)

    def __init__(self, config: dict, placeholder: str = "Ask Isha anything…", parent=None):
        super().__init__(parent)
        self._config = config
        self._voice = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.input = QLineEdit()
        self.input.setObjectName("commandBar")
        self.input.setPlaceholderText(placeholder)
        self.input.setMinimumHeight(48)
        self.input.setClearButtonEnabled(True)
        self.input.returnPressed.connect(self._submit)
        self.input.textEdited.connect(self._schedule_suggest)
        layout.addWidget(self.input)

        self.mic = QPushButton("🎤", self.input)
        self.mic.setObjectName("micButton")
        self.mic.setFixedSize(34, 34)
        self.mic.setCursor(Qt.PointingHandCursor)
        self.mic.setToolTip("Speak a command")
        self.mic.clicked.connect(self._toggle_voice)

        self.suggestions = QListWidget()
        self.suggestions.setVisible(False)
        self.suggestions.setMaximumHeight(150)
        self.suggestions.setFocusPolicy(Qt.NoFocus)
        self.suggestions.itemClicked.connect(self._pick_suggestion)
        layout.addWidget(self.suggestions)

        self._suggest_timer = QTimer(self)
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(SUGGEST_DEBOUNCE_MS)
        self._suggest_timer.timeout.connect(self._suggest_now)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.mic.move(self.input.width() - self.mic.width() - 7,
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
        self._suggest_timer.start()

    def _suggest_now(self) -> None:
        last_word = self.input.text().strip().lower().split(" ")[-1] if self.input.text().strip() else ""
        matches = self._suggest(last_word) if len(last_word) >= 2 else []
        self.suggestions.clear()
        if matches:
            self.suggestions.addItems(matches)
            self.suggestions.setVisible(True)
        else:
            self.suggestions.setVisible(False)

    def _suggest(self, prefix: str) -> list:
        """Same cheap local source the palette used: installed app names +
        mode names; registry is disk-cached and warmed at startup."""
        try:
            from app_registry import get_app_registry
            candidates = set(get_app_registry().keys()) | set(self._config.get("modes", {}).keys())
        except Exception:
            candidates = set(self._config.get("modes", {}).keys())
        starts = sorted(c for c in candidates if c.startswith(prefix))
        if len(starts) >= MAX_SUGGESTIONS:
            return starts[:MAX_SUGGESTIONS]
        contains = sorted(c for c in candidates if prefix in c and c not in starts)
        return (starts + contains)[:MAX_SUGGESTIONS]

    def _pick_suggestion(self, item) -> None:
        words = self.input.text().rstrip().split(" ")
        words[-1] = item.text()
        self.input.setText(" ".join(words) + " ")
        self.suggestions.setVisible(False)
        self.input.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.suggestions.isVisible():
            self.suggestions.setVisible(False)
        else:
            super().keyPressEvent(event)

    # -- voice ------------------------------------------------------------
    def _toggle_voice(self) -> None:
        from services.voice_controller import get_voice_controller
        controller = get_voice_controller()
        if controller.listening:
            controller.stop()
            return
        self._set_listening(True)
        controller.partial.connect(self._on_partial)
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
        self.mic.setProperty("listening", "true" if on else "false")
        self.mic.style().unpolish(self.mic)
        self.mic.style().polish(self.mic)

    def _on_partial(self, text: str) -> None:
        self.input.setText(text)
        self.input.setStyleSheet("color: palette(mid);")

    def _on_final(self, text: str) -> None:
        self.input.setStyleSheet("")
        self.input.setText(text)
        self.input.setFocus()
        self.input.end(False)  # user reviews and presses Enter — voice never auto-executes

    def _on_voice_stopped(self) -> None:
        self._set_listening(False)
        self.input.setStyleSheet("")
        self._disconnect_voice()

    def _on_voice_unavailable(self, reason: str) -> None:
        self._set_listening(False)
        self.input.setPlaceholderText(reason)
        self._disconnect_voice()

    def _disconnect_voice(self) -> None:
        try:
            from services.voice_controller import get_voice_controller
            controller = get_voice_controller()
            controller.partial.disconnect(self._on_partial)
            controller.final.disconnect(self._on_final)
            controller.stopped.disconnect(self._on_voice_stopped)
            controller.unavailable.disconnect(self._on_voice_unavailable)
        except (RuntimeError, TypeError):
            pass
