"""
Modes page (§6.1, reworked in Cycle 6) — the list of existing modes comes
first as its own clearly-separated section (accent-colored names), and the
"Add a new mode" card sits *below* the list in its own section so it never
crowds the top edge. Modes without a configured volume say plainly that the
current system volume just stays as it is. Structural edits go through the
runner so they behave exactly like typed commands; small field edits mutate
config directly.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
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


class ModesPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        self.window = window

        body = QWidget()
        body.setObjectName("pageBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(36, 30, 36, 26)
        layout.setSpacing(14)

        title = QLabel("Modes")
        title.setProperty("class", "title")
        layout.addWidget(title)
        subtitle = QLabel("One click opens your whole setup — apps, websites, volume, theme.")
        subtitle.setProperty("class", "subtitle")
        layout.addWidget(subtitle)

        # --- section: your modes (list first — Cycle 6 UI 10/11) ----------
        layout.addWidget(_section_label("Your modes"))
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(12)
        layout.addLayout(self.list_layout)

        # --- section: add a new mode (moved below the list) ----------------
        layout.addSpacing(10)
        layout.addWidget(_divider())
        layout.addWidget(_section_label("Add a new mode"))
        new_card = QFrame()
        new_card.setProperty("class", "card")
        new_card.setStyleSheet("QFrame.card { border-style: dashed; }")
        new_layout = QHBoxLayout(new_card)
        new_layout.setContentsMargins(16, 14, 16, 14)
        new_layout.setSpacing(10)
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("mode name (e.g. study)")
        self.new_name.setMaximumWidth(200)
        new_layout.addWidget(self.new_name)
        self.new_apps = QLineEdit()
        self.new_apps.setPlaceholderText("apps and websites, e.g. “chrome and youtube.com”")
        self.new_apps.returnPressed.connect(self._create)
        new_layout.addWidget(self.new_apps, 1)
        create = QPushButton("Create mode")
        create.setProperty("class", "accent")
        create.clicked.connect(self._create)
        new_layout.addWidget(create)
        layout.addWidget(new_card)

        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(make_scroll_area(config, body))

        runner.finished.connect(lambda *_: self.refresh())
        self.refresh()

    def _create(self) -> None:
        name = self.new_name.text().strip()
        apps = self.new_apps.text().strip()
        if not name or not apps:
            return
        self.runner.submit(f"create {name} mode {apps}", source="modes_page")
        self.new_name.clear()
        self.new_apps.clear()

    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        modes = self.config.get("modes", {}) or {}
        if not modes:
            hint = QLabel("No modes yet — create one in the section below.")
            hint.setProperty("class", "hint")
            self.list_layout.addWidget(hint)
            return
        active = self.config.get("active_mode")
        for name in sorted(modes):
            self.list_layout.addWidget(self._mode_card(name, modes[name], name == active))

    # ------------------------------------------------------------------
    def _mode_card(self, name: str, mode: dict, is_active: bool) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(("● " if is_active else "") + name)
        title.setProperty("class", "accentTitle")  # Cycle 6 UI 9: theme-colored mode names
        header.addWidget(title, 1)
        toggle = QPushButton("Deactivate" if is_active else "Activate")
        if not is_active:
            toggle.setProperty("class", "accent")
        verb = "deactivate" if is_active else "activate"
        toggle.clicked.connect(lambda _=False, v=verb, n=name: self.runner.submit(f"{v} mode {n}", source="modes_page"))
        header.addWidget(toggle)
        delete = QPushButton("delete")
        delete.setProperty("class", "ghost")
        delete.clicked.connect(lambda _=False, n=name: self.runner.submit(f"delete mode {n}", source="modes_page"))
        header.addWidget(delete)
        layout.addLayout(header)

        # items chips
        chips = QHBoxLayout()
        chips.setSpacing(8)
        for item in mode.get("apps", []) or []:
            item_name = item.get("name") if isinstance(item, dict) else str(item)
            kind = "🌐 " if isinstance(item, dict) and item.get("type") == "website" else ""
            chip = QPushButton(f"{kind}{item_name} ✕")
            chip.setProperty("class", "ghost")
            chip.setToolTip("Remove from this mode")
            chip.clicked.connect(lambda _=False, n=name, i=item_name:
                                 self.runner.submit(f"update {n} mode remove {i}", source="modes_page"))
            chips.addWidget(chip)
        add_field = QLineEdit()
        add_field.setPlaceholderText("add app or site…")
        add_field.setMaximumWidth(200)
        add_field.returnPressed.connect(
            lambda f=add_field, n=name: (self.runner.submit(f"update {n} mode add {f.text().strip()}",
                                                            source="modes_page"), f.clear())
            if f.text().strip() else None)
        chips.addWidget(add_field)
        chips.addStretch(1)
        layout.addLayout(chips)

        # volume / theme / layout row
        row = QHBoxLayout()
        row.setSpacing(12)
        system_state = mode.get("system_state", {}) or {}

        row.addWidget(QLabel("volume"))
        volume = QSpinBox()
        volume.setRange(0, 100)
        volume.setSpecialValueText("—")
        volume.setValue(int(system_state.get("volume", 0) or 0))
        volume.valueChanged.connect(lambda v, m=mode: self._set_state(m, "volume", v))
        row.addWidget(volume)

        row.addWidget(QLabel("theme"))
        theme = QComboBox()
        theme.addItems(["(none)", "dark", "light"])
        theme.setCurrentText(system_state.get("theme") or "(none)")
        theme.currentTextChanged.connect(lambda t, m=mode: self._set_state(m, "theme", None if t == "(none)" else t))
        row.addWidget(theme)

        capture = QPushButton("capture window layout")
        capture.setToolTip("Snapshots where this mode's windows are right now, so activating "
                           "the mode puts them back in the same places.")
        capture.clicked.connect(lambda _=False, n=name: self.runner.submit(f"{n} mode layout", source="modes_page"))
        row.addWidget(capture)
        row.addStretch(1)
        layout.addLayout(row)

        # Cycle 6 UI 12: be explicit about what "no volume" means
        if not system_state.get("volume"):
            volume_hint = QLabel("No volume set for this mode — whatever volume is active when the "
                                 "mode starts simply stays as it is.")
            volume_hint.setProperty("class", "hint")
            volume_hint.setWordWrap(True)
            layout.addWidget(volume_hint)

        # script row
        script_row = QHBoxLayout()
        script_row.addWidget(QLabel("script"))
        script = QLineEdit(mode.get("script") or "")
        script.setPlaceholderText("a command, or a saved script name (see Customization ▸ Scripts)")
        script.editingFinished.connect(lambda m=mode, f=script: self._set_script(m, f.text()))
        script_row.addWidget(script, 1)
        allow_on = (self.config.get("settings", {}) or {}).get("allow_scripts", False)
        state = QLabel("scripts enabled" if allow_on else "scripts disabled (Settings ▸ General)")
        state.setProperty("class", "hint")
        script_row.addWidget(state)
        layout.addLayout(script_row)

        # triggers
        triggers = [t for t in self.config.get("triggers", []) or [] if t.get("mode") == name]
        trigger_row = QHBoxLayout()
        label = QLabel("auto-triggers: " + (", ".join(self._trigger_text(t) for t in triggers) if triggers else "none"))
        label.setProperty("class", "hint")
        trigger_row.addWidget(label, 1)
        for trigger in triggers:
            remove = QPushButton("remove trigger")
            remove.setProperty("class", "ghost")
            remove.clicked.connect(lambda _=False, t=trigger: self._remove_trigger(t))
            trigger_row.addWidget(remove)
        at_field = QLineEdit()
        at_field.setPlaceholderText("daily at HH:MM")
        at_field.setMaximumWidth(130)
        at_field.returnPressed.connect(lambda f=at_field, n=name: self._add_time_trigger(n, f))
        trigger_row.addWidget(at_field)
        layout.addLayout(trigger_row)

        return card

    @staticmethod
    def _trigger_text(trigger: dict) -> str:
        kind = trigger.get("type")
        if kind == "time":
            return f"at {trigger.get('at')}" + (f" ({','.join(trigger.get('days', []))})" if trigger.get("days") else "")
        if kind == "battery":
            return "on battery"
        if kind == "app_launch":
            return f"when {trigger.get('app')} starts"
        if kind == "idle":
            return f"idle {trigger.get('minutes')} min"
        return kind or "?"

    def _set_state(self, mode: dict, key: str, value) -> None:
        state = mode.setdefault("system_state", {})
        if value in (None, 0) and key == "volume":
            state.pop("volume", None)
        elif value is None:
            state.pop(key, None)
        else:
            state[key] = value
        save_config(self.config)

    def _set_script(self, mode: dict, text: str) -> None:
        mode["script"] = text.strip() or None
        save_config(self.config)

    def _add_time_trigger(self, mode_name: str, field: QLineEdit) -> None:
        text = field.text().strip()
        if ":" not in text:
            return
        at = text.split()[-1]
        self.config.setdefault("triggers", []).append({"mode": mode_name, "type": "time", "at": at})
        save_config(self.config)
        field.clear()
        self.refresh()

    def _remove_trigger(self, trigger: dict) -> None:
        triggers = self.config.get("triggers", [])
        if trigger in triggers:
            triggers.remove(trigger)
            save_config(self.config)
        self.refresh()
