"""
Shared visual language for every Tkinter surface Isha shows (command palette,
settings window, onboarding wizard) — one small module so they read as one
calm, coherent app instead of three windows that happen to share a codebase.

Design intent: calm, simple, unhurried. Muted slate background instead of
near-black, a single soft accent color used sparingly, generous padding, and
one type scale reused everywhere rather than every window inventing its own.
Nothing here changes the accessibility guarantees command_palette.py already
documents (high contrast, large default font, keyboard-only nav, plain-
sentence output) — this only makes the existing choices consistent.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# Slate, not near-black — reads as calm rather than "terminal at 2am", while
# keeping contrast well above WCAG AA for body text.
BG = "#191c22"
BG_RAISED = "#21252d"       # cards / entry fields / anything "above" the base
BG_HOVER = "#2a2f3a"
BORDER = "#333947"

FG = "#eceef2"              # primary text
FG_MUTED = "#9aa0ad"        # secondary text / hints
FG_FAINT = "#6b7280"        # tertiary / disabled

ACCENT = "#5b8def"          # single accent color, used sparingly (focus rings, primary actions)
ACCENT_HOVER = "#7aa4f2"

SUCCESS = "#6fcf97"
ERROR = "#e8798a"
WARNING = "#e8b969"

FONT_FAMILY = "Segoe UI"

PAD = 14      # base spacing unit — every window's padding is a multiple of this
PAD_SM = 8
RADIUS_NOTE = "Tkinter has no native rounded corners without a canvas hack; flat, generously-padded panels read calm enough without one."


def fonts():
    """Fresh Font objects — must be created after a Tk root exists."""
    return {
        "title": tkfont.Font(family=FONT_FAMILY, size=15, weight="bold"),
        "body": tkfont.Font(family=FONT_FAMILY, size=11),
        "body_bold": tkfont.Font(family=FONT_FAMILY, size=11, weight="bold"),
        "hint": tkfont.Font(family=FONT_FAMILY, size=10),
        "entry": tkfont.Font(family=FONT_FAMILY, size=15),
        "mono": tkfont.Font(family="Consolas", size=10),
    }


def apply_ttk_theme(root: tk.Misc) -> None:
    """Restyles ttk widgets (Notebook, Buttons, Entry, Checkbutton) to match
    the palette above — ttk ignores plain tk options, so this is the only
    way to keep e.g. a Notebook's tabs from looking like a stock gray dialog."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # the one built-in ttk theme that fully honors custom colors
    except tk.TclError:
        pass

    style.configure("Isha.TFrame", background=BG)
    style.configure("IshaCard.TFrame", background=BG_RAISED)

    style.configure(
        "Isha.TNotebook", background=BG, borderwidth=0, tabmargins=[0, PAD_SM, 0, 0],
    )
    style.configure(
        "Isha.TNotebook.Tab", background=BG, foreground=FG_MUTED,
        padding=[PAD, PAD_SM], borderwidth=0, font=(FONT_FAMILY, 10),
    )
    style.map(
        "Isha.TNotebook.Tab",
        background=[("selected", BG_RAISED)],
        foreground=[("selected", FG)],
    )

    style.configure(
        "Isha.TButton", background=BG_RAISED, foreground=FG, borderwidth=0,
        focusthickness=2, focuscolor=ACCENT, padding=[PAD, PAD_SM], font=(FONT_FAMILY, 10),
    )
    style.map("Isha.TButton", background=[("active", BG_HOVER)])

    style.configure(
        "IshaAccent.TButton", background=ACCENT, foreground="#0c1220", borderwidth=0,
        focusthickness=2, focuscolor=ACCENT_HOVER, padding=[PAD, PAD_SM], font=(FONT_FAMILY, 10, "bold"),
    )
    style.map("IshaAccent.TButton", background=[("active", ACCENT_HOVER)])

    style.configure(
        "Isha.TCheckbutton", background=BG, foreground=FG, font=(FONT_FAMILY, 11),
    )
    style.map("Isha.TCheckbutton", background=[("active", BG)])

    style.configure("Isha.TEntry", fieldbackground=BG_RAISED, foreground=FG, borderwidth=0, insertcolor=FG)


def styled_button(parent, text, command, accent=False, **kw):
    return ttk.Button(parent, text=text, command=command, style="IshaAccent.TButton" if accent else "Isha.TButton", **kw)


def section_label(parent, text, font):
    return tk.Label(parent, text=text, font=font, bg=BG, fg=FG_MUTED, anchor="w")


def card(parent, **kw):
    frame = tk.Frame(parent, bg=BG_RAISED, highlightthickness=1, highlightbackground=BORDER, **kw)
    return frame
