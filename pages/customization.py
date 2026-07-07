"""
Customization page (§6.4) — quick actions editor, aliases, snippets,
named scripts (F6), the website allow-list (F1), and Appearance (theme /
scrollbars / motion / overlay auto-hide). All edits mutate the shared
config and save immediately; appearance changes apply live.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from config_store import save_config
from shell.main_window import make_scroll_area, apply_scrollbar_policy


def _card(title: str, hint: str = None):
    card = QFrame()
    card.setProperty("class", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(8)
    label = QLabel(title)
    label.setProperty("class", "subtitle")
    layout.addWidget(label)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setProperty("class", "hint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
    return card, layout


class CustomizationPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        self.window = window

        body = QWidget()
        body.setObjectName("pageBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(14)

        title = QLabel("Customization")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # ---- appearance ------------------------------------------------
        appearance, appearance_layout = _card("Appearance")
        row = QHBoxLayout()
        row.addWidget(QLabel("Theme"))
        self.theme = QComboBox()
        self.theme.addItems(["auto", "light", "dark"])
        self.theme.currentTextChanged.connect(self._set_theme)
        row.addWidget(self.theme)
        row.addSpacing(16)
        row.addWidget(QLabel("Scrollbars"))
        self.scrollbars = QComboBox()
        self.scrollbars.addItems(["auto", "always", "hidden"])
        self.scrollbars.currentTextChanged.connect(self._set_scrollbars)
        row.addWidget(self.scrollbars)
        row.addSpacing(16)
        self.reduce_motion = QCheckBox("Reduce motion")
        self.reduce_motion.toggled.connect(lambda on: self._set_ui("reduce_motion", bool(on)))
        row.addWidget(self.reduce_motion)
        row.addStretch(1)
        appearance_layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Quick input auto-hides after"))
        self.autohide = QDoubleSpinBox()
        self.autohide.setRange(0.0, 30.0)
        self.autohide.setSingleStep(0.5)
        self.autohide.setSuffix(" s")
        self.autohide.setSpecialValueText("never")
        self.autohide.valueChanged.connect(lambda v: self._set_ui("overlay_autohide", float(v)))
        row2.addWidget(self.autohide)
        row2.addStretch(1)
        appearance_layout.addLayout(row2)
        layout.addWidget(appearance)

        # ---- quick actions ----------------------------------------------
        qa, self.qa_layout = _card("Quick actions", "Buttons on the dashboard — any command can be one.")
        self.qa_rows = QVBoxLayout()
        self.qa_layout.addLayout(self.qa_rows)
        add_row = QHBoxLayout()
        self.qa_label = QLineEdit()
        self.qa_label.setPlaceholderText("label")
        self.qa_label.setMaximumWidth(140)
        add_row.addWidget(self.qa_label)
        self.qa_command = QLineEdit()
        self.qa_command.setPlaceholderText("command (e.g. “activate study mode”)")
        add_row.addWidget(self.qa_command, 1)
        add = QPushButton("Add")
        add.clicked.connect(self._add_quick_action)
        add_row.addWidget(add)
        self.qa_layout.addLayout(add_row)
        layout.addWidget(qa)

        # ---- allow list --------------------------------------------------
        allow, self.allow_layout = _card(
            "Website allow-list",
            "Sites here open without asking; anything else gets a quiet “open this?” card first.")
        self.allow_enabled = QCheckBox("Ask before opening sites that aren't on the list")
        self.allow_enabled.toggled.connect(self._set_allow_enabled)
        self.allow_layout.addWidget(self.allow_enabled)
        self.allow_rows = QVBoxLayout()
        self.allow_layout.addLayout(self.allow_rows)
        allow_add = QHBoxLayout()
        self.allow_host = QLineEdit()
        self.allow_host.setPlaceholderText("youtube.com")
        self.allow_host.returnPressed.connect(self._add_allow)
        allow_add.addWidget(self.allow_host, 1)
        allow_button = QPushButton("Allow")
        allow_button.clicked.connect(self._add_allow)
        allow_add.addWidget(allow_button)
        self.allow_layout.addLayout(allow_add)
        layout.addWidget(allow)

        # ---- scripts ------------------------------------------------------
        scripts, self.scripts_layout = _card(
            "Scripts",
            "Scripts run as you — review before saving. Running any script needs the "
            "'allow scripts' switch in Settings, and Isha always shows the exact command first.")
        self.scripts_rows = QVBoxLayout()
        self.scripts_layout.addLayout(self.scripts_rows)
        script_add = QHBoxLayout()
        self.script_name = QLineEdit()
        self.script_name.setPlaceholderText("name (one word)")
        self.script_name.setMaximumWidth(140)
        script_add.addWidget(self.script_name)
        self.script_command = QLineEdit()
        self.script_command.setPlaceholderText("command line to save")
        script_add.addWidget(self.script_command, 1)
        script_button = QPushButton("Save script")
        script_button.clicked.connect(self._save_script)
        script_add.addWidget(script_button)
        self.scripts_layout.addLayout(script_add)
        layout.addWidget(scripts)

        # ---- aliases / snippets -------------------------------------------
        aliases, self.aliases_layout = _card("Aliases", "Your word → what Isha should hear (e.g. “browser” → “chrome”).")
        self.alias_rows = QVBoxLayout()
        self.aliases_layout.addLayout(self.alias_rows)
        alias_add = QHBoxLayout()
        self.alias_word = QLineEdit()
        self.alias_word.setPlaceholderText("your word")
        self.alias_word.setMaximumWidth(140)
        alias_add.addWidget(self.alias_word)
        self.alias_target = QLineEdit()
        self.alias_target.setPlaceholderText("means…")
        alias_add.addWidget(self.alias_target, 1)
        alias_button = QPushButton("Add")
        alias_button.clicked.connect(self._add_alias)
        alias_add.addWidget(alias_button)
        self.aliases_layout.addLayout(alias_add)
        layout.addWidget(aliases)

        snippets, self.snippets_layout = _card("Snippets", "“snippet sig” types the saved text for you.")
        self.snippet_rows = QVBoxLayout()
        self.snippets_layout.addLayout(self.snippet_rows)
        snippet_add = QHBoxLayout()
        self.snippet_name = QLineEdit()
        self.snippet_name.setPlaceholderText("name")
        self.snippet_name.setMaximumWidth(140)
        snippet_add.addWidget(self.snippet_name)
        self.snippet_text = QLineEdit()
        self.snippet_text.setPlaceholderText("expansion text")
        snippet_add.addWidget(self.snippet_text, 1)
        snippet_button = QPushButton("Add")
        snippet_button.clicked.connect(self._add_snippet)
        snippet_add.addWidget(snippet_button)
        self.snippets_layout.addLayout(snippet_add)
        layout.addWidget(snippets)

        layout.addStretch(1)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = make_scroll_area(config, body)
        outer.addWidget(self._scroll)
        self.refresh()

    # -- shared helpers ---------------------------------------------------
    def _ui(self) -> dict:
        return self.config.setdefault("settings", {}).setdefault("ui", {})

    def _set_ui(self, key: str, value) -> None:
        self._ui()[key] = value
        save_config(self.config)

    def _set_theme(self, theme: str) -> None:
        self._set_ui("theme", theme)
        self.window.apply_theme()

    def _set_scrollbars(self, mode: str) -> None:
        self._set_ui("show_scrollbars", mode)
        from PySide6.QtWidgets import QScrollArea
        for area in self.window.findChildren(QScrollArea):
            apply_scrollbar_policy(self.config, area)

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                CustomizationPage._clear(item.layout())

    def _kv_row(self, text: str, on_remove) -> QFrame:
        widget = QFrame()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setWordWrap(True)
        row.addWidget(label, 1)
        remove = QPushButton("remove")
        remove.setProperty("class", "ghost")
        remove.clicked.connect(on_remove)
        row.addWidget(remove)
        return widget

    # -- refresh ------------------------------------------------------------
    def refresh(self) -> None:
        settings = self.config.get("settings", {}) or {}
        ui = settings.get("ui", {}) or {}
        for widget, value in ((self.theme, ui.get("theme", "auto")),
                              (self.scrollbars, ui.get("show_scrollbars", "auto"))):
            widget.blockSignals(True)
            widget.setCurrentText(value)
            widget.blockSignals(False)
        self.reduce_motion.blockSignals(True)
        self.reduce_motion.setChecked(bool(ui.get("reduce_motion")))
        self.reduce_motion.blockSignals(False)
        self.autohide.blockSignals(True)
        self.autohide.setValue(float(ui.get("overlay_autohide", 2.5) or 0))
        self.autohide.blockSignals(False)
        self.allow_enabled.blockSignals(True)
        self.allow_enabled.setChecked(bool(settings.get("allow_list_enabled", True)))
        self.allow_enabled.blockSignals(False)

        self._clear(self.qa_rows)
        actions = ui.get("quick_actions") or []
        for index, entry in enumerate(actions):
            self.qa_rows.addWidget(self._kv_row(
                f"{entry.get('label')} → {entry.get('command')}",
                lambda _=False, i=index: self._remove_quick_action(i)))

        self._clear(self.allow_rows)
        for host in sorted(self.config.get("allow_list") or []):
            self.allow_rows.addWidget(self._kv_row(
                host, lambda _=False, h=host: self._remove_allow(h)))

        self._clear(self.scripts_rows)
        for name, record in sorted((self.config.get("scripts") or {}).items()):
            self.scripts_rows.addWidget(self._kv_row(
                f"{name}: {record.get('command')}",
                lambda _=False, n=name: self._remove_script(n)))

        self._clear(self.alias_rows)
        for word, target in sorted((self.config.get("aliases") or {}).items()):
            self.alias_rows.addWidget(self._kv_row(
                f"{word} → {target}", lambda _=False, w=word: self._remove_alias(w)))

        self._clear(self.snippet_rows)
        for name, text in sorted((self.config.get("snippets") or {}).items()):
            preview = text if len(text) <= 60 else text[:57] + "…"
            self.snippet_rows.addWidget(self._kv_row(
                f"{name}: {preview}", lambda _=False, n=name: self._remove_snippet(n)))

    # -- mutations -----------------------------------------------------------
    def _add_quick_action(self) -> None:
        label, command = self.qa_label.text().strip(), self.qa_command.text().strip()
        if not command:
            return
        self._ui().setdefault("quick_actions", []).append(
            {"label": label or command, "command": command})
        save_config(self.config)
        self.qa_label.clear()
        self.qa_command.clear()
        self.refresh()
        self.window.refresh_current_page()

    def _remove_quick_action(self, index: int) -> None:
        actions = self._ui().get("quick_actions") or []
        if 0 <= index < len(actions):
            actions.pop(index)
            save_config(self.config)
        self.refresh()

    def _set_allow_enabled(self, on: bool) -> None:
        self.config.setdefault("settings", {})["allow_list_enabled"] = bool(on)
        save_config(self.config)

    def _add_allow(self) -> None:
        import a_allow_list
        host = a_allow_list.add_host(self.allow_host.text(), self.config)
        if host:
            self.allow_host.clear()
        self.refresh()

    def _remove_allow(self, host: str) -> None:
        allow_list = self.config.get("allow_list") or []
        if host in allow_list:
            allow_list.remove(host)
            save_config(self.config)
        self.refresh()

    def _save_script(self) -> None:
        name = self.script_name.text().strip()
        command = self.script_command.text().strip()
        if not name or not command:
            return
        self.runner.submit(f"save script {name} as {command}", source="customization")
        self.script_name.clear()
        self.script_command.clear()

    def _remove_script(self, name: str) -> None:
        (self.config.get("scripts") or {}).pop(name, None)
        save_config(self.config)
        self.refresh()

    def _add_alias(self) -> None:
        word, target = self.alias_word.text().strip().lower(), self.alias_target.text().strip().lower()
        if not word or not target:
            return
        self.config.setdefault("aliases", {})[word] = target
        save_config(self.config)
        self.alias_word.clear()
        self.alias_target.clear()
        self.refresh()

    def _remove_alias(self, word: str) -> None:
        (self.config.get("aliases") or {}).pop(word, None)
        save_config(self.config)
        self.refresh()

    def _add_snippet(self) -> None:
        name, text = self.snippet_name.text().strip().lower(), self.snippet_text.text()
        if not name or not text:
            return
        self.config.setdefault("snippets", {})[name] = text
        save_config(self.config)
        self.snippet_name.clear()
        self.snippet_text.clear()
        self.refresh()

    def _remove_snippet(self, name: str) -> None:
        (self.config.get("snippets") or {}).pop(name, None)
        save_config(self.config)
        self.refresh()
