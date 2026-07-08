"""
Settings page (§6.5) — General (default level F2, mute behavior F3,
screenshot group F4, notifications, close action, start-with-Windows,
allow-scripts gate), Voice, Privacy, License, Updates, Help (offline
docs/help/*.md via QTextBrowser), About.
"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTextBrowser, QVBoxLayout, QWidget,
)

from config_store import save_config
from shell.main_window import make_scroll_area
from version import VERSION

DOCS = Path(__file__).resolve().parent.parent / "docs" / "help"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


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


class SettingsPage(QWidget):
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

        title = QLabel("Settings")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # ---- general -----------------------------------------------------
        general, general_layout = _card("General")

        row = QHBoxLayout()
        row.addWidget(QLabel("Default level for volume/brightness when you don't say one"))
        self.default_level = QSpinBox()
        self.default_level.setRange(0, 100)
        self.default_level.valueChanged.connect(
            lambda v: self._set_nested(("defaults", "level"), int(v)))
        row.addWidget(self.default_level)
        row.addStretch(1)
        general_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Mute with several audio devices"))
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
        general_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Closing the window"))
        self.close_action = QComboBox()
        self.close_action.addItem("keeps Isha in the tray", "tray")
        self.close_action.addItem("exits completely", "exit")
        self.close_action.currentIndexChanged.connect(
            lambda _: self._set_ui("close_action", self.close_action.currentData()))
        row.addWidget(self.close_action)
        row.addStretch(1)
        general_layout.addLayout(row)

        self.start_with_windows = QCheckBox("Start Isha when Windows starts")
        self.start_with_windows.toggled.connect(self._set_start_with_windows)
        general_layout.addWidget(self.start_with_windows)

        self.allow_scripts = QCheckBox("Allow scripts (mode scripts and saved scripts) — "
                                       "you'll always see the exact command before it runs")
        self.allow_scripts.toggled.connect(
            lambda on: self._set_setting("allow_scripts", bool(on)))
        general_layout.addWidget(self.allow_scripts)
        layout.addWidget(general)

        # ---- screenshots ---------------------------------------------------
        shots, shots_layout = _card("Screenshots")
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
        self.shot_after.addItem("just save", "save")
        self.shot_after.addItem("save and open", "save_and_open")
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

        # ---- notifications ---------------------------------------------------
        notifications, notif_layout = _card("Notifications", "Always silent, calm cards in the top-right — sound is strictly opt-in.")
        row = QHBoxLayout()
        self.notif_sound = QCheckBox("Play a single soft tick with each notification")
        self.notif_sound.toggled.connect(
            lambda on: self._set_nested(("notifications", "sound"), "soft" if on else "off"))
        row.addWidget(self.notif_sound)
        self.notif_native = QCheckBox("Use the Windows notification center instead")
        self.notif_native.toggled.connect(
            lambda on: self._set_nested(("notifications", "use_windows_native"), bool(on)))
        row.addWidget(self.notif_native)
        row.addStretch(1)
        notif_layout.addLayout(row)
        layout.addWidget(notifications)

        # ---- voice -----------------------------------------------------------
        voice, voice_layout = _card("Voice")
        import a_voice_input
        available = a_voice_input.is_available()
        status = QLabel("Voice input is ready — press the mic or Ctrl+Alt+V." if available else
                        "Voice input is optional and fully offline. It needs the 'vosk' and "
                        "'sounddevice' Python packages plus a small model folder at "
                        "~\\.isha\\vosk-model (e.g. vosk-model-small-en-us-0.15 from "
                        "alphacephei.com/vosk/models). Nothing you say ever leaves this machine.")
        status.setWordWrap(True)
        voice_layout.addWidget(status)
        layout.addWidget(voice)

        # ---- privacy ----------------------------------------------------------
        privacy, privacy_layout = _card(
            "Privacy",
            "Everything stays on this machine. One JSON config file, local logs, no telemetry, "
            "no cloud. Sending an issue report is always your explicit choice.")
        row = QHBoxLayout()
        open_logs = QPushButton("Open log folder")
        open_logs.clicked.connect(self._open_logs)
        row.addWidget(open_logs)
        open_config = QPushButton("Open config file")
        open_config.clicked.connect(self._open_config)
        row.addWidget(open_config)
        report = QPushButton("Report an issue")
        report.clicked.connect(lambda: self.runner.submit("report issue", source="settings"))
        row.addWidget(report)
        row.addStretch(1)
        privacy_layout.addLayout(row)
        layout.addWidget(privacy)

        # ---- updates -----------------------------------------------------------
        updates, updates_layout = _card("Updates", "Manual and signature-verified — Isha never downloads anything in the background.")
        row = QHBoxLayout()
        check = QPushButton("Check for updates")
        check.clicked.connect(lambda: self.runner.submit("check updates", source="settings"))
        row.addWidget(check)
        install = QPushButton("Install update…")
        install.clicked.connect(lambda: self.runner.submit("install update", source="settings"))
        row.addWidget(install)
        row.addStretch(1)
        updates_layout.addLayout(row)
        layout.addWidget(updates)

        # ---- help ----------------------------------------------------------------
        help_card, help_layout = _card("Help & docs")
        tabs = QHBoxLayout()
        self.help_view = QTextBrowser()
        self.help_view.setOpenExternalLinks(True)
        self.help_view.setMinimumHeight(320)
        for slug, label in (("getting-started", "Getting started"), ("commands", "Commands"),
                            ("scripts-and-security", "Scripts & security"), ("troubleshooting", "Troubleshooting")):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, s=slug: self._show_doc(s))
            tabs.addWidget(button)
        tabs.addStretch(1)
        help_layout.addLayout(tabs)
        help_layout.addWidget(self.help_view)
        self._help_card = help_card
        layout.addWidget(help_card)

        about = QLabel(f"Isha v{VERSION} — made to stay out of your way. 🌸")
        about.setProperty("class", "hint")
        layout.addWidget(about)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = make_scroll_area(config, body)
        outer.addWidget(self._scroll)

        self._show_doc("getting-started")
        self.refresh()

    # ------------------------------------------------------------------
    def _settings(self) -> dict:
        return self.config.setdefault("settings", {})

    def _set_setting(self, key: str, value) -> None:
        self._settings()[key] = value
        save_config(self.config)

    def _set_ui(self, key: str, value) -> None:
        self._settings().setdefault("ui", {})[key] = value
        save_config(self.config)

    def _set_nested(self, path: tuple, value) -> None:
        node = self._settings()
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value
        save_config(self.config)

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
                    winreg.SetValueEx(key, "Isha", 0, winreg.REG_SZ, f'"{sys.executable}" "{Path(__file__).resolve().parent.parent / "app.py"}"'
                                      if not getattr(sys, "frozen", False) else f'"{sys.executable}"')
                else:
                    try:
                        winreg.DeleteValue(key, "Isha")
                    except FileNotFoundError:
                        pass
        except OSError:
            pass

    def _open_logs(self) -> None:
        from platform_paths import logs_dir
        import os
        try:
            os.startfile(str(logs_dir()))
        except OSError:
            pass

    def _open_config(self) -> None:
        from platform_paths import config_file
        import os
        try:
            os.startfile(str(config_file()))
        except OSError:
            pass

    def _show_doc(self, slug: str) -> None:
        path = DOCS / f"{slug}.md"
        try:
            self.help_view.setMarkdown(path.read_text(encoding="utf-8"))
        except OSError:
            self.help_view.setMarkdown(f"*Couldn't load {path.name}.*")

    def show_section(self, section: str) -> None:
        if section == "help":
            self._scroll.ensureWidgetVisible(self._help_card)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        settings = self._settings()
        ui = settings.get("ui", {}) or {}

        self.default_level.blockSignals(True)
        self.default_level.setValue(int((settings.get("defaults", {}) or {}).get("level", 50)))
        self.default_level.blockSignals(False)

        audio = settings.get("audio", {}) or {}
        behavior = audio.get("mute_behavior", "halve_all")
        index = max(0, self.mute_behavior.findData(behavior))
        self.mute_behavior.blockSignals(True)
        self.mute_behavior.setCurrentIndex(index)
        self.mute_behavior.blockSignals(False)
        self.mute_level.blockSignals(True)
        self.mute_level.setValue(int(audio.get("mute_level", 50)))
        self.mute_level.setEnabled(behavior == "set_all_to")
        self.mute_level.blockSignals(False)

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

        notifications = settings.get("notifications", {}) or {}
        self.notif_sound.blockSignals(True)
        self.notif_sound.setChecked(notifications.get("sound") == "soft")
        self.notif_sound.blockSignals(False)
        self.notif_native.blockSignals(True)
        self.notif_native.setChecked(bool(notifications.get("use_windows_native")))
        self.notif_native.blockSignals(False)
