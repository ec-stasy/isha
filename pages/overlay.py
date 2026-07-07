"""
Quick-input overlay (§4.2) — the calm centered type box on top of all apps.
Frameless, always-on-top, no taskbar entry; one rounded input on a raised
card with the sakura sprig at its left edge, suggestions below, result line
below that. Esc dismisses; Enter runs through the shared runner; the card
auto-hides shortly after a successful result. Built once and reused so the
hotkey → visible path stays well under 50 ms.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from widgets.command_bar import CommandBar

ASSETS = Path(__file__).resolve().parent.parent / "assets"
OVERLAY_WIDTH = 640

_overlay = None


def get_overlay(config: dict, runner):
    global _overlay
    if _overlay is None:
        _overlay = QuickInputOverlay(config, runner)
    return _overlay


class _SprigMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._renderer = QSvgRenderer(str(ASSETS / "sprig.svg"))
        self.setFixedSize(36, 36)

    def paintEvent(self, event):
        if self._renderer.isValid():
            painter = QPainter(self)
            painter.setOpacity(0.8)
            self._renderer.render(painter, QRectF(0, 0, 36, 36))
            painter.end()


class QuickInputOverlay(QWidget):
    def __init__(self, config: dict, runner):
        super().__init__(None)
        self.config = config
        self.runner = runner
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(OVERLAY_WIDTH)

        card = QFrame(self)
        card.setObjectName("overlayCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(_SprigMark())
        self.bar = CommandBar(config, placeholder="Ask Isha…")
        self.bar.submitted.connect(self._submit)
        top.addWidget(self.bar, 1)
        layout.addLayout(top)

        self.result_line = QLabel("")
        self.result_line.setProperty("class", "secondary")
        self.result_line.setWordWrap(True)
        self.result_line.setVisible(False)
        layout.addWidget(self.result_line)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        runner.finished.connect(self._on_finished)

    def show_overlay(self, start_listening: bool = False) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(screen.center().x() - self.width() // 2,
                  screen.top() + int(screen.height() * 0.28))
        self.result_line.setVisible(False)
        self._hide_timer.stop()
        self.show()
        self.raise_()
        self.activateWindow()
        self.bar.input.setFocus()
        if start_listening:
            self.bar.start_listening()

    def _submit(self, text: str) -> None:
        self.result_line.setText(f"… {text}")
        self.result_line.setVisible(True)
        self.runner.submit(text, source="overlay")

    def _on_finished(self, text: str, source: str, outcomes: list) -> None:
        if source != "overlay" or not self.isVisible():
            return
        lines, all_ok = [], True
        for outcome in outcomes:
            result = outcome["result"]
            all_ok = all_ok and result.success
            lines.append(("✓ " if result.success else "✕ ") + result.message)
        self.result_line.setText("\n".join(lines) or "Nothing happened.")
        self.result_line.setVisible(True)
        if all_ok:
            autohide = (self.config.get("settings", {}).get("ui", {}) or {}).get("overlay_autohide", 2.5)
            if autohide:
                self._hide_timer.start(int(float(autohide) * 1000))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
