"""
The single main window (§3.3): sidebar + lazily-built page stack, the faint
branch SVG painted into the backdrop, native wheel scrolling everywhere,
window geometry remembered, close-to-tray by default (asked once, quietly).
Pages are built on first visit and refreshed in place — never
destroy-and-rebuild.
"""
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QHBoxLayout, QMainWindow, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from config_store import save_config
from design import tokens
from shell.sidebar import Sidebar
from version import VERSION

ASSETS = Path(__file__).resolve().parent.parent / "assets"

DEFAULT_W, DEFAULT_H = 1200, 780
MIN_W, MIN_H = 980, 640


def make_scroll_area(config: dict, inner: QWidget) -> QScrollArea:
    """Every page body scrolls through one of these — wheel/trackpad/keys all
    work natively; scrollbar visibility follows ui.show_scrollbars."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(inner)
    area.setFrameShape(QScrollArea.NoFrame)
    apply_scrollbar_policy(config, area)
    return area


def apply_scrollbar_policy(config: dict, area: QScrollArea) -> None:
    mode = (config.get("settings", {}).get("ui", {}) or {}).get("show_scrollbars", "auto")
    policy = {
        "always": Qt.ScrollBarAlwaysOn,
        "hidden": Qt.ScrollBarAlwaysOff,
    }.get(mode, Qt.ScrollBarAsNeeded)
    area.setVerticalScrollBarPolicy(policy)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


class ContentBackdrop(QWidget):
    """Paints the branch SVG faintly into the top-right of the content area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("appRoot")
        svg_path = ASSETS / "branch.svg"
        self._renderer = QSvgRenderer(str(svg_path)) if svg_path.exists() else None
        self._opacity = 0.16

    def set_theme(self, theme: str) -> None:
        self._opacity = 0.16 if theme == "light" else 0.10
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._renderer is None or not self._renderer.isValid():
            return
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        width = min(self.width() * 0.42, 480)
        height = width * (180 / 420)
        self._renderer.render(painter, QRectF(self.width() - width, 0, width, height))
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self, config: dict, runner, notifier):
        super().__init__()
        self.config = config
        self.runner = runner
        self.notifier = notifier
        self._pages = {}          # key -> widget (built lazily)
        self._page_factories = {}
        self._force_quit = False

        self.setWindowTitle(f"Isha")
        self.setMinimumSize(MIN_W, MIN_H)

        backdrop = ContentBackdrop()
        self._backdrop = backdrop
        self.setCentralWidget(backdrop)

        root = QHBoxLayout(backdrop)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(config)
        self.sidebar.navigate.connect(self.show_page)
        root.addWidget(self.sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        content.addWidget(self.stack)
        root.addLayout(content, 1)

        self._register_pages()
        self._restore_geometry()

        QShortcut(QKeySequence("Ctrl+B"), self, self.sidebar.toggle)
        QShortcut(QKeySequence("Ctrl+,"), self, lambda: self.show_page("settings"))
        QShortcut(QKeySequence("Ctrl+K"), self, self._focus_command_bar)
        QShortcut(QKeySequence("F1"), self, lambda: self.show_page("settings", section="help"))

        # Perceived cold start (P3): the window frame paints first; the
        # dashboard (whose first QLineEdit pays Qt's one-time input-stack
        # init, ~750 ms on a mid-range machine) builds one event-loop turn
        # later, so launch feels immediate.
        QTimer.singleShot(0, lambda: self.show_page("dashboard"))

    # -- pages ----------------------------------------------------------
    def _register_pages(self) -> None:
        def dashboard():
            from pages.dashboard import DashboardPage
            return DashboardPage(self.config, self.runner, self)

        def modes():
            from pages.modes import ModesPage
            return ModesPage(self.config, self.runner, self)

        def reminders():
            from pages.reminders import RemindersPage
            return RemindersPage(self.config, self.runner, self)

        def shortcuts():
            from pages.shortcuts import ShortcutsPage
            return ShortcutsPage(self.config, self.runner, self)

        def customization():
            from pages.customization import CustomizationPage
            return CustomizationPage(self.config, self.runner, self)

        def settings():
            from pages.settings import SettingsPage
            return SettingsPage(self.config, self.runner, self)

        self._page_factories = {
            "dashboard": dashboard, "modes": modes, "reminders": reminders,
            "shortcuts": shortcuts, "customization": customization, "settings": settings,
        }

    def show_page(self, key: str, section: str = None) -> None:
        if key not in self._pages:
            page = self._page_factories[key]()
            self._pages[key] = page
            self.stack.addWidget(page)
        page = self._pages[key]
        if hasattr(page, "refresh"):
            page.refresh()
        if section and hasattr(page, "show_section"):
            page.show_section(section)
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)

    def refresh_current_page(self) -> None:
        page = self.stack.currentWidget()
        if page is not None and hasattr(page, "refresh"):
            page.refresh()

    def _focus_command_bar(self) -> None:
        self.show_page("dashboard")
        page = self._pages.get("dashboard")
        if page is not None and hasattr(page, "focus_command_bar"):
            page.focus_command_bar()

    # -- theme ----------------------------------------------------------
    def apply_theme(self) -> None:
        from PySide6.QtWidgets import QApplication
        theme = tokens.resolve_theme(
            (self.config.get("settings", {}).get("ui", {}) or {}).get("theme", "auto"))
        QApplication.instance().setStyleSheet(tokens.build_qss(theme))
        self._backdrop.set_theme(theme)

    # -- geometry / close behavior ---------------------------------------
    def _restore_geometry(self) -> None:
        saved = (self.config.get("settings", {}).get("ui", {}) or {}).get("window") or {}
        self.resize(saved.get("w", DEFAULT_W), saved.get("h", DEFAULT_H))
        if "x" in saved and "y" in saved:
            self.move(saved["x"], saved["y"])
        if saved.get("maximized"):
            self.setWindowState(Qt.WindowMaximized)

    def _save_geometry(self) -> None:
        ui = self.config.setdefault("settings", {}).setdefault("ui", {})
        if self.isMaximized():
            ui.setdefault("window", {})["maximized"] = True
        else:
            geo = self.geometry()
            ui["window"] = {"x": geo.x(), "y": geo.y(), "w": geo.width(), "h": geo.height(),
                            "maximized": False}
        save_config(self.config)

    def force_quit(self) -> None:
        self._force_quit = True
        self.close()

    def closeEvent(self, event):
        self._save_geometry()
        if self._force_quit:
            event.accept()
            return

        ui = self.config.setdefault("settings", {}).setdefault("ui", {})
        action = ui.get("close_action")
        if action is None:
            # asked once, quietly, the first time — never a modal alarm
            from widgets.quiet_prompt import QuietPrompt
            keep_running = QuietPrompt.ask(
                "Keep Isha running?",
                "Closing this window can keep Isha in the tray (hotkeys, reminders and "
                "modes keep working) or exit completely. You can change this any time "
                "in Settings.",
                yes_label="Keep in tray", no_label="Exit completely", parent=self)
            action = "tray" if keep_running else "exit"
            ui["close_action"] = action
            save_config(self.config)

        if action == "tray":
            event.ignore()
            self.hide()
            if self.notifier is not None and not ui.get("_tray_hint_shown"):
                self.notifier.notify("Isha", "Still running here in the tray — the hotkey still works.")
                ui["_tray_hint_shown"] = True
                save_config(self.config)
        else:
            event.accept()
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()

    def bring_to_front(self) -> None:
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
