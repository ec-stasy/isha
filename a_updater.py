"""
Auto-update check (Phase 5) — verifies a signed version manifest before ever
reporting an update as available, let alone applying one. Fails closed: if
signature verification isn't possible (the optional 'cryptography' package
isn't installed) or the signature doesn't check out, no update is trusted.
This is the client half of ROADMAP.md's "signed version manifest / signed
installer" design; Phase 6 owns actually building and signing a release.

Manual only — Isha never polls for updates in the background. That keeps the
"nothing leaves this machine unless you ask" promise intact and costs nothing
in idle resource usage; a periodic opt-in check can be added later behind its
own setting if users want it.

SECURITY: ISHA_UPDATE_PUBLIC_KEY_HEX below is a placeholder generated for
this repo only (not a real product key, no matching private key exists for
it). Before shipping, replace it with the real Ed25519 public key whose
private half is kept offline and used by Phase 6's release pipeline to sign
each manifest. Never commit a private key. Until replaced, every manifest
correctly fails verification — fail closed, not fail open.
"""
import hashlib
import json
import os
import secrets
import shutil
import sys
import time
import urllib.request
from pathlib import Path

from execution_result import ExecutionResult
from platform_paths import app_data_dir
from version import VERSION

IS_WINDOWS = sys.platform == "win32"

ISHA_UPDATE_PUBLIC_KEY_HEX = "596fb998a1cfea78281c3600f5f59ec7704c8f475613513db940a4a2d2b0414c"

_MANIFEST_TIMEOUT_SECONDS = 15
_DOWNLOAD_TIMEOUT_SECONDS = 60
_STALE_UPDATE_DIR_SECONDS = 24 * 60 * 60


def _current_version_tuple():
    return _parse_version_tuple(VERSION)


def _parse_version_tuple(v):
    try:
        return tuple(int(p) for p in str(v).split("."))
    except (ValueError, AttributeError):
        return None


def canonical_manifest_payload(version, url, sha256) -> bytes:
    """
    The exact bytes a manifest's signature covers. Track A3 security fix: this
    used to be f"{version}|{url}|{sha256}" — pipe-delimited concatenation is
    not a canonical encoding, so a field containing '|' (a URL certainly can)
    makes the (version, url, sha256) split ambiguous. Canonical, sorted-key
    JSON has no such ambiguity, and matches a_licensing.py's approach.
    tools/sign_manifest.py (seller-side, offline) must produce these exact
    bytes for a manifest's signature to verify.
    """
    return json.dumps(
        {"version": str(version), "url": str(url), "sha256": str(sha256)},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _verify_signature(manifest: dict) -> bool:
    try:
        import base64
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return False

    signature_b64 = manifest.get("signature")
    if not signature_b64:
        return False

    payload = canonical_manifest_payload(manifest.get("version"), manifest.get("url"), manifest.get("sha256"))
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(ISHA_UPDATE_PUBLIC_KEY_HEX))
        public_key.verify(base64.b64decode(signature_b64), payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def check_for_update(config: dict) -> ExecutionResult:
    """
    Fetches and verifies the manifest at settings.update_manifest_url.
    success=True means the check itself completed and was trustworthy —
    data["update_available"] says whether there's actually a newer version.
    success=False means the check couldn't be completed or couldn't be
    trusted (no config, bad URL, network failure, or signature failure).
    """
    manifest_url = (config.get("settings", {}) or {}).get("update_manifest_url")
    if not manifest_url:
        return ExecutionResult(
            False,
            "No update manifest URL is configured — set settings.update_manifest_url "
            "in config.json to enable update checks.",
            error="not_configured",
        )
    if not str(manifest_url).lower().startswith("https://"):
        return ExecutionResult(False, "Refusing to check updates over a non-HTTPS URL.", error="insecure_url")

    try:
        with urllib.request.urlopen(manifest_url, timeout=_MANIFEST_TIMEOUT_SECONDS) as resp:
            raw = resp.read()
        manifest = json.loads(raw)
    except Exception as e:
        return ExecutionResult(False, f"Couldn't check for updates: {e}", error="fetch_failed")

    if not isinstance(manifest, dict):
        return ExecutionResult(False, "Update manifest wasn't a JSON object.", error="bad_manifest")

    if not _verify_signature(manifest):
        return ExecutionResult(
            False,
            "Update manifest failed signature verification — ignoring it. This could "
            "mean tampering, a misconfigured server, or the optional 'cryptography' "
            "package isn't installed.",
            error="signature_invalid",
        )

    remote_version = _parse_version_tuple(manifest.get("version"))
    if remote_version is None:
        return ExecutionResult(False, "Update manifest has an unreadable version string.", error="bad_manifest")

    if remote_version <= _current_version_tuple():
        return ExecutionResult(True, f"You're up to date (v{VERSION}).", data={"update_available": False})

    return ExecutionResult(
        True,
        f"Update available: v{manifest.get('version')} (you have v{VERSION}).",
        data={
            "update_available": True,
            "version": manifest.get("version"),
            "url": manifest.get("url"),
            "sha256": manifest.get("sha256"),
            "notes": manifest.get("notes", ""),
        },
    )


def _lock_down_windows_dir(path: Path) -> None:
    """Best-effort owner-only ACL — icacls ships with every Windows install,
    so this needs no extra dependency. Failure here is never fatal: the
    random unguessable path is the primary defense, this just raises the bar
    further where the OS lets us."""
    if not IS_WINDOWS:
        return
    try:
        import subprocess
        username = os.environ.get("USERNAME", "")
        if not username:
            return
        subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(OI)(CI)F"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def _fresh_update_dir() -> Path:
    """
    Track A2 security fix: the old code wrote installers to a *predictable*
    filename (isha_update_<version>.exe) in the shared, world-writable system
    temp dir — any other local process could plant or swap that file. This
    creates a fresh, randomly-named, owner-only directory per download under
    Isha's own per-user app-data folder instead.
    """
    base = app_data_dir() / "updates"
    base.mkdir(parents=True, exist_ok=True)
    directory = base / secrets.token_hex(16)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    _lock_down_windows_dir(directory)
    return directory


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_and_verify(manifest_data: dict) -> ExecutionResult:
    """
    Downloads the installer named in an already-signature-verified manifest
    and checks its sha256 before returning the local path. Actually running
    the installer is a separate, confirmation-gated step (executor.apply_update),
    which re-verifies the hash again immediately before launch (see
    verify_installer_before_launch) to close the TOCTOU window between this
    check and that launch — this function never executes anything itself.
    """
    url = manifest_data.get("url")
    expected_sha256 = manifest_data.get("sha256")
    if not url or not expected_sha256:
        return ExecutionResult(False, "Manifest is missing a download URL or checksum.", error="bad_manifest")
    if not str(url).lower().startswith("https://"):
        return ExecutionResult(False, "Refusing to download an installer over a non-HTTPS URL.", error="insecure_url")

    try:
        with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as resp:
            data = resp.read()
    except Exception as e:
        return ExecutionResult(False, f"Couldn't download the update: {e}", error="download_failed")

    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256.lower() != str(expected_sha256).lower():
        return ExecutionResult(
            False,
            "Downloaded installer's checksum doesn't match the signed manifest — refusing to run it.",
            error="checksum_mismatch",
        )

    directory = _fresh_update_dir()
    dest = directory / f"{secrets.token_hex(8)}.exe"
    try:
        dest.write_bytes(data)
    except OSError as e:
        return ExecutionResult(False, f"Couldn't save the installer: {e}", error="io_error")

    return ExecutionResult(
        True, f"Update downloaded and verified: {dest}",
        data={"installer_path": str(dest), "sha256": str(expected_sha256)},
    )


def verify_installer_before_launch(installer_path: str, expected_sha256: str) -> ExecutionResult:
    """
    Track A2 fix (TOCTOU close): re-hashes the installer immediately before
    Popen, right in executor.apply_update, rather than trusting the hash
    check done at download time — closing the window during which a local
    process could have swapped the file to near-zero.
    """
    path = Path(installer_path)
    if not path.is_file():
        return ExecutionResult(False, "Installer file is missing.", error="missing_file")
    try:
        actual = _hash_file(path)
    except OSError as e:
        return ExecutionResult(False, f"Couldn't re-verify the installer: {e}", error="io_error")
    if actual.lower() != str(expected_sha256).lower():
        return ExecutionResult(
            False,
            "Installer's checksum changed since it was downloaded — refusing to run it.",
            error="checksum_mismatch",
        )
    return ExecutionResult(True, "Installer re-verified.")


def cleanup_stale_update_dirs() -> None:
    """
    Called once at startup (main.py / tray_app.py): removes downloaded-
    installer directories older than a day. Deleting an installer
    immediately after launching it risks breaking installers that keep
    reading from disk while they run, so cleanup happens on the *next*
    start instead, per Track A2's fix list.
    """
    base = app_data_dir() / "updates"
    if not base.is_dir():
        return
    now = time.time()
    for entry in base.iterdir():
        try:
            if entry.is_dir() and (now - entry.stat().st_mtime) > _STALE_UPDATE_DIR_SECONDS:
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            continue
