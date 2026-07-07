# Isha — Threat Model

One page, honest about both sides. Isha is a single-user Windows desktop
assistant that runs with the privileges of the logged-in user, holds no
server-side account, and (per the product promise) sends nothing off the
machine unless the user explicitly asks it to.

## Trust boundary

**Isha defends the boundary between "this Windows user account" and
everything outside it.** Concretely:

- Another local user account on the same machine.
- A planted or tampered file dropped by something that isn't already running
  as this user (a USB drive, a download, a different account's cron/task).
- A malicious or compromised update server, or a manifest that gets
  tampered with in transit or at rest.
- A malicious or compromised license-signing process (mitigated by keeping
  license and update signing keys separate — see below).
- A hostile network (MITM, DNS spoofing) between this machine and any URL
  Isha is explicitly told to fetch.

**Isha explicitly does not defend against malware already running as this
user**, or a physically compromised machine (disk removed and read offline,
a keylogger already installed, etc.). Nothing that runs client-side, in any
product, meaningfully can — once code runs as you, it can do anything you
can, including reading Isha's own config and any DPAPI-protected secrets
(DPAPI ties data to the *user*, not to a still-running Isha process).
Advertising otherwise would be dishonest; this file exists so nobody has to
guess where the line is.

## What's actually dangerous in Isha, and how each is addressed

Isha's most dangerous surface isn't the command a human is watching type —
it's everything that can run *without* a human in the loop, or that reads a
file which is itself plain, user-editable JSON.

| Risk | Where | Mitigation |
|---|---|---|
| A mode's free-text `script` field is an arbitrary-process-launch primitive; auto-triggers used to fire it silently, unconfirmed. | `executor._run_mode_script`, `mode_scheduler.py` | Off by default (`settings.allow_mode_scripts`); requires a live, per-call confirm callback that shows the literal script text; auto-triggers never supply one, so a scheduled activation can never run a script — see A1 in `ROADMAP.md`. |
| Downloaded update installer sat at a predictable path in shared, world-writable temp; window between checksum-check and launch (TOCTOU). | `a_updater.py`, `executor.apply_update` | Random-named, owner-only directory under `%APPDATA%\Isha\updates\`; checksum re-verified immediately before `Popen`, not only at download time; stale directories cleaned up on next start. |
| Update manifest signature covered a pipe-delimited string, which is ambiguous if a field contains `|`. | `a_updater.canonical_manifest_payload` | Signs/verifies canonical, sorted-key JSON bytes instead, matching the license-signing scheme. |
| App-registry cache (`app_registry_cache.json`) is plain JSON, writable by any process running as this user; `open_app` used to launch whatever path was in it. | `executor._is_path_trustworthy` | Re-validated at launch time: the path must still exist and (on Windows) live under an allow-listed install root or currently be reachable via `PATH` — the cache is a convenience index, never an authority. |
| `%APPDATA%\Isha\` had no real access control (`os.chmod(0o600)` is a no-op on NTFS). | `platform_paths.app_data_dir` | Owner-only ACL applied via `icacls` once per process start — raises the bar from "any local process" to "a process already running as this user," the honest limit of what a single-user desktop app can enforce. |
| The stored license record (buyer email + raw key) sat in `config.json` in cleartext — the one piece of genuine PII Isha holds. | `a_licensing._store_license_record` / `_load_license_record` | Encrypted at rest with DPAPI (`CryptProtectData`) on Windows, tied to the OS user account; plaintext fallback only on non-Windows dev environments, which never ship. |
| Update and license signing use separate Ed25519 keypairs. | `a_updater.py` / `a_licensing.py` | Deliberate: a compromised license key only lets someone forge licenses (revenue impact); a compromised update key could run arbitrary code on every installed copy. Keeping them apart limits blast radius. |

## Regression coverage

`tests/test_security_hardening.py` locks in every fix above as an
executable assertion — run with `python -m unittest discover -s tests`.
These are the tests that must never go red again; a red result here means a
real security regression, not a flaky test.

## What's deliberately *not* hardened further (for now)

- **Enforcement of licensing stays a soft gate.** Hardening the license
  *store* is about protecting the buyer's PII, not about locking non-payers
  out — see `ROADMAP.md` Section 6 and `a_licensing.py`'s module docstring.
- **No Authenticode verification of the update installer yet** — that needs
  a real code-signing certificate (Track D3) to exist first; until then, the
  sha256-from-a-signed-manifest chain is the trust root, and it's kept
  airtight per the table above.
- **No defense against an already-running malicious process on this
  account.** See "Trust boundary" above — this is a limit of what any
  client-side desktop software can do, not an oversight.
