"""
Multi-device-aware mute (F3). With pycaw present, mute enumerates every
*active* audio output device and applies settings.audio.mute_behavior
(halve_all — the default — / mute_all / mute_default_only / set_all_to);
per-device levels are snapshotted in memory first so unmute genuinely
restores them (finally fixing the honest-but-sad "toggled mute, can't
guarantee unmute" message). The snapshot is deliberately not persisted —
after a restart, unmute just sets devices to the configured default level.

Without pycaw, both calls degrade to exactly the old media-key behavior
with the old honest message.
"""
from execution_result import ExecutionResult

# in-memory only, by design (minimal-storage rule)
_snapshot = {}  # device_id -> {"level": float 0..1, "muted": bool}


def _active_render_endpoints():
    """[(device_id, friendly_name, IAudioEndpointVolume), ...] for every
    active output device, COM references kept alive by the tuple."""
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    endpoints = []
    for device in AudioUtilities.GetAllDevices():
        # state 1 == DEVICE_STATE_ACTIVE; render endpoints only
        if getattr(device, "state", None) not in (1,) or device.id is None:
            continue
        if "{0.0.0.00000000}" not in str(device.id):  # render endpoints carry the eRender GUID prefix
            continue
        try:
            interface = device._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            endpoints.append((str(device.id), device.FriendlyName or "audio device", volume))
        except Exception:
            continue
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
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            speakers = AudioUtilities.GetSpeakers()
            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            cast(interface, POINTER(IAudioEndpointVolume)).SetMute(1, None)
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
