from urllib.parse import quote, urlparse

from app_registry import get_app_registry
from command_ir import CommandIR

try:
    from rapidfuzz import fuzz
    _score = lambda a, b: fuzz.WRatio(a, b)
except ImportError:
    # dev/CI fallback so resolution logic works without the rapidfuzz dependency installed
    from difflib import SequenceMatcher
    _score = lambda a, b: SequenceMatcher(None, a, b).ratio() * 100

FUZZY_MATCH_THRESHOLD = 75  # below this, guessing which app the user meant is a security/UX risk — ask instead

# small built-in set of common websites; user aliases (config["aliases"]) are merged on top
DEFAULT_URL_TARGETS = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "maps": "https://maps.google.com",
}

# actions whose target names apps (resolved against the app registry)
APP_TARGET_ACTIONS = {
    "open_app", "close_app", "uninstall_app",
    "focus_window", "maximize_window", "minimize_window",
    "show_window", "hide_window", "snap_window", "resize_window", "move_window",
}

MODE_LOOKUP_ACTIONS = {"activate_mode", "deactivate_mode", "delete_mode"}
MODE_APP_LIST_ACTIONS = {"create_mode", "update_mode"}
MODE_FIELD_ACTIONS = {"set_mode_script", "set_mode_volume", "set_mode_theme", "capture_mode_layout"}

# actions that change system/user state in a way that's hard or impossible to undo,
# plus (Phase 5) actions that send data off the machine or run a downloaded
# installer — not "destructive" to local state, but risky enough to need the
# same explicit yes/no gate rather than firing silently
DESTRUCTIVE_ACTIONS = {
    "shutdown", "restart", "hibernate", "uninstall_app", "delete_mode", "empty_recycle_bin",
    "send_report", "apply_update",
}

ALLOWED_URL_SCHEMES = {"http", "https"}


def _best_match(name: str, candidates: dict):
    """Returns (matched_key, score) for the best fuzzy match, or (None, 0) if candidates is empty."""
    if not name or not candidates:
        return None, 0
    best_key, best_score = None, 0
    for key in candidates:
        score = _score(name, key)
        if score > best_score:
            best_key, best_score = key, score
    return best_key, best_score


def _top_candidates(name: str, candidates: dict, n: int = 3) -> list:
    scored = sorted(candidates.keys(), key=lambda k: _score(name, k), reverse=True)
    return scored[:n]


def _resolve_app_target(ir: CommandIR, app_registry: dict, aliases: dict) -> None:
    if not ir.target:
        return

    raw = str(ir.target).lower()
    alias_target = aliases.get(raw, raw)

    match_key, score = _best_match(alias_target, app_registry)

    if match_key and score >= FUZZY_MATCH_THRESHOLD:
        ir.target = dict(app_registry[match_key])
    else:
        candidates = _top_candidates(alias_target, app_registry)
        if candidates:
            ir.warnings.append(
                f"Couldn't confidently match '{ir.target}' to an installed app. "
                f"Did you mean: {', '.join(candidates)}?"
            )
        else:
            ir.errors.append(f"No installed app found matching '{ir.target}'.")


def _resolve_url_target(ir: CommandIR, aliases: dict) -> None:
    if not ir.target:
        return

    raw = str(ir.target).strip().lower()
    known_urls = {**DEFAULT_URL_TARGETS, **{k: v for k, v in aliases.items() if str(v).startswith("http")}}

    if raw in known_urls:
        url = known_urls[raw]
    elif ir.action == "search":
        # free text with no dedicated site match -> treat as a search query
        url = f"https://www.google.com/search?q={quote(str(ir.target))}"
    elif "." in raw and " " not in raw:
        # looks like a bare domain, e.g. "example.com"
        url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
    else:
        match_key, score = _best_match(raw, known_urls)
        if match_key and score >= FUZZY_MATCH_THRESHOLD:
            url = known_urls[match_key]
        else:
            # fall back to a search rather than refusing outright
            url = f"https://www.google.com/search?q={quote(str(ir.target))}"

    scheme = urlparse(url).scheme
    if scheme not in ALLOWED_URL_SCHEMES:
        ir.errors.append(f"Refusing to open URL with disallowed scheme '{scheme}'.")
        return

    ir.target = url


def _resolve_mode_lookup(ir: CommandIR, modes: dict) -> None:
    if not ir.target:
        return
    name = str(ir.target).lower()
    if name not in modes:
        ir.errors.append(f"No mode named '{ir.target}' exists.")


def _looks_like_website(raw: str, aliases: dict) -> bool:
    raw = raw.lower()
    if raw in DEFAULT_URL_TARGETS:
        return True
    if raw in aliases and str(aliases[raw]).startswith(("http://", "https://")):
        return True
    return raw.startswith(("http://", "https://")) or ("." in raw and " " not in raw)


def _resolve_mode_website_item(raw_name: str, aliases: dict) -> dict:
    """Mixed apps/websites in one mode app list — Modes 2.0's 'launch apps and
    websites' with no new parser syntax: anything that looks like a URL/domain
    is classified as a website item instead of an (unresolvable) app."""
    raw = str(raw_name).lower()
    known_urls = {**DEFAULT_URL_TARGETS, **{k: v for k, v in aliases.items() if str(v).startswith("http")}}
    if raw in known_urls:
        url = known_urls[raw]
    elif raw.startswith(("http://", "https://")):
        url = raw
    else:
        url = f"https://{raw}"
    return {"type": "website", "name": raw_name, "url": url}


def _resolve_mode_app_list(ir: CommandIR, app_registry: dict, aliases: dict) -> None:
    for param_key in ("new", "add", "remove"):
        names = ir.params.get(param_key)
        if not names:
            continue
        resolved = []
        unresolved = []
        for raw_name in names:
            raw_str = str(raw_name)
            if _looks_like_website(raw_str, aliases):
                resolved.append(_resolve_mode_website_item(raw_name, aliases))
                continue

            alias_name = aliases.get(raw_str.lower(), raw_str.lower())
            match_key, score = _best_match(alias_name, app_registry)
            if match_key and score >= FUZZY_MATCH_THRESHOLD:
                resolved.append({"type": "app", **app_registry[match_key]})
            else:
                # keep the raw name — apps can be installed after the mode is created,
                # so re-resolve at activation time instead of failing now
                resolved.append({"type": "app", "name": raw_name, "path": None})
                unresolved.append(raw_name)
        ir.params[param_key] = resolved
        if unresolved:
            ir.warnings.append(
                f"Couldn't resolve these apps yet (will retry when the mode runs): {', '.join(unresolved)}"
            )


def resolve(ir: CommandIR, config: dict = None) -> CommandIR:
    """
    Turns the parser's free-text target into something the executor can act on:
    an installed app's path, a validated URL, or a checked mode reference.
    Ambiguous matches become warnings (disambiguate) rather than guesses —
    silently launching the wrong binary is a security risk, not just a UX one.
    """
    config = config or {}
    aliases = config.get("aliases", {})
    modes = config.get("modes", {})

    if ir.errors:
        # parser already flagged this command as unactionable; don't do more work
        return ir

    if ir.action == "open_app" and ir.target and str(ir.target).lower() in (config.get("scripts") or {}):
        # F6: "run backup" — an exact saved-script name wins over app fuzzy
        # matching (exact only, so no app can be shadowed by accident)
        ir.action = "run_script"
        ir.target = str(ir.target).lower()
    elif ir.action in APP_TARGET_ACTIONS:
        _resolve_app_target(ir, get_app_registry(), aliases)
    elif ir.action in ("open_url", "search"):
        _resolve_url_target(ir, aliases)
    elif ir.action in MODE_LOOKUP_ACTIONS:
        _resolve_mode_lookup(ir, modes)
    elif ir.action in MODE_APP_LIST_ACTIONS:
        _resolve_mode_app_list(ir, get_app_registry(), aliases)
        if ir.action == "update_mode" and ir.target and str(ir.target).lower() not in modes:
            ir.errors.append(f"No mode named '{ir.target}' exists to update.")
    elif ir.action in MODE_FIELD_ACTIONS:
        _resolve_mode_lookup(ir, modes)

    return ir


# actions that act on a 0-100 level and may arrive without one (F2)
LEVELED_ACTIONS = {"set_value"}


def validate(ir: CommandIR, config: dict = None) -> CommandIR:
    """Semantic sanity checks on the resolved CommandIR, plus a safety gate for destructive actions."""
    level = ir.params.get("level")
    if isinstance(level, int) and not (0 <= level <= 100):
        ir.warnings.append(f"Level {level} is outside the expected 0-100 range; it will be clamped.")
        ir.params["level"] = max(0, min(100, level))

    # F2: a leveled action with no level gets the user's configured default
    # instead of erroring out
    if ir.action in LEVELED_ACTIONS and ir.params.get("level") is None:
        settings = (config or {}).get("settings", {}) or {}
        default_level = (settings.get("defaults", {}) or {}).get("level", 50)
        try:
            default_level = max(0, min(100, int(default_level)))
        except (TypeError, ValueError):
            default_level = 50
        ir.params["level"] = default_level
        ir.warnings = [w for w in ir.warnings if w != "No Level Found!"]
        ir.warnings.append(
            f"No level given — using your default ({default_level}). "
            f"Say e.g. '{str(ir.target or 'volume')} 70' for a specific level.")

    if ir.action in DESTRUCTIVE_ACTIONS:
        ir.params["requires_confirmation"] = True

    return ir


def resolve_and_validate(ir: CommandIR, config: dict = None) -> CommandIR:
    ir = resolve(ir, config)
    ir = validate(ir, config)
    return ir
