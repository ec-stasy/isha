"""
Internet-connectivity check — a plain TCP reachability probe (no HTTP request,
no payload) run only when the user explicitly asks. Doesn't conflict with the
"no data sent" promise: nothing but a TCP handshake leaves the machine, and
only on direct user request, never in the background.
"""
import socket

from execution_result import ExecutionResult

# Public DNS resolvers — reachable almost everywhere, used only for a raw TCP
# connect probe (port 53, no query sent).
_PROBE_HOSTS = [("8.8.8.8", 53), ("1.1.1.1", 53)]


def check_internet(timeout: float = 3.0) -> ExecutionResult:
    for host, port in _PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return ExecutionResult(True, "Internet connection looks good.", data={"probed": host})
        except OSError:
            continue

    return ExecutionResult(False, "No internet connection detected.", error="offline", data={"probed": _PROBE_HOSTS})
