"""
Spotlight-style command palette: a small, borderless, always-on-top window
with one text entry. Typed text runs through the exact same pipeline as the
CLI (main.process_command_safe) — one brain, three input paths, per the
roadmap's accessibility principle.

Accessibility choices (deliberate, not decoration):
 - Keyboard-only: Enter submits, Escape closes, Tab reaches every control.
 - High-contrast palette (light and dark variants) with a large default font,
   so it's usable without perfect vision and doesn't rely on color alone.
 - Every widget has a text label; results are plain sentences (ExecutionResult
   messages are already written to be screen-reader-friendly), not icons.
 - Nothing here auto-confirms destructive actions — the executor's
   confirmation gate applies identically to palette input as to the CLI.
"""
import tkinter as tk
from tkinter import messagebox

from config_store import save_config
from main import process_command_safe
import ui_theme
from ui_theme import BG, BG_RAISED, BORDER, FG, FG_MUTED, ACCENT, SUCCESS, ERROR, WARNING, PAD, PAD_SM

WINDOW_WIDTH = 640


class CommandPalette:
    def __init__(self, config: dict, on_close=None, on_open_settings=None, on_open_dashboard=None):
        self.config = config
        self._on_close = on_close
        self._on_open_settings = on_open_settings
        self._on_open_dashboard = on_open_dashboard

        self.root = tk.Tk()
        self.root.title("Isha — Command Palette")
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)  # borderless, Spotlight-style
        self.root.attributes("-topmost", True)
        self.root.withdraw()  # hidden until show()

        ui_theme.apply_ttk_theme(self.root)
        fonts = ui_theme.fonts()

        outer = tk.Frame(self.root, bg=BG, padx=PAD, pady=PAD)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x", pady=(0, PAD_SM))
        tk.Label(header, text="Isha", font=fonts["title"], bg=BG, fg=FG, anchor="w").pack(side="left")
        if self._on_open_settings:
            ui_theme.styled_button(header, "⚙ Settings", self._on_open_settings).pack(side="right")
        if self._on_open_dashboard:
            ui_theme.styled_button(header, "Dashboard", self._on_open_dashboard).pack(side="right", padx=(0, PAD_SM))

        self.hint_label = tk.Label(
            outer, text="Type a command · Enter to run · Esc to close",
            font=fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w",
        )
        self.hint_label.pack(fill="x")

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            outer, textvariable=self.entry_var, font=fonts["entry"],
            bg=BG_RAISED, fg=FG, insertbackground=FG,
            relief="flat", highlightthickness=2,
            highlightbackground=BORDER, highlightcolor=ACCENT,
        )
        self.entry.pack(fill="x", ipady=10, pady=(PAD_SM, PAD_SM))

        self.suggestion_label = tk.Label(
            outer, text="", font=fonts["hint"], bg=BG, fg=FG_MUTED, anchor="w",
        )
        self.suggestion_label.pack(fill="x")

        self.output_card = ui_theme.card(outer, padx=PAD_SM, pady=PAD_SM)
        self.output = tk.Label(
            self.output_card, text="", font=fonts["body"], bg=BG_RAISED, fg=FG,
            anchor="w", justify="left", wraplength=WINDOW_WIDTH - 32 - 2 * PAD,
        )
        self.output.pack(fill="x")
        # not packed until there's something to show — an empty card is just visual noise

        self.entry.bind("<Return>", self._on_submit)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, _event) -> None:
        # Deliberately a no-op, not "close on focus loss": <FocusOut> also
        # fires when the confirmation messagebox (a child Toplevel parented
        # to this window) takes focus, which would otherwise hide the palette
        # out from under an in-progress yes/no prompt. Escape remains the
        # reliable, always-available way to close the palette.
        pass

    def _confirm_dialog(self, resolved_ir) -> bool:
        if resolved_ir.action == "run_mode_script":
            return messagebox.askyesno(
                "Isha — confirm mode script",
                f"Isha is about to run this mode script:\n\n{resolved_ir.target}\n\nAllow?",
                parent=self.root,
            )
        name = resolved_ir.target if isinstance(resolved_ir.target, str) else (resolved_ir.target or {}).get("name") or resolved_ir.action
        return messagebox.askyesno(
            "Isha — confirm",
            f"'{resolved_ir.action}' on '{name}' can't be easily undone. Proceed?",
            parent=self.root,
        )

    def _on_submit(self, _event=None) -> None:
        text = self.entry_var.get().strip()
        if not text:
            return

        outcomes = process_command_safe(text, self.config, confirm_callback=self._confirm_dialog)
        self._render_outcomes(outcomes)
        self.entry_var.set("")
        self.suggestion_label.configure(text="")

    def _on_key_release(self, event) -> None:
        # Enter/Escape are handled by their own bindings; live suggestions
        # would just be noise for them.
        if event.keysym in ("Return", "Escape"):
            return
        text = self.entry_var.get().strip()
        last_word = text.split()[-1].lower() if text else ""
        if len(last_word) < 2:
            self.suggestion_label.configure(text="")
            return

        matches = self._suggest(last_word)
        self.suggestion_label.configure(text=("did you mean: " + ", ".join(matches)) if matches else "")

    def _suggest(self, prefix: str, limit: int = 5) -> list:
        """Cheap, local "did you mean" / autocomplete hint — installed app names
        and existing mode names, no network, no heavy matching (registry is
        already disk-cached, mode list is tiny)."""
        try:
            from app_registry import get_app_registry
            candidates = set(get_app_registry().keys()) | set(self.config.get("modes", {}).keys())
        except Exception:
            candidates = set(self.config.get("modes", {}).keys())

        starts_with = sorted(c for c in candidates if c.startswith(prefix))
        if len(starts_with) >= limit:
            return starts_with[:limit]

        contains = sorted(c for c in candidates if prefix in c and c not in starts_with)
        return (starts_with + contains)[:limit]

    def _render_outcomes(self, outcomes: list) -> None:
        lines = []
        for outcome in outcomes:
            result = outcome["result"]
            mark = "✓" if result.success else "✕"
            lines.append(f"{mark}  {result.message}")
            for warning in outcome["warnings"]:
                lines.append(f"   ⚠ {warning}")

        self._show_output("\n".join(lines) if lines else "Nothing happened.",
                           fg=(ERROR if any(not o["result"].success for o in outcomes) else FG))

    def _show_output(self, text: str, fg=FG) -> None:
        self.output.configure(text=text, fg=fg)
        self.output_card.pack(fill="x", pady=(PAD_SM, 0))

    def show(self) -> None:
        self.root.deiconify()
        self._center()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.entry.focus_force()
        self._show_onboarding_if_first_run()

    def _show_onboarding_if_first_run(self) -> None:
        if self.config.get("settings", {}).get("onboarded"):
            return
        self._show_output(
            "Welcome to Isha. Type a command in plain English — e.g. \"open chrome\" or "
            "\"create study mode chrome and youtube\". \"help\" shows the full cheat sheet; "
            "\"undo\" reverses your last action. Destructive actions always ask first.",
            fg=FG,
        )
        self.config.setdefault("settings", {})["onboarded"] = True
        save_config(self.config)

    def hide(self) -> None:
        self.root.withdraw()
        self.output_card.pack_forget()
        if self._on_close:
            self._on_close()

    def _center(self) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        height = self.root.winfo_reqheight()
        x = (screen_w - WINDOW_WIDTH) // 2
        y = screen_h // 4
        self.root.geometry(f"{WINDOW_WIDTH}x{height}+{x}+{y}")

    def destroy(self) -> None:
        self.root.destroy()
