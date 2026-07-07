"""
Offline signed licensing (Phase 6) — the client half of ROADMAP.md Section 6's
"sell once, fully local" commercial model. A license is a small JSON payload
(license_id, email, product, issued_at, optional expires_at, informational
max_devices) plus an Ed25519 signature over it, both hex-encoded and joined
with a dot: "<hex(payload)>.<hex(signature)>". Verification is entirely local
and offline — no activation server contacted, matching the "no phone-home"
promise everywhere else in Isha.

Why hex, not base64: Isha's own command tokenizer (input_processor.py)
lowercases everything and strips any character outside [\\w\\s.-], which
would silently corrupt a case-sensitive base64 blob's '+', '/' and '='
characters if a license key were ever typed or pasted into the palette/CLI.
Hex is lowercase-safe, alphanumeric-only, and the single separating dot
survives the tokenizer's "keep a dot between two word characters" rule — so
the whole key reliably stays one token.

SECURITY: ISHA_LICENSE_PUBLIC_KEY_HEX below is a placeholder generated for
this repo only — there is no matching private key, so every license
correctly fails verification until it's replaced with the real public key
(see tools/generate_license.py, run offline, private key never committed).
Fail closed, not fail open, exactly like a_updater.py's update-manifest key.

Enforcement is intentionally soft in one sense and hard in another: an
unlicensed copy of Isha still fully works (no feature is ever locked behind
a key — ROADMAP.md Section 6's "don't over-engineer anti-piracy" guardrail),
but a key that *has* been activated is locked to the device it was activated
on. activate_license() stamps the device fingerprint into the stored record
on first use; get_license_status()/is_licensed() re-check that fingerprint
against the current machine on every call, so copying config.json to another
PC (or restoring it after a hardware change) makes the license read as
"not licensed on this device" rather than silently working everywhere. This
is a local, offline check only (there is no activation-cap server), so it
guards against casual config-file sharing, not a determined attacker forging
their own fingerprint — same threat model as the rest of this module's
offline verification.
"""
import hashlib
import json
import sys
import time
import platform
import uuid
from datetime import datetime, timezone

from config_store import save_config
from execution_result import ExecutionResult

ISHA_LICENSE_PUBLIC_KEY_HEX = "80350603bf6c8082de0ef975b9882a9e415002c07fa5bd0944fcdc098231674e"

PRODUCT_ID = "isha"

IS_WINDOWS = sys.platform == "win32"


# ---------------------------------------------------------------------------------------
# Track A5 security fix: activate_license used to store the license record —
# including the buyer's email and the raw key it decodes from — in
# config.json in cleartext. That file is plain, user-editable JSON with no
# secrecy guarantee, and the buyer's email is the one piece of genuine
# personal data Isha holds; the whole product promise is "we don't keep your
# data." On Windows, encrypt the record at rest with DPAPI (CryptProtectData),
# which ties the ciphertext to this Windows user account and needs no key
# management of our own. Non-Windows dev environments fall back to plaintext
# (there's no DPAPI there, and Isha only ships for Windows).

def _dpapi_call(func_name: str, data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    in_blob = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = _BLOB()

    func = getattr(ctypes.windll.crypt32, func_name)
    if not func(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise OSError(f"{func_name} failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _dpapi_protect(data: bytes) -> bytes:
    return _dpapi_call("CryptProtectData", data)


def _dpapi_unprotect(data: bytes) -> bytes:
    return _dpapi_call("CryptUnprotectData", data)


def _store_license_record(config: dict, record: dict) -> None:
    if IS_WINDOWS:
        try:
            encrypted = _dpapi_protect(json.dumps(record).encode("utf-8"))
            config["license"] = {"encrypted": encrypted.hex()}
            save_config(config)
            return
        except Exception:
            pass  # DPAPI unexpectedly unavailable — fail open to plaintext rather than losing the license entirely
    config["license"] = record
    save_config(config)


def _load_license_record(config: dict):
    """Returns the decrypted record dict, or None if there's nothing usable
    stored (missing, corrupt, or undecryptable on this machine)."""
    stored = config.get("license")
    if not stored:
        return None
    if "encrypted" in stored:
        try:
            data = _dpapi_unprotect(bytes.fromhex(stored["encrypted"]))
            return json.loads(data)
        except Exception:
            return None
    return stored  # plaintext fallback: non-Windows dev, or a pre-A5 config file


def _verify_signature(payload_bytes: bytes, signature: bytes) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return False

    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(ISHA_LICENSE_PUBLIC_KEY_HEX))
        public_key.verify(signature, payload_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _decode_license_string(license_str: str):
    """Splits '<hex payload>.<hex signature>' into raw bytes, or (None, None)
    on any malformed input — never raises, since this only ever sees
    user-supplied text."""
    if not license_str or "." not in license_str:
        return None, None
    payload_hex, _, sig_hex = license_str.partition(".")
    try:
        payload_bytes = bytes.fromhex(payload_hex)
        signature = bytes.fromhex(sig_hex)
    except ValueError:
        return None, None
    return payload_bytes, signature


def _device_fingerprint() -> str:
    """
    A stable-ish local identifier, stored only in this machine's own
    config.json and never transmitted anywhere. It exists purely so a human
    support conversation ('report issue' + a chat) can reference "which
    device" without any online activation-cap server — there isn't one yet
    (same gap as Phase 5's report-intake endpoint), so this is bookkeeping
    only and enforces nothing by itself.
    """
    raw = f"{platform.node()}|{uuid.getnode()}|{sys.platform}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def verify_license_string(license_str: str) -> ExecutionResult:
    """
    Pure verification, no side effects — used by both activate_license (a new
    key) and get_license_status (re-checking a stored one). success=True
    means the signature checked out AND the license is for this product AND
    isn't expired; data then holds the decoded payload fields.
    """
    payload_bytes, signature = _decode_license_string(license_str)
    if payload_bytes is None:
        return ExecutionResult(False, "That doesn't look like a valid license key.", error="bad_format")

    if not _verify_signature(payload_bytes, signature):
        return ExecutionResult(
            False,
            "License signature didn't verify — this key is invalid or corrupted, or "
            "the optional 'cryptography' package isn't installed.",
            error="signature_invalid",
        )

    try:
        payload = json.loads(payload_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ExecutionResult(False, "License payload is unreadable.", error="bad_payload")

    if not isinstance(payload, dict) or payload.get("product") != PRODUCT_ID:
        return ExecutionResult(False, "This license key isn't for Isha.", error="wrong_product")

    expires_at = payload.get("expires_at")
    if expires_at is not None:
        try:
            if time.time() > float(expires_at):
                return ExecutionResult(False, "This license has expired.", error="expired", data=dict(payload))
        except (TypeError, ValueError):
            return ExecutionResult(False, "License has an unreadable expiry date.", error="bad_payload")

    return ExecutionResult(True, "License verified.", data=dict(payload))


def activate_license(config: dict, license_str: str) -> ExecutionResult:
    """
    Verifies the key and, only on success, stores it. A failed attempt never
    overwrites a previously-activated valid license.

    One-device enforcement: a license already activated (and still verifying
    fingerprint-valid) on *this* device can't be silently swapped for a
    different license_id by activating a new key — that would defeat the
    fingerprint stamping below, since the new key would just re-stamp over
    the old record. Callers must 'deactivate license' first, which is an
    explicit, deliberate action (matching deactivate_license's own docstring
    about moving to a new machine), not something a second 'activate' call
    should do as a side effect.
    """
    result = verify_license_string(license_str)
    if not result.success:
        return result

    existing = _load_license_record(config)
    if existing and existing.get("raw") and existing.get("license_id") != result.data.get("license_id"):
        existing_check = verify_license_string(existing["raw"])
        if existing_check.success and existing.get("device_fingerprint") == _device_fingerprint():
            return ExecutionResult(
                False,
                "A different license is already activated on this device — "
                "run 'deactivate license' first if you want to switch keys.",
                error="already_activated",
            )

    license_record = {
        "raw": license_str,
        "license_id": result.data.get("license_id"),
        "email": result.data.get("email"),
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "device_fingerprint": _device_fingerprint(),
    }
    _store_license_record(config, license_record)

    return ExecutionResult(
        True,
        f"License activated for {result.data.get('email', 'this copy of Isha')} on this device only "
        "— thank you for supporting Isha!",
        data=license_record,
    )


def deactivate_license(config: dict) -> ExecutionResult:
    """Clears the local license record. Purely local bookkeeping — there is no
    online activation-cap server yet to notify, so this just frees this
    device's own config for a future 'activate license' (e.g. after moving to
    a new machine)."""
    if not config.get("license"):
        return ExecutionResult(False, "No license is currently activated on this device.", error="not_found")
    config["license"] = None
    save_config(config)
    return ExecutionResult(True, "License removed from this device. Activate again any time with your key.")


def get_license_status(config: dict) -> ExecutionResult:
    """
    Always re-verifies the stored raw license string's signature rather than
    trusting cached fields in config.json: config.json is plain, user-editable
    JSON, so trusting a cached "licensed": true flag would make this whole
    gate worthless against a two-minute text-editor edit. success is always
    True here (the *check* completed); data["licensed"] is the real answer.

    Also re-checks the stored device_fingerprint against this machine's
    current one — this is what makes activation single-device: a config.json
    copied to (or restored on) another PC carries a fingerprint that won't
    match there, so it reads as unlicensed on the new device rather than
    silently carrying the license over.
    """
    stored = _load_license_record(config)
    if not stored or not stored.get("raw"):
        return ExecutionResult(
            True,
            "Not licensed yet — use 'activate license <key>' with the key from your purchase email.",
            data={"licensed": False},
        )

    result = verify_license_string(stored["raw"])
    if not result.success:
        return ExecutionResult(
            True,
            f"Stored license is no longer valid ({result.message}) — activate a new one.",
            data={"licensed": False, "reason": result.error},
        )

    if stored.get("device_fingerprint") != _device_fingerprint():
        return ExecutionResult(
            True,
            "This license is activated on a different device — licenses are single-device; "
            "activate your own key here with 'activate license <key>'.",
            data={"licensed": False, "reason": "wrong_device"},
        )

    return ExecutionResult(
        True,
        f"Licensed to {result.data.get('email', 'unknown')} (id {result.data.get('license_id', '?')}) — this device only.",
        data={"licensed": True, **result.data},
    )


def is_licensed(config: dict) -> bool:
    return bool(get_license_status(config).data.get("licensed"))


# ---------------------------------------------------------------------------------------
# Free tier (Isha Lite): the public download is the full codebase, gated down
# to a handful of actions rather than a separate build — app open/close and
# volume/brightness control, the set of things useful enough to hook someone
# without giving away the whole product. Everything else asks for an upgrade.
# Purely a local, informational gate (same offline threat model as the rest
# of this module): it stops the honest majority from being confused about
# what they paid for, not a determined attacker from patching it out.
FREE_ACTIONS = {"open_app", "close_app", "mute_volume", "unmute_volume"}
FREE_VALUE_TARGETS = {"volume", "brightness"}

# Meta/hygiene actions that must work regardless of license — most obviously
# activating a license itself (Cycle 4 fix: the gate used to block
# activate_license, so an unlicensed install could never *become* licensed),
# plus help, undo of an allowed action, and the support/update paths.
META_ACTIONS = {
    "activate_license", "license_status", "deactivate_license",
    "show_help", "undo_last_action",
    "report_issue", "send_report", "check_for_updates", "apply_update",
}


def is_action_free_tier(action: str, target) -> bool:
    """True if this resolved action is allowed without a license."""
    if action in FREE_ACTIONS or action in META_ACTIONS:
        return True
    if action in ("increase_value", "decrease_value", "set_value", "toggle_value"):
        return target in FREE_VALUE_TARGETS
    return False


def free_tier_upgrade_message() -> str:
    return (
        "That's part of full Isha. You're using Isha Lite (free) — open/close apps and "
        "volume/brightness. Upgrade for the rest: https://isha.app/#pricing"
    )
