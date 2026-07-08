"""
Dashboard page (§4.1, reworked in Cycle 6) — the command bar sits at the
vertical center of the page (Claude-style "new chat" placement) with
everything else organized below it: quick actions (pencil-icon edit), the
three most recently used modes as cards, and a scrollable recent-actions
feed covering the last 15 minutes. The logs viewer is gone from this page
(the log file lives in Settings ▸ Privacy). The internet speed test shows a
live speedometer dialog while it runs.
"""
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from shell.main_window import make_scroll_area, apply_scrollbar_policy
from version import VERSION
from widgets.command_bar import CommandBar

RECENT_WINDOW_S = 15 * 60   # keep 15 minutes of actions visible
MAX_RECENT = 60
BAR_MAX_WIDTH = 780
RECENT_MODE_CARDS = 3


def _card(title: str = None) -> tuple:
    card = QFrame()
    card.setProperty("class", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    if title:
        label = QLabel(title)
        label.setProperty("class", "subtitle")
        layout.addWidget(label)
    return card, layout


class _SpeedBridge(QObject):
    """Marshals a_check_internet's worker-thread progress onto the UI thread."""
    progress = Signal(str, float, float)


class DashboardPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        self.window = window
        self._recent = []  # newest first: {"ok", "message", "at"}
        self._speed_dialog = None

        body = QWidget()
        body.setObjectName("pageBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(40, 28, 40, 24)
        layout.setSpacing(18)

        # --- centered command area (Cycle 6 UI-2) -------------------------
        layout.addStretch(3)

        greeting = QLabel("What can Isha do for you?")
        greeting.setProperty("class", "title")
        greeting.setAlignment(Qt.AlignHCenter)
        layout.addWidget(greeting)

        bar_row = QHBoxLayout()
        bar_row.addStretch(1)
        self.bar = CommandBar(config)
        self.bar.setMaximumWidth(BAR_MAX_WIDTH)
        self.bar.setMinimumWidth(420)
        self.bar.submitted.connect(lambda text: runner.submit(text, source="dashboard"))
        bar_row.addWidget(self.bar, 4)
        bar_row.addStretch(1)
        layout.addLayout(bar_row)

        result_row = QHBoxLayout()
        result_row.addStretch(1)
        self.result_line = QLabel("")
        self.result_line.setProperty("class", "secondary")
        self.result_line.setWordWrap(True)
        self.result_line.setVisible(False)
        self.result_line.setMaximumWidth(BAR_MAX_WIDTH)
        result_row.addWidget(self.result_line, 4)
        result_row.addStretch(1)
        layout.addLayout(result_row)

        self._result_fade = QTimer(self)
        self._result_fade.setSingleShot(True)
        self._result_fade.setInterval(8000)
        self._result_fade.timeout.connect(lambda: self.result_line.setVisible(False))

        layout.addStretch(2)

        # --- quick actions -------------------------------------------------
        qa_card, qa_layout = _card()
        header = QHBoxLayout()
        qa_title = QLabel("Quick actions")
        qa_title.setProperty("class", "subtitle")
        header.addWidget(qa_title, 1)
        customize = QPushButton("✎")
        customize.setProperty("class", "ghost")
        customize.setToolTip("Edit quick actions (Customization)")
        customize.setCursor(Qt.PointingHandCursor)
        customize.clicked.connect(lambda: self.window.show_page("customization"))
        header.addWidget(customize)
        qa_layout.addLayout(header)
        self.qa_row = QHBoxLayout()
        self.qa_row.setSpacing(10)
        qa_layout.addLayout(self.qa_row)
        layout.addWidget(qa_card)

        # --- recently used modes + recent actions --------------------------
        row = QHBoxLayout()
        row.setSpacing(18)

        modes_card, self.modes_layout = _card()
        modes_header = QHBoxLayout()
        modes_title = QLabel("Recent modes")
        modes_title.setProperty("class", "subtitle")
        modes_header.addWidget(modes_title, 1)
        manage = QPushButton("manage ▸")
        manage.setProperty("class", "ghost")
        manage.setCursor(Qt.PointingHandCursor)
        manage.clicked.connect(lambda: self.window.show_page("modes"))
        modes_header.addWidget(manage)
        self.modes_layout.addLayout(modes_header)
        self._mode_cards_row = QHBoxLayout()
        self._mode_cards_row.setSpacing(10)
        self.modes_layout.addLayout(self._mode_cards_row)
        row.addWidget(modes_card, 3)

        recent_card, self.recent_layout = _card("Recent actions")
        self._recent_rows_host = QWidget()
        self._recent_rows = QVBoxLayout(self._recent_rows_host)
        self._recent_rows.setContentsMargins(0, 0, 0, 0)
        self._recent_rows.setSpacing(6)
        self._recent_rows.addStretch(1)
        recent_scroll = QScrollArea()
        recent_scroll.setWidgetResizable(True)
        recent_scroll.setWidget(self._recent_rows_host)
        recent_scroll.setFrameShape(QScrollArea.NoFrame)
        recent_scroll.setFixedHeight(210)
        apply_scrollbar_policy(config, recent_scroll)
        self.recent_layout.addWidget(recent_scroll)
        row.addWidget(recent_card, 2)
        layout.addLayout(row)

        footer = QLabel(f"Isha v{VERSION} — everything stays on this machine.")
        footer.setProperty("class", "hint")
        footer.setAlignment(Qt.AlignHCenter)
        layout.addWidget(footer)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(make_scroll_area(config, body))

        runner.started.connect(self._on_started)
        runner.finished.connect(self._on_finished)

        # speed test progress → speedometer dialog (Cycle 6 A13)
        self._speed_bridge = _SpeedBridge()
        self._speed_bridge.progress.connect(self._on_speed_progress, Qt.QueuedConnection)
        try:
            import a_check_internet
            a_check_internet.register_progress_listener(
                lambda phase, mbps, fraction: self._speed_bridge.progress.emit(phase, float(mbps), float(fraction)))
        except Exception:
            pass

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

        if self._speed_dialog is not None and self._speed_dialog.isVisible() and outcomes:
            first = outcomes[0]["result"]
            if (first.data or {}).get("download_mbps") is not None or "speed test" in first.message.lower():
                self._speed_dialog.finish(first.message)

        self._remember_active_mode()
        self._render_recent()
        self._render_modes()  # a command may have switched modes

    def _on_speed_progress(self, phase: str, mbps: float, fraction: float) -> None:
        if self._speed_dialog is None:
            from widgets.speedometer import SpeedometerDialog
            self._speed_dialog = SpeedometerDialog(self.config, parent=self.window)
        if not self._speed_dialog.isVisible():
            self._speed_dialog.begin()
        self._speed_dialog.update_progress(phase, mbps, fraction)

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
        if not actions:
            hint = QLabel("No quick actions yet — add some with the ✎ button.")
            hint.setProperty("class", "hint")
            self.qa_row.addWidget(hint)
        for entry in actions:
            button = QPushButton(entry.get("label") or entry.get("command", ""))
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(entry.get("command", ""))
            button.clicked.connect(
                lambda _=False, c=entry.get("command", ""): self.runner.submit(c, source="quick_action"))
            self.qa_row.addWidget(button)
        self.qa_row.addStretch(1)

    def _remember_active_mode(self) -> None:
        active = self.config.get("active_mode")
        if not active:
            return
        ui = self.config.setdefault("settings", {}).setdefault("ui", {})
        recent = [m for m in (ui.get("recent_modes") or []) if m != active]
        recent.insert(0, active)
        ui["recent_modes"] = recent[:6]
        from config_store import save_config
        save_config(self.config)

    def _recent_mode_names(self) -> list:
        modes = self.config.get("modes", {}) or {}
        ui = self.config.get("settings", {}).get("ui", {}) or {}
        names = [m for m in (ui.get("recent_modes") or []) if m in modes]
        for name in sorted(modes):
            if name not in names:
                names.append(name)
        return names[:RECENT_MODE_CARDS]

    def _render_modes(self) -> None:
        self._clear_layout(self._mode_cards_row)
        modes = self.config.get("modes", {}) or {}
        active = self.config.get("active_mode")
        if not modes:
            hint = QLabel("No modes yet — try “create study mode chrome and youtube”.")
            hint.setProperty("class", "hint")
            hint.setWordWrap(True)
            self._mode_cards_row.addWidget(hint)
            return
        for name in self._recent_mode_names():
            mode = modes.get(name) or {}
            is_active = name == active
            card = QFrame()
            card.setProperty("class", "card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(6)
            title = QLabel(("● " if is_active else "") + name)
            title.setProperty("class", "accentTitle")
            card_layout.addWidget(title)
            count = len(mode.get("apps", []) or [])
            detail = QLabel(f"{count} app{'s' if count != 1 else ''}/site{'s' if count != 1 else ''}")
            detail.setProperty("class", "hint")
            card_layout.addWidget(detail)
            button = QPushButton("Deactivate" if is_active else "Activate")
            if not is_active:
                button.setProperty("class", "accent")
            verb = "deactivate" if is_active else "activate"
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _=False, v=verb, n=name: self.runner.submit(f"{v} mode {n}", source="dashboard"))
            card_layout.addWidget(button)
            self._mode_cards_row.addWidget(card, 1)
        self._mode_cards_row.addStretch(0)

    def _render_recent(self) -> None:
        # prune anything older than the 15-minute window first
        now = time.time()
        self._recent = [r for r in self._recent if now - r["at"] <= RECENT_WINDOW_S]

        self._clear_layout(self._recent_rows)
        if not self._recent:
            hint = QLabel("Actions from the last 15 minutes show up here.")
            hint.setProperty("class", "hint")
            self._recent_rows.addWidget(hint)
            self._recent_rows.addStretch(1)
            return
        for record in self._recent:
            age = int(now - record["at"])
            when = "now" if age < 60 else f"{age // 60}m ago"
            message = record["message"]
            if len(message) > 110:
                message = message[:107] + "…"
            label = QLabel(("✓  " if record["ok"] else "✕  ") + message + f"   · {when}")
            label.setProperty("class", "secondary" if record["ok"] else "error")
            label.setWordWrap(True)
            self._recent_rows.addWidget(label)
        self._recent_rows.addStretch(1)
