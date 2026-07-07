"""
Website allow-list (F1) — a strict tightening of the URL gate. Allow-listed
hosts open exactly as before; anything else is only opened after an explicit
affirmative from a quiet prompt (never an alarm), and non-interactive paths
(scheduled mode activations) skip the URL with a toast instead.

Matching is on the parsed hostname (urllib.parse) — never substring-on-the-
whole-URL, so "evil.com/?q=youtube.com" can't ride on a "youtube.com" entry.
"youtube.com" matches itself, "www.youtube.com" and any subdomain. IDN hosts
are compared in punycode.
"""
from urllib.parse import urlparse

from command_ir import CommandIR
from execution_result import ExecutionResult
from config_store import _normalize_host, save_config


def normalize_host(url_or_host: str) -> str:
    return _normalize_host(url_or_host)


def is_enabled(config: dict) -> bool:
    return bool((config.get("settings", {}) or {}).get("allow_list_enabled", True))


def is_allowed(url: str, config: dict) -> bool:
    """True if the URL's host is covered by the allow-list (or the feature is off)."""
    if not is_enabled(config):
        return True
    host = normalize_host(url)
    if not host:
        return False
    for pattern in config.get("allow_list", []) or []:
        entry = normalize_host(pattern)
        if entry and (host == entry or host.endswith("." + entry)):
            return True
    return False


def add_host(url_or_host: str, config: dict) -> str:
    """Adds the normalized host; returns it. Idempotent."""
    host = normalize_host(url_or_host)
    if host:
        allow_list = config.setdefault("allow_list", [])
        if host not in allow_list:
            allow_list.append(host)
            save_config(config)
    return host


# ---------------------------------------------------------------------------
# executor handlers

def add_allow_site(ir: CommandIR, config: dict) -> ExecutionResult:
    host = normalize_host(str(ir.target or ""))
    if not host:
        return ExecutionResult(False, f"'{ir.target}' doesn't look like a website address.", error="bad_host")
    if host in (config.get("allow_list") or []):
        return ExecutionResult(True, f"{host} is already on your allow list.")
    add_host(host, config)
    return ExecutionResult(True, f"Added {host} to your allow list — it will open without asking now.",
                           data={"host": host})


def remove_allow_site(ir: CommandIR, config: dict) -> ExecutionResult:
    host = normalize_host(str(ir.target or ""))
    allow_list = config.get("allow_list") or []
    if host not in allow_list:
        return ExecutionResult(False, f"{host or ir.target} isn't on your allow list.", error="not_found")
    allow_list.remove(host)
    save_config(config)
    return ExecutionResult(True, f"Removed {host} from your allow list — Isha will ask before opening it.",
                           data={"host": host})


def show_allow_list(ir: CommandIR, config: dict) -> ExecutionResult:
    entries = config.get("allow_list") or []
    if not is_enabled(config):
        return ExecutionResult(True, "The website allow list is turned off — every site opens without asking.")
    if not entries:
        return ExecutionResult(True, "Your allow list is empty — Isha will quietly ask before opening any website.")
    return ExecutionResult(True, "Websites that open without asking: " + ", ".join(sorted(entries)),
                           data={"allow_list": sorted(entries)})
