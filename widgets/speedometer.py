"""
Speedometer dialog (Cycle 6 A13) — a calm animated gauge shown while the
internet speed test runs. Pure presentation: `a_check_internet` emits
(phase, mbps, fraction) progress events from its worker thread; the
dashboard marshals them onto the UI thread and feeds this dialog. The needle
eases toward the latest instantaneous speed; when the test finishes the
final download/upload numbers are shown.
"""
import math

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from design import tokens

_MAX_MBPS = 200.0  # top of the dial; sqrt scale keeps low speeds readable
_TICKS = [0, 5, 10, 25, 50, 100, 200]
_SWEEP_START = 210.0   # degrees (Qt: 0° = 3 o'clock, counter-clockwise positive)
_SWEEP_TOTAL = -240.0  # clockwise 240° sweep


def _fraction_for(mbps: float) -> float:
    return max(0.0, min(1.0, math.sqrt(max(mbps, 0.0) / _MAX_MBPS)))


class _GaugeWidget(QWidget):
    def __init__(self, theme_palette: dict, parent=None):
        super().__init__(parent)
        self._palette = theme_palette
        self._shown_mbps = 0.0
        self._target_mbps = 0.0
        self.setMinimumSize(300, 220)

        self._anim = QTimer(self)
        self._anim.setInterval(33)
        self._anim.timeout.connect(self._step)
        self._anim.start()

    def set_target(self, mbps: float) -> None:
        self._target_mbps = max(0.0, mbps)

    def _step(self) -> None:
        delta = self._target_mbps - self._shown_mbps
        if abs(delta) < 0.05:
            self._shown_mbps = self._target_mbps
        else:
            self._shown_mbps += delta * 0.18  # ease toward the live reading
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = self._palette

        side = min(self.width(), self.height() * 2 - 40)
        rect = QRectF((self.width() - side) / 2 + 20, 24, side - 40, side - 40)

        # track arc
        pen = QPen(QColor(colors["border"]), 12, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, int(_SWEEP_START * 16), int(_SWEEP_TOTAL * 16))

        # filled arc up to the current reading
        fraction = _fraction_for(self._shown_mbps)
        pen.setColor(QColor(colors["accent"]))
        painter.setPen(pen)
        painter.drawArc(rect, int(_SWEEP_START * 16), int(_SWEEP_TOTAL * fraction * 16))

        # tick labels
        painter.setPen(QPen(QColor(colors["fg_muted"])))
        tick_font = QFont()
        tick_font.setPointSizeF(8)
        painter.setFont(tick_font)
        center = rect.center()
        radius = rect.width() / 2 + 4
        for tick in _TICKS:
            angle = math.radians(_SWEEP_START + _SWEEP_TOTAL * _fraction_for(tick))
            x = center.x() + (radius + 10) * math.cos(angle)
            y = center.y() - (radius + 10) * math.sin(angle)
            painter.drawText(QRectF(x - 16, y - 8, 32, 16), Qt.AlignCenter, str(tick))

        # needle
        angle = math.radians(_SWEEP_START + _SWEEP_TOTAL * fraction)
        needle_len = rect.width() / 2 - 18
        painter.setPen(QPen(QColor(colors["fg"]), 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(
            center.x(), center.y(),
            center.x() + needle_len * math.cos(angle),
            center.y() - needle_len * math.sin(angle))
        painter.setBrush(QColor(colors["accent"]))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, 6, 6)

        # live number
        painter.setPen(QPen(QColor(colors["fg"])))
        number_font = QFont()
        number_font.setPointSizeF(18)
        number_font.setBold(True)
        painter.setFont(number_font)
        painter.drawText(QRectF(rect.left(), center.y() + 26, rect.width(), 34),
                         Qt.AlignCenter, f"{self._shown_mbps:.1f}")
        painter.setPen(QPen(QColor(colors["fg_muted"])))
        painter.setFont(tick_font)
        painter.drawText(QRectF(rect.left(), center.y() + 58, rect.width(), 16),
                         Qt.AlignCenter, "Mbps")
        painter.end()


class SpeedometerDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(False)

        theme = tokens.resolve_theme(
            (config.get("settings", {}).get("ui", {}) or {}).get("theme", "auto"))
        palette = tokens.palette(theme)

        card = QFrame(self)
        card.setObjectName("quietPrompt")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(8)

        title = QLabel("Internet speed")
        title.setProperty("class", "subtitle")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title, alignment=Qt.AlignHCenter)

        self.gauge = _GaugeWidget(palette)
        layout.addWidget(self.gauge)

        self.phase_label = QLabel("Testing download speed…")
        self.phase_label.setProperty("class", "secondary")
        self.phase_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self.phase_label)

        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignHCenter)
        self.result_label.setVisible(False)
        layout.addWidget(self.result_label)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.close_button, alignment=Qt.AlignHCenter)

    def begin(self) -> None:
        self.result_label.setVisible(False)
        self.phase_label.setText("Testing download speed…")
        self.gauge.set_target(0.0)
        self.show()
        self.raise_()

    def update_progress(self, phase: str, mbps: float, fraction: float) -> None:
        if phase == "download":
            self.phase_label.setText("Testing download speed…")
            self.gauge.set_target(mbps)
        elif phase == "upload":
            self.phase_label.setText("Testing upload speed…")
            self.gauge.set_target(mbps)
        elif phase == "done":
            self.phase_label.setText("Done.")
            self.gauge.set_target(mbps)

    def finish(self, message: str) -> None:
        self.phase_label.setText("")
        self.result_label.setText(message)
        self.result_label.setVisible(True)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None and parent.isVisible():
            center = parent.frameGeometry().center()
        else:
            center = self.screen().availableGeometry().center()
        geo = self.frameGeometry()
        geo.moveCenter(center)
        self.move(geo.topLeft())
