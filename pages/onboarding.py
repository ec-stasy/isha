"""
First-run onboarding (§6) — three quiet in-window cards over the dashboard
(welcome/privacy → the command bar + hotkey → make a first mode), honoring
the existing settings.onboarded flag. No wizard window, no modal chrome.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from config_store import save_config

SLIDES = [
    ("Welcome to Isha 🌸",
     "Type what you want in plain English (or Hinglish) — “open chrome”, “mute”, "
     "“remind me to stretch at 4pm”.\n\nEverything runs and stays on this machine. "
     "Nothing you type or say ever leaves it."),
    ("One bar, anywhere",
     "The bar at the top of the dashboard runs any command — or press "
     "Ctrl+Alt+Space from inside any app for the quick input box.\n\nThe mic "
     "button types your words live; you always press Enter yourself."),
    ("Make it yours",
     "Try “create study mode chrome and youtube” — then one click opens your whole "
     "setup.\n\nQuick actions, themes, reminders and shortcuts all live in the "
     "sidebar. Destructive actions always check with you first, quietly."),
]


def show_onboarding(window, config: dict) -> None:
    dialog = _Onboarding(window)
    dialog.exec()
    config.setdefault("settings", {})["onboarded"] = True
    save_config(config)


class _Onboarding(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._index = 0

        card = QFrame(self)
        card.setObjectName("quietPrompt")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)

        self.title = QLabel()
        self.title.setProperty("class", "title")
        layout.addWidget(self.title)

        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setMinimumWidth(400)
        self.body.setMaximumWidth(460)
        layout.addWidget(self.body)

        row = QHBoxLayout()
        self.dots = QLabel()
        self.dots.setProperty("class", "hint")
        row.addWidget(self.dots, 1)
        skip = QPushButton("Skip")
        skip.setProperty("class", "ghost")
        skip.clicked.connect(self.accept)
        row.addWidget(skip)
        self.next_button = QPushButton()
        self.next_button.setProperty("class", "accent")
        self.next_button.clicked.connect(self._advance)
        row.addWidget(self.next_button)
        layout.addLayout(row)

        self._render()

    def _render(self) -> None:
        title, body = SLIDES[self._index]
        self.title.setText(title)
        self.body.setText(body)
        self.dots.setText("  ".join("●" if i == self._index else "○" for i in range(len(SLIDES))))
        self.next_button.setText("Get started" if self._index == len(SLIDES) - 1 else "Next")

    def _advance(self) -> None:
        if self._index >= len(SLIDES) - 1:
            self.accept()
            return
        self._index += 1
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            geo = self.frameGeometry()
            geo.moveCenter(parent.frameGeometry().center())
            self.move(geo.topLeft())
