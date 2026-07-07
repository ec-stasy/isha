"""
Silent, calm, top-right toast notifications (§4.5). Frameless cards at the
screen's top-right: title + one sentence + optional action buttons,
auto-dismiss after 6 s, stack up to 3, fade in/out (unless reduce_motion),
no sound by default (`notifications.sound: "soft"` opts into a single quiet
tick). A session-only in-memory ring of the last 50 feeds the notification
center — deliberately never persisted (minimal-storage rule).

Background threads (scheduler, hotkeys) call notify() freely: it marshals
itself onto the UI thread via a queued signal.
"""
import sys

from PySide6.QtCore import QObject, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

TOAST_WIDTH = 320
TOAST_LIFETIME_MS = 6000
MAX_VISIBLE = 3
MARGIN = 16
HISTORY_LIMIT = 50


class _Toast(QWidget):
    def __init__(self, notifier, title: str, message: str, actions=None):
        super().__init__(None)
        self._notifier = notifier
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedWidth(TOAST_WIDTH)

        card = QFrame(self)
        card.setObjectName("toastCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        top = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 600;")
        top.addWidget(title_label, 1)
        close = QPushButton("×")
        close.setProperty("class", "ghost")
        close.setFixedSize(22, 22)
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        layout.addLayout(top)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setProperty("class", "secondary")
        layout.addWidget(body)

        if actions:
            row = QHBoxLayout()
            row.addStretch(1)
            for label, callback in actions:
                b = QPushButton(label)
                b.clicked.connect(lambda _=False, cb=callback: (self.dismiss(), cb and cb()))
                row.addWidget(b)
            layout.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._timer.start(TOAST_LIFETIME_MS)
        self._fade = None

    def show_animated(self, reduce_motion: bool) -> None:
        self.show()
        if not reduce_motion:
            self.setWindowOpacity(0.0)
            self._fade = QPropertyAnimation(self, b"windowOpacity", self)
            self._fade.setDuration(180)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()

    def dismiss(self) -> None:
        self._timer.stop()
        self._notifier._remove(self)
        self.close()
        self.deleteLater()

    def enterEvent(self, event):
        self._timer.stop()  # hovering pauses auto-dismiss
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._timer.start(2000)
        super().leaveEvent(event)


class Notifier(QObject):
    _incoming = Signal(str, str, bool, object)  # marshals cross-thread calls to the UI thread

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._toasts = []
        self.history = []  # session-only ring, newest first
        self._incoming.connect(self._show_on_ui_thread, Qt.QueuedConnection)

    # Public API — thread-safe.
    def notify(self, title: str, message: str, sound: bool = False, actions=None) -> None:
        self._incoming.emit(title, message, sound, actions)

    # -- UI thread ------------------------------------------------------
    def _show_on_ui_thread(self, title, message, sound, actions) -> None:
        self.history.insert(0, {"title": title, "message": message})
        del self.history[HISTORY_LIMIT:]

        settings = self._config.get("settings", {}) or {}
        if (settings.get("notifications", {}) or {}).get("use_windows_native"):
            tray = getattr(QApplication.instance(), "isha_tray", None)
            if tray is not None:
                tray.showMessage(title, message)
                return

        while len(self._toasts) >= MAX_VISIBLE:
            self._toasts[0].dismiss()

        toast = _Toast(self, title, message, actions)
        self._toasts.append(toast)
        self._layout_toasts()
        toast.show_animated(bool((settings.get("ui", {}) or {}).get("reduce_motion")))
        self._layout_toasts()

        # sound only if the user opted in — and then a single soft tick
        if (settings.get("notifications", {}) or {}).get("sound") == "soft" and sys.platform == "win32":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def _remove(self, toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._layout_toasts()

    def _layout_toasts(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        y = area.top() + MARGIN
        for toast in reversed(self._toasts):  # newest at the top
            toast.adjustSize()
            toast.move(area.right() - toast.width() - MARGIN, y)
            y += toast.height() + 4
