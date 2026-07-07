"""
Settings window (Track C2) — replaces "edit config.json by hand" for the
handful of things users actually want to change day to day: the mode-scripts
opt-in (Track A1), aliases, snippets, and license status. Everything here
mutates the same config dict the rest of the running app holds a reference
to, then calls config_store.save_config — so a change (e.g. flipping
"allow mode scripts") takes effect immediately, without a restart, exactly
like a typed command would.

Deliberately not a general-purpose config editor: auto-triggers (time,
battery, app-launch) are still config.json-editable only — this covers what
most users touch, not everything that exists. Hotkeys (palette, voice, and
any number of user-bound command hotkeys) are editable here, in the Hotkeys
tab.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import ui_theme
from ui_theme import BG, BG_RAISED, FG, FG_MUTED, PAD, PAD_SM
from config_store import save_config
from version import VERSION

WINDOW_WIDTH = 560
WINDOW_HEIGHT = 460


class SettingsWindow:
    def __init__(self, config: dict, master: tk.Misc):
        self.config = config
        self.win = tk.Toplevel(master)
        self.win.title("Isha — Settings")
        self.win.configure(bg=BG)
        self.win.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.win.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.win.transient(master)

        ui_theme.apply_ttk_theme(self.win)
        self.fonts = ui_theme.fonts()

        outer = tk.Frame(self.win, bg=BG, padx=PAD, pady=PAD)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Settings", font=self.fonts["title"], bg=BG, fg=FG, anchor="w").pack(fill="x", pady=(0, PAD_SM))

        notebook = ttk.Notebook(outer, style="Isha.TNotebook")
        notebook.pack(fill="both", expand=True)

        self._build_general_tab(notebook)
        self._build_hotkeys_tab(notebook)
        self._build_aliases_tab(notebook)
        self._build_snippets_tab(notebook)
        self._build_license_tab(notebook)
        self._build_about_tab(notebook)

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_force()

    # -----------------------------------------------------------------
    def _tab_frame(self, notebook, title):
        frame = tk.Frame(notebook, bg=BG, padx=PAD, pady=PAD)
        notebook.add(frame, text=title)
        return frame

    # -----------------------------------------------------------------
    def _build_general_tab(self, notebook):
        frame = self._tab_frame(notebook, "General")

        settings = self.config.setdefault("settings", {})

        tk.Label(
            frame, text="Hotkeys", font=self.fonts["body_bold"], bg=BG, fg=FG, anchor="w",
        ).pack(fill="x")
        tk.Label(
            frame,
            text=(
                f"Palette: {settings.get('hotkey', 'ctrl+alt+space')}   ·   "
                f"Voice: {settings.get('voice_hotkey', 'ctrl+alt+v')}\n"
                "Rebind these two, and bind hotkeys to any command of your own, "
                "from the \"Hotkeys\" tab."
            ),
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, justify="left", anchor="w", wraplength=WINDOW_WIDTH - 2 * PAD,
        ).pack(fill="x", pady=(2, PAD))

        tk.Label(
            frame, text="Mode scripts", font=self.fonts["body_bold"], bg=BG, fg=FG, anchor="w",
        ).pack(fill="x")
        tk.Label(
            frame,
            text=(
                "A mode's activation script can run any command on your machine. It's off "
                "by default, and even when on, Isha shows you the exact command and asks "
                "before running it — an automatic trigger (time, battery, app-launch, idle) "
                "never runs a script on its own, no matter this setting."
            ),
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, justify="left", anchor="w", wraplength=WINDOW_WIDTH - 2 * PAD,
        ).pack(fill="x", pady=(2, PAD_SM))

        self.allow_scripts_var = tk.BooleanVar(value=bool(settings.get("allow_mode_scripts", False)))
        ttk.Checkbutton(
            frame, text="Allow mode activation scripts (asks every time)",
            variable=self.allow_scripts_var, style="Isha.TCheckbutton",
            command=self._on_toggle_allow_scripts,
        ).pack(fill="x", anchor="w")

    def _on_toggle_allow_scripts(self):
        self.config.setdefault("settings", {})["allow_mode_scripts"] = bool(self.allow_scripts_var.get())
        save_config(self.config)

    # -----------------------------------------------------------------
    def _build_hotkeys_tab(self, notebook):
        """
        Custom command hotkeys — a third, user-defined input path alongside
        typed text and voice: bind any key combo to any command, exactly the
        same command text you'd type into the palette. Bindings are stored in
        config["hotkeys"] (combo -> command text) and registered by
        tray_app.py's MultiHotkeyListener at startup, so a change here needs
        a restart to take effect — same restart requirement as the
        palette/voice hotkeys above, called out explicitly rather than
        silently doing nothing until restart.
        """
        frame = self._tab_frame(notebook, "Hotkeys")

        tk.Label(
            frame,
            text="Bind a key combo to any command, e.g. \"ctrl+alt+m\" → \"activate study mode\".",
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w", wraplength=WINDOW_WIDTH - 2 * PAD,
        ).pack(fill="x", pady=(0, PAD_SM))

        self.hotkey_list = tk.Listbox(
            frame, bg=BG_RAISED, fg=FG, relief="flat", highlightthickness=0,
            selectbackground=ui_theme.ACCENT, font=self.fonts["body"], height=8,
        )
        self.hotkey_list.pack(fill="both", expand=True, pady=(0, PAD_SM))
        self._reload_hotkeys()

        form = tk.Frame(frame, bg=BG)
        form.pack(fill="x")
        self.hotkey_combo_var = tk.StringVar()
        self.hotkey_command_var = tk.StringVar()
        tk.Entry(form, textvariable=self.hotkey_combo_var, bg=BG_RAISED, fg=FG, relief="flat",
                  insertbackground=FG, font=self.fonts["body"], width=16).pack(side="left", padx=(0, PAD_SM), ipady=4)
        tk.Label(form, text="→", bg=BG, fg=FG_MUTED).pack(side="left", padx=(0, PAD_SM))
        tk.Entry(form, textvariable=self.hotkey_command_var, bg=BG_RAISED, fg=FG, relief="flat",
                  insertbackground=FG, font=self.fonts["body"]).pack(side="left", fill="x", expand=True, padx=(0, PAD_SM), ipady=4)
        ui_theme.styled_button(form, "Bind", self._add_hotkey, accent=True).pack(side="left", padx=(0, PAD_SM))
        ui_theme.styled_button(form, "Remove selected", self._remove_hotkey).pack(side="left")

        tk.Label(
            frame, text="Restart Isha for hotkey changes to take effect.",
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w",
        ).pack(fill="x", pady=(PAD_SM, 0))

    def _reload_hotkeys(self):
        self.hotkey_list.delete(0, tk.END)
        settings = self.config.get("settings", {})
        reserved = {settings.get("hotkey", "ctrl+alt+space"), settings.get("voice_hotkey", "ctrl+alt+v")}
        for combo, command_text in sorted(self.config.get("hotkeys", {}).items()):
            note = "  (reserved by palette/voice)" if combo in reserved else ""
            self.hotkey_list.insert(tk.END, f"{combo}  →  {command_text}{note}")

    def _add_hotkey(self):
        from hotkey_listener import parse_hotkey

        combo = self.hotkey_combo_var.get().strip().lower()
        command_text = self.hotkey_command_var.get().strip()
        if not combo or not command_text:
            messagebox.showinfo("Isha", "Enter both a key combo and a command.", parent=self.win)
            return
        try:
            parse_hotkey(combo)
        except ValueError as e:
            messagebox.showinfo("Isha", f"That doesn't look like a valid hotkey ({e}).", parent=self.win)
            return

        settings = self.config.get("settings", {})
        if combo in (settings.get("hotkey", "ctrl+alt+space"), settings.get("voice_hotkey", "ctrl+alt+v")):
            messagebox.showinfo(
                "Isha", "That combo is already used by the palette or voice hotkey — pick another.",
                parent=self.win,
            )
            return

        self.config.setdefault("hotkeys", {})[combo] = command_text
        save_config(self.config)
        self.hotkey_combo_var.set("")
        self.hotkey_command_var.set("")
        self._reload_hotkeys()

    def _remove_hotkey(self):
        selection = self.hotkey_list.curselection()
        if not selection:
            return
        combo = self.hotkey_list.get(selection[0]).split("  →  ")[0]
        self.config.get("hotkeys", {}).pop(combo, None)
        save_config(self.config)
        self._reload_hotkeys()

    # -----------------------------------------------------------------
    def _build_aliases_tab(self, notebook):
        frame = self._tab_frame(notebook, "Aliases")

        tk.Label(
            frame, text="Your own names for apps or sites — e.g. \"browser\" → \"chrome\".",
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w", wraplength=WINDOW_WIDTH - 2 * PAD,
        ).pack(fill="x", pady=(0, PAD_SM))

        self.alias_list = tk.Listbox(
            frame, bg=BG_RAISED, fg=FG, relief="flat", highlightthickness=0,
            selectbackground=ui_theme.ACCENT, font=self.fonts["body"], height=8,
        )
        self.alias_list.pack(fill="both", expand=True, pady=(0, PAD_SM))
        self._reload_aliases()

        form = tk.Frame(frame, bg=BG)
        form.pack(fill="x")
        self.alias_word_var = tk.StringVar()
        self.alias_target_var = tk.StringVar()
        tk.Entry(form, textvariable=self.alias_word_var, bg=BG_RAISED, fg=FG, relief="flat",
                  insertbackground=FG, font=self.fonts["body"], width=14).pack(side="left", padx=(0, PAD_SM), ipady=4)
        tk.Label(form, text="→", bg=BG, fg=FG_MUTED).pack(side="left", padx=(0, PAD_SM))
        tk.Entry(form, textvariable=self.alias_target_var, bg=BG_RAISED, fg=FG, relief="flat",
                  insertbackground=FG, font=self.fonts["body"], width=14).pack(side="left", padx=(0, PAD_SM), ipady=4)
        ui_theme.styled_button(form, "Add", self._add_alias, accent=True).pack(side="left", padx=(0, PAD_SM))
        ui_theme.styled_button(form, "Remove selected", self._remove_alias).pack(side="left")

    def _reload_aliases(self):
        self.alias_list.delete(0, tk.END)
        for word, target in sorted(self.config.get("aliases", {}).items()):
            self.alias_list.insert(tk.END, f"{word}  →  {target}")

    def _add_alias(self):
        word = self.alias_word_var.get().strip().lower()
        target = self.alias_target_var.get().strip().lower()
        if not word or not target:
            messagebox.showinfo("Isha", "Enter both an alias and what it should mean.", parent=self.win)
            return
        self.config.setdefault("aliases", {})[word] = target
        save_config(self.config)
        self.alias_word_var.set("")
        self.alias_target_var.set("")
        self._reload_aliases()

    def _remove_alias(self):
        selection = self.alias_list.curselection()
        if not selection:
            return
        word = self.alias_list.get(selection[0]).split("  →  ")[0]
        self.config.get("aliases", {}).pop(word, None)
        save_config(self.config)
        self._reload_aliases()

    # -----------------------------------------------------------------
    def _build_snippets_tab(self, notebook):
        frame = self._tab_frame(notebook, "Snippets")

        tk.Label(
            frame, text="Short names that expand to longer text (\"expand <name>\").",
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w", wraplength=WINDOW_WIDTH - 2 * PAD,
        ).pack(fill="x", pady=(0, PAD_SM))

        self.snippet_list = tk.Listbox(
            frame, bg=BG_RAISED, fg=FG, relief="flat", highlightthickness=0,
            selectbackground=ui_theme.ACCENT, font=self.fonts["body"], height=6,
        )
        self.snippet_list.pack(fill="both", expand=True, pady=(0, PAD_SM))
        self._reload_snippets()

        form = tk.Frame(frame, bg=BG)
        form.pack(fill="x")
        self.snippet_name_var = tk.StringVar()
        tk.Entry(form, textvariable=self.snippet_name_var, bg=BG_RAISED, fg=FG, relief="flat",
                  insertbackground=FG, font=self.fonts["body"], width=14).pack(side="left", padx=(0, PAD_SM), ipady=4)
        self.snippet_text_var = tk.StringVar()
        tk.Entry(form, textvariable=self.snippet_text_var, bg=BG_RAISED, fg=FG, relief="flat",
                  insertbackground=FG, font=self.fonts["body"]).pack(side="left", fill="x", expand=True, padx=(0, PAD_SM), ipady=4)
        ui_theme.styled_button(form, "Add", self._add_snippet, accent=True).pack(side="left", padx=(0, PAD_SM))
        ui_theme.styled_button(form, "Remove selected", self._remove_snippet).pack(side="left")

    def _reload_snippets(self):
        self.snippet_list.delete(0, tk.END)
        for name, text in sorted(self.config.get("snippets", {}).items()):
            preview = text if len(text) <= 40 else text[:37] + "..."
            self.snippet_list.insert(tk.END, f"{name}  →  {preview}")

    def _add_snippet(self):
        name = self.snippet_name_var.get().strip().lower()
        text = self.snippet_text_var.get()
        if not name or not text:
            messagebox.showinfo("Isha", "Enter both a snippet name and its expansion text.", parent=self.win)
            return
        self.config.setdefault("snippets", {})[name] = text
        save_config(self.config)
        self.snippet_name_var.set("")
        self.snippet_text_var.set("")
        self._reload_snippets()

    def _remove_snippet(self):
        selection = self.snippet_list.curselection()
        if not selection:
            return
        name = self.snippet_list.get(selection[0]).split("  →  ")[0]
        self.config.get("snippets", {}).pop(name, None)
        save_config(self.config)
        self._reload_snippets()

    # -----------------------------------------------------------------
    def _build_license_tab(self, notebook):
        frame = self._tab_frame(notebook, "License")
        import a_licensing

        self.license_status_label = tk.Label(
            frame, text="", font=self.fonts["body"], bg=BG, fg=FG, anchor="w",
            justify="left", wraplength=WINDOW_WIDTH - 2 * PAD,
        )
        self.license_status_label.pack(fill="x", pady=(0, PAD))
        self._refresh_license_status()

        tk.Label(frame, text="Activate a new key", font=self.fonts["body_bold"], bg=BG, fg=FG, anchor="w").pack(fill="x")
        form = tk.Frame(frame, bg=BG)
        form.pack(fill="x", pady=(PAD_SM, PAD_SM))
        self.license_key_var = tk.StringVar()
        tk.Entry(form, textvariable=self.license_key_var, bg=BG_RAISED, fg=FG, relief="flat",
                  insertbackground=FG, font=self.fonts["body"]).pack(side="left", fill="x", expand=True, padx=(0, PAD_SM), ipady=4)
        ui_theme.styled_button(form, "Activate", self._activate_license, accent=True).pack(side="left")

        ui_theme.styled_button(frame, "Deactivate this device", self._deactivate_license).pack(anchor="w")

        tk.Label(
            frame,
            text=(
                "Isha works fully either way — licensing just supports continued development. "
                "A license key activates on one device at a time; use \"Deactivate this device\" "
                "before activating it on another machine."
            ),
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w", wraplength=WINDOW_WIDTH - 2 * PAD,
        ).pack(fill="x", pady=(PAD, 0))

    def _refresh_license_status(self):
        import a_licensing
        result = a_licensing.get_license_status(self.config)
        self.license_status_label.configure(
            text=result.message,
            fg=(ui_theme.SUCCESS if result.data.get("licensed") else FG_MUTED),
        )

    def _activate_license(self):
        import a_licensing
        key = self.license_key_var.get().strip()
        if not key:
            return
        result = a_licensing.activate_license(self.config, key)
        messagebox.showinfo("Isha — license", result.message, parent=self.win)
        if result.success:
            self.license_key_var.set("")
        self._refresh_license_status()

    def _deactivate_license(self):
        import a_licensing
        result = a_licensing.deactivate_license(self.config)
        messagebox.showinfo("Isha — license", result.message, parent=self.win)
        self._refresh_license_status()

    # -----------------------------------------------------------------
    def _build_about_tab(self, notebook):
        frame = self._tab_frame(notebook, "About")
        tk.Label(
            frame, text=f"Isha v{VERSION}", font=self.fonts["body_bold"], bg=BG, fg=FG, anchor="w",
        ).pack(fill="x", pady=(0, PAD_SM))
        tk.Label(
            frame,
            text=(
                "A local Windows assistant. Nothing leaves this machine unless you "
                "explicitly ask to report an issue or check for updates — see "
                "THREAT_MODEL.md in the install folder for exactly what that promise "
                "does and doesn't cover."
            ),
            font=self.fonts["hint"], bg=BG, fg=FG_MUTED, justify="left", anchor="w",
            wraplength=WINDOW_WIDTH - 2 * PAD,
        ).pack(fill="x")
