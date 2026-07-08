"""
Track A6: security regression suite. Locks in every Track A fix as an
executable assertion so none of them can silently regress. Stdlib
unittest only (no extra test-runner dependency) — run with:

    python -m unittest discover -s tests -v

Run from the repo root so the bare module imports (executor, a_updater, ...)
resolve; sys.path is adjusted below so `python tests/test_security_hardening.py`
also works directly.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import executor
import a_updater
from command_ir import CommandIR


class ModeScriptGatingTests(unittest.TestCase):
    """A1: a mode's `script` field must never run without an explicit,
    per-run human confirmation — never from an automatic trigger."""

    def setUp(self):
        executor.set_confirm_callback(None)

    def tearDown(self):
        executor.set_confirm_callback(None)

    def test_disabled_by_default_skips_script(self):
        config = {"settings": {}}  # allow_mode_scripts absent -> off
        result = executor._run_mode_script("calc.exe", config)
        self.assertTrue(result.success)
        self.assertEqual(result.data.get("skipped"), "disabled")

    def test_enabled_but_no_confirm_callback_skips_script(self):
        """This is exactly mode_scheduler's auto-trigger case: no confirm
        callback is ever supplied for a scheduled activation, so even with
        the setting on, the script must not run."""
        config = {"settings": {"allow_mode_scripts": True}}
        result = executor._run_mode_script("calc.exe", config)
        self.assertTrue(result.success)
        self.assertEqual(result.data.get("skipped"), "no_confirm")

    def test_enabled_with_declined_confirmation_skips_script(self):
        config = {"settings": {"allow_mode_scripts": True}}
        executor.set_confirm_callback(lambda ir: False)
        result = executor._run_mode_script("calc.exe", config)
        self.assertTrue(result.success)
        self.assertEqual(result.data.get("skipped"), "declined")

    def test_enabled_with_approved_confirmation_runs_script(self):
        config = {"settings": {"allow_mode_scripts": True}}
        seen = {}

        def fake_confirm(ir: CommandIR) -> bool:
            seen["action"] = ir.action
            seen["target"] = ir.target
            return True

        executor.set_confirm_callback(fake_confirm)

        launched = []
        original_popen = executor.subprocess.Popen
        executor.subprocess.Popen = lambda args, **kw: launched.append(args)
        try:
            result = executor._run_mode_script("echo hi", config)
        finally:
            executor.subprocess.Popen = original_popen

        self.assertTrue(result.success)
        self.assertFalse((result.data or {}).get("skipped"))
        self.assertEqual(seen["action"], "run_mode_script")
        self.assertEqual(seen["target"], "echo hi")
        self.assertTrue(launched)  # the script really did get launched, only after approval


class UpdaterHardeningTests(unittest.TestCase):
    """A2: unpredictable per-download install location + TOCTOU-closing
    re-verification before launch."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_app_data_dir = a_updater.app_data_dir
        tmp_path = Path(self._tmp.name)
        a_updater.app_data_dir = lambda: tmp_path

    def tearDown(self):
        a_updater.app_data_dir = self._old_app_data_dir
        self._tmp.cleanup()

    def test_update_dirs_are_random_and_distinct(self):
        first = a_updater._fresh_update_dir()
        second = a_updater._fresh_update_dir()
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_dir())
        self.assertTrue(second.is_dir())
        # not the old predictable "isha_update_<version>.exe" shared-temp scheme
        self.assertNotIn("isha_update_", str(first))

    def test_reverify_before_launch_accepts_untampered_file(self):
        directory = a_updater._fresh_update_dir()
        installer = directory / "installer.exe"
        installer.write_bytes(b"totally-a-real-installer")
        expected = a_updater._hash_file(installer)

        result = a_updater.verify_installer_before_launch(str(installer), expected)
        self.assertTrue(result.success)

    def test_reverify_before_launch_rejects_swapped_file(self):
        """Simulates a local process swapping the installer between download
        and launch (the TOCTOU window A2 closes)."""
        directory = a_updater._fresh_update_dir()
        installer = directory / "installer.exe"
        installer.write_bytes(b"totally-a-real-installer")
        expected = a_updater._hash_file(installer)

        installer.write_bytes(b"swapped-malicious-payload")

        result = a_updater.verify_installer_before_launch(str(installer), expected)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "checksum_mismatch")

    def test_cleanup_removes_only_stale_dirs(self):
        fresh = a_updater._fresh_update_dir()
        stale = a_updater._fresh_update_dir()
        old_time = __import__("time").time() - a_updater._STALE_UPDATE_DIR_SECONDS - 3600
        os.utime(stale, (old_time, old_time))

        a_updater.cleanup_stale_update_dirs()

        self.assertTrue(fresh.exists())
        self.assertFalse(stale.exists())


class ManifestSignatureTests(unittest.TestCase):
    """A3: the manifest signature must cover canonical JSON bytes, not an
    ambiguous pipe-delimited string."""

    @classmethod
    def setUpClass(cls):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            raise unittest.SkipTest("optional 'cryptography' package not installed")
        cls.private_key = Ed25519PrivateKey.generate()
        cls.public_key = cls.private_key.public_key()

    def setUp(self):
        self._old_key = a_updater.ISHA_UPDATE_PUBLIC_KEY_HEX
        a_updater.ISHA_UPDATE_PUBLIC_KEY_HEX = self.public_key.public_bytes(
            __import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.Raw,
            __import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.Raw,
        ).hex()

    def tearDown(self):
        a_updater.ISHA_UPDATE_PUBLIC_KEY_HEX = self._old_key

    def _signed_manifest(self, version="1.0.0", url="https://example.com/isha.exe", sha256="a" * 64):
        import base64
        payload = a_updater.canonical_manifest_payload(version, url, sha256)
        signature = self.private_key.sign(payload)
        return {"version": version, "url": url, "sha256": sha256, "signature": base64.b64encode(signature).decode("ascii")}

    def test_valid_canonical_signature_verifies(self):
        manifest = self._signed_manifest()
        self.assertTrue(a_updater._verify_signature(manifest))

    def test_tampering_any_field_after_signing_fails(self):
        manifest = self._signed_manifest()
        manifest["url"] = "https://evil.example.com/malware.exe"
        self.assertFalse(a_updater._verify_signature(manifest))

    def test_pipe_character_in_url_cannot_confuse_the_boundary(self):
        """The old pipe-delimited scheme made 'version|url|sha256' ambiguous
        if a field contained '|'. Canonical JSON has no such ambiguity."""
        manifest = self._signed_manifest(url="https://example.com/a|b.exe")
        self.assertTrue(a_updater._verify_signature(manifest))
        manifest["sha256"] = "b" * 64  # now genuinely tampered
        self.assertFalse(a_updater._verify_signature(manifest))


class AppPathTrustTests(unittest.TestCase):
    """A4: a path pulled from the (attacker-writable) app-registry cache must
    be re-validated at launch time, not trusted just because it's cached."""

    def test_nonexistent_path_is_never_trustworthy(self):
        self.assertFalse(executor._is_path_trustworthy("/no/such/planted/evil.exe"))

    def test_real_file_is_trustworthy_on_this_dev_platform(self):
        with tempfile.NamedTemporaryFile(suffix=".exe") as f:
            # On non-Windows dev platforms only existence can be meaningfully
            # asserted (no Program Files/App Paths concept); real Windows
            # additionally requires an allow-listed root or a live PATH hit,
            # which this bare tempfile deliberately does not satisfy.
            if executor.IS_WINDOWS:
                self.assertFalse(executor._is_path_trustworthy(f.name))
            else:
                self.assertTrue(executor._is_path_trustworthy(f.name))


if __name__ == "__main__":
    unittest.main()
