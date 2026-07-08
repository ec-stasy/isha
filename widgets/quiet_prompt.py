"""
Quiet prompts (§4.4) — every confirmation in Isha 2.0 goes through this
card: destructive actions, script first-runs, non-allow-listed URLs. No
danger icon, no system sound, plain calm language, Esc = decline, and focus
defaults to the declining button. This replaces every messagebox.* use.

It changes the chrome, not the gate: callers still only proceed on an
explicit affirmative, and non-interactive callers never reach here at all.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)


# Cycle 6 A15: per-action confirmation copy. Irreversible actions must say
# so plainly — the old generic "can't be easily undone" implied a restart or
# an emptied recycle bin could somehow be undone.
_ACTION_MESSAGES = {
    "restart": ("Restart this PC?",
                "This restarts Windows right away. Unsaved work in open apps may be lost, "
                "and a restart cannot be undone."),
    "shutdown": ("Shut down this PC?",
                 "This shuts Windows down right away. Unsaved work in open apps may be "
                 "lost, and a shutdown cannot be undone."),
    "hibernate": ("Hibernate this PC?",
                  "Windows will save the current session to disk and power off. Your work "
                  "is preserved, but anything mid-download or mid-call will pause."),
    "empty_recycle_bin": ("Empty the Recycle Bin?",
                          "This permanently deletes everything in the Recycle Bin. "
                          "Once emptied, those files cannot be recovered — this cannot be undone."),
    "uninstall_app": ("Open the uninstaller?",
                      "Isha will open Windows Settings so you can uninstall it there — "
                      "nothing is removed until you confirm inside Settings."),
    "delete_mode": ("Delete this mode?",
                    "The mode's saved apps, websites and settings are removed. You can "
                    "always create it again, but its configuration is gone."),
    "send_report": ("Send this report?",
                    "The report zip leaves this machine and is uploaded to Isha's intake "
                    "server. Nothing is ever sent without this confirmation."),
    "apply_update": ("Install the update?",
                     "The downloaded, signature-verified installer will run now and may "
                     "restart Isha when it finishes."),
}


def _message_for(resolved_ir) -> tuple:
    """(title, body) in plain calm sentences for a resolved CommandIR."""
    action = getattr(resolved_ir, "action", "") or ""
    target = getattr(resolved_ir, "target", None)
    if action == "run_mode_script" or action == "run_script":
        return (
            "Run this script?",
            f"Isha is about to run:\n\n{target}\n\nScripts run with your permissions — "
            "only continue if you recognize this command.",
        )
    if action in _ACTION_MESSAGES:
        return _ACTION_MESSAGES[action]
    name = target if isinstance(target, str) else (target or {}).get("name") if isinstance(target, dict) else None
    name = name or action.replace("_", " ")
    return ("Just checking", f"“{action.replace('_', ' ')}” on “{name}” can’t be easily undone. Continue?")


class QuietPrompt(QDialog):
    """A small frameless card centered over its parent (or the screen).
    Returns True only on the explicit affirmative."""

    def __init__(self, title: str, body: str, yes_label: str = "Yes, continue",
                 no_label: str = "Not now", parent=None, extra_buttons=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._choice = None  # None=declined, "yes", or an extra button's key

        card = QFrame(self)
        card.setObjectName("quietPrompt")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setProperty("class", "subtitle")
        title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(title_label)

        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setMinimumWidth(340)
        body_label.setMaximumWidth(460)
        layout.addWidget(body_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)

        no_button = QPushButton(no_label)
        no_button.clicked.connect(self.reject)
        buttons.addWidget(no_button)

        for key, label in (extra_buttons or []):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            buttons.addWidget(b)

        yes_button = QPushButton(yes_label)
        yes_button.setProperty("class", "accent")
        yes_button.clicked.connect(lambda: self._pick("yes"))
        buttons.addWidget(yes_button)

        layout.addLayout(buttons)
        no_button.setFocus()  # declining is the default for destructive actions

    def _pick(self, choice: str) -> None:
        self._choice = choice
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

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

    @property
    def choice(self):
        return self._choice

    @staticmethod
    def ask(title: str, body: str, yes_label: str = "Yes, continue",
            no_label: str = "Not now", parent=None) -> bool:
        prompt = QuietPrompt(title, body, yes_label, no_label, parent)
        prompt.exec()
        return prompt.choice == "yes"

    @staticmethod
    def ask_for_ir(resolved_ir, parent=None) -> bool:
        title, body = _message_for(resolved_ir)
        return QuietPrompt.ask(title, body, parent=parent)
