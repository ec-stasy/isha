"""
"Shizuka" design system — the single source of visual truth for every Qt
surface (NEW_VERSION_ROADMAP.md §2). Two themes, same design at two
temperatures: "washi" (warm paper white) and "yoru" (deep warm black, brown
undertone — deliberately not blue-slate, not metallic). One sakura accent,
used sparingly. Anything not expressible in these tokens is out of scope by
definition.
"""

LIGHT = {
    "bg": "#F7F3EC",
    "bg_raised": "#FFFDF8",
    "bg_hover": "#EFE9DF",
    "border": "#E3DCCF",
    "fg": "#3A332C",
    "fg_muted": "#8A8177",
    "fg_faint": "#B5AC9F",
    "accent": "#C9748A",
    "accent_hover": "#B96379",
    "accent_soft": "#F2DEE4",
    "accent_text": "#FFFFFF",
    "branch": "rgba(74, 64, 56, 0.18)",
    "success": "#7BA886",
    "warning": "#D9A662",
    "error": "#C97B74",
    "shadow": "rgba(0, 0, 0, 0.06)",
    "scrollbar": "rgba(58, 51, 44, 0.25)",
}

DARK = {
    "bg": "#171412",
    "bg_raised": "#201C19",
    "bg_hover": "#2A2521",
    "border": "#332D28",
    "fg": "#EDE7DE",
    "fg_muted": "#9C948A",
    "fg_faint": "#6B645C",
    "accent": "#D98BA0",
    "accent_hover": "#E29FB1",
    "accent_soft": "#3D2E33",
    "accent_text": "#241418",
    "branch": "rgba(237, 231, 222, 0.10)",
    "success": "#8CBB97",
    "warning": "#E4B677",
    "error": "#D68D86",
    "shadow": "rgba(0, 0, 0, 0.30)",
    "scrollbar": "rgba(237, 231, 222, 0.22)",
}

FONT_FAMILY = '"Segoe UI Variable Display", "Segoe UI", sans-serif'
FONT_MONO = '"Cascadia Mono", "Consolas", monospace'

# type scale (pt) and spacing grid (px)
SIZE_TITLE = 17
SIZE_SUBTITLE = 12
SIZE_BODY = 10.5
SIZE_SECONDARY = 9.5
SIZE_HINT = 9

PAD = 16
PAD_SM = 8
PAD_LG = 24

RADIUS_CARD = 10
RADIUS_BUTTON = 8
RADIUS_OVERLAY = 14

MOTION_MS = 180  # 150–200 ms ease-out everywhere; ui.reduce_motion disables


def palette(theme: str) -> dict:
    return DARK if theme == "dark" else LIGHT


def resolve_theme(setting: str) -> str:
    """Maps the ui.theme setting ('auto'|'light'|'dark') to a concrete theme,
    following Windows' AppsUseLightTheme for 'auto'."""
    if setting in ("light", "dark"):
        return setting
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if light else "dark"
    except OSError:
        return "dark"


def build_qss(theme: str) -> str:
    """Fills design/theme.qss's $placeholders with the theme's tokens.
    ($-substitution, not str.format — QSS is full of literal braces.)"""
    from pathlib import Path
    from string import Template
    template = (Path(__file__).parent / "theme.qss").read_text(encoding="utf-8")
    tokens = dict(palette(theme))
    tokens.update({
        "font_family": FONT_FAMILY,
        "font_mono": FONT_MONO,
        "size_title": SIZE_TITLE,
        "size_subtitle": SIZE_SUBTITLE,
        "size_body": SIZE_BODY,
        "size_secondary": SIZE_SECONDARY,
        "size_hint": SIZE_HINT,
        "radius_card": RADIUS_CARD,
        "radius_button": RADIUS_BUTTON,
        "radius_overlay": RADIUS_OVERLAY,
        "pad": PAD,
        "pad_sm": PAD_SM,
        "pad_lg": PAD_LG,
    })
    return Template(template).substitute({k: str(v) for k, v in tokens.items()})
