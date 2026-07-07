"""
Dashboard — a single at-a-glance overview window: which mode is active (with
one-click switching), what Isha has done recently, whether this device is
licensed, and quick shortcuts into the actions people reach for most. It
complements settings_window.py rather than replacing it: settings is where
you *configure* Isha, the dashboard is where you glance at *state* and act on
it, same split as most desktop apps' "Home" vs. "Preferences".

Reuses main.process_command_safe for every action here, so nothing on this
screen behaves differently from typing the same command into the palette.
"""
import json
import tkinter as tk
from tkinter import ttk, messagebox

import ui_theme
from ui_theme import BG, BG_RAISED, FG, FG_MUTED, PAD, PAD_SM
from config_store import save_config
from platform_paths import logs_dir
from version import VERSION

WINDOW_WIDTH = 640
WINDOW_HEIGHT = 560

MAX_RECENT_SHOWN = 12


class DashboardWindow:
    def __init__(self, config: dict, master: tk.Misc):
        self.config = config
        self.win = tk.Toplevel(master)
        self.win.title("Isha — Dashboard")
        self.win.configure(bg=BG)
        self.win.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.win.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.win.transient(master)

        ui_theme.apply_ttk_theme(self.win)
        self.fonts = ui_theme.fonts()

        outer = tk.Frame(self.win, bg=BG, padx=PAD, pady=PAD)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, PAD))
        tk.Label(header, text="Dashboard", font=self.fonts["title"], bg=BG, fg=FG, anchor="w").pack(side="left")
        ui_theme.styled_button(header, "Settings...", self._open_settings).pack(side="right")

        canvas_frame = tk.Frame(outer, bg=BG)
        canvas_frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(canvas_frame, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        body = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=body, anchor="nw", width=WINDOW_WIDTH - 2 * PAD - 20)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self._build_quick_actions(body)
        self._build_modes_section(body)
        self._build_license_section(body)
        self._build_recent_section(body)

        tk.Label(
            outer, text=f"Isha v{VERSION}", font=self.fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w",
        ).pack(fill="x", pady=(PAD_SM, 0))

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_force()

    # -----------------------------------------------------------------
    def _section(self, parent, title):
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="x", pady=(0, PAD))
        tk.Label(wrap, text=title, font=self.fonts["body_bold"], bg=BG, fg=FG, anchor="w").pack(fill="x", pady=(0, PAD_SM))
        card = ui_theme.card(wrap, padx=PAD_SM, pady=PAD_SM)
        card.pack(fill="x")
        return card

    # -----------------------------------------------------------------
    def _run_command(self, command_text: str):
        from main import process_command_safe

        def confirm(resolved_ir):
            name = resolved_ir.target if isinstance(resolved_ir.target, str) else (resolved_ir.target or {}).get("name") or resolved_ir.action
            return messagebox.askyesno(
                "Isha — confirm", f"'{resolved_ir.action}' on '{name}' can't be easily undone. Proceed?", parent=self.win,
            )

        outcomes = process_command_safe(command_text, self.config, confirm_callback=confirm)
        messages = [o["result"].message for o in outcomes] or ["Nothing happened."]
        messagebox.showinfo("Isha", "\n".join(messages), parent=self.win)
        self._refresh()

    def _refresh(self):
        # Simplest correct approach: rebuild the whole window in place rather
        # than diffing widget state — this is an occasional-glance dashboard,
        # not a live-updating view, so a full rebuild after an action is
        # cheap and guarantees every section (modes, license, recent) is
        # consistent with the change that was just made.
        master = self.win.master
        self.win.destroy()
        DashboardWindow(self.config, master)

    def _open_settings(self):
        from settings_window import SettingsWindow
        SettingsWindow(self.config, self.win.master)

    # -----------------------------------------------------------------
    def _build_quick_actions(self, parent):
        card = self._section(parent, "Quick actions")
        row = tk.Frame(card, bg=BG_RAISED)
        row.pack(fill="x")
        actions = [
            ("Take screenshot", "take screenshot"),
            ("Check disk space", "check disk space"),
            ("Check internet", "check internet"),
            ("Empty recycle bin", "empty recycle bin"),
            ("Undo last action", "undo"),
        ]
        for label, command_text in actions:
            ui_theme.styled_button(row, label, lambda c=command_text: self._run_command(c)).pack(
                side="left", padx=(0, PAD_SM), pady=PAD_SM,
            )

    # -----------------------------------------------------------------
    def _build_modes_section(self, parent):
        card = self._section(parent, "Modes")
        modes = self.config.get("modes", {})
        active_mode = self.config.get("active_mode")

        tk.Label(
            card, text=(f"Active: {active_mode}" if active_mode else "No mode active"),
            font=self.fonts["body"], bg=BG_RAISED, fg=FG, anchor="w",
        ).pack(fill="x", pady=(0, PAD_SM))

        if not modes:
            tk.Label(
                card, text="No modes created yet — try \"create study mode chrome and youtube\" in the palette.",
                font=self.fonts["hint"], bg=BG_RAISED, fg=FG_MUTED, anchor="w", wraplength=WINDOW_WIDTH - 4 * PAD,
            ).pack(fill="x")
            return

        for name in sorted(modes.keys()):
            row = tk.Frame(card, bg=BG_RAISED)
            row.pack(fill="x", pady=(0, 4))
            is_active = name == active_mode
            label_text = f"{name}  (active)" if is_active else name
            tk.Label(row, text=label_text, font=self.fonts["body"], bg=BG_RAISED, fg=FG, anchor="w").pack(side="left")
            if not is_active:
                ui_theme.styled_button(
                    row, "Activate", lambda n=name: self._run_command(f"activate mode {n}"), accent=True,
                ).pack(side="right")
            else:
                ui_theme.styled_button(
                    row, "Deactivate", lambda n=name: self._run_command(f"deactivate mode {n}"),
                ).pack(side="right")

    # -----------------------------------------------------------------
    def _build_license_section(self, parent):
        card = self._section(parent, "License")
        import a_licensing
        result = a_licensing.get_license_status(self.config)
        licensed = result.data.get("licensed")
        tk.Label(
            card, text=result.message,
            font=self.fonts["body"], bg=BG_RAISED,
            fg=(ui_theme.SUCCESS if licensed else FG_MUTED),
            anchor="w", justify="left", wraplength=WINDOW_WIDTH - 4 * PAD,
        ).pack(fill="x")

        if not licensed:
            row = tk.Frame(card, bg=BG_RAISED)
            row.pack(fill="x", pady=(PAD_SM, 0))
            tk.Label(
                row,
                text="You're on Isha Lite (free): open/close apps and volume/brightness only.",
                font=self.fonts["hint"], bg=BG_RAISED, fg=FG_MUTED, anchor="w",
                justify="left", wraplength=WINDOW_WIDTH - 4 * PAD,
            ).pack(fill="x", pady=(0, PAD_SM))
            ui_theme.styled_button(row, "Upgrade to full Isha", self._open_upgrade_page, accent=True).pack(anchor="w")

    def _open_upgrade_page(self):
        import webbrowser
        webbrowser.open("https://isha.app/#pricing")

    # -----------------------------------------------------------------
    def _build_recent_section(self, parent):
        card = self._section(parent, "Recent activity")
        records = self._load_recent_records()
        if not records:
            tk.Label(
                card, text="No activity recorded yet on this device.",
                font=self.fonts["hint"], bg=BG_RAISED, fg=FG_MUTED, anchor="w",
            ).pack(fill="x")
            return

        for record in records:
            result = (record.get("execution_result") or {})
            mark = "✓" if result.get("success") else "✕"
            message = result.get("message") or "(no message)"
            preview = message if len(message) <= 90 else message[:87] + "..."
            tk.Label(
                card, text=f"{mark}  {preview}", font=self.fonts["hint"], bg=BG_RAISED,
                fg=(FG if result.get("success") else ui_theme.ERROR), anchor="w",
                justify="left", wraplength=WINDOW_WIDTH - 4 * PAD,
            ).pack(fill="x", pady=(0, 2))

    def _load_recent_records(self) -> list:
        """
        Tails commands.jsonl for the dashboard's "recent activity" list.
        Best-effort only: a missing/corrupt log file (fresh install, or mid-
        rotation) just means an empty list, never a dashboard crash — this is
        a glance view, not the source of truth (that's the log file itself).
        """
        path = logs_dir() / "commands.jsonl"
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return []

        records = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "command_id" not in record:
                continue  # a crash record, not a command record
            records.append(record)
            if len(records) >= MAX_RECENT_SHOWN:
                break
        return records
