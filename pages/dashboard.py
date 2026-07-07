"""
Dashboard page (§4.1) — command bar top-center with mic, customizable quick
actions, modes strip, recent actions, and an expandable logs view. Refreshes
update models in place; the page is never destroyed and rebuilt.
"""
import json
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from platform_paths import logs_dir
from shell.main_window import make_scroll_area
from version import VERSION
from widgets.command_bar import CommandBar

MAX_RECENT = 12
LOG_PAGE = 100


def _card(title: str = None) -> tuple:
    card = QFrame()
    card.setProperty("class", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)
    if title:
        label = QLabel(title)
        label.setProperty("class", "subtitle")
        layout.addWidget(label)
    return card, layout


class DashboardPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        self.window = window
        self._recent = []  # newest first: {"ok", "message", "at"}

        body = QWidget()
        body.setObjectName("pageBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(16)

        # 1. command bar
        self.bar = CommandBar(config)
        self.bar.submitted.connect(lambda text: runner.submit(text, source="dashboard"))
        layout.addWidget(self.bar)

        self.result_line = QLabel("")
        self.result_line.setProperty("class", "secondary")
        self.result_line.setWordWrap(True)
        self.result_line.setVisible(False)
        layout.addWidget(self.result_line)

        self._result_fade = QTimer(self)
        self._result_fade.setSingleShot(True)
        self._result_fade.setInterval(6000)
        self._result_fade.timeout.connect(lambda: self.result_line.setVisible(False))

        # 2. quick actions
        qa_card, qa_layout = _card()
        header = QHBoxLayout()
        qa_title = QLabel("Quick actions")
        qa_title.setProperty("class", "subtitle")
        header.addWidget(qa_title, 1)
        customize = QPushButton("customize")
        customize.setProperty("class", "ghost")
        customize.clicked.connect(lambda: self.window.show_page("customization"))
        header.addWidget(customize)
        qa_layout.addLayout(header)
        self.qa_row = QHBoxLayout()
        self.qa_row.setSpacing(8)
        qa_layout.addLayout(self.qa_row)
        layout.addWidget(qa_card)

        # 3. modes strip + 4. recent actions (side by side)
        row = QHBoxLayout()
        row.setSpacing(16)

        modes_card, self.modes_layout = _card("Modes")
        manage = QPushButton("manage ▸")
        manage.setProperty("class", "ghost")
        manage.clicked.connect(lambda: self.window.show_page("modes"))
        self.modes_layout.addWidget(manage, alignment=Qt.AlignRight)
        row.addWidget(modes_card, 1)

        recent_card, self.recent_layout = _card("Recent actions")
        row.addWidget(recent_card, 1)
        layout.addLayout(row)

        # 5. logs (collapsed by default)
        logs_card, logs_layout = _card()
        logs_header = QHBoxLayout()
        logs_title = QLabel("Logs")
        logs_title.setProperty("class", "subtitle")
        logs_header.addWidget(logs_title, 1)
        self.logs_toggle = QPushButton("show")
        self.logs_toggle.setProperty("class", "ghost")
        self.logs_toggle.clicked.connect(self._toggle_logs)
        logs_header.addWidget(self.logs_toggle)
        logs_layout.addLayout(logs_header)

        self.logs_filter = QLineEdit()
        self.logs_filter.setPlaceholderText("filter…")
        self.logs_filter.setVisible(False)
        self.logs_filter.textChanged.connect(self._render_logs)
        logs_layout.addWidget(self.logs_filter)

        self.logs_view = QPlainTextEdit()
        self.logs_view.setReadOnly(True)
        self.logs_view.setProperty("class", "mono")
        self.logs_view.setVisible(False)
        self.logs_view.setMinimumHeight(220)
        logs_layout.addWidget(self.logs_view)
        layout.addWidget(logs_card)

        layout.addStretch(1)
        footer = QLabel(f"Isha v{VERSION} — everything stays on this machine.")
        footer.setProperty("class", "hint")
        layout.addWidget(footer)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(make_scroll_area(config, body))

        runner.started.connect(self._on_started)
        runner.finished.connect(self._on_finished)

        self._mode_rows = QVBoxLayout()
        self.modes_layout.insertLayout(1, self._mode_rows)
        self._recent_rows = QVBoxLayout()
        self.recent_layout.addLayout(self._recent_rows)
        self.refresh()

    # -- runner feedback ---------------------------------------------------
    def _on_started(self, text: str, source: str) -> None:
        self.result_line.setText(f"… {text}")
        self.result_line.setVisible(True)
        self._result_fade.stop()

    def _on_finished(self, text: str, source: str, outcomes: list) -> None:
        lines, all_ok = [], True
        for outcome in outcomes:
            result = outcome["result"]
            all_ok = all_ok and result.success
            lines.append(("✓ " if result.success else "✕ ") + result.message)
            for warning in outcome.get("warnings", []):
                lines.append(f"   note: {warning}")
            self._recent.insert(0, {"ok": result.success, "message": result.message,
                                    "at": time.time()})
        del self._recent[MAX_RECENT:]
        self.result_line.setText("\n".join(lines) or "Nothing happened.")
        self.result_line.setProperty("class", "success" if all_ok else "error")
        self.result_line.style().unpolish(self.result_line)
        self.result_line.style().polish(self.result_line)
        self.result_line.setVisible(True)
        self._result_fade.start()
        self._render_recent()
        self._render_modes()  # a command may have switched modes

    def focus_command_bar(self) -> None:
        self.bar.input.setFocus()

    # -- sections ----------------------------------------------------------
    def refresh(self) -> None:
        self._render_quick_actions()
        self._render_modes()
        self._render_recent()

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _render_quick_actions(self) -> None:
        self._clear_layout(self.qa_row)
        actions = (self.config.get("settings", {}).get("ui", {}) or {}).get("quick_actions") or []
        for entry in actions:
            button = QPushButton(entry.get("label") or entry.get("command", ""))
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _=False, c=entry.get("command", ""): self.runner.submit(c, source="quick_action"))
            self.qa_row.addWidget(button)
        self.qa_row.addStretch(1)

    def _render_modes(self) -> None:
        self._clear_layout(self._mode_rows)
        modes = self.config.get("modes", {})
        active = self.config.get("active_mode")
        if not modes:
            hint = QLabel("No modes yet — try “create study mode chrome and youtube”.")
            hint.setProperty("class", "hint")
            hint.setWordWrap(True)
            self._mode_rows.addWidget(hint)
            return
        for name in sorted(modes):
            row = QHBoxLayout()
            label = QLabel(("● " if name == active else "○ ") + name)
            row.addWidget(label, 1)
            button = QPushButton("Deactivate" if name == active else "Activate")
            if name != active:
                button.setProperty("class", "accent")
            verb = "deactivate" if name == active else "activate"
            button.clicked.connect(
                lambda _=False, v=verb, n=name: self.runner.submit(f"{v} mode {n}", source="dashboard"))
            row.addWidget(button)
            self._mode_rows.addLayout(row)

    def _render_recent(self) -> None:
        self._clear_layout(self._recent_rows)
        if not self._recent:
            hint = QLabel("Actions you run will show up here.")
            hint.setProperty("class", "hint")
            self._recent_rows.addWidget(hint)
            return
        now = time.time()
        for record in self._recent:
            age = int(now - record["at"])
            when = "now" if age < 60 else f"{age // 60}m ago" if age < 3600 else f"{age // 3600}h ago"
            message = record["message"]
            if len(message) > 90:
                message = message[:87] + "…"
            label = QLabel(("✓  " if record["ok"] else "✕  ") + message + f"   · {when}")
            label.setProperty("class", "secondary" if record["ok"] else "error")
            label.setWordWrap(True)
            self._recent_rows.addWidget(label)

    # -- logs ---------------------------------------------------------------
    def _toggle_logs(self) -> None:
        visible = not self.logs_view.isVisible()
        self.logs_view.setVisible(visible)
        self.logs_filter.setVisible(visible)
        self.logs_toggle.setText("hide" if visible else "show")
        if visible:
            self._render_logs()

    def _render_logs(self) -> None:
        path = logs_dir() / "commands.jsonl"
        if not path.exists():
            self.logs_view.setPlainText("No log entries yet.")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-LOG_PAGE:]
        except OSError:
            self.logs_view.setPlainText("Couldn't read the log file.")
            return
        needle = self.logs_filter.text().strip().lower()
        rendered = []
        for line in reversed(lines):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            result = record.get("execution_result") or {}
            if "command_id" not in record:
                continue  # crash record, not a command record
            text = (f"{record.get('timestamp', '')}  "
                    f"{'OK ' if result.get('success') else 'ERR'}  "
                    f"{record.get('raw_input', '')}  →  {result.get('message', '')}")
            if not needle or needle in text.lower():
                rendered.append(text)
        self.logs_view.setPlainText("\n".join(rendered) or "No matching entries.")
