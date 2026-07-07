import json
import os
import tempfile
from pathlib import Path

from platform_paths import config_file

# Schema version lets migrations detect and upgrade old config files.
# v2 (Cycle 4 "Sakura"): allow_list, scripts, reminders new shape,
# settings.allow_scripts (renamed), settings.defaults/audio/screenshot/
# notifications/ui groups. See NEW_VERSION_ROADMAP.md §5.F7.
SCHEMA_VERSION = 2


def _default_settings() -> dict:
    return {
        "onboarded": False,
        "allow_scripts": False,          # gates ALL script execution (Track A1; renamed from allow_mode_scripts)
        "allow_list_enabled": True,      # F1: website allow-list on by default
        "defaults": {"level": 50},       # F2: level used when a leveled action gets none
        "audio": {"mute_behavior": "halve_all", "mute_level": 50},  # F3
        "screenshot": {"dir": None, "after": "save", "prtscr": "off", "capture": "full"},  # F4 (dir None = system Pictures\Screenshots)
        "notifications": {"sound": "off", "use_windows_native": False},
        "ui": {
            "theme": "auto",             # auto follows Windows light/dark
            "sidebar_collapsed": False,
            "show_scrollbars": "auto",   # auto | always | hidden
            "reduce_motion": False,
            "close_action": "tray",      # tray | exit
            "overlay_autohide": 2.5,
            "window": {},                # geometry remembered by the shell
            "quick_actions": [
                {"label": "Screenshot", "command": "take screenshot"},
                {"label": "Mute", "command": "mute volume"},
                {"label": "Lock", "command": "lock the pc"},
                {"label": "Check internet", "command": "check internet"},
                {"label": "Empty recycle bin", "command": "empty recycle bin"},
            ],
        },
        "hotkey": "ctrl+alt+space",
        "voice_hotkey": None,
        "report_intake_url": None,
        "update_manifest_url": None,
    }


def _default_config() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        # mode_name -> {"apps": [{"type": "app"|"website", ...}], "script": str|None,
        #               "system_state": {"volume": int, "theme": "dark"|"light"}, "window_layout": {}}
        "modes": {},
        "active_mode": None,
        "aliases": {},      # user word -> canonical app/url name
        "hotkeys": {},      # action -> key combo
        "settings": _default_settings(),
        "allow_list": [],   # F1: normalized host patterns ("youtube.com" matches subdomains)
        "reminders": [],    # F5: {"id","text","at" ISO,"repeat","enabled","last_fired"}
        "scripts": {},      # F6: name -> {"command": str, "created": ISO}
        "triggers": [],     # auto-trigger records for mode_scheduler.py
        "snippets": {},     # snippet name -> expansion text
        "license": None,    # see a_licensing.py (DPAPI-wrapped on Windows)
    }


def _deep_fill(target: dict, defaults: dict) -> None:
    """Recursively setdefault nested dicts so new settings keys appear without
    ever overwriting a value the user already chose."""
    for key, value in defaults.items():
        if key not in target:
            target[key] = value
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_fill(target[key], value)


def _migrate_v1_to_v2(config: dict) -> dict:
    """
    Idempotent v1 → v2 upgrade. Principles: never lose a user choice, never
    change behavior silently (allow-list is seeded from mode websites so a
    working mode keeps working; the old screenshot folder is kept as the
    configured dir so files don't start landing elsewhere).
    """
    settings = config.setdefault("settings", {})

    # rename allow_mode_scripts -> allow_scripts (same meaning, wider scope)
    if "allow_scripts" not in settings:
        settings["allow_scripts"] = bool(settings.pop("allow_mode_scripts", False))
    else:
        settings.pop("allow_mode_scripts", None)

    # seed the allow-list from every website already saved in a mode, so
    # upgrading never breaks a mode the user already trusts
    if "allow_list" not in config:
        seeded = []
        for mode in (config.get("modes") or {}).values():
            for item in (mode or {}).get("apps", []) or []:
                if isinstance(item, dict) and item.get("type") == "website":
                    host = _normalize_host(item.get("url") or item.get("name") or "")
                    if host and host not in seeded:
                        seeded.append(host)
        config["allow_list"] = seeded

    # v1 kept screenshots in Pictures\Isha Screenshots; keep that folder as the
    # explicit configured value if it exists, so nothing moves silently
    _deep_fill(settings, _default_settings())
    if settings["screenshot"]["dir"] is None:
        legacy = Path.home() / "Pictures" / "Isha Screenshots"
        if legacy.is_dir():
            settings["screenshot"]["dir"] = str(legacy)

    # reminders: upgrade any old write-only records to the v2 shape
    upgraded = []
    for i, record in enumerate(config.get("reminders") or []):
        if not isinstance(record, dict):
            continue
        if "id" in record and "at" in record:
            upgraded.append(record)
            continue
        upgraded.append({
            "id": record.get("id") or f"r{i+1}",
            "text": record.get("text") or record.get("message") or str(record),
            "at": record.get("at") or record.get("time") or None,
            "repeat": record.get("repeat") or "none",
            "enabled": bool(record.get("at") or record.get("time")),
            "last_fired": None,
        })
    config["reminders"] = upgraded

    config.setdefault("scripts", {})
    config["schema_version"] = 2
    return config


def _normalize_host(url_or_host: str) -> str:
    """Lowercased, punycode-encoded registrable host, stripped of a leading
    'www.'. Parsing (never substring matching) is what keeps
    'evil.com/?q=youtube.com' from matching 'youtube.com'."""
    from urllib.parse import urlparse
    text = (url_or_host or "").strip().lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    host = urlparse(text).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    try:
        host = host.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        pass
    return host


def load_config() -> dict:
    """
    Loads the config store, creating a fresh default one on first run.
    Never raises on a missing file; a corrupt file is backed up rather than
    silently discarded, since it may hold data the user cares about.
    """
    path = config_file()

    if not path.exists():
        config = _default_config()
        save_config(config)
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Preserve the unreadable file instead of overwriting user data silently.
        backup_path = path.with_suffix(".corrupt.json")
        try:
            path.replace(backup_path)
        except OSError:
            pass
        config = _default_config()
        save_config(config)
        return config

    migrated = False
    if int(config.get("schema_version") or 1) < 2:
        config = _migrate_v1_to_v2(config)
        migrated = True

    # fill in any keys missing from an older config version (deep for settings)
    defaults = _default_config()
    for key, value in defaults.items():
        config.setdefault(key, value)
    _deep_fill(config["settings"], _default_settings())

    if migrated:
        save_config(config)
    return config


def save_config(config: dict) -> None:
    """
    Atomically writes the config store so a crash mid-write can never corrupt it.
    Restricts file permissions to the owner where the OS supports it.
    """
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".config_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
