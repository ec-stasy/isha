"""
Settings page (§6.5, reworked in Cycle 6) — Obsidian-style rows: every
setting is a full-width row with a bold name and a real explanation on the
left and its control on the right, grouped into a few calm sections.
Appearance lives here now (moved from Customization, plus the new app-wide
font size); behavior-of-Isha settings (defaults, volume, screenshots)
moved to Customization; Privacy, Updates and Help are full dedicated pages
reachable from the bottom section.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from config_store import save_config
from shell.main_window import make_scroll_area, apply_scrollbar_policy
from version import VERSION


def _section(title: str) -> tuple:
    card = QFrame()
    card.setProperty("class", "card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(4)
    label = QLabel(title)
    label.setProperty("class", "subtitle")
    label.setStyleSheet("font-weight: 600; margin-bottom: 6px;")
    layout.addWidget(label)
    return card, layout


def _setting_row(name: str, description: str, control: QWidget = None) -> QWidget:
    """One Obsidian-style settings row: name + description left, control right."""
    row_widget = QWidget()
    row = QHBoxLayout(row_widget)
    row.setContentsMargins(0, 10, 0, 10)
    row.setSpacing(24)

    text_column = QVBoxLayout()
    text_column.setSpacing(3)
    name_label = QLabel(name)
    name_label.setProperty("class", "settingName")
    text_column.addWidget(name_label)
    if description:
        desc_label = QLabel(description)
        desc_label.setProperty("class", "hint")
        desc_label.setWordWrap(True)
        text_column.addWidget(desc_label)
    row.addLayout(text_column, 1)

    if control is not None:
        row.addWidget(control, alignment=Qt.AlignVCenter)
    return row_widget


def _row_divider() -> QFrame:
    line = QFrame()
    line.setProperty("class", "hline")
    line.setFixedHeight(1)
    return line


class SettingsPage(QWidget):
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

        title = QLabel("Settings")
        title.setProperty("class", "title")
        layout.addWidget(title)
        subtitle = QLabel("How Isha looks and feels. Behavior settings (volume, screenshots, "
                          "quick actions) live on the Customization page.")
        subtitle.setProperty("class", "subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ---- appearance (moved here — Cycle 6 UI 24) -----------------------
        appearance, appearance_layout = _section("Appearance")

        self.theme = QComboBox()
        self.theme.addItem("follow Windows (auto)", "auto")
        self.theme.addItem("light — warm paper white", "light")
        self.theme.addItem("dark — deep warm black", "dark")
        self.theme.currentIndexChanged.connect(
            lambda _: self._set_theme(self.theme.currentData()))
        appearance_layout.addWidget(_setting_row(
            "Theme",
            "Isha's own colors. “Auto” follows your Windows light/dark setting; the two fixed "
            "themes are the same design at two temperatures.",
            self.theme))
        appearance_layout.addWidget(_row_divider())

        self.font_scale = QComboBox()
        self.font_scale.addItem("compact (90%)", 0.9)
        self.font_scale.addItem("default (100%)", 1.0)
        self.font_scale.addItem("comfortable (110%)", 1.1)
        self.font_scale.addItem("large (125%)", 1.25)
        self.font_scale.currentIndexChanged.connect(
            lambda _: self._set_font_scale(self.font_scale.currentData()))
        appearance_layout.addWidget(_setting_row(
            "Font size",
            "Scales every piece of text in the app at once — pick “comfortable” or “large” "
            "if things feel cramped or hard to read. Applies immediately.",
            self.font_scale))
        appearance_layout.addWidget(_row_divider())

        self.scrollbars = QComboBox()
        self.scrollbars.addItem("show while scrolling (auto)", "auto")
        self.scrollbars.addItem("always visible", "always")
        self.scrollbars.addItem("hidden", "hidden")
        self.scrollbars.currentIndexChanged.connect(
            lambda _: self._set_scrollbars(self.scrollbars.currentData()))
        appearance_layout.addWidget(_setting_row(
            "Scrollbars",
            "Whether page scrollbars are always visible, appear only when needed, or stay "
            "hidden (scrolling itself always works).",
            self.scrollbars))
        appearance_layout.addWidget(_row_divider())

        self.reduce_motion = QCheckBox()
        self.reduce_motion.toggled.connect(lambda on: self._set_ui("reduce_motion", bool(on)))
        appearance_layout.addWidget(_setting_row(
            "Reduce motion",
            "Turns off the small animations (sidebar slide, easing needles) for a completely "
            "still interface — useful if animation is distracting or triggers discomfort.",
            self.reduce_motion))
        layout.addWidget(appearance)

        # ---- behavior -------------------------------------------------------
        behavior, behavior_layout = _section("Behavior")

        self.autohide = QDoubleSpinBox()
        self.autohide.setRange(0.0, 30.0)
        self.autohide.setSingleStep(0.5)
        self.autohide.setSuffix(" s")
        self.autohide.setSpecialValueText("keep open")
        self.autohide.valueChanged.connect(lambda v: self._set_ui("overlay_autohide", float(v)))
        behavior_layout.addWidget(_setting_row(
            "Result display time (quick input)",
            "After a command run from the quick-input window (the hotkey popup) succeeds, its "
            "result stays on screen this long before the popup hides itself. This is about the "
            "response you see, not what you typed. “Keep open” disables auto-hiding entirely.",
            self.autohide))
        layout.addWidget(behavior)

        # ---- notifications (single dropdown — Cycle 6 UI 23) ----------------
        notifications, notif_layout = _section("Notifications")

        self.notif_style = QComboBox()
        self.notif_style.addItem("calm in-app cards (default)", "cards")
        self.notif_style.addItem("Windows notification center", "native")
        self.notif_style.currentIndexChanged.connect(self._set_notif_style)
        notif_layout.addWidget(_setting_row(
            "Where notifications appear",
            "Reminders and background events can show as Isha's own quiet cards in the "
            "top-right of your screen, or go through the regular Windows notification "
            "center (so they collect in the Windows history and respect Focus Assist).",
            self.notif_style))
        notif_layout.addWidget(_row_divider())

        self.notif_sound = QCheckBox()
        self.notif_sound.toggled.connect(
            lambda on: self._set_nested(("notifications", "sound"), "soft" if on else "off"))
        notif_layout.addWidget(_setting_row(
            "Notification sound",
            "Plays one soft tick with each notification. Off by default — notifications are "
            "always silent unless you opt in here.",
            self.notif_sound))
        layout.addWidget(notifications)

        # ---- voice -----------------------------------------------------------
        voice, voice_layout = _section("Voice input")
        import a_voice_input
        if a_voice_input.is_available():
            voice_text = ("Ready — click the mic in the command bar or press Ctrl+Alt+V, speak, "
                          "and the words appear in the input for you to review (voice never runs "
                          "a command by itself). Voice needs an internet connection: the audio of "
                          "your command is sent to an online speech service to be transcribed — "
                          "only the audio, never your files or settings. There is nothing to "
                          "install or download.")
        else:
            voice_text = ("Voice isn't available in this build: " +
                          (a_voice_input.unavailable_reason() or "unknown reason."))
        status = QLabel(voice_text)
        status.setWordWrap(True)
        voice_layout.addWidget(status)
        layout.addWidget(voice)

        # ---- more pages -------------------------------------------------------
        more, more_layout = _section("More")
        for key, name, description in (
                ("privacy", "Privacy", "Exactly what Isha stores, where it lives on this PC, and what (never) leaves this machine."),
                ("updates", "Updates", "How update checking works, why it's manual, and how downloads are verified before they run."),
                ("help", "Help & docs", "Getting started, the full command list, scripts & security, and troubleshooting.")):
            button = QPushButton("open ▸")
            button.setProperty("class", "ghost")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=key: self.window.show_page(k))
            more_layout.addWidget(_setting_row(name, description, button))
            if key != "help":
                more_layout.addWidget(_row_divider())
        layout.addWidget(more)

        about = QLabel(f"Isha v{VERSION} — made to stay out of your way. 🌸")
        about.setProperty("class", "hint")
        layout.addWidget(about)
        layout.addStretch(1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = make_scroll_area(config, body)
        outer.addWidget(self._scroll)

        self.refresh()

    # ------------------------------------------------------------------
    def _settings(self) -> dict:
        return self.config.setdefault("settings", {})

    def _set_ui(self, key: str, value) -> None:
        self._settings().setdefault("ui", {})[key] = value
        save_config(self.config)

    def _set_nested(self, path: tuple, value) -> None:
        node = self._settings()
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = value
        save_config(self.config)

    def _set_theme(self, theme: str) -> None:
        self._set_ui("theme", theme)
        self.window.apply_theme()

    def _set_font_scale(self, scale: float) -> None:
        self._set_ui("font_scale", float(scale))
        self.window.apply_theme()

    def _set_scrollbars(self, mode: str) -> None:
        self._set_ui("show_scrollbars", mode)
        from PySide6.QtWidgets import QScrollArea
        for area in self.window.findChildren(QScrollArea):
            apply_scrollbar_policy(self.config, area)

    def _set_notif_style(self, _index: int) -> None:
        native = self.notif_style.currentData() == "native"
        self._set_nested(("notifications", "use_windows_native"), native)

    def show_section(self, section: str) -> None:
        if section == "help":
            self.window.show_page("help")

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        settings = self._settings()
        ui = settings.get("ui", {}) or {}

        self.theme.blockSignals(True)
        self.theme.setCurrentIndex(max(0, self.theme.findData(ui.get("theme", "auto"))))
        self.theme.blockSignals(False)

        self.font_scale.blockSignals(True)
        index = self.font_scale.findData(float(ui.get("font_scale", 1.0)))
        self.font_scale.setCurrentIndex(index if index >= 0 else 1)
        self.font_scale.blockSignals(False)

        self.scrollbars.blockSignals(True)
        self.scrollbars.setCurrentIndex(max(0, self.scrollbars.findData(ui.get("show_scrollbars", "auto"))))
        self.scrollbars.blockSignals(False)

        self.reduce_motion.blockSignals(True)
        self.reduce_motion.setChecked(bool(ui.get("reduce_motion")))
        self.reduce_motion.blockSignals(False)

        self.autohide.blockSignals(True)
        self.autohide.setValue(float(ui.get("overlay_autohide", 2.5) or 0))
        self.autohide.blockSignals(False)

        notifications = settings.get("notifications", {}) or {}
        self.notif_style.blockSignals(True)
        self.notif_style.setCurrentIndex(max(0, self.notif_style.findData(
            "native" if notifications.get("use_windows_native") else "cards")))
        self.notif_style.blockSignals(False)
        self.notif_sound.blockSignals(True)
        self.notif_sound.setChecked(notifications.get("sound") == "soft")
        self.notif_sound.blockSignals(False)
