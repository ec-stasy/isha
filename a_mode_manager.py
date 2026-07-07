from config_store import save_config
from execution_result import ExecutionResult


def get_mode(config: dict, name: str) -> dict:
    return config.get("modes", {}).get(str(name).lower())


def create_mode(config: dict, name: str, apps: list) -> ExecutionResult:
    name = str(name).lower()
    if name in config["modes"]:
        return ExecutionResult(False, f"A mode named '{name}' already exists.", error="mode_exists")

    config["modes"][name] = {
        "apps": apps or [],
        "script": None,          # optional command run on activate; config-editable (see ROADMAP)
        "system_state": {},      # optional {"volume": int, "theme": "dark"|"light"}; config-editable
        "window_layout": {},     # optional {app_name: {"x","y","w","h"}}; config-editable
    }
    save_config(config)
    return ExecutionResult(True, f"Created mode '{name}' with {len(apps or [])} app(s).", data={"mode": name})


def update_mode(config: dict, name: str, add: list = None, remove: list = None) -> ExecutionResult:
    name = str(name).lower()
    mode = config["modes"].get(name)
    if mode is None:
        return ExecutionResult(False, f"No mode named '{name}' exists.", error="mode_not_found")

    apps = mode.setdefault("apps", [])
    existing_names = {a.get("name") if isinstance(a, dict) else a for a in apps}

    for app in (add or []):
        app_name = app.get("name") if isinstance(app, dict) else app
        if app_name not in existing_names:
            apps.append(app)
            existing_names.add(app_name)

    if remove:
        remove_names = {a.get("name") if isinstance(a, dict) else a for a in remove}
        mode["apps"] = [a for a in apps if (a.get("name") if isinstance(a, dict) else a) not in remove_names]

    save_config(config)
    return ExecutionResult(True, f"Updated mode '{name}'.", data={"mode": name, "apps": mode["apps"]})


def delete_mode(config: dict, name: str) -> ExecutionResult:
    name = str(name).lower()
    if name not in config["modes"]:
        return ExecutionResult(False, f"No mode named '{name}' exists.", error="mode_not_found")

    del config["modes"][name]
    save_config(config)
    return ExecutionResult(True, f"Deleted mode '{name}'.", data={"mode": name})


def get_mode_apps(config: dict, name: str) -> list:
    """Apps/websites to launch/close for a mode activation/deactivation — used by the executor."""
    mode = get_mode(config, name)
    if mode is None:
        return []
    return mode.get("apps", [])


def get_mode_script(config: dict, name: str) -> str:
    mode = get_mode(config, name)
    return (mode or {}).get("script")


def get_mode_system_state(config: dict, name: str) -> dict:
    mode = get_mode(config, name)
    return (mode or {}).get("system_state", {})


def get_mode_window_layout(config: dict, name: str) -> dict:
    mode = get_mode(config, name)
    return (mode or {}).get("window_layout", {})


def set_active_mode(config: dict, name) -> None:
    config["active_mode"] = name
    save_config(config)


# ---------------------------------------------------------------------------------------
# Phase 4 — typed setters for the fields that were config-editable-only in Phase 3

def set_mode_script(config: dict, name: str, script: str) -> ExecutionResult:
    name = str(name).lower()
    mode = config["modes"].get(name)
    if mode is None:
        return ExecutionResult(False, f"No mode named '{name}' exists.", error="mode_not_found")
    mode["script"] = script
    save_config(config)
    return ExecutionResult(True, f"Set '{name}' mode's activation script.", data={"mode": name, "script": script})


def set_mode_volume(config: dict, name: str, level: int) -> ExecutionResult:
    name = str(name).lower()
    mode = config["modes"].get(name)
    if mode is None:
        return ExecutionResult(False, f"No mode named '{name}' exists.", error="mode_not_found")
    mode.setdefault("system_state", {})["volume"] = max(0, min(100, level))
    save_config(config)
    return ExecutionResult(True, f"Set '{name}' mode's volume to {level}%.", data={"mode": name, "level": level})


def set_mode_theme(config: dict, name: str, theme: str) -> ExecutionResult:
    name = str(name).lower()
    mode = config["modes"].get(name)
    if mode is None:
        return ExecutionResult(False, f"No mode named '{name}' exists.", error="mode_not_found")
    mode.setdefault("system_state", {})["theme"] = theme
    save_config(config)
    return ExecutionResult(True, f"Set '{name}' mode's theme to {theme}.", data={"mode": name, "theme": theme})


def set_mode_window_layout(config: dict, name: str, layout: dict) -> ExecutionResult:
    name = str(name).lower()
    mode = config["modes"].get(name)
    if mode is None:
        return ExecutionResult(False, f"No mode named '{name}' exists.", error="mode_not_found")
    mode["window_layout"] = layout
    save_config(config)
    return ExecutionResult(True, f"Captured window layout for '{name}' mode ({len(layout)} window(s)).", data={"mode": name, "layout": layout})
