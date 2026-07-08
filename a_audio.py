"""
Multi-device-aware audio control (F3, reworked in Cycle 6).

Cycle 6 A6: different pycaw releases return different things — sometimes a
raw IMMDevice (has .Activate), sometimes an AudioDevice wrapper (the COM
interface hangs off ._dev). The old code assumed one shape and crashed with
"'AudioDevice' object has no attribute 'Activate'" on the other.
`_activate_endpoint_volume` handles both, and every caller (including
executor's exact-level setter) goes through it.

New in Cycle 6: `list_output_devices` / `set_device_volume` power the
Customization page's per-device volume UI. Individual device levels are
persisted in settings.audio.device_levels keyed by the endpoint id, so a
device that is unplugged and reconnected later keeps its remembered level.

Without pycaw, everything degrades to the old media-key behavior with the
old honest message.
"""
from execution_result import ExecutionResult

# in-memory only, by design (minimal-storage rule)
_snapshot = {}  # device_id -> {"level": float 0..1, "muted": bool}


def _activate_endpoint_volume(device):
    """IAudioEndpointVolume pointer from either pycaw device shape, or None."""
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import IAudioEndpointVolume

    com_device = getattr(device, "_dev", device)
    activate = getattr(com_device, "Activate", None)
    if activate is None:
        return None
    try:
        interface = activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        return None


def default_endpoint_volume():
    """IAudioEndpointVolume for the default output device, or None.
    Raises ImportError if pycaw/comtypes aren't installed."""
    from pycaw.pycaw import AudioUtilities  # ImportError propagates deliberately
    try:
        speakers = AudioUtilities.GetSpeakers()
    except Exception:
        return None
    if speakers is None:
        return None
    return _activate_endpoint_volume(speakers)


def _active_render_endpoints():
    """[(device_id, friendly_name, IAudioEndpointVolume), ...] for every
    active output device, COM references kept alive by the tuple."""
    from pycaw.pycaw import AudioUtilities

    endpoints = []
    try:
        devices = AudioUtilities.GetAllDevices()
    except Exception:
        devices = []
    for device in devices:
        # DEVICE_STATE_ACTIVE only — the raw constant is 1, but newer pycaw
        # returns an AudioDeviceState enum (Cycle 6 A6: the old `state != 1`
        # check silently filtered *every* device out on enum builds)
        state = getattr(device, "state", None)
        state_value = getattr(state, "value", state)
        if state_value != 1 or device.id is None:
            continue
        if "{0.0.0.00000000}" not in str(device.id):  # render endpoints carry the eRender GUID prefix
            continue
        volume = _activate_endpoint_volume(device)
        if volume is not None:
            endpoints.append((str(device.id), device.FriendlyName or "audio device", volume))

    if not endpoints:
        # some pycaw builds fail GetAllDevices() entirely — fall back to the
        # default device alone so "one device" behavior still works
        try:
            volume = default_endpoint_volume()
        except ImportError:
            volume = None
        if volume is not None:
            endpoints.append(("default", "default audio device", volume))
    return endpoints


def _media_key_fallback(unmute: bool = False) -> ExecutionResult:
    import ctypes
    VK_VOLUME_MUTE = 0xAD
    ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
    if unmute:
        return ExecutionResult(True, "Toggled mute (Windows has no dedicated 'unmute' key "
                               "without the optional pycaw module).")
    return ExecutionResult(True, "Muted (toggle key).")


def mute(config: dict) -> ExecutionResult:
    settings = (config.get("settings", {}) or {}).get("audio", {}) or {}
    behavior = settings.get("mute_behavior", "halve_all")

    try:
        endpoints = _active_render_endpoints()
    except Exception:
        endpoints = []
    if not endpoints:
        return _media_key_fallback()

    # snapshot first, so unmute can truly restore
    _snapshot.clear()
    for device_id, name, volume in endpoints:
        try:
            _snapshot[device_id] = {"level": volume.GetMasterVolumeLevelScalar(),
                                    "muted": bool(volume.GetMute())}
        except Exception:
            continue

    if len(endpoints) == 1 or behavior == "mute_default_only":
        # classic fast path: hard-mute the default device only
        try:
            volume = default_endpoint_volume()
            if volume is None:
                return _media_key_fallback()
            volume.SetMute(1, None)
            return ExecutionResult(True, "Muted.")
        except Exception:
            return _media_key_fallback()

    changed = 0
    for device_id, name, volume in endpoints:
        try:
            if behavior == "mute_all":
                volume.SetMute(1, None)
            elif behavior == "set_all_to":
                level = max(0, min(100, int(settings.get("mute_level", 50))))
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            else:  # halve_all (default)
                volume.SetMasterVolumeLevelScalar(volume.GetMasterVolumeLevelScalar() / 2.0, None)
            changed += 1
        except Exception:
            continue

    verb = {"mute_all": "Muted", "set_all_to": f"Set to {settings.get('mute_level', 50)}%"}\
        .get(behavior, "Halved the volume of")
    return ExecutionResult(True, f"{verb} {changed} audio device(s).",
                           data={"devices": changed, "behavior": behavior})


def unmute(config: dict) -> ExecutionResult:
    try:
        endpoints = _active_render_endpoints()
    except Exception:
        endpoints = []
    if not endpoints:
        return _media_key_fallback(unmute=True)

    default_level = int(((config.get("settings", {}) or {}).get("defaults", {}) or {}).get("level", 50))
    restored = 0
    for device_id, name, volume in endpoints:
        saved = _snapshot.get(device_id)
        try:
            if saved is not None:
                volume.SetMute(1 if saved["muted"] else 0, None)
                volume.SetMasterVolumeLevelScalar(saved["level"], None)
            else:
                volume.SetMute(0, None)
                volume.SetMasterVolumeLevelScalar(default_level / 100.0, None)
            restored += 1
        except Exception:
            continue
    _snapshot.clear()
    return ExecutionResult(True, f"Restored {restored} audio device(s).", data={"devices": restored})


# ---------------------------------------------------------------------------
# per-device volume (Cycle 6 — Customization ▸ Volume ▸ Individual)

def list_output_devices(config: dict = None) -> list:
    """[{"id", "name", "level" (0-100 int), "saved" (int|None)}, ...] for every
    active output device; [] when pycaw is unavailable."""
    try:
        endpoints = _active_render_endpoints()
    except Exception:
        return []
    saved_levels = (((config or {}).get("settings", {}) or {}).get("audio", {}) or {}).get("device_levels", {}) or {}
    devices = []
    for device_id, name, volume in endpoints:
        try:
            level = int(round(volume.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            level = 0
        devices.append({"id": device_id, "name": name, "level": level,
                        "saved": saved_levels.get(device_id)})
    return devices


def set_device_volume(device_id: str, level: int, config: dict = None, persist: bool = True) -> bool:
    """Sets one device's volume now and (by default) remembers it in
    settings.audio.device_levels so reconnects of the same device keep it."""
    level = max(0, min(100, int(level)))
    applied = False
    try:
        for did, name, volume in _active_render_endpoints():
            if did == device_id:
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
                applied = True
                break
    except Exception:
        pass
    if persist and config is not None:
        audio = config.setdefault("settings", {}).setdefault("audio", {})
        audio.setdefault("device_levels", {})[device_id] = level
        from config_store import save_config
        save_config(config)
    return applied


def apply_saved_device_levels(config: dict) -> int:
    """Applies remembered per-device levels to whatever is connected right
    now (used when the volume mode is 'individual'). Returns how many applied."""
    saved = ((config.get("settings", {}) or {}).get("audio", {}) or {}).get("device_levels", {}) or {}
    if not saved:
        return 0
    applied = 0
    try:
        for device_id, name, volume in _active_render_endpoints():
            if device_id in saved:
                try:
                    volume.SetMasterVolumeLevelScalar(max(0, min(100, int(saved[device_id]))) / 100.0, None)
                    applied += 1
                except Exception:
                    continue
    except Exception:
        pass
    return applied
