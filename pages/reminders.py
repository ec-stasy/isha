"""
Reminders page (§6.2, reworked in Cycle 6) — the reminder list is its own
clearly-separated section first (no per-row checkboxes; a quiet pause/resume
button instead), each entry has an inline "edit time" affordance that
re-parses natural language ("4:30 pm", "tomorrow 9am"), and the "add a new
reminder" card sits below the list — same structure as the Modes page.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from config_store import save_config
from shell.main_window import make_scroll_area


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("class", "subtitle")
    label.setStyleSheet("font-weight: 600; margin-top: 8px;")
    return label


def _divider() -> QFrame:
    line = QFrame()
    line.setProperty("class", "hline")
    line.setFixedHeight(1)
    return line


class RemindersPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        self.window = window
        self._editing_id = None  # reminder id whose time editor is open

        body = QWidget()
        body.setObjectName("pageBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(36, 30, 36, 26)
        layout.setSpacing(14)

        title = QLabel("Reminders")
        title.setProperty("class", "title")
        layout.addWidget(title)
        subtitle = QLabel("Quiet cards, right on time — never an alarm.")
        subtitle.setProperty("class", "subtitle")
        layout.addWidget(subtitle)

        # --- section: your reminders ---------------------------------------
        layout.addWidget(_section_label("Your reminders"))
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(10)
        layout.addLayout(self.list_layout)

        # --- section: add a new reminder ------------------------------------
        layout.addSpacing(10)
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Add a new reminder"))
        new_card = QFrame()
        new_card.setProperty("class", "card")
        new_card.setStyleSheet("QFrame.card { border-style: dashed; }")
        new_layout = QHBoxLayout(new_card)
        new_layout.setContentsMargins(16, 14, 16, 14)
        self.new_text = QLineEdit()
        self.new_text.setPlaceholderText("Remind me to…  (e.g. “stretch at 4pm”, “standup daily at 9am”)")
        self.new_text.returnPressed.connect(self._add)
        new_layout.addWidget(self.new_text, 1)
        add = QPushButton("Add")
        add.setProperty("class", "accent")
        add.clicked.connect(self._add)
        new_layout.addWidget(add)
        layout.addWidget(new_card)

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
            hint = QLabel("No reminders yet — add one in the section below.")
            hint.setProperty("class", "hint")
            self.list_layout.addWidget(hint)
            return

        for record in sorted(records, key=lambda r: r.get("at") or "9999"):
            self.list_layout.addWidget(self._reminder_card(record))

    # ------------------------------------------------------------------
    def _friendly_time(self, record: dict) -> str:
        raw = record.get("at")
        if not raw:
            return "no time set"
        try:
            from datetime import datetime
            return datetime.fromisoformat(raw).strftime("%a %d %b, %H:%M")
        except (ValueError, TypeError):
            return str(raw)

    def _reminder_card(self, record: dict) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        column = QVBoxLayout(card)
        column.setContentsMargins(16, 12, 16, 12)
        column.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(10)

        text = QLabel(record.get("text", ""))
        text.setProperty("class", "settingName")
        if not record.get("enabled"):
            text.setProperty("class", "secondary")
        row.addWidget(text, 1)

        repeat = record.get("repeat")
        badge = QLabel(self._friendly_time(record)
                       + (f"  · {repeat}" if repeat and repeat != "none" else "")
                       + ("" if record.get("enabled") else "  · paused"))
        badge.setProperty("class", "secondary")
        row.addWidget(badge)

        edit = QPushButton("edit time")
        edit.setProperty("class", "ghost")
        edit.clicked.connect(lambda _=False, rec=record: self._toggle_edit(rec))
        row.addWidget(edit)

        pause = QPushButton("pause" if record.get("enabled") else "resume")
        pause.setProperty("class", "ghost")
        pause.setToolTip("A paused reminder stays saved but never fires")
        pause.clicked.connect(lambda _=False, rec=record: self._toggle(rec))
        row.addWidget(pause)

        delete = QPushButton("delete")
        delete.setProperty("class", "ghost")
        delete.clicked.connect(lambda _=False, rec=record: self._delete(rec))
        row.addWidget(delete)
        column.addLayout(row)

        # inline time editor (Cycle 6 UI 15)
        if self._editing_id == record.get("id"):
            editor_row = QHBoxLayout()
            editor_row.setSpacing(8)
            editor = QLineEdit()
            editor.setPlaceholderText("new time, e.g. “4:30 pm”, “tomorrow 9am”, “in 20 minutes”")
            editor_row.addWidget(editor, 1)
            self._edit_feedback = QLabel("")
            self._edit_feedback.setProperty("class", "hint")

            def _apply(rec=record, field=editor):
                value = field.text().strip()
                if not value:
                    return
                import a_reminders
                result = a_reminders.reschedule(self.config, rec.get("id"), value)
                if result.success:
                    self._editing_id = None
                    self.refresh()
                else:
                    self._edit_feedback.setText(result.message)

            editor.returnPressed.connect(_apply)
            save = QPushButton("Save")
            save.setProperty("class", "accent")
            save.clicked.connect(_apply)
            editor_row.addWidget(save)
            cancel = QPushButton("cancel")
            cancel.setProperty("class", "ghost")
            cancel.clicked.connect(lambda: self._toggle_edit(record))
            editor_row.addWidget(cancel)
            column.addLayout(editor_row)
            column.addWidget(self._edit_feedback)

        return card

    def _toggle_edit(self, record: dict) -> None:
        rid = record.get("id")
        self._editing_id = None if self._editing_id == rid else rid
        self.refresh()

    def _toggle(self, record: dict) -> None:
        record["enabled"] = not bool(record.get("enabled"))
        save_config(self.config)
        self.refresh()

    def _delete(self, record: dict) -> None:
        reminders = self.config.get("reminders", [])
        if record in reminders:
            reminders.remove(record)
            save_config(self.config)
        self.refresh()
