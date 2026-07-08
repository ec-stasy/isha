"""
Dedicated Privacy / Updates / Help pages (Cycle 6 UI 22) — the old Settings
page squeezed each of these into a three-line card; they're now full pages
with real explanations, reachable from Settings ▸ More (and F1 for Help).
Each page has a back link to Settings.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from shell.main_window import make_scroll_area
from version import VERSION

DOCS = Path(__file__).resolve().parent.parent / "docs" / "help"


def _base_page(config, window, title_text: str, subtitle_text: str):
    """(page_widget, content_layout) with title, subtitle and a back link."""
    page = QWidget()
    body = QWidget()
    body.setObjectName("pageBody")
    layout = QVBoxLayout(body)
    layout.setContentsMargins(36, 30, 36, 26)
    layout.setSpacing(14)

    back = QPushButton("‹ back to Settings")
    back.setProperty("class", "ghost")
    back.setCursor(Qt.PointingHandCursor)
    back.clicked.connect(lambda: window.show_page("settings"))
    layout.addWidget(back, alignment=Qt.AlignLeft)

    title = QLabel(title_text)
    title.setProperty("class", "title")
    layout.addWidget(title)
    subtitle = QLabel(subtitle_text)
    subtitle.setProperty("class", "subtitle")
    subtitle.setWordWrap(True)
    layout.addWidget(subtitle)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(make_scroll_area(config, body))
    return page, layout


def _text_card(layout, heading: str, paragraphs) -> None:
    card = QFrame()
    card.setProperty("class", "card")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(20, 18, 20, 18)
    card_layout.setSpacing(8)
    head = QLabel(heading)
    head.setProperty("class", "settingName")
    card_layout.addWidget(head)
    for text in paragraphs:
        p = QLabel(text)
        p.setWordWrap(True)
        p.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card_layout.addWidget(p)
    layout.addWidget(card)


class PrivacyPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        self.config = config
        self.runner = runner
        page, layout = _base_page(config, window, "Privacy",
                                  "The whole promise in one line: nothing leaves this machine "
                                  "unless you explicitly send it.")
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(page)

        _text_card(layout, "What Isha stores, and where", [
            "Everything Isha knows lives in one folder on this PC: %APPDATA%\\Isha. That's a "
            "single human-readable config.json (your modes, reminders, aliases, settings), a "
            "logs folder (one line per command you ran, kept locally so problems can be "
            "diagnosed), and a small cache of your installed apps so “open chrome” resolves "
            "instantly.",
            "Sensitive content — reminder text, clipboard history, search queries — is redacted "
            "in the log file before it's written. Clipboard history is never written to disk at "
            "all; it lives only in memory while Isha runs.",
        ])
        _text_card(layout, "What uses the network (and only when you ask)", [
            "• Opening a website — because you asked to open it.",
            "• “Check internet” — a speed measurement against Cloudflare's public speed-test "
            "endpoint, only when you run the command; the payload is random bytes.",
            "• Voice input — the audio of a voice command is sent to an online speech service "
            "to be turned into text (you saw a one-time notice about this before first use). "
            "Only the audio is sent, only while the mic is on.",
            "• “Check updates” / “Install update” — manual only, never in the background, and "
            "every download is cryptographically verified before it runs.",
            "• Sending an issue report — builds a local zip first, shows you exactly what's in "
            "it, and uploads nothing until you separately confirm 'send report'.",
            "There is no telemetry, no analytics, no account, and no background phoning home. "
            "A plain install that you never ask to touch the network makes zero network calls.",
        ])
        _text_card(layout, "Your controls", [
            "The buttons below open the actual files, so you can verify all of this yourself.",
        ])

        row = QHBoxLayout()
        open_logs = QPushButton("Open log folder")
        open_logs.clicked.connect(self._open_logs)
        row.addWidget(open_logs)
        open_config = QPushButton("Open config file")
        open_config.clicked.connect(self._open_config)
        row.addWidget(open_config)
        report = QPushButton("Report an issue")
        report.setToolTip("Builds a local zip and shows you what's inside — nothing is sent")
        report.clicked.connect(lambda: runner.submit("report issue", source="privacy_page"))
        row.addWidget(report)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

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


class UpdatesPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        page, layout = _base_page(config, window, "Updates",
                                  "Manual, verified, and never in the background.")
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(page)

        _text_card(layout, "How updating works", [
            f"You're on Isha v{VERSION}.",
            "1. “Check for updates” fetches a small version manifest — this happens only when "
            "you click the button or type the command, never on a timer.",
            "2. The manifest is signed. Isha verifies the Ed25519 signature with a public key "
            "built into the app before trusting anything in it — an unsigned or tampered "
            "manifest is simply refused.",
            "3. If a newer version exists, the installer is downloaded to a private folder and "
            "its SHA-256 checksum is compared against the signed manifest. A mismatch means it "
            "is deleted, not run.",
            "4. “Install update” re-verifies the checksum immediately before launching the "
            "installer, and always asks you to confirm first. The installer then shows its own "
            "normal windows — nothing is ever installed silently.",
        ])
        _text_card(layout, "Why it's manual", [
            "A background updater would mean Isha makes network calls you didn't ask for, "
            "which would break the privacy promise on the Privacy page. Checking takes two "
            "seconds when you want it; do it whenever suits you.",
        ])

        row = QHBoxLayout()
        check = QPushButton("Check for updates")
        check.setProperty("class", "accent")
        check.clicked.connect(lambda: runner.submit("check updates", source="updates_page"))
        row.addWidget(check)
        install = QPushButton("Install update…")
        install.clicked.connect(lambda: runner.submit("install update", source="updates_page"))
        row.addWidget(install)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)


class HelpPage(QWidget):
    def __init__(self, config: dict, runner, window):
        super().__init__()
        page, layout = _base_page(config, window, "Help & docs",
                                  "Everything Isha can do, in plain words. (F1 opens this page.)")
        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(page)

        tabs = QHBoxLayout()
        self.help_view = QTextBrowser()
        self.help_view.setOpenExternalLinks(True)
        self.help_view.setMinimumHeight(460)
        self._buttons = {}
        for slug, label in (("getting-started", "Getting started"), ("commands", "Commands"),
                            ("scripts-and-security", "Scripts & security"), ("troubleshooting", "Troubleshooting")):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, s=slug: self._show_doc(s))
            tabs.addWidget(button)
            self._buttons[slug] = button
        tabs.addStretch(1)
        layout.addLayout(tabs)
        layout.addWidget(self.help_view)
        layout.addStretch(1)

        self._show_doc("getting-started")

    def _show_doc(self, slug: str) -> None:
        path = DOCS / f"{slug}.md"
        try:
            self.help_view.setMarkdown(path.read_text(encoding="utf-8"))
        except OSError:
            self.help_view.setMarkdown(f"*Couldn't load {path.name}.*")
