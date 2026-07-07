"""
First-run onboarding wizard (Track C3) — replaces the single printed/shown
message with a short, calm, guided walkthrough: the privacy promise up
front, where the hotkey lives, and creating a first mode (the app's actual
differentiator) instead of leaving a brand-new user staring at an empty
command box wondering what to type.

Three steps, not a dozen — the goal is orientation, not a tour. Skippable at
any point; skipping still marks the run as onboarded, same as finishing.
"""
import tkinter as tk
from tkinter import ttk

import ui_theme
from ui_theme import BG, BG_RAISED, FG, FG_MUTED, ACCENT, PAD, PAD_SM
from config_store import save_config

WINDOW_WIDTH = 520
WINDOW_HEIGHT = 380


class OnboardingWizard:
    def __init__(self, config: dict, master: tk.Misc, on_done=None):
        self.config = config
        self._on_done = on_done

        self.win = tk.Toplevel(master)
        self.win.title("Welcome to Isha")
        self.win.configure(bg=BG)
        self.win.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.win.resizable(False, False)
        self.win.transient(master)
        self.win.attributes("-topmost", True)

        ui_theme.apply_ttk_theme(self.win)
        self.fonts = ui_theme.fonts()

        outer = tk.Frame(self.win, bg=BG, padx=PAD * 2, pady=PAD * 2)
        outer.pack(fill="both", expand=True)

        self.dots_row = tk.Frame(outer, bg=BG)
        self.dots_row.pack(pady=(0, PAD))

        self.content = tk.Frame(outer, bg=BG)
        self.content.pack(fill="both", expand=True)

        footer = tk.Frame(outer, bg=BG)
        footer.pack(fill="x", pady=(PAD, 0))
        self.skip_button = ui_theme.styled_button(footer, "Skip", self._finish)
        self.skip_button.pack(side="left")
        self.back_button = ui_theme.styled_button(footer, "Back", self._go_back)
        self.back_button.pack(side="right", padx=(PAD_SM, 0))
        self.next_button = ui_theme.styled_button(footer, "Next", self._go_next, accent=True)
        self.next_button.pack(side="right")

        self._pages = [self._build_welcome_page, self._build_hotkey_page, self._build_first_mode_page]
        self._page_index = 0
        self._mode_name_var = tk.StringVar()
        self._mode_apps_var = tk.StringVar()

        self._render_dots()
        self._render_page()
        self.win.bind("<Escape>", lambda e: self._finish())
        self.win.focus_force()

    # -----------------------------------------------------------------
    def _render_dots(self):
        for child in self.dots_row.winfo_children():
            child.destroy()
        for i in range(len(self._pages)):
            color = ACCENT if i == self._page_index else BG_RAISED
            dot = tk.Label(self.dots_row, text="●", fg=color, bg=BG, font=(ui_theme.FONT_FAMILY, 8))
            dot.pack(side="left", padx=3)

    def _render_page(self):
        for child in self.content.winfo_children():
            child.destroy()
        self._pages[self._page_index]()
        self._render_dots()
        self.back_button.configure(state=("disabled" if self._page_index == 0 else "normal"))
        is_last = self._page_index == len(self._pages) - 1
        self.next_button.configure(text=("Get started" if is_last else "Next"))
        self.skip_button.configure(text=("" if is_last else "Skip"))
        if is_last:
            self.skip_button.pack_forget()
        else:
            self.skip_button.pack(side="left")

    def _go_next(self):
        if self._page_index == len(self._pages) - 1:
            self._create_first_mode_if_filled_in()
            self._finish()
            return
        self._page_index += 1
        self._render_page()

    def _go_back(self):
        if self._page_index > 0:
            self._page_index -= 1
            self._render_page()

    def _finish(self):
        self.config.setdefault("settings", {})["onboarded"] = True
        save_config(self.config)
        self.win.destroy()
        if self._on_done:
            self._on_done()

    # -----------------------------------------------------------------
    def _heading(self, text):
        tk.Label(self.content, text=text, font=self.fonts["title"], bg=BG, fg=FG, anchor="w", justify="left").pack(fill="x", pady=(0, PAD_SM))

    def _body(self, text):
        tk.Label(
            self.content, text=text, font=self.fonts["body"], bg=BG, fg=FG_MUTED,
            anchor="w", justify="left", wraplength=WINDOW_WIDTH - 4 * PAD,
        ).pack(fill="x")

    def _build_welcome_page(self):
        self._heading("Welcome to Isha")
        self._body(
            "A local assistant for Windows — type a command in plain English (or "
            "Hinglish) and it runs. Nothing here ever leaves this machine unless you "
            "explicitly ask it to, e.g. to report an issue."
        )

    def _build_hotkey_page(self):
        hotkey = self.config.get("settings", {}).get("hotkey", "ctrl+alt+space")
        self._heading("Open Isha any time")
        self._body(
            f"Press {hotkey} anywhere to open the command palette, or click the tray "
            "icon. Type \"help\" for a full cheat sheet, and \"undo\" if a command didn't "
            "do what you meant. Destructive actions (shutdown, delete mode, ...) always "
            "ask you to confirm first — nothing risky ever runs silently."
        )

    def _build_first_mode_page(self):
        self._heading("Create your first mode (optional)")
        self._body(
            "Modes are Isha's headline feature — one command opens (or closes) a whole "
            "group of apps and sites together. Give it a name and a few apps now, or "
            "skip and do it later by typing \"create <name> mode <apps>\"."
        )
        form = tk.Frame(self.content, bg=BG)
        form.pack(fill="x", pady=(PAD, 0))
        tk.Label(form, text="Name", font=self.fonts["hint"], bg=BG, fg=FG_MUTED).grid(row=0, column=0, sticky="w")
        tk.Entry(
            form, textvariable=self._mode_name_var, bg=BG_RAISED, fg=FG, relief="flat",
            insertbackground=FG, font=self.fonts["body"],
        ).grid(row=1, column=0, sticky="ew", pady=(2, PAD_SM), ipady=4)
        tk.Label(form, text="Apps (comma-separated)", font=self.fonts["hint"], bg=BG, fg=FG_MUTED).grid(row=2, column=0, sticky="w")
        tk.Entry(
            form, textvariable=self._mode_apps_var, bg=BG_RAISED, fg=FG, relief="flat",
            insertbackground=FG, font=self.fonts["body"],
        ).grid(row=3, column=0, sticky="ew", pady=(2, 0), ipady=4)
        form.columnconfigure(0, weight=1)

    def _create_first_mode_if_filled_in(self):
        name = self._mode_name_var.get().strip()
        apps = self._mode_apps_var.get().strip()
        if not name or not apps:
            return
        from main import process_command_safe
        app_list = " and ".join(a.strip() for a in apps.split(",") if a.strip())
        process_command_safe(f"create {name} mode {app_list}", self.config)
