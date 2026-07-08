"""
Internet checks. `check_internet` stays the plain TCP reachability probe
(no HTTP, no payload). Cycle 6 A13 adds `speed_test()` — a real download and
upload measurement against Cloudflare's public speed-test endpoints
(speed.cloudflare.com), run ONLY when the user explicitly asks ("check
internet" / "speed test"), never in the background. The payload is random
bytes; nothing identifying is sent.

UI hook: `register_progress_listener(fn)` — fn(phase, mbps, fraction) is
called from the measuring thread while a test runs ("download"/"upload"/
"done"), which is what animates the dashboard's speedometer gauge.
"""
import socket
import time
import urllib.request

from execution_result import ExecutionResult

# Public DNS resolvers — reachable almost everywhere, used only for a raw TCP
# connect probe (port 53, no query sent).
_PROBE_HOSTS = [("8.8.8.8", 53), ("1.1.1.1", 53)]

_DOWNLOAD_URL = "https://speed.cloudflare.com/__down?bytes={}"
_UPLOAD_URL = "https://speed.cloudflare.com/__up"
_DOWNLOAD_BYTES = 20_000_000   # 20 MB cap; the time cap below usually ends first
_UPLOAD_BYTES = 8_000_000      # 8 MB
_TIME_CAP_S = 6.0              # per direction
_CHUNK = 64 * 1024

_progress_listener = None


def register_progress_listener(fn) -> None:
    """fn(phase: str, mbps: float, fraction: float 0..1) — called from the
    worker thread; the GUI must marshal to its own thread."""
    global _progress_listener
    _progress_listener = fn


def _emit(phase: str, mbps: float, fraction: float) -> None:
    listener = _progress_listener
    if listener is not None:
        try:
            listener(phase, mbps, fraction)
        except Exception:
            pass


def check_internet(timeout: float = 3.0) -> ExecutionResult:
    for host, port in _PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return ExecutionResult(True, "Internet connection looks good.", data={"probed": host})
        except OSError:
            continue

    return ExecutionResult(False, "No internet connection detected.", error="offline", data={"probed": _PROBE_HOSTS})


def _measure_download() -> float:
    """Returns Mbps (megabits/s), or raises OSError."""
    request = urllib.request.Request(_DOWNLOAD_URL.format(_DOWNLOAD_BYTES),
                                     headers={"User-Agent": "Isha-speedtest"})
    received = 0
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=10) as response:
        while True:
            chunk = response.read(_CHUNK)
            if not chunk:
                break
            received += len(chunk)
            elapsed = time.monotonic() - start
            if elapsed > 0.2:
                _emit("download", (received * 8 / 1_000_000) / elapsed,
                      min(1.0, max(received / _DOWNLOAD_BYTES, elapsed / _TIME_CAP_S)))
            if elapsed >= _TIME_CAP_S:
                break
    elapsed = max(time.monotonic() - start, 0.001)
    return (received * 8 / 1_000_000) / elapsed


def _measure_upload() -> float:
    """Returns Mbps, or raises OSError. Sends random bytes in one POST."""
    payload = bytes(bytearray(os_urandom_cached(_UPLOAD_BYTES)))
    request = urllib.request.Request(_UPLOAD_URL, data=payload, method="POST",
                                     headers={"User-Agent": "Isha-speedtest",
                                              "Content-Type": "application/octet-stream"})
    start = time.monotonic()
    _emit("upload", 0.0, 0.0)
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
    elapsed = max(time.monotonic() - start, 0.001)
    mbps = (_UPLOAD_BYTES * 8 / 1_000_000) / elapsed
    _emit("upload", mbps, 1.0)
    return mbps


_random_block = None

def os_urandom_cached(size: int) -> bytes:
    """Random-ish payload without regenerating megabytes each call."""
    global _random_block
    import os
    if _random_block is None or len(_random_block) < size:
        _random_block = os.urandom(min(size, 1_000_000)) * (size // min(size, 1_000_000) + 1)
    return _random_block[:size]


def speed_test() -> ExecutionResult:
    try:
        _emit("download", 0.0, 0.0)
        down = _measure_download()
    except OSError as e:
        _emit("done", 0.0, 1.0)
        return ExecutionResult(False, f"Connected, but the speed test failed: {e}", error="speed_test_failed")
    try:
        up = _measure_upload()
    except OSError:
        up = None
    _emit("done", down, 1.0)

    if up is None:
        message = f"Download {down:.1f} Mbps (upload test didn't complete)."
    else:
        message = f"Download {down:.1f} Mbps  ·  Upload {up:.1f} Mbps."
    return ExecutionResult(True, message, data={"download_mbps": round(down, 1),
                                                "upload_mbps": round(up, 1) if up is not None else None})
