# Packaging Isha into a deliverable installer

This turns the Python source into **one file you can hand to anyone**:
`IshaSetup-x.y.z.exe`. Everything here **must run on a real Windows machine** —
you cannot build a Windows executable from Linux/WSL (the container this repo was
developed in can't do this step; that's why it's a runbook, not something already
built).

```
packaging/
  isha.spec          PyInstaller build recipe  (source -> dist\Isha\ app folder)
  isha.manifest      app manifest: per-user (asInvoker), DPI-aware
  version_info.txt   Windows exe version metadata (auto-synced from version.py)
  isha.iss           Inno Setup script  (app folder -> IshaSetup-x.y.z.exe)
  build.ps1          one command that runs both of the above (and optional signing)
  isha.ico           <-- YOU ADD THIS: the app/installer icon (see step 0)
```

---

## Prerequisites (install once, on Windows)

1. **Python 3.10+** — from python.org (the official installer includes Tkinter,
   which Isha's palette needs).
2. **App dependencies + PyInstaller:**
   ```
   pip install -r requirements.txt pyinstaller
   ```
   Install the optional Windows packages too, so the bundle includes them:
   ```
   pip install pywin32 pycaw comtypes pystray Pillow rapidfuzz cryptography
   ```
3. **Inno Setup 6** — https://jrsoftware.org/isdl.php (gives you `iscc`).

---

## Step 0 — add an icon

Create `packaging/isha.ico` (a real multi-size `.ico`, 16–256px). Any icon tool
or an online PNG→ICO converter works. Both the spec and the installer reference
it; if it's missing, the build still works but uses a default icon.

## Step 1 — build

From the **project root**:
```
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```
That produces:
- `dist\Isha\` — the app as a folder (you can run `dist\Isha\Isha.exe` to test)
- `dist\installer\IshaSetup-<version>.exe` — the thing you ship

To build just the app folder (skip the installer): add `-SkipInstaller`.

## Step 2 — smoke-test the build

Run `dist\Isha\Isha.exe`. Confirm the tray icon appears, the hotkey opens the
palette, a few commands work, and settings/onboarding windows render. This is
also **Track B1** — the first time the Win32 code runs on real Windows. Keep a
checklist of what works / breaks (the roadmap has the full list under Track B1).

## Step 3 — code-sign (when you have a cert — Track D3)

Until signed, Windows SmartScreen warns on first run. This is expected, not a
bug. Once you have an Authenticode cert (an **EV** cert clears SmartScreen
instantly; a standard OV cert builds reputation over time):
```
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -SignThumbprint <YOUR_CERT_THUMBPRINT>
```
This signs both `Isha.exe` and the installer. Verify with
`signtool verify /pa dist\installer\IshaSetup-<version>.exe`.

## Step 4 — the real update-signing key (do this ONCE, offline, before your first release)

The shipped code has a **placeholder** update public key, so every update
currently fails verification by design. Before distributing updates, generate the
real keypair (`tools\sign_manifest.py keygen` → paste the public half into
`a_updater.py` → `ISHA_UPDATE_PUBLIC_KEY_HEX`). **Keep the private key offline
forever** — a password manager or hardware key. Anyone with it can forge updates.
Never commit it. Then rebuild (Step 1) so the release contains the real public key.

---

## Release checklist (each version)

1. Bump `VERSION` in `version.py`.
2. `build.ps1` (signed, once you have a cert).
3. Smoke-test `dist\Isha\Isha.exe`.
4. Upload `IshaSetup-<version>.exe` to your release host (GitHub Releases /
   Cloudflare R2) — **not** into the website repo.
5. Update the download URL your Merchant-of-Record emails to buyers.
6. *(When the update feed is live)* publish a signed update manifest
   (`tools\sign_manifest.py sign ...`) so existing installs can update.

---

## Why per-user, not admin

Isha installs and runs **without Administrator rights** on purpose
(`isha.manifest` = `asInvoker`, `isha.iss` = `PrivilegesRequired=lowest`). It's a
single-user app that only touches the current user's apps and `%APPDATA%\Isha`.
Requiring elevation would add a UAC prompt on every launch, break "start with
Windows", and make SmartScreen warier. If *you* ever want to run it elevated for
testing, right-click → Run as administrator — but shipping it that way would hurt
every user. See `isha.manifest` for the full reasoning.
