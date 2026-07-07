"""
Reminders page (§6.2) — list sorted by next occurrence with enable toggles
and delete, plus an inline "new reminder" row whose natural time entry goes
through the exact same parser as the typed command.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from config_store import save_config
from shell.main_window import make_scroll_area


class RemindersPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        self.window = window

        body = QWidget()
        body.setObjectName("pageBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Reminders")
        title.setProperty("class", "title")
        layout.addWidget(title)
        subtitle = QLabel("Quiet cards, right on time — never an alarm.")
        subtitle.setProperty("class", "subtitle")
        layout.addWidget(subtitle)

        # inline new-reminder row
        new_card = QFrame()
        new_card.setProperty("class", "card")
        new_layout = QHBoxLayout(new_card)
        new_layout.setContentsMargins(14, 12, 14, 12)
        self.new_text = QLineEdit()
        self.new_text.setPlaceholderText("Remind me to…  (e.g. “stretch at 4pm”, “standup daily at 9am”)")
        self.new_text.returnPressed.connect(self._add)
        new_layout.addWidget(self.new_text, 1)
        add = QPushButton("Add")
        add.setProperty("class", "accent")
        add.clicked.connect(self._add)
        new_layout.addWidget(add)
        layout.addWidget(new_card)

        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        layout.addLayout(self.list_layout)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(make_scroll_area(config, body))

        runner.finished.connect(lambda *_: self.refresh())
        self.refresh()

    def _add(self) -> None:
        text = self.new_text.text().strip()
        if not text:
            return
        command = text if text.lower().startswith(("remind", "set reminder")) else f"remind me to {text}"
        self.runner.submit(command, source="reminders_page")
        self.new_text.clear()

    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        records = [r for r in self.config.get("reminders", []) or [] if isinstance(r, dict)]
        if not records:
            hint = QLabel("No reminders yet — add one above.")
            hint.setProperty("class", "hint")
            self.list_layout.addWidget(hint)
            return

        for record in sorted(records, key=lambda r: r.get("at") or "9999"):
            card = QFrame()
            card.setProperty("class", "card")
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 10, 14, 10)

            toggle = QCheckBox()
            toggle.setChecked(bool(record.get("enabled")))
            toggle.setToolTip("On/off — off keeps it saved but never fires")
            toggle.toggled.connect(lambda on, rec=record: self._toggle(rec, on))
            row.addWidget(toggle)

            text = QLabel(record.get("text", ""))
            row.addWidget(text, 1)

            when = record.get("at") or "no time set"
            repeat = record.get("repeat")
            badge = QLabel(when + (f"  · {repeat}" if repeat and repeat != "none" else ""))
            badge.setProperty("class", "secondary")
            row.addWidget(badge)

            delete = QPushButton("delete")
            delete.setProperty("class", "ghost")
            delete.clicked.connect(lambda _=False, rec=record: self._delete(rec))
            row.addWidget(delete)

            self.list_layout.addWidget(card)

    def _toggle(self, record: dict, on: bool) -> None:
        record["enabled"] = bool(on)
        save_config(self.config)

    def _delete(self, record: dict) -> None:
        reminders = self.config.get("reminders", [])
        if record in reminders:
            reminders.remove(record)
            save_config(self.config)
        self.refresh()
