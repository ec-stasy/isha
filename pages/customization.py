"""
Customization page (§6.4, reworked in Cycle 6) — everything about how Isha
*behaves* for you: General (default level, close behavior, start with
Windows, scripts gate — moved here from Settings), Volume (mute behavior +
an "Individual" per-device mode with remembered levels), Screenshots (moved
here from Settings), quick actions as a clear name→action table, the
website allow-list, scripts, aliases and snippets. Appearance moved to the
Settings page.
"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from config_store import save_config
from shell.main_window import make_scroll_area

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _card(title: str, hint: str = None):
    card = QFrame()
    card.setProperty("class", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    label = QLabel(title)
    label.setProperty("class", "subtitle")
    label.setStyleSheet("font-weight: 600;")
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
        layout.setContentsMargins(36, 30, 36, 26)
        layout.setSpacing(16)

        title = QLabel("Customization")
        title.setProperty("class", "title")
        layout.addWidget(title)
        subtitle = QLabel("How Isha behaves for you — defaults, volume, screenshots, quick actions and your own words.")
        subtitle.setProperty("class", "subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ---- general (moved here from Settings — Cycle 6 UI 16) -----------
        general, general_layout = _card(
            "General",
            "Everyday behavior: the level used when you don't say one, what closing the "
            "window does, and whether Isha starts with Windows.")

        row = QHBoxLayout()
        row.addWidget(QLabel("Default level when you don't say one (e.g. plain “set volume”)"))
        self.default_level = QSpinBox()
        self.default_level.setRange(0, 100)
        self.default_level.valueChanged.connect(
            lambda v: self._set_nested(("defaults", "level"), int(v)))
        row.addWidget(self.default_level)
        row.addStretch(1)
        general_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Closing the window"))
        self.close_action = QComboBox()
        self.close_action.addItem("keeps Isha running in the tray (hotkeys and reminders keep working)", "tray")
        self.close_action.addItem("exits Isha completely", "exit")
        self.close_action.currentIndexChanged.connect(
            lambda _: self._set_ui("close_action", self.close_action.currentData()))
        row.addWidget(self.close_action)
        row.addStretch(1)
        general_layout.addLayout(row)

        self.start_with_windows = QCheckBox("Start Isha automatically when Windows starts")
        self.start_with_windows.toggled.connect(self._set_start_with_windows)
        general_layout.addWidget(self.start_with_windows)

        self.allow_scripts = QCheckBox("Allow scripts (mode scripts and saved scripts) — "
                                       "you'll always see the exact command before it runs")
        self.allow_scripts.toggled.connect(
            lambda on: self._set_setting("allow_scripts", bool(on)))
        general_layout.addWidget(self.allow_scripts)
        layout.addWidget(general)

        # ---- volume (Cycle 6 UI 17/18) -------------------------------------
        volume_card, volume_layout = _card(
            "Volume",
            "“Together” treats every output device the same. “Individual” lists each "
            "connected device with its own level — levels are remembered per device, so "
            "a headset you reconnect next week keeps its setting, and newly connected "
            "devices simply appear in the list.")

        row = QHBoxLayout()
        row.addWidget(QLabel("Device volume control"))
        self.volume_mode = QComboBox()
        self.volume_mode.addItem("Together — one volume for all devices (default)", "together")
        self.volume_mode.addItem("Individual — set each device separately", "individual")
        self.volume_mode.currentIndexChanged.connect(self._set_volume_mode)
        row.addWidget(self.volume_mode)
        row.addStretch(1)
        volume_layout.addLayout(row)

        self.device_rows_host = QWidget()
        self.device_rows = QVBoxLayout(self.device_rows_host)
        self.device_rows.setContentsMargins(0, 0, 0, 0)
        self.device_rows.setSpacing(8)
        volume_layout.addWidget(self.device_rows_host)

        row = QHBoxLayout()
        row.addWidget(QLabel("When you say “mute” with several devices connected"))
        self.mute_behavior = QComboBox()
        self.mute_behavior.addItem("halve every device's volume (default)", "halve_all")
        self.mute_behavior.addItem("hard-mute every device", "mute_all")
        self.mute_behavior.addItem("mute the default device only", "mute_default_only")
        self.mute_behavior.addItem("set every device to a fixed level…", "set_all_to")
        self.mute_behavior.currentIndexChanged.connect(self._set_mute_behavior)
        row.addWidget(self.mute_behavior)
        self.mute_level = QSpinBox()
        self.mute_level.setRange(0, 100)
        self.mute_level.valueChanged.connect(
            lambda v: self._set_nested(("audio", "mute_level"), int(v)))
        row.addWidget(self.mute_level)
        row.addStretch(1)
        volume_layout.addLayout(row)
        layout.addWidget(volume_card)

        # ---- screenshots (moved here from Settings — Cycle 6 UI 19) --------
        shots, shots_layout = _card(
            "Screenshots",
            "Where captures are saved, what happens after one is taken, and whether the "
            "Print Screen key should trigger Isha.")
        row = QHBoxLayout()
        row.addWidget(QLabel("Save to"))
        self.shot_dir = QLineEdit()
        self.shot_dir.setPlaceholderText("system Pictures\\Screenshots (default)")
        self.shot_dir.editingFinished.connect(
            lambda: self._set_nested(("screenshot", "dir"), self.shot_dir.text().strip() or None))
        row.addWidget(self.shot_dir, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_shot_dir)
        row.addWidget(browse)
        shots_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("After capture"))
        self.shot_after = QComboBox()
        self.shot_after.addItem("just save the file", "save")
        self.shot_after.addItem("save and open it", "save_and_open")
        self.shot_after.currentIndexChanged.connect(
            lambda _: self._set_nested(("screenshot", "after"), self.shot_after.currentData()))
        row.addWidget(self.shot_after)
        row.addSpacing(16)
        row.addWidget(QLabel("Capture"))
        self.shot_capture = QComboBox()
        self.shot_capture.addItem("the full screen", "full")
        self.shot_capture.addItem("the active window", "window")
        self.shot_capture.currentIndexChanged.connect(
            lambda _: self._set_nested(("screenshot", "capture"), self.shot_capture.currentData()))
        row.addWidget(self.shot_capture)
        row.addStretch(1)
        shots_layout.addLayout(row)

        self.prtscr = QCheckBox("Print Screen key takes an Isha screenshot")
        self.prtscr.toggled.connect(
            lambda on: self._set_nested(("screenshot", "prtscr"), "isha" if on else "off"))
        shots_layout.addWidget(self.prtscr)
        prtscr_note = QLabel("Honest note: if Windows 11's “Use Print Screen to open Snipping Tool” is on, "
                             "Windows wins. Takes effect on next launch; if the key can't be claimed, this "
                             "switches itself back off and tells you.")
        prtscr_note.setProperty("class", "hint")
        prtscr_note.setWordWrap(True)
        shots_layout.addWidget(prtscr_note)
        layout.addWidget(shots)

        # ---- quick actions as a table (Cycle 6 UI 20) -----------------------
        qa, self.qa_layout = _card(
            "Quick actions",
            "Buttons on the dashboard. The table shows exactly which command each button runs.")
        self.qa_grid_host = QWidget()
        self.qa_grid = QGridLayout(self.qa_grid_host)
        self.qa_grid.setContentsMargins(0, 0, 0, 0)
        self.qa_grid.setHorizontalSpacing(18)
        self.qa_grid.setVerticalSpacing(6)
        self.qa_layout.addWidget(self.qa_grid_host)
        add_row = QHBoxLayout()
        self.qa_label = QLineEdit()
        self.qa_label.setPlaceholderText("display name")
        self.qa_label.setMaximumWidth(160)
        add_row.addWidget(self.qa_label)
        self.qa_command = QLineEdit()
        self.qa_command.setPlaceholderText("command it runs (e.g. “activate study mode”)")
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
            "'allow scripts' switch above, and Isha always shows the exact command first.")
        self.scripts_rows = QVBoxLayout()
        self.scripts_layout.addLayout(self.scripts_rows)
        script_add = QHBoxLayout()
        self.script_name = QLineEdit()
        self.script_name.setPlaceholderText("name (one word)")
        self.script_name.setMaximumWidth(160)
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
        self.alias_word.setMaximumWidth(160)
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
        self.snippet_name.setMaximumWidth(160)
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
    def _settings(self) -> dict:
        return self.config.setdefault("settings", {})

    def _ui(self) -> dict:
        return self._settings().setdefault("ui", {})

    def _set_setting(self, key: str, value) -> None:
        self._settings()[key] = value
        save_config(self.config)

    def _set_ui(self, key: str, value) -> None:
        self._ui()[key] = value
        save_config(self.config)

    def _set_nested(self, path: tuple, value) -> None:
        node = self._settings()
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value
        save_config(self.config)

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

    # -- volume mode / devices (Cycle 6) -----------------------------------
    def _set_volume_mode(self, _index: int) -> None:
        mode = self.volume_mode.currentData()
        self._set_nested(("audio", "volume_mode"), mode)
        self._render_devices()
        if mode == "individual":
            import a_audio
            a_audio.apply_saved_device_levels(self.config)

    def _render_devices(self) -> None:
        self._clear(self.device_rows)
        if (self._settings().get("audio", {}) or {}).get("volume_mode", "together") != "individual":
            self.device_rows_host.setVisible(False)
            return
        self.device_rows_host.setVisible(True)
        try:
            import a_audio
            devices = a_audio.list_output_devices(self.config)
        except Exception:
            devices = []
        if not devices:
            hint = QLabel("No audio devices found (or the audio module isn't available).")
            hint.setProperty("class", "hint")
            self.device_rows.addWidget(hint)
            return
        for device in devices:
            row_frame = QFrame()
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            name = QLabel(device["name"])
            name.setMinimumWidth(180)
            row.addWidget(name, 1)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(device.get("saved") if device.get("saved") is not None else device["level"]))
            slider.setFixedWidth(220)
            value_label = QLabel(f"{slider.value()}%")
            value_label.setFixedWidth(44)
            slider.valueChanged.connect(lambda v, lab=value_label: lab.setText(f"{v}%"))
            slider.sliderReleased.connect(
                lambda s=slider, d=device: self._apply_device_volume(d["id"], s.value()))
            row.addWidget(slider)
            row.addWidget(value_label)
            self.device_rows.addWidget(row_frame)
        note = QLabel("Move a slider to set that device now — the level is remembered for "
                      "whenever this device is connected.")
        note.setProperty("class", "hint")
        note.setWordWrap(True)
        self.device_rows.addWidget(note)

    def _apply_device_volume(self, device_id: str, level: int) -> None:
        import a_audio
        a_audio.set_device_volume(device_id, level, self.config, persist=True)

    # -- refresh ------------------------------------------------------------
    def refresh(self) -> None:
        settings = self._settings()
        ui = settings.get("ui", {}) or {}

        self.default_level.blockSignals(True)
        self.default_level.setValue(int((settings.get("defaults", {}) or {}).get("level", 50)))
        self.default_level.blockSignals(False)

        self.close_action.blockSignals(True)
        self.close_action.setCurrentIndex(max(0, self.close_action.findData(ui.get("close_action") or "tray")))
        self.close_action.blockSignals(False)

        if sys.platform == "win32":
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                    winreg.QueryValueEx(key, "Isha")
                registered = True
            except OSError:
                registered = False
            self.start_with_windows.blockSignals(True)
            self.start_with_windows.setChecked(registered)
            self.start_with_windows.blockSignals(False)

        self.allow_scripts.blockSignals(True)
        self.allow_scripts.setChecked(bool(settings.get("allow_scripts")))
        self.allow_scripts.blockSignals(False)

        audio = settings.get("audio", {}) or {}
        self.volume_mode.blockSignals(True)
        self.volume_mode.setCurrentIndex(max(0, self.volume_mode.findData(audio.get("volume_mode", "together"))))
        self.volume_mode.blockSignals(False)
        behavior = audio.get("mute_behavior", "halve_all")
        self.mute_behavior.blockSignals(True)
        self.mute_behavior.setCurrentIndex(max(0, self.mute_behavior.findData(behavior)))
        self.mute_behavior.blockSignals(False)
        self.mute_level.blockSignals(True)
        self.mute_level.setValue(int(audio.get("mute_level", 50)))
        self.mute_level.setEnabled(behavior == "set_all_to")
        self.mute_level.blockSignals(False)
        self._render_devices()

        shot = settings.get("screenshot", {}) or {}
        self.shot_dir.setText(shot.get("dir") or "")
        self.shot_after.blockSignals(True)
        self.shot_after.setCurrentIndex(max(0, self.shot_after.findData(shot.get("after", "save"))))
        self.shot_after.blockSignals(False)
        self.shot_capture.blockSignals(True)
        self.shot_capture.setCurrentIndex(max(0, self.shot_capture.findData(shot.get("capture", "full"))))
        self.shot_capture.blockSignals(False)
        self.prtscr.blockSignals(True)
        self.prtscr.setChecked(shot.get("prtscr") == "isha")
        self.prtscr.blockSignals(False)

        # quick actions table
        self._clear(self.qa_grid)
        actions = ui.get("quick_actions") or []
        if actions:
            name_header = QLabel("Display name")
            name_header.setProperty("class", "hint")
            action_header = QLabel("Action it runs")
            action_header.setProperty("class", "hint")
            self.qa_grid.addWidget(name_header, 0, 0)
            self.qa_grid.addWidget(action_header, 0, 1)
            for row_index, entry in enumerate(actions, start=1):
                name_label = QLabel(entry.get("label") or "")
                name_label.setProperty("class", "settingName")
                command_label = QLabel(entry.get("command") or "")
                remove = QPushButton("remove")
                remove.setProperty("class", "ghost")
                remove.clicked.connect(lambda _=False, i=row_index - 1: self._remove_quick_action(i))
                self.qa_grid.addWidget(name_label, row_index, 0)
                self.qa_grid.addWidget(command_label, row_index, 1)
                self.qa_grid.addWidget(remove, row_index, 2)
            self.qa_grid.setColumnStretch(1, 1)

        self.allow_enabled.blockSignals(True)
        self.allow_enabled.setChecked(bool(settings.get("allow_list_enabled", True)))
        self.allow_enabled.blockSignals(False)

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
    def _set_mute_behavior(self, _index: int) -> None:
        behavior = self.mute_behavior.currentData()
        self._set_nested(("audio", "mute_behavior"), behavior)
        self.mute_level.setEnabled(behavior == "set_all_to")

    def _browse_shot_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Screenshots folder")
        if directory:
            self.shot_dir.setText(directory)
            self._set_nested(("screenshot", "dir"), directory)

    def _set_start_with_windows(self, on: bool) -> None:
        if sys.platform != "win32":
            return
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if on:
                    winreg.SetValueEx(key, "Isha", 0, winreg.REG_SZ,
                                      f'"{sys.executable}"' if getattr(sys, "frozen", False)
                                      else f'"{sys.executable}" "{Path(__file__).resolve().parent.parent / "app.py"}"')
                else:
                    try:
                        winreg.DeleteValue(key, "Isha")
                    except FileNotFoundError:
                        pass
        except OSError:
            pass

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
        self._settings()["allow_list_enabled"] = bool(on)
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
