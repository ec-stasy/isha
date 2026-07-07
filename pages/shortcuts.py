"""
Shortcuts page (§6.3) — every binding in one table, with real rebinding
(closes Cycle 2's deferral): click "change", press the keys, and the global
listener re-registers live; a conflict keeps the old binding and says so
calmly. Custom command hotkeys (combo → command text) are managed here too.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from config_store import save_config
from shell.main_window import make_scroll_area


def _combo_from_sequence(sequence: QKeySequence) -> str:
    """Qt 'Ctrl+Alt+Space' -> our 'ctrl+alt+space' format."""
    text = sequence.toString()
    return "+".join(part.strip().lower() for part in text.split("+") if part.strip())


class ShortcutsPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        self.window = window

        body = QWidget()
        body.setObjectName("pageBody")
        self._layout = QVBoxLayout(body)
        self._layout.setContentsMargins(32, 28, 32, 24)
        self._layout.setSpacing(12)

        title = QLabel("Keyboard shortcuts")
        title.setProperty("class", "title")
        self._layout.addWidget(title)
        subtitle = QLabel("Global hotkeys work from inside any app.")
        subtitle.setProperty("class", "subtitle")
        self._layout.addWidget(subtitle)

        self.bindings_layout = QVBoxLayout()
        self.bindings_layout.setSpacing(8)
        self._layout.addLayout(self.bindings_layout)

        # in-app keys (fixed)
        card = QFrame()
        card.setProperty("class", "card")
        in_app = QVBoxLayout(card)
        in_app.setContentsMargins(16, 12, 16, 12)
        header = QLabel("Inside the window")
        header.setProperty("class", "subtitle")
        in_app.addWidget(header)
        for combo, what in (("Ctrl+K", "focus the command bar"), ("Ctrl+B", "collapse/expand the sidebar"),
                            ("Ctrl+,", "open Settings"), ("F1", "open Help"),
                            ("Esc", "dismiss any card or overlay"), ("Enter", "submit / confirm")):
            row = QLabel(f"{combo} — {what}")
            row.setProperty("class", "secondary")
            in_app.addWidget(row)
        self._layout.addWidget(card)

        # custom command hotkeys
        custom_card = QFrame()
        custom_card.setProperty("class", "card")
        custom = QVBoxLayout(custom_card)
        custom.setContentsMargins(16, 12, 16, 12)
        custom_header = QLabel("Custom command hotkeys")
        custom_header.setProperty("class", "subtitle")
        custom.addWidget(custom_header)
        note = QLabel("A hotkey firing unattended never confirms a destructive action — those need you present.")
        note.setProperty("class", "hint")
        note.setWordWrap(True)
        custom.addWidget(note)
        self.custom_layout = QVBoxLayout()
        custom.addLayout(self.custom_layout)

        add_row = QHBoxLayout()
        self.new_combo = QKeySequenceEdit()
        self.new_combo.setMaximumWidth(160)
        add_row.addWidget(self.new_combo)
        self.new_command = QLineEdit()
        self.new_command.setPlaceholderText("command to run (e.g. “take screenshot”)")
        add_row.addWidget(self.new_command, 1)
        add = QPushButton("Add")
        add.clicked.connect(self._add_custom)
        add_row.addWidget(add)
        custom.addLayout(add_row)
        self._layout.addWidget(custom_card)

        restart_note = QLabel("Global hotkey changes apply immediately when possible; if a key is held by "
                              "another app, the old binding is kept and you'll see a note here.")
        restart_note.setProperty("class", "hint")
        restart_note.setWordWrap(True)
        self._layout.addWidget(restart_note)
        self.status = QLabel("")
        self.status.setProperty("class", "secondary")
        self._layout.addWidget(self.status)
        self._layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(make_scroll_area(config, body))
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        for layout in (self.bindings_layout, self.custom_layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        settings = self.config.get("settings", {}) or {}
        self.bindings_layout.addWidget(self._binding_card(
            "Quick input box", settings.get("hotkey", "ctrl+alt+space"), "hotkey"))
        self.bindings_layout.addWidget(self._binding_card(
            "Voice input", settings.get("voice_hotkey") or "ctrl+alt+v", "voice_hotkey"))

        prtscr_on = (settings.get("screenshot", {}) or {}).get("prtscr") == "isha"
        prtscr_label = "Print Screen takes an Isha screenshot" if prtscr_on else \
            "Print Screen: handled by Windows (enable in Settings ▸ General)"
        prtscr = QLabel(prtscr_label)
        prtscr.setProperty("class", "secondary")
        self.bindings_layout.addWidget(prtscr)

        for combo, command in (self.config.get("hotkeys", {}) or {}).items():
            row_widget = QFrame()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(f"{combo}  →  {command}"), 1)
            remove = QPushButton("remove")
            remove.setProperty("class", "ghost")
            remove.clicked.connect(lambda _=False, c=combo: self._remove_custom(c))
            row.addWidget(remove)
            self.custom_layout.addWidget(row_widget)

    def _binding_card(self, label: str, combo: str, settings_key: str) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 10, 16, 10)
        row.addWidget(QLabel(label), 1)
        current = QLabel(combo)
        current.setProperty("class", "secondary")
        row.addWidget(current)

        editor = QKeySequenceEdit()
        editor.setMaximumWidth(160)
        editor.setVisible(False)
        row.addWidget(editor)

        change = QPushButton("change")
        row.addWidget(change)

        def start():
            editor.clear()
            editor.setVisible(True)
            editor.setFocus()
            change.setText("save")
            change.clicked.disconnect()
            change.clicked.connect(finish)

        def finish():
            sequence = editor.keySequence()
            new_combo = _combo_from_sequence(sequence) if not sequence.isEmpty() else None
            editor.setVisible(False)
            change.setText("change")
            change.clicked.disconnect()
            change.clicked.connect(start)
            if new_combo:
                self._rebind(settings_key, new_combo, current)

        change.clicked.connect(start)
        return card

    def _rebind(self, settings_key: str, combo: str, label: QLabel) -> None:
        from PySide6.QtWidgets import QApplication
        rebind = getattr(QApplication.instance(), "isha_rebind_hotkey", None)
        old = (self.config.get("settings", {}) or {}).get(settings_key)
        if rebind is not None:
            ok, message = rebind(settings_key, combo)
            if not ok:
                self.status.setText(f"Kept {old or 'the old binding'} — {message}")
                return
        self.config.setdefault("settings", {})[settings_key] = combo
        save_config(self.config)
        label.setText(combo)
        self.status.setText(f"Saved — {combo} is live.")

    def _add_custom(self) -> None:
        sequence = self.new_combo.keySequence()
        command = self.new_command.text().strip()
        if sequence.isEmpty() or not command:
            return
        combo = _combo_from_sequence(sequence)
        self.config.setdefault("hotkeys", {})[combo] = command
        save_config(self.config)
        self.new_combo.clear()
        self.new_command.clear()
        self.status.setText(f"Added {combo} — it becomes active on next launch.")
        self.refresh()

    def _remove_custom(self, combo: str) -> None:
        (self.config.get("hotkeys", {}) or {}).pop(combo, None)
        save_config(self.config)
        self.refresh()
