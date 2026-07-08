import os
from urllib.parse import quote, urlparse

from app_registry import get_app_registry, curated_apps
from command_ir import CommandIR

try:
    from rapidfuzz import fuzz
    _HAVE_RAPIDFUZZ = True
except ImportError:
    _HAVE_RAPIDFUZZ = False
    from difflib import SequenceMatcher

FUZZY_MATCH_THRESHOLD = 75  # below this, guessing which app the user meant is a security/UX risk — ask instead

# Common websites launchable by bare name ("open wikipedia") — Cycle 6 A5.
# User aliases (config["aliases"]) are merged on top and win.
DEFAULT_URL_TARGETS = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "maps": "https://maps.google.com",
    "wikipedia": "https://www.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "spotify": "https://open.spotify.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "translate": "https://translate.google.com",
    "pinterest": "https://www.pinterest.com",
    "twitch": "https://www.twitch.tv",
    "telegram": "https://web.telegram.org",
    "outlook": "https://outlook.live.com",
    "canva": "https://www.canva.com",
    "notion": "https://www.notion.so",
}

# Cycle 6 A3 — core Windows utilities. These are *not* files on disk (URIs,
# shell folders) or live in system32; they resolve before any fuzzy app
# matching and launch via os.startfile / PATH, never through the file-trust
# check. Keys are the canonical name; SYSTEM_UTILITY_SYNONYMS maps what users
# actually say onto them.
def _windir(*parts) -> str:
    return os.path.join(os.environ.get("WINDIR", r"C:\Windows"), *parts)


SYSTEM_UTILITIES = {
    "settings": {"uri": "ms-settings:"},
    "camera": {"uri": "microsoft.windows.camera:"},
    "recycle bin": {"uri": "shell:RecycleBinFolder"},
    "file explorer": {"path": _windir("explorer.exe")},
    "calculator": {"uri": "calculator:"},
    "task manager": {"path": _windir("System32", "Taskmgr.exe")},
    "control panel": {"path": _windir("System32", "control.exe")},
    "command prompt": {"path": _windir("System32", "cmd.exe")},
    "powershell": {"path": _windir("System32", "WindowsPowerShell", "v1.0", "powershell.exe")},
    "terminal": {"exe": "wt.exe"},
    "notepad": {"exe": "notepad.exe"},
    "paint": {"path": _windir("System32", "mspaint.exe")},
    "snipping tool": {"uri": "ms-screenclip:"},
    "downloads": {"uri": "shell:Downloads"},
    "documents": {"uri": "shell:Personal"},
    "pictures": {"uri": "shell:My Pictures"},
    "this pc": {"uri": "shell:MyComputerFolder"},
    "microsoft store": {"uri": "ms-windows-store:"},
    "photos": {"uri": "ms-photos:"},
    "clock": {"uri": "ms-clock:"},
    "bluetooth settings": {"uri": "ms-settings:bluetooth"},
    "wifi settings": {"uri": "ms-settings:network-wifi"},
    "display settings": {"uri": "ms-settings:display"},
    "sound settings": {"uri": "ms-settings:sound"},
}

SYSTEM_UTILITY_SYNONYMS = {
    "windows settings": "settings",
    "setting": "settings",
    "system settings": "settings",
    "recyclebin": "recycle bin",
    "trash": "recycle bin",
    "dustbin": "recycle bin",
    "explorer": "file explorer",
    "files": "file explorer",
    "my computer": "this pc",
    "computer": "this pc",
    "calc": "calculator",
    "taskmanager": "task manager",
    "cmd": "command prompt",
    "store": "microsoft store",
    "app store": "microsoft store",
    "alarms": "clock",
    "screen clip": "snipping tool",
    "screen snip": "snipping tool",
    "downloads folder": "downloads",
}

# common shorthand for installed apps — tried as extra query variants before
# fuzzy matching, so "open vs code" finds the App Paths "code" entry (A1)
BUILTIN_APP_ALIASES = {
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "google chrome": "chrome",
    "ms word": "winword",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "edge": "msedge",
    "microsoft edge": "msedge",
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
# (delete_last_screenshot is deliberately NOT here: it moves the file to the
# Recycle Bin, so it's recoverable — a confirmation would be friction, not safety)
DESTRUCTIVE_ACTIONS = {
    "shutdown", "restart", "hibernate", "uninstall_app", "delete_mode", "empty_recycle_bin",
    "send_report", "apply_update",
}

ALLOWED_URL_SCHEMES = {"http", "https"}


# ---------------------------------------------------------------------------
# scoring (Cycle 6 A1) — the old bare-WRatio scorer let 2-letter PATH stubs
# ("od", "at", "ex") outrank real app names via partial-match inflation.

def _full_ratio(a: str, b: str) -> float:
    if _HAVE_RAPIDFUZZ:
        return fuzz.ratio(a, b)
    return SequenceMatcher(None, a, b).ratio() * 100


def _token_ratio(a: str, b: str) -> float:
    if _HAVE_RAPIDFUZZ:
        return fuzz.token_set_ratio(a, b)
    a_sorted = " ".join(sorted(a.split()))
    b_sorted = " ".join(sorted(b.split()))
    return SequenceMatcher(None, a_sorted, b_sorted).ratio() * 100


def _app_score(query: str, key: str) -> float:
    """0-100 confidence that registry entry `key` is what `query` means."""
    q = query.strip().lower()
    k = key.strip().lower()
    if not q or not k:
        return 0
    if q == k:
        return 100
    q_ns, k_ns = q.replace(" ", ""), k.replace(" ", "")
    if q_ns == k_ns:
        return 100
    # short-name guard: tiny names ("od", "at", "ex") only ever match exactly
    if len(k_ns) <= 3 or len(q_ns) <= 2:
        return 0
    # containment (either direction) with real length is a strong signal:
    # "chrome" in "google chrome", "notepad" in "notepad++"
    if len(q_ns) >= 4 and (q_ns in k_ns or k_ns in q_ns):
        return 90
    return 0.55 * _token_ratio(q, k) + 0.45 * _full_ratio(q, k)


def _best_match(name: str, candidates: dict):
    """Returns (matched_key, score) for the best fuzzy match, or (None, 0) if candidates is empty."""
    if not name or not candidates:
        return None, 0
    best_key, best_score = None, 0
    for key in candidates:
        score = _app_score(name, key)
        if score > best_score:
            best_key, best_score = key, score
    return best_key, best_score


def _top_candidates(name: str, candidates: dict, n: int = 3) -> list:
    scored = sorted(candidates.keys(), key=lambda k: _app_score(name, k), reverse=True)
    return [k for k in scored[:n] if _app_score(name, k) > 30]


def _match_system_utility(raw: str):
    """Exact/synonym match against the curated utilities table (A3)."""
    name = SYSTEM_UTILITY_SYNONYMS.get(raw, raw)
    entry = SYSTEM_UTILITIES.get(name)
    if entry is not None:
        return {"name": name, **entry}
    return None


def _query_variants(raw: str, aliases: dict) -> list:
    """The strings we try against the registry, most specific first."""
    variants = [raw]
    if raw in aliases and not str(aliases[raw]).startswith("http"):
        variants.insert(0, str(aliases[raw]).lower())
    builtin = BUILTIN_APP_ALIASES.get(raw)
    if builtin:
        variants.append(builtin)
    return variants


def _resolve_app_target(ir: CommandIR, app_registry: dict, aliases: dict) -> None:
    if not ir.target:
        return

    raw = str(ir.target).lower().strip()
    variants = _query_variants(raw, aliases)
    curated = curated_apps(app_registry)

    # 1. exact registry name match — any source, including PATH exes
    for query in variants:
        entry = app_registry.get(query)
        if entry:
            ir.target = dict(entry)
            return

    # 2. curated system utility (settings / camera / recycle bin / ...) —
    #    only for opening; closing "settings" by image name is unreliable and
    #    closing a URI is meaningless
    if ir.action == "open_app":
        for query in variants:
            utility = _match_system_utility(query)
            if utility is not None:
                ir.target = utility
                return

    # 3. fuzzy match — over *curated* apps only (Start Menu / App Paths),
    #    never the PATH junk drawer (A1)
    best_key, best_score, best_query = None, 0, raw
    for query in variants:
        match_key, score = _best_match(query, curated)
        if score > best_score:
            best_key, best_score, best_query = match_key, score, query
    if best_key and best_score >= FUZZY_MATCH_THRESHOLD:
        ir.target = dict(curated[best_key])
        return

    # 4. website fallback (A5): "open wikipedia" with no such app installed
    if ir.action == "open_app":
        known_urls = {**DEFAULT_URL_TARGETS,
                      **{k: v for k, v in aliases.items() if str(v).startswith("http")}}
        if raw in known_urls:
            ir.action = "open_url"
            ir.target = known_urls[raw]
            return
        if "." in raw and " " not in raw:
            ir.action = "open_url"
            ir.target = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
            return

    # 5. give up honestly, with *plausible* suggestions only
    candidates = _top_candidates(raw, curated)
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
    curated = curated_apps(app_registry)
    for param_key in ("new", "add", "remove"):
        names = ir.params.get(param_key)
        if not names:
            continue
        resolved = []
        unresolved = []
        for raw_name in names:
            raw_str = str(raw_name).lower()
            if _looks_like_website(raw_str, aliases):
                resolved.append(_resolve_mode_website_item(raw_name, aliases))
                continue

            variants = _query_variants(raw_str, aliases)
            entry = None
            for query in variants:
                entry = app_registry.get(query)
                if entry:
                    break
            if entry is None:
                for query in variants:
                    match_key, score = _best_match(query, curated)
                    if match_key and score >= FUZZY_MATCH_THRESHOLD:
                        entry = curated[match_key]
                        break
            if entry is not None:
                resolved.append({"type": "app", **entry})
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
