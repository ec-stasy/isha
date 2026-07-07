import json
import os
import sys
import time
from pathlib import Path

from platform_paths import app_registry_cache_file

CACHE_TTL_SECONDS = 24 * 60 * 60  # rebuild at most once a day; scanning disk/registry is not free

# In-process copy of the disk cache (audit, Phase 5): the palette's live "did
# you mean" suggestions call get_app_registry() on every keystroke, so without
# this, a single typing session could re-read and re-parse the cache JSON file
# from disk dozens of times a minute for data that can't have changed within
# this process's lifetime. Same TTL/staleness rules as the disk cache — this
# is purely about not repeating I/O we already did.
_memory_cache = None


def _scan_path_executables() -> dict:
    """Every .exe reachable on PATH: name (without extension) -> absolute path."""
    found = {}
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        d = Path(directory)
        if not d.is_dir():
            continue
        try:
            for entry in d.iterdir():
                if entry.suffix.lower() == ".exe" and entry.is_file():
                    found.setdefault(entry.stem.lower(), str(entry))
        except OSError:
            continue
    return found


def _scan_app_paths_registry() -> dict:
    """HKLM/HKCU ...\\App Paths — the canonical Windows registry of installed app launch targets."""
    if sys.platform != "win32":
        return {}

    import winreg

    found = {}
    subkey = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                i = 0
                while True:
                    try:
                        app_name = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(key, app_name) as app_key:
                            path, _ = winreg.QueryValueEx(app_key, "")
                            if path:
                                found.setdefault(Path(app_name).stem.lower(), path)
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _scan_start_menu_shortcuts() -> dict:
    """Resolves .lnk shortcuts under both the common and per-user Start Menu."""
    if sys.platform != "win32":
        return {}

    try:
        import win32com.client
    except ImportError:
        # pywin32 not installed — degrade gracefully rather than crash the whole scan
        return {}

    found = {}
    start_menu_dirs = [
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]

    shell = win32com.client.Dispatch("WScript.Shell")
    for base in start_menu_dirs:
        if not base.is_dir():
            continue
        for lnk_path in base.rglob("*.lnk"):
            try:
                shortcut = shell.CreateShortCut(str(lnk_path))
                target = shortcut.Targetpath
                if target:
                    found.setdefault(lnk_path.stem.lower(), target)
            except Exception:
                # a single unreadable shortcut shouldn't abort the whole scan
                continue
    return found


def _build_registry() -> dict:
    """
    Later sources win on name collisions: PATH exes are the most generic,
    App Paths registry entries are curated by installers, Start Menu shortcuts
    are the closest match to what a user would click — so they take priority.
    """
    registry = {}
    registry.update(_scan_path_executables())
    registry.update(_scan_app_paths_registry())
    registry.update(_scan_start_menu_shortcuts())
    return {name: {"name": name, "path": path} for name, path in registry.items()}


def get_app_registry(force_refresh: bool = False) -> dict:
    """
    Returns {app_name_lowercase: {"name": ..., "path": ...}}, cached both in
    memory and to disk since scanning Start Menu/registry/PATH on every
    command would be wasteful.
    """
    global _memory_cache

    if not force_refresh and _memory_cache is not None:
        if time.time() - _memory_cache.get("built_at", 0) < CACHE_TTL_SECONDS:
            return _memory_cache.get("apps", {})

    cache_path = app_registry_cache_file()

    if not force_refresh and cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("built_at", 0) < CACHE_TTL_SECONDS:
                _memory_cache = cached
                return cached.get("apps", {})
        except (json.JSONDecodeError, OSError):
            pass  # fall through to rebuild

    apps = _build_registry()
    payload = {"built_at": time.time(), "apps": apps}
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        pass  # cache is a pure optimization; failing to write it isn't fatal

    _memory_cache = payload
    return apps
