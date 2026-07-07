"""
Collapsible sidebar (§3.3): fixed page order, icon rail (56 px) or expanded
(220 px), chevron or Ctrl+B toggles, state persisted in
settings.ui.sidebar_collapsed. Active item gets the accent_soft wash.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from design import tokens

COLLAPSED_W = 56
EXPANDED_W = 220

PAGES = [
    ("dashboard", "◻", "Dashboard"),
    ("modes", "▣", "Modes"),
    ("reminders", "◷", "Reminders"),
    ("shortcuts", "⌘", "Shortcuts"),
    ("customization", "✎", "Customization"),
    ("settings", "⚙", "Settings"),
]


class Sidebar(QFrame):
    navigate = Signal(str)  # page key

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self.setObjectName("sidebar")
        collapsed = bool(config.get("settings", {}).get("ui", {}).get("sidebar_collapsed"))
        self._collapsed = collapsed
        self.setFixedWidth(COLLAPSED_W if collapsed else EXPANDED_W)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 14, 8, 12)
        layout.setSpacing(4)

        self._brand = QLabel("🌸  Isha")
        self._brand.setProperty("class", "title")
        self._brand.setStyleSheet("padding: 4px 6px 12px 6px;")
        layout.addWidget(self._brand)

        self._buttons = {}
        for key, icon, label in PAGES:
            button = QPushButton()
            button.setProperty("class", "navItem")
            button.setCursor(Qt_pointing_hand())
            button.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
            layout.addWidget(button)
            self._buttons[key] = (button, icon, label)

        layout.addStretch(1)

        self._chevron = QPushButton()
        self._chevron.setProperty("class", "ghost")
        self._chevron.setToolTip("Collapse sidebar (Ctrl+B)")
        self._chevron.clicked.connect(self.toggle)
        layout.addWidget(self._chevron)

        self._relabel()
        self.set_active("dashboard")

    # ------------------------------------------------------------------
    def _relabel(self) -> None:
        for key, (button, icon, label) in self._buttons.items():
            button.setText(icon if self._collapsed else f"{icon}   {label}")
            button.setToolTip(label if self._collapsed else "")
        self._brand.setText("🌸" if self._collapsed else "🌸  Isha")
        self._chevron.setText("»" if self._collapsed else "«  collapse")

    def set_active(self, key: str) -> None:
        for k, (button, _, _) in self._buttons.items():
            button.setProperty("active", "true" if k == key else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        ui = self._config.setdefault("settings", {}).setdefault("ui", {})
        ui["sidebar_collapsed"] = self._collapsed
        from config_store import save_config
        save_config(self._config)

        target = COLLAPSED_W if self._collapsed else EXPANDED_W
        if ui.get("reduce_motion"):
            self.setFixedWidth(target)
        else:
            self._anim = QPropertyAnimation(self, b"minimumWidth", self)
            self._anim.setDuration(tokens.MOTION_MS)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.setStartValue(self.width())
            self._anim.setEndValue(target)
            self._anim.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))
            self._anim.start()
        self._relabel()


def Qt_pointing_hand():
    from PySide6.QtCore import Qt
    return Qt.PointingHandCursor
