import json
import os
import re
import sys
import time
from pathlib import Path

from platform_paths import app_registry_cache_file

CACHE_TTL_SECONDS = 24 * 60 * 60  # rebuild at most once a day; scanning disk/registry is not free

# Cycle 6: entries gained "source" and "args" fields (A1/A4) — bumping the
# schema invalidates every pre-Cycle-6 cache file so stale entries without
# them can never feed the resolver again.
CACHE_SCHEMA = 2

# In-process copy of the disk cache (audit, Phase 5): the palette's live "did
# you mean" suggestions call get_app_registry() on every keystroke, so without
# this, a single typing session could re-read and re-parse the cache JSON file
# from disk dozens of times a minute for data that can't have changed within
# this process's lifetime. Same TTL/staleness rules as the disk cache — this
# is purely about not repeating I/O we already did.
_memory_cache = None

# Start-Menu shortcuts that are never what a user means by "open <app>"
_SHORTCUT_NOISE = re.compile(r"uninstall|readme|help|documentation|website|report a problem", re.IGNORECASE)


def _scan_path_executables() -> dict:
    """Every .exe reachable on PATH: name (without extension) -> entry.

    Cycle 6 (A1): these are the most generic, junk-heavy source (Git's
    usr\\bin ships od.exe, ex.exe, at.exe...). They're tagged source="path"
    so the resolver only ever uses them for *exact* name matches — they must
    never win a fuzzy match against a real installed app.
    """
    found = {}
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        d = Path(directory)
        if not d.is_dir():
            continue
        try:
            for entry in d.iterdir():
                if entry.suffix.lower() == ".exe" and entry.is_file():
                    found.setdefault(entry.stem.lower(), {"path": str(entry), "source": "path"})
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
                                found.setdefault(Path(app_name).stem.lower(),
                                                 {"path": path.strip('"'), "source": "app_paths"})
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _split_shortcut_args(raw: str) -> list:
    """Best-effort split of a .lnk Arguments string into a Popen args list."""
    if not raw:
        return []
    try:
        import shlex
        return shlex.split(raw, posix=False)
    except ValueError:
        return raw.split()


def _scan_start_menu_shortcuts() -> dict:
    """Resolves .lnk shortcuts under both the common and per-user Start Menu.

    Cycle 6 (A4): the shortcut's Arguments are kept — a Chrome/Edge web-app
    shortcut is `chrome_proxy.exe --profile-directory=... --app-id=...`, and
    dropping the arguments used to turn "open github" into "open a blank
    Chrome window".
    """
    if sys.platform != "win32":
        return {}

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        # pywin32 not installed — degrade gracefully rather than crash the whole scan
        return {}

    found = {}
    start_menu_dirs = [
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]

    try:
        pythoncom.CoInitialize()  # the registry warmup runs on its own thread
    except Exception:
        pass
    # (no matching CoUninitialize: the COM shortcut objects may outlive this
    # call via the garbage collector, and releasing them after uninitialize
    # spams "Win32 exception occurred releasing IUnknown" warnings)
    shell = win32com.client.Dispatch("WScript.Shell")
    for base in start_menu_dirs:
        if not base.is_dir():
            continue
        for lnk_path in base.rglob("*.lnk"):
            if _SHORTCUT_NOISE.search(lnk_path.stem):
                continue
            try:
                shortcut = shell.CreateShortCut(str(lnk_path))
                target = shortcut.Targetpath
                if not target or not target.lower().endswith(".exe"):
                    continue
                entry = {"path": target, "source": "start_menu"}
                args = _split_shortcut_args(getattr(shortcut, "Arguments", "") or "")
                if args:
                    entry["args"] = args
                    # a browser web-app shortcut *is* the website-as-app the
                    # user installed — mark it so the resolver can prefer it
                    # for names like "github"
                    if any("--app-id=" in a for a in args):
                        entry["web_app"] = True
                found.setdefault(lnk_path.stem.lower(), entry)
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
    return {name: {"name": name, **entry} for name, entry in registry.items()}


def get_app_registry(force_refresh: bool = False) -> dict:
    """
    Returns {app_name_lowercase: {"name", "path", "source", ["args"], ["web_app"]}},
    cached both in memory and to disk since scanning Start Menu/registry/PATH
    on every command would be wasteful.
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
            if (cached.get("schema") == CACHE_SCHEMA
                    and time.time() - cached.get("built_at", 0) < CACHE_TTL_SECONDS):
                _memory_cache = cached
                return cached.get("apps", {})
        except (json.JSONDecodeError, OSError):
            pass  # fall through to rebuild

    apps = _build_registry()
    payload = {"built_at": time.time(), "schema": CACHE_SCHEMA, "apps": apps}
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        pass  # cache is a pure optimization; failing to write it isn't fatal

    _memory_cache = payload
    return apps


def curated_apps(registry: dict = None) -> dict:
    """The fuzzy-matchable subset: real installed apps (Start Menu / App
    Paths), not the PATH junk drawer. PATH entries stay exact-match-only."""
    registry = registry if registry is not None else get_app_registry()
    return {name: entry for name, entry in registry.items()
            if entry.get("source") in ("start_menu", "app_paths")}
