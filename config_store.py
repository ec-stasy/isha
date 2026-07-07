import json
import os
import tempfile
from pathlib import Path

from platform_paths import config_file

# Schema version lets future migrations detect and upgrade old config files.
SCHEMA_VERSION = 1


def _default_config() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        # mode_name -> {"apps": [{"type": "app"|"website", ...}], "script": str|None,
        #               "system_state": {"volume": int, "theme": "dark"|"light"}, "window_layout": {}}
        "modes": {},
        "active_mode": None,  # currently-active mode name, for Modes 2.0 clean switching
        "aliases": {},      # user word -> canonical app/url name
        "hotkeys": {},      # action -> key combo
        "settings": {},     # misc user preferences
        "reminders": [],    # persisted reminder/task records (Phase 1: storage only)
        "triggers": [],     # auto-trigger records for mode_scheduler.py: {"mode","type":"time"|"battery",...}
        "snippets": {},     # snippet name -> expansion text, for the expand_snippet action
        "license": None,    # {"raw","license_id","email","activated_at","device_fingerprint"} or None; see a_licensing.py
    }


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

    # fill in any keys missing from an older config version
    defaults = _default_config()
    for key, value in defaults.items():
        config.setdefault(key, value)

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
