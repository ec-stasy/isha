# Isha — Project Roadmap & Plan

> A lightweight, fully-local Windows assistant that performs system actions via
> keyboard shortcuts, typed text, or voice. **Free and fully unlocked** — no
> licensing, no tiers; nothing leaves this machine. Headline feature: **Modes**
> — starting/closing a group of apps/websites together — plus assorted system
> utilities.
>
> **History note.** Cycles 1–3 designed and built a one-time-purchase model with
> an offline signed-license system and an "Isha Lite" free tier. **Cycle 5
> (2026-07-08) removed all of that** — the product is now simply free. The
> licensing material in Cycles 1–4 below is kept as a historical record; see
> **Cycle 5** at the end of this file for exactly what was stripped out.

---

# Cycle 1 — Foundation (Phases 1–6, complete 2026-07-06)

> Everything in Sections 1–7 below is **Cycle 1**: the full end-to-end spine,
> input layer, Modes 2.0, comfort/accessibility layer, support tooling, and the
> client half of offline licensing — all built and self-verified on WSL/Linux,
> pending real-Windows and visual verification. Cycle 2 (at the end of this
> file) is the plan for what comes next: security hardening first, then making
> the product actually real (verified on Windows, packaged, signed) and
> genuinely comfortable to live with day to day.

## 1. Current State (assessment)

**All six phases — 1 (Spine), 2 (Input layer), 3 (Modes 2.0 + utilities),
4 (Comfort), 5 (Support), and 6 (Commercialize) — are complete as of
2026-07-06.** One command now runs
fully end-to-end — typed text → parsed → resolved against a real app registry
→ executed → logged as a reproducible JSON-lines record — reachable three ways
(CLI, global hotkey, tray-driven command palette) plus a fourth, non-interactive
path (auto-triggers) and an optional fifth (voice), all funnelling through the
same pipeline function so behavior can't diverge. Modes are now a real context
switch (apps + websites, a script on activate, per-mode volume/theme,
best-effort window-layout restore, clean A→B switching, and typed shorthand to
set the script/volume/theme/layout fields without hand-editing config.json)
instead of just an app launcher. Auto-triggers cover time, on-battery,
app-launch, and idle. A website opened for a mode gets a best-effort dedicated
browser window that deactivation can actually close, instead of always being
reported unclosable. Phase 4 added real comfort/safety layers: an actual
yes/no confirmation (CLI prompt or palette dialog) instead of just refusing;
a single-level "undo"; custom aliases; a "help" cheat sheet; first-run
onboarding; live "did you mean" suggestions; toast/sound notifications; and an
optional Vosk-based voice-input module.

**Phase 5 (Support) adds one-click issue reporting and a signed auto-update
check**, both opt-in and both fail-closed by design:
- `a_issue_reporter.py` builds a local zip (system/version info + the last ~50
  already-redacted command-log records + an optional typed description),
  shows the user exactly what's in it, and never uploads anything —
  `send_report` is a separate, explicitly-confirmed action that refuses
  outright unless `settings.report_intake_url` is configured (HTTPS-only).
  There is no intake server behind that URL yet; standing one up (with
  dedup-by-signature, per the roadmap's Section 5) is future infrastructure
  work, not a client-side gap.
- `a_updater.py` checks a signed JSON manifest (`settings.update_manifest_url`,
  also opt-in and HTTPS-only), verifies its Ed25519 signature with the
  optional `cryptography` package before trusting anything in it, downloads
  the installer only after that, re-checks its sha256 against the manifest,
  and only *launches* it after a real confirmation prompt — never silently.
  Update checks are manual only (tray menu or typed "check updates"), not a
  background poller, so a plain install makes zero network calls it wasn't
  explicitly asked to make. `ISHA_UPDATE_PUBLIC_KEY_HEX` in that file is a
  placeholder (32 zero bytes) with no matching private key — every manifest
  correctly fails verification until it's replaced with the real product key
  as part of Phase 6's release pipeline. Both new tray menu items ("Report an
  issue", "Check for updates", "Install update...") route through
  `process_command_safe` exactly like typed commands; only "Install update"
  needs Tkinter (for its confirm dialog), so it's the one routed through the
  UI queue to run on the Tk thread rather than pystray's own callback thread.

**Phase 6 (Commercialize) adds offline signed licensing** — the client-side
half of Section 6's "sell once, fully local" model:
- `a_licensing.py` verifies a license key entirely offline: the key is
  `<hex(payload json)>.<hex(signature)>`, and `verify_license_string()`
  checks the Ed25519 signature (own keypair, separate from the updater's —
  a compromised license key would only let someone forge licenses, a much
  smaller blast radius than a compromised update key, so they're kept apart),
  the product field, and any expiry — entirely locally, no network call.
  Hex, not base64: Isha's own tokenizer (`input_processor.py`) lowercases
  everything and strips `+`/`/`/`=`, which would silently corrupt a
  case-sensitive base64 blob if a key were ever typed or pasted into the
  palette; hex is lowercase-safe and survives intact (verified directly —
  see Section 1's "verified by hand" list below).
- `activate_license`/`license_status`/`deactivate_license` (typed commands
  "activate license <key>", "license status"/"check license", "deactivate
  license") store/clear the verified key in `config["license"]`.
  `get_license_status()` **always re-verifies the stored key's signature**
  rather than trusting a cached `"licensed": true` flag — `config.json` is
  plain, user-editable JSON, so trusting a cached flag would make the whole
  gate defeatable with a text editor.
- `ISHA_LICENSE_PUBLIC_KEY_HEX` is a placeholder (32 zero bytes, no matching
  private key) exactly like the updater's — every license correctly fails
  verification until it's replaced with the real product public key.
  `tools/generate_license.py` is the seller-side counterpart: **not** part of
  the shipped app, **not** imported by anything in it, run by hand to (a)
  generate the real keypair (`keygen` — public half goes in
  `a_licensing.py`, private half stays offline, never committed) and (b)
  sign a license per sale (`sign --private-key ... --email ...`).
- **Enforcement is a deliberate soft gate, not a hard lock**: an unlicensed
  copy of Isha is fully functional. `main.py`'s CLI loop and `tray_app.py`
  each show a one-time-per-run, non-blocking reminder
  (`_show_license_reminder_if_unlicensed` / `_notify_license_status_if_unlicensed`)
  pointing at `activate license <key>`, and that's the entire enforcement
  surface. This is a considered choice, not an oversight: Section 6 of this
  file already says *"Don't over-engineer anti-piracy at this price
  point,"* and a hard lock would also brick every install before the real
  key is generated, or for any user without the optional `cryptography`
  package — directly contradicting "customer satisfaction second" for a
  feature whose only job is to say thank-you to paying customers, not to
  police non-paying ones. The verification mechanism itself is fully real
  and unforgeable without the private key; only its *consequence* is soft.
  Tightening this later (e.g. refusing specific actions when unlicensed) is
  a small, contained change — `a_licensing.is_licensed(config)` already
  exists as the one function such a change would call.
- Device fingerprinting (`_device_fingerprint()`) is computed and stored
  locally on activation, but — like Phase 5's report-intake endpoint —
  there is no online activation server to enforce the "2 devices" cap
  against yet; the fingerprint exists only so a human support conversation
  can reference "which machine" without needing one. Building that server
  is backend infrastructure work, not a client-side gap.
- **Not implemented in code, and can't be**: the Merchant-of-Record checkout
  (Paddle/Lemon Squeezy/Razorpay account setup, product listing, tax
  handling) and Authenticode/EV code-signing certificate are business/account
  setup and a purchased artifact, not something a codebase change can
  produce. They're the two concrete remaining action items before an actual
  sale can happen — see "What Phase 6 deliberately does NOT do yet" below.

**This pass also included a full security/correctness audit of the existing
codebase** (requested alongside Phase 5), which found and fixed several real
bugs predating this session, most notably in `command_parser.py`'s core
verb-matching loop:
- **Safety bug**: `AMBIGUOUS_VERBS` has always contained two-word entries
  ("turn on", "turn off", "switch on", "switch off"), but the loop only ever
  checked a *single* token against that set, so those entries could never
  match. In practice, "turn off wifi" (and "turn off"/"switch off" followed by
  almost anything) fell through to the bare `"turn off": "shutdown"` mapping —
  i.e. asking to disable Wi-Fi or Bluetooth triggered a full system-shutdown
  confirmation prompt instead of toggling the named target. Fixed by matching
  the two-word form before the one-word form, plus adding the missing
  `VERB_TARGET_ACTION_MAP` entries (`dnd`, `network`, `bt`, `backlight`, and
  full `switch on`/`switch off` coverage) that were causing the fallback in
  the first place.
- **Dead code**: several three-word `VERB_ACTION_MAP` keys ("shut down app",
  "send to taskbar", "take me to", and a few Hinglish ones) were unreachable —
  the lookup only ever tried a two-word join. Worse, "shut down app notepad"
  matched the two-word "shut down" → shutdown *before* ever reaching the
  (unreachable) three-word key, turning "close this one app" into the same
  accidental shutdown prompt. Fixed by trying the three-word form first.
- **Target leakage**: shape functions like `free_target` only recognized a
  *whole* multi-word verb phrase as filterable (checking one token at a time
  against `VERB_ACTION_MAP`), so a multi-word verb's individual words (e.g.
  "down" in "close down", "to"/"taskbar" in "send to taskbar") used to leak
  into the parsed target. Fixed generically: the parser now slices out
  exactly the matched verb span before calling the shape function, so every
  shape function gets a clean target without needing its own fix — except the
  handful (mode-field setters, `alias_pair`, `report_issue`) whose *own*
  trigger word doubles as the field/value boundary, which were updated to not
  assume that word is still present.
- **Functional bug**: the clipboard-history background poller
  (`a_clipboard_history.ClipboardHistory`) was fully implemented but its
  `.start()` was never called anywhere — `show clipboard history` always
  reported empty. Fixed by starting (and stopping on quit) the poller in
  `tray_app.py`, alongside `ModeScheduler`.
- **Efficiency**: `app_registry.get_app_registry()` re-read and re-parsed its
  disk cache file on every call with no in-memory memoization — including
  once per keystroke from the palette's live "did you mean" suggestions.
  Added an in-process cache layer on top of the existing disk-cache TTL, so
  a typing session no longer re-hits disk for data that can't have changed
  within the process's lifetime.

**A second, Phase-6-triggered audit pass on `logger.py` found and fixed a real
PII leak**, predating this session, in the sensitive-action redaction path
itself: `log_command()` redacted `raw_input` and the structured
`command_ir`/`resolved_ir`/`execution_result.data` fields for a sensitive
action, but never the raw **token list** or the execution result's
**message** string — both can carry the exact same content in the clear,
right next to the redacted copies, which defeats the redaction rather than
just being incomplete. Concretely: building `activate_license`'s log record
put the full plaintext license key (which decodes to the buyer's email) in
the `"tokens"` array, and `activate_license`/`license_status`'s own success
messages ("License activated for buyer@example.com...") were logged
verbatim — un-redacted — one field over from the correctly-redacted `data`
dict. The same gap applied to every pre-existing sensitive action too (e.g.
`search`'s message echoes the resolved URL/query in full). Fixed by redacting
`tokens` and `execution_result["message"]` the same way as every other field
when `action in SENSITIVE_ACTIONS`; re-verified by activating a real test
license and grepping the resulting log file for the plaintext email, license
key, and a test search query — none present after the fix (all three were
present before it).

Verified by hand on WSL/Linux (mode CRUD, resolver fuzzy-matching, confirmation
gating incl. confirm/deny callbacks, redaction (including the fixed
tokens/message leak above), undo of
open/close/create/delete-mode/activate/deactivate/mute, the mode-field parser
syntax, the fixed bare-domain tokenization, the fixed multi-word verb matching
— re-tested against ~35 phrasings covering every affected action plus every
previously-working one to confirm no regressions — app-launch/idle trigger
edge-detection logic, issue-report zip building/content, update-manifest
signature verification (valid/tampered/missing-signature all behave
correctly), the full license verify/activate/status/deactivate cycle against
a real generated Ed25519 keypair (correct-key success, tampered-signature
rejection, wrong-product rejection, expired rejection, and the shipped
placeholder key failing closed against a validly-signed license as expected),
and every utility's graceful-degradation path, all exercised directly);
Windows-only pieces — the Phase 1 handlers (volume, brightness,
window management, power actions), the Phase 2 global hotkey (`RegisterHotKey`
via ctypes), Phase 3's window-layout restore (`win32gui.SetWindowPos`),
recycle-bin emptying (`SHEmptyRecycleBinW`), clipboard polling
(`win32clipboard`), snippet typing (`SendInput`), and on-battery trigger
(`GetSystemPowerStatus`), Phase 4's window-rect capture (`GetWindowRect`),
dedicated-window website tracking (`--new-window` + hwnd enumeration +
`WM_CLOSE`), idle detection (`GetLastInputInfo`), and voice input
(`sounddevice`/Vosk), and Phase 5's installer launch (`subprocess.Popen` on a
downloaded, checksum-verified `.exe`) — are implemented but **not yet run on
real Windows**. Tkinter/pystray/Pillow/pywin32/vosk/sounddevice aren't
installed in this dev environment either, so the palette, tray icon,
confirmation dialogs, live suggestions, and every Windows-only utility are
implemented and reviewed but not visually tested. `cryptography` (needed for
real signature verification, both updates and licenses) *is* available here
and was used to test the verify/reject logic directly, end to end, with real
generated keypairs. That's the next thing to verify before building on top
of any of it.

Pipeline:

```
main.py / tray_app.py / mode_scheduler.py → input_processor → command_splitter
        → command_parser → CommandIR → c_resolver_validator (resolve+validate)
        → executor (+ undo_manager) → logger
```

`main.process_command_safe()` is the single reusable entry point for all four
non-voice input paths (CLI loop, hotkey trigger, palette submit, scheduled
trigger) — it never raises, always returns a structured per-sub-command
outcome, and logs a crash record instead of propagating an exception into
whichever front end called it. It now also accepts an optional
`confirm_callback` so each front end can supply its own real confirmation UI
for destructive actions (CLI `input()`, palette `messagebox`) — front ends
that don't pass one (the scheduler's auto-triggers) keep the old, safe-by-
default behavior: destructive actions simply refuse.

| File | Status | Notes |
|------|--------|-------|
| `input_processor.py` | ✅ working, bug fixed (2026-07-06) | tokenize, normalize, word→int; now keeps dots sandwiched between word characters (e.g. `youtube.com` stays one token) while still stripping stray/trailing punctuation, so bare domains classify correctly as websites in a mode's app list. Side effect: decimal-looking input like `5.5` now survives as a string instead of being mangled into `55` — arguably a related fix, not a regression. |
| `command_splitter.py` | ✅ working, bug fixed (2026-07-06) | splits multi-command sentences; now recognizes `create`/`update`/`make`/`new`/`add` + `mode` sentences and stops splitting on bare "and" inside the app/website list (e.g. "create study mode chrome and youtube" no longer breaks in two) |
| `command_parser.py` | ✅ updated, bugs fixed (2026-07-06) | verb→action mapping, ambiguous-verb resolution, English + Hinglish, mode-aware; extended with Phase 3 utility vocabulary, Phase 4's mode-field setters/aliases/undo/help, Phase 5's `check updates`/`install update`/`report issue`/`send report`, and Phase 6's `activate license`/`license status`/`check license`/`deactivate license`. Audit fixes: the main loop now matches two-word ambiguous verbs (`turn on`/`turn off`/`switch on`/`switch off`) and three-word `VERB_ACTION_MAP` phrases before falling back to shorter ones — previously "turn off wifi" (and similar) fell through to `"turn off": "shutdown"` and triggered a full shutdown confirmation instead of toggling the named target, and three-word keys like "shut down app" were unreachable entirely. The parser also now slices the matched verb span out of the token list before calling each action's shape function, fixing target-leakage for multi-word verbs (e.g. "close down chrome" no longer parsed a target of "down chrome") |
| `command_ir.py` | ✅ working | `CommandIR` contract: action / target / params / errors / warnings |
| `platform_paths.py` | ✅ new | resolves `%APPDATA%\Isha` (Windows) / `~/.isha` (dev), used by config/logs/cache |
| `config_store.py` | ✅ updated | atomic, backed-up-on-corruption JSON store at `%APPDATA%\Isha\config.json` — modes (`script`/`system_state`/`window_layout`, now also settable via typed commands), `active_mode`, aliases, hotkeys, settings (incl. `onboarded`, `voice_hotkey`), reminders, `triggers`, `snippets`, and Phase 6's `license` (the verified key record, or `None`) |
| `logger.py` | ✅ updated, PII-leak fixed (2026-07-06) | rotating JSON-lines log per command (raw input → tokens → CommandIR → resolution → execution result) + crash log; redacts sensitive actions (`set_reminder`, `schedule_task`, `add_task`, `search`, `open_url`, `show_clipboard_history`, `expand_snippet`, and Phase 6's `activate_license`/`license_status`) in every field. Audit fix: redaction previously covered `raw_input` and the structured `command_ir`/`resolved_ir`/`execution_result.data` fields but not the raw **token list** or the execution result's **message** string — both could carry the same sensitive content (a license key, a buyer's email, a search query) in the clear right next to the redacted copies, defeating the point. Both are now redacted the same way as everything else |
| `app_registry.py` | ✅ updated, efficiency fix (2026-07-06) | scans PATH exes + `App Paths` registry + Start Menu `.lnk` shortcuts (pywin32), merged and cached to disk with a 24h TTL; now also memoized in memory (same TTL) so repeated calls within one run — e.g. the palette's live suggestions on every keystroke — don't re-read/re-parse the disk cache each time |
| `c_resolver_validator.py` | ✅ updated | fuzzy-matches app/mode targets (`rapidfuzz`, falls back to `difflib`) against a confidence threshold — below it, asks via a warning instead of guessing; validates URL schemes (http/https only); flags destructive actions with `requires_confirmation` (now incl. `empty_recycle_bin`, and Phase 5's `send_report`/`apply_update` since both are risky enough — data egress / running a downloaded installer — to need the same explicit gate even though they aren't "destructive" to local state); classifies each mode-list item as an app or a website; validates mode existence for the Phase 4 mode-field actions too. Phase 6's license actions need no resolution step (the target is either absent or an opaque key string), so this file is unchanged by Phase 6 |
| `executor.py` | ✅ updated | dispatch table now covers 60 actions; every handler returns a structured `ExecutionResult`, never a silent side-effect; destructive/risky actions (`shutdown`, `restart`, `hibernate`, `uninstall_app`, `delete_mode`, `empty_recycle_bin`, `send_report`, `apply_update`) are hard-gated behind `requires_confirmation` + `confirmed`, backed by a real confirm/deny UI (see `main.py`/`command_palette.py`/`tray_app.py`); `uninstall_app` deliberately opens Windows Settings rather than auto-uninstalling; `copy_item`/`rename_item` deliberately unimplemented (parser gives free text, not validated paths — guessing wrong risks real files); `activate_mode`/`deactivate_mode` do Modes 2.0's clean switching, script-on-activate, system-state, and window-layout work, plus Phase 4's dedicated-window website tracking so a website item can actually be closed (in-session only, and — known limitation — the wait for the new window blocks the calling thread for up to a few seconds per site); `capture_mode_layout`/`set_mode_script`/`set_mode_volume`/`set_mode_theme`/`add_alias`/`remove_alias`/`undo_last_action`/`show_help` (Phase 4), Phase 5's `report_issue`/`send_report`/`check_for_updates`/`apply_update`, and Phase 6's `activate_license`/`license_status`/`deactivate_license` handlers (none of the three license actions need `requires_confirmation` — they're local-only and freely reversible by re-entering the key) |
| `a_mode_manager.py` | ✅ updated | create/update/delete/get against the config store, plus `get_mode_script`/`get_mode_system_state`/`get_mode_window_layout`/`set_active_mode` and Phase 4's typed setters `set_mode_script`/`set_mode_volume`/`set_mode_theme`/`set_mode_window_layout` — the fields are still config-editable too, but no longer config-*only* |
| `execution_result.py` | ✅ new | shared `ExecutionResult(success, message, data, error)` dataclass used by both executor and mode manager |
| `undo_manager.py` | ✅ new | in-memory-only bounded stack (depth 10) of reversible-action records for `open_app`/`close_app`/`activate_mode`/`deactivate_mode`/`create_mode`/`delete_mode`/`mute_volume`; `main.process_command` snapshots pre-execution state and records a builder-produced undo entry after every successful execute; `undo_last_action` pops and re-runs the inverse through the same `executor.execute` — never persisted, and never records anything for actions with no safe inverse (shutdown, empty_recycle_bin, uninstall) |
| `a_notifications.py` | ✅ new | toast/sound layer with no new required dependency — prefers the tray's `pystray` `icon.notify()` (registered by `tray_app.py`), falls back to a console print; optional `winsound` beep on Windows |
| `main.py` | ✅ updated | exposes `process_command`/`process_command_safe` (structured, non-raising) as the shared entry point for all four non-voice input paths; both now accept an optional `confirm_callback` for real destructive-action confirmation; wires `undo_manager` snapshot/record around every `execute()` call; CLI loop prompts via `input()` for confirmation and shows a one-time onboarding message on first run |
| `hotkey_listener.py` | ✅ new | global hotkey via ctypes `RegisterHotKey` + its own `GetMessageW` loop on a background thread — no extra dependency; Windows-only, explicit error string set (not raised) on other platforms or if the combo is already taken; `tray_app.py` now runs two instances (palette hotkey + optional voice hotkey) |
| `command_palette.py` | ✅ updated | borderless, always-on-top Tkinter window; one entry box + live "did you mean" suggestion line + output label; Enter runs a command through `main.process_command_safe` with a real `messagebox.askyesno` confirmation dialog for destructive actions, Escape closes; shows a one-time onboarding message on first open; high-contrast colors, large font, full keyboard nav, plain-sentence output for screen readers |
| `tray_app.py` | ✅ updated | wires tray icon (`pystray`) + hotkey listener + voice hotkey listener + palette + `ModeScheduler` + clipboard-history poller together via a thread-safe queue (hotkey/tray/scheduler threads never touch Tkinter directly); registers the tray icon with `a_notifications` for toasts; three new Phase 5 menu items ("Check for updates", "Install update...", "Report an issue") — the first two are read-only/local and run on a background thread, "Install update" needs a real confirm dialog so it's the only one routed through the UI queue to run on the Tk thread; every optional piece fails with a clear printed message and keeps the rest running rather than crashing the process. Audit fix: now actually calls `.start()`/`.stop()` on the clipboard-history poller, which previously existed but was never started anywhere |
| `mode_scheduler.py` | ✅ updated | auto-triggers: background poller (20s) for `config["triggers"]` — time-based (fire-once-per-minute dedup, optional day-of-week filter), on-battery (edge-triggered via `GetSystemPowerStatus`), and Phase 4's app-launch (edge-triggered via `a_application_manager.is_app_running`) and idle (`GetLastInputInfo`-based, re-arms once the user is active again) — fires through `main.process_command_safe` and posts a toast via `a_notifications` so a background activation isn't silent |
| `a_application_manager.py` | ✅ new | `list_installed_apps` (wraps `app_registry`); `is_app_running` via `tasklist` (Windows-only, defaults to `False` elsewhere — a false negative just re-launches an already-running app, harmless) |
| `a_check_disk_space.py` | ✅ new | `shutil.disk_usage`-based free/used/total report; stdlib only, works on every OS |
| `a_check_internet.py` | ✅ new | raw TCP connect probe to a public DNS resolver (no HTTP request, no payload) — only runs on direct user request, never in the background |
| `a_screenshot.py` | ✅ new | full-desktop capture via Pillow's `ImageGrab`, saved locally to `Pictures\Isha Screenshots`; never uploaded |
| `a_clipboard_history.py` | ✅ new, bug fixed (2026-07-06) | capped, in-memory-only clipboard history (never written to disk, since clipboard content routinely includes secrets); Windows-only (`win32clipboard`), explicit error elsewhere. Audit fix: the poller thread was fully implemented but `.start()` was never called anywhere in the codebase, so this feature always silently reported an empty history — now started/stopped by `tray_app.py` |
| `a_pomodoro.py` | ✅ updated | focus/pomodoro timer optionally tied to a mode — activates the mode for the work interval, deactivates for the break interval, repeats until stopped; phase changes go through `a_notifications` (toast + optional beep) instead of a bare `print` |
| `a_voice_input.py` | ✅ new | optional module (Vosk + `sounddevice`), imported only when the voice hotkey fires; `is_available()`/`listen_and_transcribe()` degrade to `False`/`None` if either dependency or the downloaded model is missing — never a crash, never phones home (offline model, matches "no data leaves the machine") |
| `version.py` | ✅ new | single `VERSION` string constant — compared against update manifests and stamped into issue reports |
| `a_issue_reporter.py` | ✅ new | builds a local zip (`system_info.json`, last ~50 redacted `commands_log.jsonl` lines, optional `description.txt`, and a `manifest.txt` listing exactly what's included) under `%APPDATA%\Isha\reports\`; `build_report()` never touches the network; `send_report()`/`latest_report_path()` are separate, only upload if `settings.report_intake_url` is set and HTTPS |
| `a_updater.py` | ✅ new | `check_for_update()` fetches `settings.update_manifest_url` (opt-in, HTTPS-only, manual — no background polling) and verifies its Ed25519 signature via the optional `cryptography` package before trusting it; fails closed (never reports an update as available) if unconfigured, unreachable, unsigned, or `cryptography` isn't installed. `download_and_verify()` re-checks the installer's sha256 against the signed manifest before ever handing a path back. `ISHA_UPDATE_PUBLIC_KEY_HEX` is a placeholder — must be replaced with the real product key (private half kept offline) before a real update feed goes live |
| `a_licensing.py` | ✅ new (Phase 6) | offline Ed25519 license verification — key format `<hex(payload json)>.<hex(signature)>` (hex, not base64, so it survives `input_processor.py`'s lowercase-and-strip tokenizing intact); `verify_license_string()` checks signature + product + expiry entirely locally; `activate_license`/`deactivate_license`/`get_license_status` manage `config["license"]`, always **re-verifying** the stored key's signature rather than trusting a cached flag; `_device_fingerprint()` is local-only bookkeeping (no online cap-enforcement server exists yet); `ISHA_LICENSE_PUBLIC_KEY_HEX` is a placeholder (own keypair, separate from the updater's) — every license fails verification until it's replaced with the real product public key |
| `tools/generate_license.py` | ✅ new (Phase 6) | seller-side-only offline CLI, **not** imported by the app and **not** shipped to customers: `keygen` generates the real Ed25519 product keypair (public half → `a_licensing.py`, private half stays offline, never committed); `sign --private-key ... --email ...` signs one license per sale |

**Key architectural asset:** `CommandIR` is deterministic and serializable. Logging
it means any parse bug is perfectly reproducible from a single log line — the
foundation for both debugging and issue reporting. This is now wired up in
`logger.py`, not just a design intention.

**What Phase 1 deliberately does NOT do yet (by design, not oversight):**
- No real confirmation UX — destructive actions currently just refuse and say so.
- Volume/brightness/wifi/bluetooth/DND/night-light/airplane-mode toggles: only
  volume and dark/light theme are implemented; the rest return an explicit
  "not yet implemented" result rather than a fake success.
- Window snap/resize/move (the interactive `snap_window`/`resize_window`/
  `move_window` actions, e.g. "snap chrome left"): still `_not_yet_implemented`.
  Phase 3 added per-mode window-layout *restore* instead (a stored `{x,y,w,h}`
  applied via `SetWindowPos` on activate) — a different mechanism, not this one.
- No background scheduler for one-off reminders/tasks: they're persisted to the
  config store but nothing fires them yet (Phase 3's `mode_scheduler.py` only
  fires mode auto-triggers, not arbitrary reminders).
- `requirements.txt` lists `rapidfuzz`/`pywin32`/`pycaw`/`comtypes` as optional —
  every feature that needs one checks for it and fails explicitly if missing.

**What Phase 2 deliberately does NOT do yet (by design, not oversight):**
- No confirmation dialog in the palette for destructive actions — same gate as
  the CLI applies (refuses, explains why); a real confirm UI is Phase 4.
- No hotkey re-binding UI — `config["settings"]["hotkey"]` can be edited by hand
  in `config.json`, defaulting to `ctrl+alt+space`; a settings window is Phase 3/4.
- No fuzzy/autocomplete suggestions *while typing* in the palette — it runs the
  full command on Enter only; live suggestions are a Phase 4 comfort feature.
- No packaging yet (PyInstaller/Nuitka) — `tray_app.py` runs from source only.
- Tray icon is a placeholder generated shape, not real product art.

**What Phase 3 deliberately does NOT do yet — status after Phase 4:**
- ~~No parser syntax for a mode's `script`/`system_state`/`window_layout`
  fields~~ — **fixed in Phase 4**: `"<mode> mode script <command>"`, `"<mode>
  mode vol <0-100>"`, `"<mode> mode theme dark|light"`, and `"<mode> mode
  layout"` (captures the current window positions of the mode's open apps) are
  now typed commands; config.json editing still works too.
- ~~Bare domains with a dot don't classify as websites~~ — **fixed in
  Phase 4**: the tokenizer now keeps a dot when it sits between two word
  characters, so `youtube.com` survives as one token.
- Auto-triggers now cover time-of-day, on-battery, app-launch, and idle
  (**app-launch and idle added in Phase 4**) — no headphone-plugged-in or other
  device-event triggers yet; `config["triggers"]` records outside those four
  `type`s are simply never matched.
- ~~Deactivating a mode can't close a website's browser tab~~ — **improved in
  Phase 4**: a website item is now opened in its own dedicated browser window
  (via the default browser's `--new-window`/`-new-window` flag) and the window
  handle is tracked in-memory for the running session, so deactivation can
  send it a real `WM_CLOSE`. This is still best-effort, not a full fix: it only
  works if the browser actually honors the new-window flag, only within the
  same running Isha process (the tracking table isn't persisted), and it
  closes a *window*, not a specific tab if the user later merged it into
  another window.
- Text snippets still expand by literally typing the expansion via
  `SendInput` (Windows only) — **deliberately still not** a system-wide "type a
  trigger phrase, auto-replace" keyboard hook. This was reaffirmed in Phase 4:
  a low-level keyboard hook is a real keylogging-risk primitive, and adding one
  isn't worth it for a snippet-expansion convenience feature. Security first.
- ~~Pomodoro phase changes print to the console~~ — **fixed in Phase 4**: they
  now go through `a_notifications` (toast via the tray icon when running,
  console fallback otherwise, optional beep).
- No packaging or real icon/asset work for any of the utilities — still out of
  scope; that's Phase 5/6 territory (installer + code-signing).

**What Phase 4 deliberately does NOT do yet (by design, not oversight):**
- Undo is single-level and covers only actions with an unambiguous, safe
  inverse (open/close app, activate/deactivate mode, create/delete mode,
  mute/unmute). Destructive actions with no safe inverse (`shutdown`,
  `empty_recycle_bin`, `uninstall_app`) never get an undo record — there is
  nothing safe to undo them with, and pretending otherwise would be dangerous.
- Volume-level changes aren't undoable — reading the *current* level back
  reliably needs `pycaw`, and without a "before" snapshot there's nothing
  correct to restore, so this was left out rather than guessing.
- The confirmation dialog is a plain yes/no (`input()` on the CLI,
  `messagebox.askyesno` in the palette) — no "type the app name to confirm"
  friction step, no per-action skip-next-time setting.
- Live palette suggestions are a simple prefix/substring match over app and
  mode names (no typo-tolerant fuzzy ranking) — enough to be a "did you mean"
  hint without adding a heavier matching pass on every keystroke, matching the
  "keep it lightweight" guardrail.
- Voice input requires the user to separately install `vosk` + `sounddevice`
  and download a Vosk model — there's no in-app model download/installer yet;
  it's a fixed-duration (4s) recording per hotkey press, not continuous
  listening or true push-to-talk (hold-to-record).
- No first-run setup *wizard* — onboarding is a single printed/shown message,
  not a guided walkthrough with screenshots.
- Aliases are a flat word→canonical-name map with no namespacing or per-mode
  scoping.

**Known minor limitations found during the Phase 5 audit but deliberately left
alone (low-value/high-risk to fix blind):**
- `_open_website_item`'s wait for a mode's new browser window (up to 3s,
  polled) runs synchronously inside `activate_mode`, so activating a mode with
  website items can briefly block whichever thread called it — including the
  palette's Tk main thread if triggered by typed input there. Not fixed this
  pass: making it properly asynchronous would mean reworking how the palette
  calls `process_command_safe` (currently synchronous, matching its
  render-immediately design), and that's not something to change blind
  without a real Tkinter environment to verify against.
- `("remove", "app")`/`("delete", "app")` → `uninstall_app` still leaks the
  discriminator word "app" into the parsed target (e.g. "remove app chrome"
  → target `"app chrome"` instead of `"chrome"`), same root cause as the
  target-leakage bug fixed above but for a target-token discriminator rather
  than a verb — fuzzy-matching in `c_resolver_validator.py` mostly absorbs the
  extra word, but "uninstall chrome" (the primary phrasing, unaffected) is the
  reliable form. Left alone because fixing it generically risks breaking
  `("turn on"/"turn off", "wifi"/"volume"/...)` entries where the target token
  *is* meaningful data, not a discriminator to drop — that distinction isn't
  currently represented anywhere in `VERB_TARGET_ACTION_MAP`.

**What Phase 5 deliberately does NOT do yet (by design, not oversight):**
- No intake server. `send_report` refuses outright unless
  `settings.report_intake_url` is configured — there's no Isha-run endpoint to
  point it at yet. Standing one up, with dedup-by-error-signature (Section 5),
  is backend work, not a client gap.
- No background/periodic update checking — "check updates" is manual only
  (typed command or tray menu). This is deliberate, not a missing feature: it
  keeps the "nothing leaves this machine unless asked" promise airtight for a
  plain install. An opt-in periodic check could be added later behind its own
  setting if users want it.
- `ISHA_UPDATE_PUBLIC_KEY_HEX` in `a_updater.py` is a placeholder (32 zero
  bytes, no matching private key) — every real manifest will correctly fail
  verification until it's replaced with the actual product key generated by
  `tools/generate_license.py keygen` (or any equivalent Ed25519 keygen) as
  part of shipping a real release. This is intentional fail-closed behavior,
  not a bug: shipping with a placeholder that verified anything would be worse.
- `apply_update` only launches the downloaded, checksum-verified installer
  (`subprocess.Popen`) and lets it show its own UI — there's no silent-install
  flag handling or auto-restart, since what the actual installer looks like
  is itself part of the packaging work still outstanding (see "What Phase 6
  deliberately does NOT do yet" below).
- Issue reports include OS/Python version and redacted command-log lines
  only — no automatic screenshot attachment or system-specs dump (CPU/RAM/GPU)
  beyond `platform.platform()`; kept intentionally minimal per the "opt-in and
  transparent" promise rather than bundling more "just in case."

**What Phase 6 deliberately does NOT do yet (by design, not oversight):**
- **No hard license enforcement.** An unlicensed copy of Isha is fully
  functional — see `a_licensing.py`'s module docstring and Section 1's Phase 6
  writeup above for the full reasoning (this file's own Section 6 already
  says not to over-engineer anti-piracy at this price point, and a hard lock
  would brick every install before the real key exists). If the business
  ever wants to tighten this, `a_licensing.is_licensed(config)` is the one
  function a stricter gate would call — it's already correct and tested,
  only its consequence would need to change.
- **No online activation server.** `_device_fingerprint()` is computed and
  stored locally on activation, but nothing enforces the "2 devices" cap
  against it — there's no server to ask. Same category of gap as Phase 5's
  missing report-intake endpoint: backend infrastructure, not a client bug.
- **No Merchant-of-Record integration.** Paddle/Lemon Squeezy/Razorpay account
  setup, product listing, checkout flow, tax handling, and license-key email
  delivery are all manual, external, business/account steps — nothing in this
  repo talks to a payment processor, and nothing should until an actual
  account exists to configure. This is the single biggest remaining item
  before Isha can actually be sold.
- **No code-signing.** Windows Authenticode/EV certificates are a purchased,
  identity-verified artifact from a CA, not something a codebase change can
  produce. Until binaries are signed, Windows SmartScreen will warn on first
  run of any built installer — expected, not a bug in this code.
- **No installer/packaging step at all yet.** `tray_app.py` still runs from
  source; PyInstaller/Nuitka packaging (mentioned since Phase 1/2's "Stack"
  notes) hasn't been done. The license/update/report mechanisms are all built
  and tested against running from source — packaging is the next concrete
  step, not a redesign.
- `tools/generate_license.py`'s `--max-devices` field is recorded in every
  license's payload but, per the no-activation-server point above, is
  informational only right now — nothing reads or enforces it yet.

**Next up:** run this on real Windows to shake out every untested Win32 path —
Phase 1's (volume/theme registry writes, window enumeration, shutdown/lock/sleep
calls), Phase 2's (global hotkey registration), Phase 3's (window-layout
`SetWindowPos`, `SHEmptyRecycleBinW`, `win32clipboard` polling, `SendInput`
snippet typing, `GetSystemPowerStatus` battery trigger), Phase 4's
(`GetWindowRect` layout capture, the dedicated-window website tracking,
`GetLastInputInfo` idle detection, and — with `vosk`/`sounddevice` actually
installed — the voice-input path), and Phase 5's (the installer-launch step of
`apply_update`, and the three new tray menu items) — and visually test the
palette/tray/confirmation-dialog/utilities with `pystray`/`Pillow`/Tk/`pywin32`
actually installed, since none of them exist in this dev container. Also worth
doing before relying on it: point `settings.update_manifest_url` at a real
signed manifest (with the real product key swapped in) and confirm the whole
check → download → verify → launch chain end-to-end on Windows. For Phase 6
specifically: run `tools/generate_license.py keygen` for real, paste the
public half into `a_licensing.py`, sign a real license and confirm
`activate license` on real Windows; then start on the genuinely outstanding
work — an actual PyInstaller/Nuitka build, a Merchant-of-Record account, and
a code-signing certificate — since none of those are code changes this
codebase can make on its own.

---

## 2. Finish the Spine (must precede all "features")

Nothing ships until one command runs end-to-end.

1. **`executor.py`** — dispatch table `action → handler`, mirroring `ACTION_FUNCTION_MAP`.
   Handlers wrap Win32 / `ctypes` / `subprocess`. Every handler returns a structured
   result (success/failure/message); never silent side-effects.
2. **App/URL resolver** (`c_resolver_validator.py`) — build an **app registry** by scanning
   Start-Menu `.lnk` shortcuts, `HKLM/HKCU ...\App Paths` registry keys, and `PATH`. Cache it.
   Use **`rapidfuzz`** for fuzzy matching with a confidence threshold; below threshold →
   disambiguate/ask instead of guessing.
3. **State/config store** — one small JSON or SQLite file in `%APPDATA%\Isha\`: modes,
   user aliases, hotkey bindings, settings. Backs the mode feature.
4. **Mode engine** (`a_mode_manager.py`) — activate/deactivate/create/update/delete against
   the store. Parser already emits `activate_mode`, `create_mode`, params `add`/`remove`/`new`.

**Stack (keeps it lightweight):** pure Python + `pywin32`/`ctypes`. Tray via `pystray`,
small borderless windows via Tkinter. Package with **PyInstaller** (one-folder, fast start)
or **Nuitka** (smaller/faster). No Electron, no Qt. Idle RAM in tens of MB, not hundreds.

---

## 3. New Functionalities — make Modes the killer feature

**Modes 2.0** = a full context switch, not just an app launcher:

- Launch/close apps **and** websites
- **Restore window layout** — positions, sizes, monitor, snap zones (parser already
  handles `snap`/`move`/`resize` directions)
- **System state per mode** — volume, brightness, DND/night-light, Wi-Fi/Bluetooth
- **Run a script/command** on activate
- **Auto-triggers** — time-based ("Work mode at 9am"), on-event (headphones → Focus,
  on-battery → Power-saver)
- **Clean switching** — A→B closes A's apps not in B, opens B's delta only

Small set of high-value utilities (each is a cheap handler):

- **Command palette / quick launcher** — Spotlight-style borderless bar on a hotkey,
  fuzzy search. Becomes the primary UI and makes everything discoverable.
- **Clipboard history** (lightweight, capped, local)
- **Text snippets / expansion**
- **System utilities** — disk-space & internet checks (already stubbed), screenshot,
  lock, empty recycle bin, quick toggles
- **Focus/Pomodoro timer** tied to a mode

Guardrail: keep the core tiny; heavy things (voice, etc.) are **optional modules**
loaded on demand.

---

## 4. Comfort & Accessibility

- **Three input paths, one brain** — hotkey/palette, typed text, and voice all produce
  the same token list feeding the existing parser.
- **Voice as an optional module** — push-to-talk hotkey. Use **Vosk** (offline, ~50MB,
  private — matches the "local, no data" promise) over Whisper. Load model on first use.
- **Custom aliases** — users define their own names ("open my email"). Feeds the resolver.
  Big for comfort and non-English users.
- **"Did you mean" + autocomplete** — surface the parser's `warnings`/`errors` as gentle
  suggestions, not hard failures.
- **Undo last action** + **confirmation prompts for destructive actions**
  (shutdown, uninstall, close-all) — a dry-run/confirm layer in the executor.
- **First-run onboarding** + always-available **cheat sheet overlay**.
- **Toast notifications + optional sound** for feedback.
- **Accessibility basics** — keyboard-only nav, high-contrast theme, screen-reader labels.
- **Hinglish is a real moat** — bilingual parsing already exists; lean into it for the
  Indian market.

---

## 5. Issue Reporting (simple for users, debuggable for us)

**Logging (foundation):**

- Rotating logs in `%APPDATA%\Isha\logs\`. Per command, log one JSON-lines record:
  **raw input → token list → CommandIR → resolution → execution result**, with timestamp
  and per-command ID.
- Deterministic `CommandIR` → **replay any parse bug exactly** without the user's machine.
- **Global exception hook** writes a crash record with the last N command records.
- Redact sensitive content (clipboard text, reminder bodies) before writing.

**Reporting (user side — one click):**

- Tray **"Report an issue"** button: bundles last ~50 log records + OS/version info +
  optional one-line description into a zip; shows the user **exactly what's included**;
  uploads to intake endpoint or saves the zip to email.
- Show a **Report ID** back to the user.
- **Opt-in and transparent** — non-negotiable given the "we take no data" promise.
  Never auto-send.

**Our side:** tiny intake endpoint that dedupes by error/parse signature so many reports
of the same gap collapse into one ticket. Optionally tag with license ID.

---

## 6. Commercialization & Security

Model: sell once, fully local, store only buyer name/email/phone, push updates through
the app. Maps cleanly to an **offline signed-license** design (no usage phone-home).

**Licensing (offline, cryptographic):**

- **Ed25519/RSA signed license key** per purchase, binding email + order info. App verifies
  the signature locally with an **embedded public key** — offline, unforgeable, no client secret.
- Optional **one-time online activation** with device fingerprint + activation cap
  (e.g. 2 devices) to curb sharing. Keep optional so offline machines still work.
- Don't over-engineer anti-piracy at this price point.

**Payments & delivery (minimize backend):**

- Use a **Merchant-of-Record** — **Paddle** or **Lemon Squeezy** — for global VAT/GST,
  checkout, license-key generation, and email delivery. Add **Razorpay** for India.
- Delivery = automated email with key + signed installer link.

**Updates:**

- App fetches a **signed version manifest** (static JSON on CDN); if newer, downloads a
  **signed installer** and **verifies the signature before applying**.
- **Code-sign binaries** (Windows Authenticode; **EV cert** clears SmartScreen instantly).
  Budget for the cert — biggest driver of "trustworthy install" perception.

**Data minimization (keeps the promise credible):**

- Buyer PII lives in the MoR / a minimal separate DB — **never** in the app's telemetry path.
  App sends nothing unless the user clicks "Report issue." Advertise this on the store page.
- HTTPS everywhere, rate-limit activation/intake endpoints, embed **only public keys** in client.

---

## 7. Phased Roadmap

| Phase | Goal | Deliverable | Status |
|------|------|-------------|--------|
| **1. Spine** | One command works end-to-end | executor + app resolver + config store + structured logging | ✅ done (2026-07-06) |
| **2. Input layer** | Make it usable | tray app + global hotkey + command palette | ✅ done (2026-07-06) — pending real-Windows/visual verification |
| **3. Modes 2.0 + utilities** | Ship the differentiator | full mode engine + core utilities | ✅ done (2026-07-06) — pending real-Windows/visual verification |
| **4. Comfort** | Broaden appeal | aliases, undo, confirmations, onboarding, voice (optional module) | ✅ done (2026-07-06) — pending real-Windows/visual verification |
| **5. Support** | Sustainable | one-click issue reporting + auto-updater | ✅ done (2026-07-06) — pending real-Windows/visual verification |
| **6. Commercialize** | Sell it | offline licensing + MoR checkout + code-signed installer | ✅ licensing done (2026-07-06) — MoR checkout, code-signing cert, and installer packaging remain manual/business steps, not code |

**All six phases are done.** Modes are the real differentiator — mixed
apps/websites, script-on-activate, per-mode system state (settable via typed
commands), best-effort window-layout restore (capturable via a typed command
too), clean A→B switching, and four kinds of auto-triggers (time, battery,
app-launch, idle) — sitting on top of a small set of high-value utilities
(disk/internet checks, screenshot, a now-actually-running clipboard history,
snippets, a mode-tied pomodoro timer with real toast notifications). Phase 4
(Comfort) closed out the "make it pleasant and safe to use" work: real yes/no
confirmation dialogs, a working single-level undo, custom aliases, a help
cheat sheet, first-run onboarding, live "did you mean" suggestions, and
optional voice input. Phase 5 (Support) adds one-click local issue reports
(opt-in send, never automatic) and a fail-closed signed update check —
neither one makes a network call the user didn't ask for. Alongside Phase 5,
a full audit of the existing codebase found and fixed a real safety bug (some
"turn off X"/"switch off X" phrasings were silently falling through to a
full system-shutdown confirmation instead of toggling X), dead parser code,
a target-leakage bug, a clipboard-history feature that was fully built but
never started, and an app-registry efficiency gap — all detailed above and
re-verified against a ~35-phrasing regression suite plus the full existing
test surface, with zero regressions found. Every architectural invariant from
Phases 1-4 held: non-raising `ExecutionResult` handlers, explicit graceful
degradation per optional dependency, the confirmation gate, sensitive-field
redaction, and the single shared pipeline entry point — still five input
paths (CLI, hotkey, palette, scheduled trigger, voice), with three of them
(CLI, palette, tray) now also reaching Phase 5's report/update actions.
Phase 6 (Commercialize) adds the client half of the "sell once, fully local"
model: `a_licensing.py`'s offline Ed25519 license verification (its own
keypair, separate from the updater's), typed `activate license`/`license
status`/`deactivate license` commands, a status record that's always
re-verified from its signature rather than trusted from a cache, and
`tools/generate_license.py` as the seller-side, never-shipped counterpart
that actually mints keys. Enforcement is a deliberate soft gate — a
one-time-per-run reminder, not a lock — matching this file's own "don't
over-engineer anti-piracy at this price point" guardrail from Section 6;
tightening it later is a small, contained change against the one
`a_licensing.is_licensed()` function, not a redesign. A second audit pass
(triggered by building a feature that logs PII for the first time) found and
fixed a real pre-existing gap in `logger.py`'s redaction: the token list and
the execution result's message string weren't being redacted for sensitive
actions, even though every other field was — meaning a license key, a
buyer's email, or a search query could survive in the log file in the clear
right next to its correctly-redacted counterpart. Both are now redacted
identically to every other field, re-verified by grepping a real test log
for a real test email/key/query after the fix and finding none.

**What's left before Isha can actually be sold is explicitly not code**:
a Merchant-of-Record account (Paddle/Lemon Squeezy/Razorpay) for checkout and
key delivery, a Windows code-signing certificate (Authenticode/EV) so
SmartScreen doesn't flag the installer, an actual PyInstaller/Nuitka
packaging pass, and running the real `tools/generate_license.py keygen` to
replace both placeholder public keys (update + license) with the real
product keypairs. None of those are gaps in this codebase — they're the
business/release steps this codebase has been built to support since Phase 1.

---
---

# Cycle 2 — Hardening, Verification & Real-World Readiness

> **Purpose.** Cycle 1 built the whole feature surface but self-verified it only
> on Linux/WSL, and it shipped with real, exploitable weaknesses that were
> acceptable while nothing had run on Windows and nothing was packaged — but are
> not acceptable in something sold to run on a stranger's machine. Cycle 2 has
> one ordering rule, non-negotiable: **security is fixed first, before any new
> feature or polish work**, because everything in Cycle 1 that made the product
> *pleasant* (auto-triggers, mode scripts, one-click update, stored license)
> also widened the attack surface, and comfort built on an unsafe base is a
> liability, not a feature. Only once the base is safe do we make the product
> *real* (verified on Windows, packaged, signed) and then *comfortable*
> (settings UI, wizard, the half-built features that never fire).
>
> The three tracks below are ordered by priority, not by phase number. **Do
> Track A before B, and B before C.** Track D (backend/business) runs in
> parallel and is mostly not code.

## Guiding principles for Cycle 2

1. **Security first, and security means the auto-executing paths.** The
   dangerous surface in Isha isn't the typed command a human is watching — it's
   everything that runs *without* a human in the loop: auto-triggers, stored
   scripts, downloaded installers, and anything driven by the plaintext,
   user-editable `config.json` / registry cache. Every item in Track A is one
   of those.
2. **Keep the "nothing leaves this machine" promise literally true.** No new
   background network calls, no telemetry, ever. Every fix here must preserve
   that.
3. **Fail closed, degrade gracefully, never fake success** — the three
   invariants Cycle 1 held. Cycle 2 keeps them.
4. **Don't regress the soft-gate philosophy.** Licensing stays a soft gate;
   hardening the *license store* is about protecting the buyer's PII, not about
   locking non-payers out.

---

## Track A — Security hardening (MUST ship before anything else in Cycle 2)

**Status: ✅ all six items done (2026-07-07).** Every fix below shipped, the
A6 regression suite (`tests/test_security_hardening.py`, 15 tests) is green,
and `THREAT_MODEL.md` documents the trust boundary in full. This pass also
added `tools/sign_manifest.py` (the update-manifest counterpart to
`tools/generate_license.py`, needed by A3) since none existed yet. Verified
by hand in addition to the automated suite: activating a mode with a script
set and `allow_mode_scripts` on but *no* confirm callback (mode_scheduler's
exact auto-trigger shape) skips the script and still opens the mode's
apps/websites; the same activation with an approving confirm callback
actually launches it; a swapped installer file is caught by the pre-launch
re-hash; a tampered manifest field fails canonical-signature verification;
a fake DPAPI round-trip proves the encrypt-on-store/decrypt-on-load plumbing
without needing real Windows to exercise the Win32 call itself.

Ordered most-severe first. A1–A3 are the ones that let *someone other than the
user* cause code to run or data to leak; they block everything else.

### A1. Auto-triggered mode scripts = silent, unconfirmed arbitrary code execution  ⚠️ highest priority — ✅ done (2026-07-07)
- **The hole.** `a_mode_manager` mode records carry a free-text `script`
  field. `executor._run_mode_script()` runs it with
  `subprocess.Popen(shlex.split(script), shell=False)` — arbitrary process
  launch. `activate_mode()` calls it on every activation. And
  `mode_scheduler._fire()` calls `main.process_command_safe("activate <mode>
  mode", config)` **with no `confirm_callback`**, on a 20s background poller,
  for time / on-battery / app-launch / idle triggers. Net effect: **any content
  that reaches a mode's `script` field executes automatically in the
  background, with no user in the loop and no confirmation.** The `script` field
  is set by a typed command *or* by hand-editing `config.json`, which is
  plaintext, world-readable-to-the-user, and written by any process running as
  the user. So this is a local privilege/persistence primitive: drop a line in
  `config.json`, and Isha's own trusted, signed (post-Cycle-2) process runs it
  on the next trigger — a textbook autorun backdoor.
- **Fix (do all four):**
  1. **Treat "run a script" as a destructive/risky action end to end.** Mark
     the script-execution step `requires_confirmation` the same way
     `shutdown`/`apply_update` already are, so an *interactive* activation
     prompts before running a script the user didn't just type.
  2. **Never run a mode script from a non-interactive trigger.** In
     `mode_scheduler._fire`, either pass a `confirm_callback` that *always
     refuses* the script step (mode still activates; apps/websites/system-state
     still apply; only the arbitrary-command step is skipped and a toast says
     so), or split "activate a mode's apps" from "run a mode's script" into two
     actions and only ever auto-fire the former.
  3. **Gate scripts behind an explicit, separate opt-in setting**
     (`settings.allow_mode_scripts`, default **off**). With it off, `script`
     fields are ignored everywhere and setting one via typed command explains
     how to enable it. Most users never need a mode script; the ones who do can
     opt into the risk knowingly.
  4. **Show the script before first run.** The first time a given script string
     would run (interactively), display it verbatim and require confirmation —
     "Isha is about to run: `<script>` — allow?" — so a config edit can't
     smuggle a command past a user who thinks they're just switching modes.
- **Acceptance:** a time trigger firing a mode whose `script` is `calc.exe`
  (harmless stand-in) does **not** launch it with the setting off / from a
  trigger; an interactive `activate work mode` prompts and shows the script
  before running it with the setting on. Add a regression test asserting the
  scheduler path never executes a script.

### A2. Update installer: predictable temp path + TOCTOU + no Authenticode check — ✅ done (2026-07-07)
- **The hole.** `a_updater.download_and_verify()` writes the installer to
  `Path(tempfile.gettempdir()) / f"isha_update_{version}.exe"` — a **predictable
  filename in the world-writable shared temp dir**. It verifies sha256 there,
  then `executor.apply_update()` launches it with `subprocess.Popen([path])`.
  Between the checksum check and the launch, a local attacker can replace the
  file (classic TOCTOU); and even absent a race, any local process can
  pre-plant `isha_update_<next-version>.exe`. The launch step also does **no
  Authenticode signature check** on the .exe it runs.
- **Fix:**
  1. Download to a **per-user, freshly-created 0700 directory with a random
     filename** (e.g. under `%LOCALAPPDATA%\Isha\updates\<random>\`), not shared
     temp. On Windows set a restrictive DACL (owner-only) so no other user can
     write it.
  2. **Re-verify the sha256 immediately before launch**, inside
     `apply_update`, not only at download time — close the TOCTOU window to
     ~zero, and re-open the file by handle rather than by re-resolving the path.
  3. **Verify the installer's Authenticode signature** (subject = the real
     Isha code-signing identity) before `Popen`, once code-signing exists
     (Track D). Until then, the sha256-from-signed-manifest chain is the trust
     root — keep it airtight.
  4. Delete the downloaded installer after launch / on next start.
- **Acceptance:** the installer path is unpredictable and not writable by other
  users; swapping the file after download but before launch is caught by the
  pre-launch re-hash and refused.

### A3. Sign the manifest over canonical bytes, not a delimiter-joined string — ✅ done (2026-07-07)
- **The hole.** `a_updater._verify_signature` builds the signed payload as
  `f"{version}|{url}|{sha256}"`. Pipe-delimited concatenation is not a
  canonical encoding: if any field can contain `|` (a URL certainly can), the
  boundaries are ambiguous and a signature could in principle be made to cover a
  different (version, url, sha256) split than intended. Licensing already does
  this correctly (signs the exact JSON payload bytes).
- **Fix:** sign/verify over the **canonical serialized bytes of the manifest's
  signed fields** (e.g. `json.dumps({"version","url","sha256"},
  sort_keys=True, separators=(",",":"))`), matching `a_licensing.py`'s approach.
  Coordinate with whatever signs manifests in the release pipeline so both
  sides agree byte-for-byte. Low severity, but cheap to make airtight and it
  removes a whole class of "did the signature really cover *this*?" doubt.

### A4. Integrity-protect the trusted-input files that drive code execution — ✅ done (2026-07-07)
- **The hole.** Two on-disk files are read as *trusted* and turned into process
  launches, yet have no integrity protection and are writable by any
  same-user process:
  - `app_registry_cache.json` — `open_app` launches paths straight out of it via
    `subprocess.Popen([path])`. Poison the cache and "open chrome" launches
    attacker's binary.
  - `config.json` — modes, scripts (A1), aliases, triggers. The whole
    behavior of the app is defined here with zero tamper-evidence.
- **Fix (pragmatic, not over-engineered):**
  1. Re-validate every path pulled from the app-registry cache **at launch
     time** — confirm it still exists, is under an expected install/Program
     Files/known location, and (post-signing) optionally that it's signed —
     rather than trusting a path just because it's in the cache. The cache is a
     convenience index, not an authority.
  2. Set an **owner-only DACL on `%APPDATA%\Isha\`** on Windows (the current
     `os.chmod(0o600)` in `config_store.save_config` is effectively a no-op on
     NTFS — it doesn't translate to an ACL). This raises the bar from "any
     process" to "a process already running as this user," which is the honest
     boundary for a single-user desktop app.
  3. Document clearly (threat model, below) that Isha's trust boundary is "code
     running as this user" — we defend against *other* users and *planted
     files*, not against malware already running as you (nothing on a desktop
     can).

### A5. Protect the stored license record (buyer PII at rest) — ✅ done (2026-07-07)
- **The hole.** `activate_license` stores the full license record — including
  `raw` (which decodes to the buyer's **email**) and `email` in cleartext — in
  `config.json`. The logging path correctly redacts license actions, but the
  config store itself keeps the PII in the clear. This is the one piece of
  genuine personal data the app holds, and the whole product promise is "we
  don't keep your data."
- **Fix:** on Windows, encrypt the license record at rest with **DPAPI**
  (`CryptProtectData`, per-user) before writing it to `config.json`, decrypting
  on read for verification. Keep a plaintext fallback on non-Windows dev only.
  Combined with A4's DACL, the buyer's email is no longer sitting in a
  world-(same-user)-readable plaintext file. Verify the license still
  activates/verifies/deactivates end to end after the change.

### A6. Security regression suite + documented threat model — ✅ done (2026-07-07)
- Add a small **security test module** that locks in every A-fix as an
  executable assertion (scheduler never runs a script; installer path is
  unpredictable and re-hashed before launch; manifest signature is over
  canonical bytes; poisoned registry-cache paths are rejected; license record
  isn't stored in cleartext on Windows). These are the tests that must never go
  red again.
- Write a one-page **THREAT_MODEL.md**: what Isha defends against (other local
  users, planted/tampered files, a malicious/compromised update or license
  server, a hostile network) and what it explicitly does not (malware already
  running as the user; a physically-compromised machine). Honesty here is part
  of the "trustworthy install" selling point.

**Exit criterion for Track A: met (2026-07-07).** Every item above is fixed,
A6's suite (`tests/test_security_hardening.py`) is green, and no
auto-executing path (trigger → script, download → launch, cache → launch)
runs anything that a human didn't explicitly and knowingly authorize.
One sub-item remains genuinely not code: A2's Authenticode-signature check on
the installer needs a real code-signing certificate to verify against
(Track D3) — until that cert exists, the sha256-from-a-signed-manifest chain
is the trust root, and `verify_installer_before_launch` keeps that chain
airtight in the meantime. Track B can now begin.

---

## Track B — Make it real: verify on Windows, then package & sign

Cycle 1's single biggest honesty gap is that **none of the Win32 code has ever
run on Windows**, and the app **only runs from source**. Nothing below is a
redesign — it's the "actually try it" and "actually ship it" work.

### B1. Full real-Windows verification pass
Run every untested Win32 path on a real Windows box and fix what breaks. Track
it as an explicit checklist (this *is* the deliverable):
- **Phase 1:** volume (`pycaw`), dark/light theme registry write, window
  enumeration, shutdown/restart/hibernate, lock.
- **Phase 2:** global hotkey registration (`RegisterHotKey` via ctypes),
  the `GetMessageW` loop, contention when the combo is already taken.
- **Phase 3:** `SetWindowPos` layout restore, `SHEmptyRecycleBinW`,
  `win32clipboard` polling, `SendInput` snippet typing, `GetSystemPowerStatus`
  battery trigger.
- **Phase 4:** `GetWindowRect` layout capture, dedicated-window website
  tracking (`--new-window` + hwnd enum + `WM_CLOSE`), `GetLastInputInfo` idle
  detection, voice input with `vosk`+`sounddevice` actually installed.
- **Phase 5:** the installer-launch step (post-A2), the three tray menu items.
- **Visual/UX:** palette, tray icon, confirmation dialogs, live suggestions,
  toasts — with `pystray`/`Pillow`/Tk/`pywin32` actually present.
- **Deliverable:** a filled-in results table (works / broke-and-fixed /
  still-broken) appended here, replacing Cycle 1's "implemented but not yet run"
  caveats with real status.

### B2. Packaging (PyInstaller one-folder first)
- Produce a **PyInstaller one-folder build** (fast start, per Cycle 1's Stack
  notes), confirm idle RAM stays in tens of MB, cold-start is acceptable, and
  every optional-dependency graceful-degradation path still behaves when the
  bundle *does* include the dependency. Nuitka is a later size/speed
  optimization, not a blocker.
- Ship a real **tray icon / product art** to replace the generated placeholder.
- Author a proper **installer** (Inno Setup or MSIX) that lays down the
  one-folder build, a Start-Menu entry, and an opt-in "start with Windows".

### B3. Code-signing wired into the pipeline (depends on Track D cert)
- Once the EV/Authenticode cert exists (D3), sign the installer **and** the
  inner executables, and turn on A2's Authenticode-verify-before-launch. Confirm
  SmartScreen is clean on a fresh machine.
- Run `tools/generate_license.py keygen` for real, paste both real public keys
  into `a_licensing.py` / `a_updater.py`, keep both private halves offline, and
  do a full **sign → publish signed manifest → check → download → verify →
  launch** dry run end to end on Windows, plus a real **sign-a-license →
  `activate license`** dry run.

**Exit criterion for Track B:** a code-signed installer installs Isha on a clean
Windows machine, every feature works or has a documented known-limitation, and
the update + license chains have been exercised end to end with real keys.

---

## Track C — Comfort, polish & finishing the half-built features

Only after A and B. These make Isha *pleasant* and close the "does NOT do yet"
list Cycle 1 accumulated. Roughly ordered by value.

**Note (2026-07-07):** C2 and C3 (and a general visual pass across every
Tkinter surface) were pulled forward and built alongside Track A, ahead of
B, since they were pure UI work with no dependency on real-Windows
verification — see their entries below for what shipped and what's still
deferred. B1–B3 (Windows verification, packaging, code-signing) remain
un-started; nothing in this codebase can substitute for actually running on
a Windows machine or purchasing a certificate.

### C1. Fire the reminders/tasks that are already persisted
`set_reminder`/`schedule_task`/`add_task` write to `config["reminders"]` but
**nothing ever fires them** — the scheduler only handles mode triggers. Extend
`mode_scheduler` (or a sibling poller) to actually fire due reminders as toasts.
This is the most-broken user-visible promise in the app.

### C2. Settings & hotkey-rebinding UI — ✅ mostly done (2026-07-07)
`settings_window.py` is a new Tk window (tray menu "Settings..." → routed
through the same UI-thread queue as "Install update...", since it's a real
Toplevel and Tkinter isn't thread-safe) with tabs for General (toggle
`allow_mode_scripts` from A1, with the same "asks every time" explanation),
Aliases (add/remove, live-editing `config["aliases"]`), Snippets (add/remove),
License (status, activate, deactivate — wraps `a_licensing.py` directly), and
About. Every change mutates the same in-memory config dict the rest of the
running app already holds, then saves — so e.g. flipping the mode-scripts
toggle takes effect immediately, no restart.
**Not done**: actual hotkey *rebinding* from the UI — the General tab shows
the current palette/voice hotkeys and points at `config.json` to change them,
same as before. Rebinding needs re-registering a live `RegisterHotKey` call,
which is Windows-only and untested here (Track B1 territory) — doing it
blind risked shipping a rebind button that silently doesn't work. Start-with-
Windows and trigger management are likewise still config.json-only.

### C3. First-run setup wizard (replace the single printed message) — ✅ done (2026-07-07)
`onboarding_wizard.py` is a 3-page guided Toplevel (welcome + privacy promise
→ where the hotkey lives → optional first-mode creation, which calls the same
`create <name> mode <apps>` pipeline a typed command would) with a dot-style
progress indicator, Back/Next/Skip, and Escape-to-skip. Shown once via
`tray_app.py` before the palette's own hidden mainloop settles (`after(200, ...)`),
and marks `settings.onboarded` the same way finishing or skipping either one
did before — so a user who already ran the old flow won't see it again. The
CLI-only path (`main.py`) still uses its original printed message, since a
terminal has no Tkinter surface to show a wizard in. Voice setup is
mentioned only in passing (full model setup is C4, not built here).

### General visual pass — ✅ done (2026-07-07), not a separate roadmap item originally
Added `ui_theme.py`: one shared palette/typography/ttk-style module used by
the command palette, the new settings window, and the new onboarding wizard,
so all three read as one calm, coherent app instead of three windows that
happened to share a codebase. Palette changes: a proper header (wordmark +
a "⚙ Settings" button wired to the new window), calmer slate colors instead
of near-black-and-neon, a results panel that only appears once there's
something to show, and ✓/✕ marks instead of shouting `[OK]`/`[FAILED]` text.
No accessibility guarantee was removed — high contrast, large default font,
full keyboard nav, and plain-sentence output all still hold; this only makes
the existing choices consistent across surfaces. **Caveat, same as every
other Tk-dependent piece in this repo**: Tkinter isn't installed in this dev
container, so none of this has been visually verified — only syntax-checked
and logically reasoned through. Real verification is part of Track B1's
"palette, tray icon, confirmation dialogs, live suggestions, toasts" pass.

### C4. In-app voice-model setup
Voice needs the user to manually `pip install vosk sounddevice` and download a
model. Add an in-app "enable voice" flow that fetches the model (with a checksum
/ signature check, honoring the same no-surprise-network rule — opt-in, shown).
Consider hold-to-record push-to-talk instead of the fixed 4s window.

### C5. Finish the interactive window ops
`snap_window` / `resize_window` / `move_window` are still `_not_yet_implemented`.
With B1 confirming `SetWindowPos` works, implement them (they share plumbing
with the layout-restore code).

### C6. Smaller polish / known limitations from Cycle 1 audits
- Fix the `("remove"/"delete","app")` → `uninstall_app` target leakage
  (`"remove app chrome"` → target `"app chrome"`), now that the generic
  verb-span-slicing fix exists to model discriminator vs. data tokens.
- Make `_open_website_item`'s up-to-3s new-window wait **asynchronous** so
  activating a website-heavy mode never blocks the Tk thread (needs a real Tk
  env to verify — now available post-B1).
- Optional: typo-tolerant fuzzy ranking in live palette suggestions;
  per-action "don't ask again" on confirmations; multi-level undo.

**Exit criterion for Track C:** the "What Phase N deliberately does NOT do yet"
lists above are either done or consciously re-deferred with a one-line reason,
and no persisted feature (reminders!) silently does nothing.

---

## Track D — Backend & business (parallel; mostly not code)

These gate an actual sale and were correctly called out in Cycle 1 as non-code.
They can proceed alongside A–C.

- **D1. Report-intake endpoint** — the HTTPS server `send_report` targets, with
  dedup-by-error-signature (Section 5). Rate-limited, stores only what the zip
  contains. Until it exists, `send_report` correctly refuses.
- **D2. Merchant-of-Record checkout** — Paddle / Lemon Squeezy (global) +
  Razorpay (India): product listing, tax handling, and **automated license-key
  delivery** wired to `tools/generate_license.py sign`. The single biggest
  non-code blocker to selling.
- **D3. Code-signing certificate** — purchase an Authenticode **EV** cert
  (clears SmartScreen instantly); feeds B3 and A2's Authenticode check.
- **D4. (Optional) online activation server** — enforces the informational
  `max_devices` cap against `_device_fingerprint()`. Keep optional so offline
  machines still activate. Low priority; the soft gate stands without it.

---

## Cycle 2 phased summary

| Track | Goal | Gate | Priority | Status |
|-------|------|------|----------|--------|
| **A. Security** | Nothing auto-executes or leaks without knowing authorization | A6 suite green | **First — blocks all else** | ✅ done (2026-07-07) |
| **B. Real & shipped** | Verified on Windows, packaged, signed | Signed installer on clean Win | After A | B2 packaging scripts written (2026-07-07, Cycle 3 §); B1 Windows verification + B3 signing remain owner/Windows steps |
| **C. Comfort** | Pleasant; half-built features finished | "does NOT do yet" list closed | After B | C2/C3 + visual pass done (2026-07-07, pulled forward); C1/C4/C5/C6 not started |
| **D. Backend/business** | Sellable | MoR live + cert + intake up | Parallel (non-code) | Not started |

**The one rule:** Track A ships before Track B, which ships before Track C.
Security is not a phase you get to later — in Cycle 2 it is the thing you do
first, precisely because Cycle 1 made Isha powerful enough to be dangerous when
it runs on its own. C2/C3 were the exception: pure UI work with zero
dependency on real-Windows verification, so they were pulled forward and
built alongside Track A rather than waiting on Track B — every other item in
Track C (reminders actually firing, window-op implementations, the async
website-wait fix) genuinely does need B1's real-Windows pass first and stays
un-started.

---

## Cycle 2 progress note (2026-07-07)

Track A (all six items) and part of Track C (C2 settings window, C3
onboarding wizard, plus a general Tk visual-consistency pass across every
window) are done — see their sections above for what shipped and the
`ROADMAP.md`-external files this pass added: `THREAT_MODEL.md`,
`tests/test_security_hardening.py` (15 tests, all green), `ui_theme.py`,
`settings_window.py`, `onboarding_wizard.py`, and `tools/sign_manifest.py`.

**What's next, in order:** Track B (B1's real-Windows verification pass is
the load-bearing item everything else in B and the rest of C depends on),
then the remaining Track C items (C1's reminders, C4's voice setup, C5's
window ops, C6's small fixes), with Track D proceeding in parallel as
business/account work throughout. None of Track B or D can be completed from
this dev container — B needs an actual Windows machine, D needs real
business accounts and a purchased certificate.

---
---

# Cycle 3 — Ship & Sell: from source tree to a product people can buy

> **Purpose.** Cycle 1 built the app; Cycle 2 made it safe. Cycle 3 is about the
> last mile: turning the source tree into a **single installer file** a stranger
> can run, standing up a **website** that sells it, and wiring a **payment +
> license-delivery** path so a purchase automatically becomes a working,
> activated copy. Most of this cycle is *not code the app runs* — it's build
> tooling, a marketing site, one tiny fulfilment server, and a sequence of
> business/account steps only the owner can perform (buy a cert, open a payment
> account, run the Windows build). This section is the plan and the runbook.
>
> **The honest split.** Everything buildable from a Linux dev container has been
> built and is in the repo (below). Everything that *requires Windows, money, or
> a business account* is documented as a step-by-step runbook, because it
> genuinely cannot be produced by a code change — you have to run the build on
> Windows, purchase the certificate, and open the payment account yourself.

## What shipped this pass (2026-07-07) — the buildable half

| Area | Files added | What it does |
|------|-------------|--------------|
| **Packaging** | `packaging/isha.spec`, `isha.manifest`, `version_info.txt`, `isha.iss`, `build.ps1`, `README.md` | PyInstaller recipe (source → `dist\Isha\` one-folder app) + Inno Setup script (app folder → `IshaSetup-x.y.z.exe`) + a one-command `build.ps1` that runs both and optionally code-signs. Per-user, no-admin install (`asInvoker` manifest, `PrivilegesRequired=lowest`). |
| **Website** | `website/index.html`, `privacy.html`, `terms.html`, `refund.html`, `styles.css`, `README.md` | A static, framework-free, tracker-free marketing + purchase site sharing the app's calm `ui_theme.py` palette. Landing + pricing + FAQ, plus the three legal pages a Merchant-of-Record requires before approving you. Hostable free on Cloudflare Pages / Netlify / GitHub Pages. |
| **Payments / fulfilment** | `server/license_webhook.py`, `requirements.txt`, `README.md` | The one small backend: a signed-webhook endpoint that turns a completed Merchant-of-Record order into a real Ed25519 Isha license key and emails it. **Verified byte-compatible** with the app's own `a_licensing.verify_license_string` (a webhook-signed key activates cleanly). Manual-first fallback documented so day-one sales need no server at all. |
| **Run / admin** | `run.bat` | Double-click to run Isha from source on Windows (auto-creates a venv + installs deps on first run). Documents that Isha deliberately does **not** need admin, and how to run elevated if ever wanted. |

None of the website or packaging files are imported by or shipped inside the
app — they're seller-side/release tooling, kept separate exactly like
`tools/generate_license.py`.

## D-track decisions locked in this pass

- **Merchant of Record, not a raw gateway.** Sell through Lemon Squeezy
  (recommended) or Paddle so VAT/GST and card data are entirely their problem,
  not yours — you never register for tax or touch a card number. Razorpay
  (India) is deferred: it's *not* an MoR, so it needs an Indian entity + GST
  registration; an MoR already sells into India in local currency, legally, on
  day one. Revisit when India's share justifies the compliance overhead.
- **Keep Isha's own offline Ed25519 licenses** (don't switch to the MoR's
  online license API). This preserves the "no phone-home, activates offline"
  promise that is the product's whole spine, and the fulfilment webhook bridges
  the two worlds: MoR handles money, Isha handles the key.
- **Per-user, no-admin install.** The honest boundary for a single-user desktop
  app; also avoids a UAC prompt on every launch, keeps "start with Windows"
  working, and keeps SmartScreen calmer. See `packaging/isha.manifest`.

## The end-to-end runbook (what YOU do, in order)

This is the sequence from here to a first sale. Steps marked **[Windows]** need a
Windows machine; **[$]** costs money; **[once]** is a one-time setup.

1. **[once] Generate the real product keys.** `python tools/generate_license.py
   keygen` (and `tools/sign_manifest.py keygen` for updates). Paste the *public*
   halves into `a_licensing.py` / `a_updater.py`; store both *private* halves
   offline forever. Until this is done, all licenses/updates fail closed by
   design. → `packaging/README.md` Step 4.
2. **[Windows][once]** Install Python + `requirements.txt` + PyInstaller + Inno
   Setup. Add `packaging/isha.ico`. → `packaging/README.md` Prereqs + Step 0.
3. **[Windows]** Run `packaging\build.ps1` → get `dist\installer\IshaSetup-<v>.exe`.
4. **[Windows] Track B1 — the real-Windows verification pass.** Smoke-test the
   built app: tray icon, hotkey palette, a dozen commands, modes, settings +
   onboarding windows, the update/report menu items. Fill in the B1 results
   table. This is still the load-bearing un-done item — the Win32 code has never
   run on Windows.
5. **[$][once] Buy a code-signing certificate** (Track D3). An **EV**
   Authenticode cert clears SmartScreen instantly; a standard OV cert builds
   reputation over time. Then rebuild with `build.ps1 -SignThumbprint <...>`.
   Without this, first-run SmartScreen warnings are expected, not a bug.
6. **[once] Open a Merchant-of-Record account** (Lemon Squeezy or Paddle),
   create the product + price, and fill in the website placeholders
   (`website/README.md` §1). Wire the checkout URL into the two buy buttons.
7. **[once] Publish the website** (Cloudflare Pages / Netlify / GitHub Pages),
   point your domain at it. → `website/README.md` §2–3.
8. **Deliver licenses.** Start **manual** (`generate_license.py sign` per order,
   reply with the key — zero servers). Automate later by deploying
   `server/license_webhook.py` and pointing the MoR's `order_created` webhook at
   it. → `server/README.md`.
9. **Host each release's installer** on GitHub Releases / Cloudflare R2 (not in
   the website repo) and put that URL in the MoR's post-purchase email.

The buyer's experience, end to end: pay on your site → MoR email with download
link + license key → install `IshaSetup-<v>.exe` → open Isha → `activate license
<key>` (offline). That whole chain is built; steps 1–7 above are the setup that
turns it on.

## Cycle 3 status summary

| Item | Owner-action needed | Status |
|------|--------------------|--------|
| Packaging scripts (PyInstaller + Inno + build.ps1) | run on Windows | ✅ written (2026-07-07) — untested off-Windows, as expected |
| Website (landing + legal + styles) | fill placeholders, host | ✅ built (2026-07-07) |
| License-fulfilment webhook | deploy + configure secrets | ✅ built + verified byte-compatible (2026-07-07) |
| Per-user/no-admin install + `run.bat` | — | ✅ done (2026-07-07) |
| Real product keypairs swapped in | run `keygen` offline | ⬜ owner step (never automatable — private key must stay offline) |
| Windows build + B1 verification | Windows machine | ⬜ owner step (needs Windows) |
| Code-signing cert | purchase (Track D3) | ⬜ owner step ($, external CA) |
| Merchant-of-Record account + checkout live | open account (Track D2) | ⬜ owner step (business account) |
| Website hosted on real domain | deploy | ⬜ owner step |

**Bottom line:** the code and content that a machine *can* produce for shipping
and selling Isha now exist and are internally consistent (the webhook's keys
verify in the app; the installer is per-user; the site has its legal pages). The
remaining work is deliberately, unavoidably yours: run the build on Windows,
buy the cert, open the payment account, host the site. The runbook above is the
exact order to do them in.


---

# Cycle 4 — Isha 2.0 "Sakura": the real desktop app (complete 2026-07-07)

> **Purpose.** Cycles 1–3 built a complete, security-hardened, fully-local
> command pipeline with a set of small Tkinter utility windows (palette,
> settings, dashboard, wizard) hanging off a tray icon. Cycle 4 turns that
> engine into a **real desktop application**: one full window that launches
> like a normal Windows program, a calm Japanese-inspired design language
> (single-line branch + sakura), a set of new user-facing features (website
> allow-list, reminders that actually fire, named scripts, smarter
> mute/screenshot behavior), a serious performance pass, and a **packaged
> `Isha.exe` / `IshaSetup.exe`** at the end.
>
> **What does NOT change:** the command pipeline
> (`input_processor → command_splitter → command_parser → CommandIR →
> c_resolver_validator → executor → logger`), the security invariants from
> Cycle 2 Track A (nothing auto-executes without knowing authorization,
> fail-closed signatures, redacted logs), the
> "nothing leaves this machine" promise, and the single-JSON local config
> store. Every new UI surface is a *presentation* of `main.process_command_safe`
> — never a second brain.

---

## 0. Grounding — what exists today and why this cycle is needed

| Today | Problem Cycle 4 fixes |
|---|---|
| App starts as a tray icon + hidden Tk root; "windows" are small Toplevels (palette 640px, dashboard 640×560, settings tabs) | Users expect a full application window on launch. Isha must open as a complete, resizable, maximizable main window — tray becomes a *minimize target*, not the primary identity |
| Four separate Tk windows (palette / dashboard / settings / wizard) that spawn independently | One single-window app with an in-app sidebar; everything navigates inside the same window |
| `ui_theme.py`: dark slate + blue accent only, no light theme, flat rectangles ("terminal at 2am" fixed, but still utilitarian) | A real design language: warm-white light theme, deep warm-black dark theme, sakura/branch line art, soft curves, calm motion |
| Confirmations are `messagebox.askyesno` (system alert style + sound), notifications are `pystray.notify` OS balloons | Everything becomes quiet, soothing, in-app or in-overlay — no alarm chrome, no system sounds |
| Dashboard `_refresh()` destroys and rebuilds the whole window; command execution runs synchronously on the Tk thread (mode website-open can block ~3s); registry scan can stall first suggestions | Perceived slowness. Cycle 4 makes execution fully asynchronous with a worker thread + UI signals, and no page ever full-rebuilds |
| Scroll wheel does not scroll the dashboard canvas (Tk canvas needs explicit `<MouseWheel>` binding — never wired) | Native, smooth wheel scrolling everywhere; scrollbar visibility is a user setting |
| Reminders are persisted but never fire (Cycle 2 C1, still open) | Full reminder engine + management page |
| Screenshots hardcode `Pictures\Isha Screenshots`, always full-screen, never opened | System-standard default path (`Pictures\Screenshots`), configurable path, PrtScr capture option, open-after-capture option |
| Mute = media-key toggle on the default device only | Multi-device-aware mute with user-selectable behavior (default: halve all devices) |
| `open_url` validates scheme only; any http(s) URL opens immediately | Website allow-list: allow-listed sites open silently; anything else gets a quiet in-context "open this?" card |
| Scripts exist only as a mode's single free-text `script` field | Named, saved scripts usable from commands and modes, behind the existing script security gate |
| Volume/brightness commands with no level are a parse-dependent guess | Missing level defaults to a configurable value (50) |

---

## 1. The one big decision: UI framework

The requested bar — full main window, collapsible animated sidebar, vector
sakura artwork, warm dual themes, soft rounded curves, smooth scrolling with
hideable scrollbars, frameless always-on-top overlay input, custom top-right
toast stack, live voice text streaming into an entry — is **beyond what plain
Tkinter can deliver at professional quality**. Tk has no rounded corners, no
per-pixel window translucency worth shipping, no smooth scrolling, no SVG,
and its theming fights you at every step (the current codebase already carries
`RADIUS_NOTE` apologizing for this).

**Decision: PySide6 (Qt Widgets, LGPL) becomes the single UI framework.**
All Tkinter surfaces are replaced; the pipeline and every `a_*.py` module are
untouched.

Why PySide6 over the alternatives considered:

- **customtkinter** — better-looking Tk, but still no SVG, weak canvas
  performance, awkward overlays; caps final quality below the requested bar.
- **pywebview / WebView2** — best possible *visual* ceiling (the design is
  just CSS, and `website/` already shares the palette), but every overlay
  (quick input box, toasts) would be its own WebView2 window with 200–400 ms
  cold-show latency and its own renderer process. The quick input box must
  appear *instantly* on a hotkey; that alone disqualifies it.
- **Electron/Tauri** — new language/runtime for the frontend, biggest bundles,
  contradicts the lightweight identity entirely.

PySide6 gives us, in one dependency: frameless translucent always-on-top
windows that show in <50 ms (quick input, toasts), QSS stylesheets (rounded
corners, hover states, theme switching at runtime), QSvgRenderer (the branch
and sakura are one small SVG each), QPropertyAnimation (sidebar
collapse, toast fade — subtle, 150–200 ms, never showy), QScrollArea (native
smooth wheel scrolling, per-widget scrollbar policy), QSystemTrayIcon
(replaces pystray), and first-class QThread/Signal plumbing for the async
executor. PyInstaller support is mature.

**Cost, stated honestly:** installed size grows to roughly 120–160 MB and idle
RAM to roughly 80–150 MB — above the old "tens of MB" guardrail from Cycle 1.
This is a deliberate trade: the product's new identity is a *full application*,
and the guardrail that still holds is the one that matters to users —
cold-start to interactive window under ~2 s, overlay show under ~50 ms, idle
CPU ~0%. Mitigations: import `PySide6` modules lazily and only the used
submodules (`QtCore`, `QtGui`, `QtWidgets`, `QtSvg` — **no QML/QtQuick, no
QtWebEngine**), exclude unused Qt plugins in the PyInstaller spec, and keep
`main.py`'s CLI entry Qt-free so the pipeline stays testable headless.

Dependency changes in `requirements.txt`: add `PySide6-Essentials` (not the
full `PySide6` metapackage — Essentials skips ~100 MB of Addons); drop
`pystray` (tray becomes QSystemTrayIcon) and Tk usage; keep `Pillow`
(screenshots), `pywin32`, `pycaw`, `comtypes`, `rapidfuzz`, `cryptography`,
optional `vosk`/`sounddevice`.

---

## 2. Design language — "Shizuka" (静か) design system

One new module, `design/tokens.py` + `design/theme.qss` (template with
`{placeholders}` filled per theme), replaces `ui_theme.py`. Everything below
is a token, so both themes are the *same design* at two temperatures — exactly
as requested.

### 2.1 Palette

| Token | Light ("Washi" — warm white) | Dark ("Yoru" — deep warm black) |
|---|---|---|
| `bg` | `#F7F3EC` (warm paper white) | `#171412` (warm near-black, brown undertone — **not** blue-slate, not metallic) |
| `bg_raised` (cards) | `#FFFDF8` | `#201C19` |
| `bg_hover` | `#EFE9DF` | `#2A2521` |
| `border` (hairlines) | `#E3DCCF` | `#332D28` |
| `fg` | `#3A332C` (warm ink, not pure black) | `#EDE7DE` (warm off-white) |
| `fg_muted` | `#8A8177` | `#9C948A` |
| `accent` (sakura) | `#C9748A` (muted sakura pink) | `#D98BA0` |
| `accent_soft` (washes, focus rings) | `#F2DEE4` | `#3D2E33` |
| `branch` (line art) | `#4A4038` at 18% opacity | `#EDE7DE` at 10% opacity |
| `success` / `warning` / `error` | `#7BA886` / `#D9A662` / `#C97B74` — all desaturated, calm | same hues, +8% lightness |

Rules: **one accent, used sparingly** (primary buttons, focus, active sidebar
item, sakura petals). Error/warning states never flash, never use system
alert styling, never play sound. All text/background pairs stay ≥ WCAG AA.

### 2.2 Artwork

- **One SVG asset**: a single-weight (1.5 px), minimal ink-brush-style branch
  entering from the top-right corner of the main window, crossing ~25% of the
  header area, carrying 3–5 five-petal sakura blossoms (accent color) and
  2–3 buds. Rendered via QSvgRenderer into the window's paintEvent backdrop
  at `branch` opacity so content always sits above it legibly.
  A smaller variant (a single sprig, one blossom) marks: the quick-input
  overlay's left edge, the toast card corner, and empty states ("no reminders
  yet"). The app icon (`packaging/isha.ico`, currently missing) is a single
  blossom on `bg` — this also closes Cycle 3 runbook step 2's icon gap.
- **No gradients, no shadows heavier than `0 2px 12px rgba(0,0,0,0.06)`,
  no glassmorphism, no metallic sheen.** Curves everywhere but restrained:
  radius 10 px cards, 8 px buttons/inputs, 14 px overlay — never pill-shaped
  except the mic button.

### 2.3 Typography & spacing

- `Segoe UI Variable Display` falling back to `Segoe UI` (ships with Win 11 —
  the target OS). Scale: 22/16 title, 14 body, 12.5 secondary, 12 hint;
  `Cascadia Mono`→`Consolas` for logs/scripts.
- 8 px spacing grid (`PAD=16`, `PAD_SM=8`, `PAD_LG=24`); cards breathe —
  the calm comes from whitespace, not decoration.

### 2.4 Motion

150–200 ms ease-out for: sidebar collapse/expand, page cross-fade (opacity
only, no slides), toast enter (fade + 8 px rise) and exit (fade). Anything
longer or bouncier is out. A global `ui.reduce_motion` setting disables all of
it (accessibility carry-over — keyboard nav, contrast, and plain-sentence
output guarantees from Cycle 1 all persist).

---

## 3. Application shell

### 3.1 New entry point and process model

- **New file `app.py`** — the packaged `.exe` entry point. Creates
  `QApplication`, enforces **single instance** (named mutex via
  `CreateMutexW`; a second launch activates the existing window instead —
  today two `tray_app.py` runs would fight over the hotkey), builds
  `MainWindow`, tray icon, hotkey listeners, schedulers, and the async
  command runner.
- `tray_app.py` is **retired** (its wiring moves into `app.py`);
  `main.py` stays exactly as-is for CLI use and tests.
- **Launch behavior:** starting Isha opens the **full main window**
  (default 1200×780, min 980×640, remembers size/position/maximized state in
  `settings.ui.window`). Closing the window **minimizes to tray by default**
  (setting: `close_action: "tray" | "exit"`, asked once via a quiet in-app
  card the first time, never a modal). Tray menu shrinks to: Open Isha /
  Quick input / Take screenshot / Exit — everything else lives in the window
  now.
- All existing background threads keep their jobs: `hotkey_listener` (ctypes,
  unchanged), `mode_scheduler` (+ reminder engine, §5.5), clipboard poller.
  They communicate with the UI **only** via Qt signals (replacing today's
  hand-rolled Tk queue).

### 3.2 Async command runner (the core perf fix)

New `services/command_runner.py`: a single worker `QThread` owning a queue of
`(command_text, source)` jobs. It calls `main.process_command_safe` off the
UI thread and emits signals: `started`, `needs_confirmation(resolved_ir) →
future`, `finished(outcomes)`. Confirmation requests marshal to the UI thread,
show the **quiet prompt** (§4.4), and resolve the future. Consequences:

- The UI never blocks — the ~3 s mode website-open wait (Cycle 2 C6's known
  limitation) stops mattering because it happens off-thread; the runner shows
  a soft inline spinner ("opening study mode…") instead.
- Every surface (dashboard bar, quick-input overlay, quick-action buttons,
  sidebar pages) submits through the same runner, so behavior can't diverge —
  same principle as `process_command_safe` itself.

### 3.3 Main window layout

```
┌────────────────────────────────────────────────────────────┐
│ ⌘ [sidebar]  │           (branch SVG, top-right, faint)     │
│ ┌──────────┐ │   ┌───────────────────────────┐  ┌────┐      │
│ │ 🌸 Isha  │ │   │  Ask Isha anything…       │  │ 🎤 │      │
│ │──────────│ │   └───────────────────────────┘  └────┘      │
│ │ ◻ Dash   │ │                                              │
│ │ ◻ Modes  │ │   Quick actions   [⚙ customize]              │
│ │ ◻ Remind │ │   [Screenshot] [Mute] [Focus mode] [Lock] …  │
│ │ ◻ Keys   │ │                                              │
│ │ ◻ Custom │ │   Modes            Recent actions            │
│ │ ◻ Settin │ │   [study ▸][work ▸] │ ✓ opened chrome  09:12 │
│ │          │ │                     │ ✓ muted volume   09:10 │
│ │ «collapse│ │   Logs (expandable)                          │
│ └──────────┘ │                                              │
└────────────────────────────────────────────────────────────┘
        ▲ toasts appear top-right, inside the window when it's
          focused, as a frameless desktop card when it isn't
```

- **Sidebar** (`shell/sidebar.py`): fixed order — Dashboard, Modes,
  Reminders, Shortcuts, Customization, Settings. Collapsible to icon rail
  (56 px) / expanded (220 px) via the chevron or `Ctrl+B`; state persisted
  (`ui.sidebar_collapsed`). Active item gets an `accent_soft` wash + 2 px
  accent bar. Navigation swaps pages in a `QStackedWidget` — **one window,
  zero Toplevels**, exactly as requested.
- **Pages are built lazily** on first visit and *updated in place* thereafter
  (model→view refresh, never destroy-and-rebuild — directly fixes the
  dashboard rebuild pattern).
- **Scrolling:** every page body is a `QScrollArea` — wheel, trackpad, PgUp/
  PgDn, Home/End all work natively. `ui.show_scrollbars: "auto" | "always" |
  "hidden"` (default `auto`: thin 6 px overlay bar, visible while scrolling,
  fades out) — the requested hide/show choice.

### 3.4 Standard behaviors checklist ("simple activities" pass)

Explicit acceptance list, because "generally found on applications" is where
Tk fell down: mouse-wheel scroll on every scrollable view; Tab/Shift-Tab
traversal in every form; Enter submits / Esc dismisses every card and overlay;
text fields support select-all/copy/cut/paste/undo and right-click context
menu; window snap (Win+arrows), maximize, DPI scaling (`Qt.HighDpiScaleFactor
RoundingPolicy.PassThrough` — crisp on 125/150%); F1 opens Help; Ctrl+, opens
Settings; Ctrl+K focuses the command bar; lists have hover states and
keyboard selection; long operations always show progress; every destructive
action confirms quietly (§4.4).

---

## 4. Surfaces

### 4.1 Dashboard page

Exactly the requested composition, top to bottom:

1. **Command bar, centered top** — large (48 px) rounded input, placeholder
   "Ask Isha anything…", with the **mic button** flush right inside it.
   Enter submits to the command runner; results appear as a soft inline
   result line under the bar (✓/✕ + plain sentence, fading after 6 s into
   Recent actions) — never a popup. Live "did you mean" suggestions render
   in a floating list under the bar (reusing the palette's existing
   suggestion source, now debounced at 120 ms).
2. **Quick actions** — a wrap-row of soft buttons. **Customizable**
   (`settings.ui.quick_actions`: ordered list of `{label, command, icon}`),
   edited via a "customize" affordance opening an in-page editor (add any
   typed command as a button, reorder, remove). Defaults: Screenshot, Mute,
   Lock, Focus mode, Check internet, Empty recycle bin.
3. **Modes strip** — the saved modes as cards (name, app count, active dot);
   click activates/deactivates through the runner; "manage ▸" jumps to the
   Modes page.
4. **Recent actions** — last ~12 command outcomes (in-memory ring, same data
   `main._recent_records` keeps), each row: ✓/✕, plain sentence, relative
   time, and an "undo" affordance where `undo_manager` has a record.
5. **Logs** — collapsed by default; expands to a read-only virtualized view
   over `commands_log.jsonl` (tail, lazy-loaded pages of 100), with a filter
   box. Read path only — the log file stays append-only and redacted.

### 4.2 Quick input overlay (global hotkey)

Replaces `command_palette.py`. A frameless, translucent-cornered,
**always-on-top** window (`Qt.WindowStaysOnTopHint | Qt.Tool`, no taskbar
entry), ~640 px wide, centered horizontally at ~28% screen height: one calm
rounded input on a `bg_raised` card with the sakura sprig at its left edge,
suggestion list below, result line below that. Shows in <50 ms on
`ctrl+alt+space` (kept; rebindable, §5.7), takes focus, Esc dismisses,
Enter runs via the shared runner and shows the ✓/✕ line, then auto-dismisses
after 2.5 s (configurable `ui.overlay_autohide`). This is the requested
"type box in the middle with a calm theme, on top of all apps."

### 4.3 Voice into the same bar

`services/voice_controller.py` wraps `a_voice_input`, upgraded from the fixed
4 s blocking record to **streaming partials**: Vosk's `KaldiRecognizer`
`PartialResult()` events emit a signal per update; whichever bar initiated
listening (dashboard bar or the overlay — the same widget class,
`widgets/command_bar.py`, is reused for both) renders the words appearing
live in the input, `fg_muted` while partial, `fg` when final. Mic button
states: idle → listening (soft accent pulse, again disabled by
`reduce_motion`) → transcribing. The voice hotkey now opens the overlay
pre-listening — the requested "words being typed into the same text bar."
Silence (1.2 s) or click ends capture; the user can edit before Enter —
voice never auto-executes, preserving the confirmation model.

### 4.4 Quiet prompts (confirmations) — no alarms, ever

New `widgets/quiet_prompt.py`, used for **every** confirmation (destructive
actions, script first-run, non-allow-listed URLs): a small `bg_raised`
rounded card, no icon-of-danger, no system sound, message in plain calm
language ("This will shut down the PC. Continue?"), two soft buttons
(accent "Yes, continue" / plain "Not now"), Esc = decline, focus defaults to
decline for destructive actions. Rendering:

- If the main window / overlay is visible → inline card sliding over the
  bar area of that surface.
- If triggered headless (tray action) → a desktop-positioned frameless card,
  top-right, same visual as toasts.

`app.py` passes a `confirm_callback` bridging the runner's confirmation
signal to this widget. `messagebox.*` disappears from the codebase.
Security note: this *changes the chrome, not the gate* — every
`requires_confirmation` path still requires an explicit affirmative; the
scheduler still gets no callback and still refuses.

### 4.5 Notifications — top-right, silent, calm

New `services/notifier.py` replacing `a_notifications`' pystray path
(same public API, so `mode_scheduler`, pomodoro, reminders keep working):

- **Toast cards** top-right: 320 px, `bg_raised`, radius 10, title + one
  sentence + optional action button (e.g. reminder "Snooze 10 min"),
  auto-dismiss 6 s, stack up to 3 (older collapse into "+n more"), fade
  animation, **no sound by default** (`notifications.sound: off|soft`, where
  `soft` is a single low-volume wood-block tick, opt-in).
- Inside the focused main window they render in-window (top-right of the
  content area); otherwise as frameless desktop cards at screen top-right
  (the "notification area or default" requested).
- A bell icon in the window header opens a **notification center** panel:
  the session's notifications (in-memory ring of 50 — deliberately not
  persisted, matching the minimal-storage rule).
- `notifications.use_windows_native: false` by default; `true` routes
  through `QSystemTrayIcon.showMessage` for users who prefer the OS center.

---

## 5. Feature work packages

Each package lists: behavior, config schema, parser/executor touch-points,
security notes, acceptance criteria.

### F1. Website allow-list + quiet open prompt

- **Behavior.** `config["allow_list"]` = list of normalized host patterns
  (`"youtube.com"` matches `www.youtube.com` and subdomains). When any path
  would open a URL (`open_url`, `search` results, a mode's website items):
  1. Isha **constructs the full URL** as it already does (bare domain →
     `https://…`).
  2. Host on the allow-list → opens immediately, exactly as today.
  3. Host not on it → the URL is **not** opened; a quiet prompt (§4.4) shows
     "Open **youtube.com**? `https://www.youtube.com/…`" with buttons
     *Open once* / *Always allow* (adds to the list, then opens) / *Not now*.
     No alarm styling, no sound — the exact requested flow.
  4. Non-interactive paths (scheduler-activated modes) **skip** the URL with
     a toast ("study mode: skipped youtube.com — not on your allow list;
     open Isha to allow it") — consistent with the Track A rule that
     background triggers never get to confirm on the user's behalf.
- **Commands.** "allow website youtube.com", "remove youtube.com from allow
  list", "show allow list" (new parser vocabulary + three small executor
  handlers on `a_allow_list.py`). Management UI lives in Customization (§6.4).
- **Config.** `"allow_list": ["youtube.com", ...]` — flat, minimal. A
  first-run migration seeds it from all websites already saved in existing
  modes, so upgrading never breaks a working mode. Setting
  `settings.allow_list_enabled` (default **on**) lets a user opt out
  entirely.
- **Security.** This is a strict tightening of `c_resolver_validator`'s URL
  gate (scheme check stays). Matching is on the **parsed hostname** via
  `urllib.parse` — never substring-on-the-whole-URL (avoids
  `evil.com/?q=youtube.com` bypasses); IDN hosts compared in punycode.
- **Acceptance.** Allow-listed URL opens with zero prompt; unlisted URL never
  opens without an affirmative; "Always allow" persists across restart;
  scheduler never opens an unlisted URL; migration seeds existing mode sites.

### F2. Default level for leveled actions

- **Behavior.** `set_volume` / `set_brightness` (and any future leveled
  action) parsed **without a number** resolve to
  `settings.defaults.level` (default **50**) instead of erroring, with the
  result sentence saying so ("Volume set to 50 — the default; say 'volume
  70' for a specific level").
- **Implementation.** One rule in `c_resolver_validator.py` (fill
  `params["level"]` when absent for actions in a `LEVELED_ACTIONS` set) —
  no parser change. Customizable in Settings ▸ General (spin 0–100).
- **Acceptance.** "set volume" → 50; user sets default 30 → "set brightness"
  → 30; explicit "volume 80" unaffected.

### F3. Multi-device-aware mute

- **Behavior.** On `mute_volume`, enumerate active audio output devices
  (pycaw `AudioUtilities`/`IMMDeviceEnumerator`; count includes e.g. laptop
  speakers + headphones + monitor). If **more than one** device is active,
  apply `settings.audio.mute_behavior`:
  | Choice (Settings ▸ General ▸ Sound) | Effect |
  |---|---|
  | `halve_all` — **default, as requested** | every device's volume → 50% of its current level |
  | `mute_all` | hard-mute every device |
  | `mute_default_only` | classic behavior — mute only the default device |
  | `set_all_to` + `audio.mute_level` (0–100) | every device → a fixed chosen level |
  Single device → classic mute (unchanged fast path).
- **Unmute.** `mute` snapshots per-device levels in memory first;
  `unmute` restores that snapshot (finally fixing the honest-but-sad
  "toggled mute, can't guarantee unmute" message when pycaw is present).
  Snapshot is in-memory only — not persisted (minimal-storage rule; a
  post-restart unmute just sets devices to `defaults.level`).
- **Degradation.** Without pycaw, exactly today's media-key behavior with
  today's honest message. This also feeds Modes: per-mode `volume` now
  applies through the same device-aware layer.
- **Acceptance.** Two active devices + default setting → both at half;
  unmute restores both exactly; setting switch changes behavior without
  restart; pycaw absent → media-key fallback.

### F4. Screenshots: PrtScr, open-after, standard path

- **Path.** Default becomes the **system-standard**
  `Pictures\Screenshots` (resolved via `SHGetKnownFolderPath(FOLDERID_Pictures)`
  — respects OneDrive-redirected Pictures — + `Screenshots`, created if
  missing; the same folder Win+PrtScr uses). `settings.screenshot.dir`
  overrides it; Settings shows a folder picker. Existing
  `Pictures\Isha Screenshots` users: migration keeps their old folder as the
  configured value so nothing moves silently.
- **After capture** — `settings.screenshot.after: "save" | "save_and_open"`
  (default `save`; `save_and_open` launches the saved PNG in the default
  viewer). Toast either way: "Screenshot saved · Open · Copy path".
- **PrtScr key** — `settings.screenshot.prtscr: "off" | "isha"` (default
  **off**). When `"isha"`, register `VK_SNAPSHOT` via the existing
  `hotkey_listener` (a third instance — the mechanism already supports N
  listeners). Settings copy explains the OS conflict honestly: Windows 11's
  "Use Print Screen to open Snipping Tool" wins if enabled, with a one-click
  pointer to that OS setting. Registration failure → quiet toast, setting
  reverts — fail-closed, never a mystery dead key.
- **Capture scope** — `settings.screenshot.capture: "full" | "window"`
  (full desktop vs. foreground window via `GetForegroundWindow` +
  `GetWindowRect` + `ImageGrab.grab(bbox)`), the requested customization
  choice. (Region-snip overlay: explicitly deferred — Windows already ships
  one, and a half-good snipper is worse than none.)
- **Acceptance.** Default path matches Win+PrtScr's folder; custom dir
  honored; PrtScr triggers capture when enabled and cleanly reports the
  Snipping Tool conflict; open-after opens; window capture crops correctly
  on multi-monitor.

### F5. Reminders that exist and fire (closes Cycle 2 C1)

- **Record** (`config["reminders"]`, replacing the write-only Phase-1 shape):
  `{"id", "text", "at": ISO-8601 local, "repeat": "none"|"daily"|"weekly"|
  {"days":[0-6]}, "enabled": true, "last_fired": ISO|null}` — minimal, flat,
  human-readable JSON, per the storage rule. Migration upgrades any old
  records.
- **Engine.** `mode_scheduler`'s existing 20 s poll loop gains a reminders
  pass (no second thread): a reminder fires when `now ≥ at` and it hasn't
  fired for that occurrence; `none` → `enabled=false` after firing;
  repeating → compute next occurrence. **Missed-while-off** reminders
  (machine asleep/Isha closed) fire once on startup with "(missed)between-
  then" phrasing rather than being dropped silently.
- **Firing** = a toast (§4.5) with **Snooze 10 min** and **Done** actions;
  optional `soft` sound only if the user enabled notification sound.
- **Commands** already parse (`set_reminder`); executor's handler now writes
  the new shape; add "show reminders", "delete reminder <n>".
- **UI**: the Reminders sidebar page (§6.2).
- **Acceptance.** "remind me to stretch at 4pm" fires a toast at 4pm with
  working snooze; daily reminder fires next day; reminder set for a time
  when Isha was closed fires as "(missed)" on next launch; disabling in UI
  stops firing without deleting.

### F6. Named scripts

- **Record.** `config["scripts"]`: `{name: {"command": str, "created":
  ISO}}`. Names share the alias namespace rules (single word, lowercased by
  the tokenizer — validated on save).
- **Use.** "run backup" (new `run_script` action: parser tries scripts before
  app fuzzy-match on a `run` verb); modes' `script` field may now be either
  a raw command (legacy) **or** a saved script name — one level of
  indirection, resolved at activation, **no nesting** (a script's command
  is never re-parsed for further script references — bounds the audit
  surface).
- **Save** via command ("save script backup as `robocopy …`" — the free-text
  tail is taken verbatim, same shape-function pattern as `add_alias`) or the
  Customization page editor (name + multiline command + a visible "scripts
  run as you — review before saving" note).
- **Security — inherits Track A1 wholesale, no exceptions:** the
  `settings.allow_mode_scripts` opt-in (renamed `allow_scripts`, migrated)
  gates *all* script execution; first run of any given command string shows
  it **verbatim** in a quiet prompt; non-interactive triggers never execute
  scripts (existing invariant, now re-asserted for `run_script` in the A6
  test suite); log records for `run_script` redact nothing (commands aren't
  PII) but saved scripts never auto-run on save.
- **Acceptance.** Save → "run backup" prompts showing the verbatim command →
  runs; with `allow_scripts` off, both saving (warns) and running (refuses,
  explains how to enable) behave; a trigger-activated mode referencing a
  named script skips it with a toast; A6 suite extended and green.

### F7. Config schema v2 (the "everything aligned" pass)

One migration (`config_store.py`: `SCHEMA_VERSION = 2`, idempotent
`_migrate_v1_to_v2`, with the existing corrupt-file backup behavior), so all
of the above lands as **one coherent, minimal, documented JSON layout**:

```jsonc
{
  "schema_version": 2,
  "modes": { ... },                    // unchanged; "script" may name a saved script
  "active_mode": null,
  "aliases": {}, "hotkeys": {}, "triggers": [], "snippets": {},
  "allow_list": [],                    // F1
  "reminders": [],                     // F5 shape
  "scripts": {},                       // F6
  "license": null,                     // unchanged (DPAPI-wrapped on Windows)
  "settings": {
    "onboarded": true,
    "allow_scripts": false,            // renamed from allow_mode_scripts
    "allow_list_enabled": true,
    "defaults": { "level": 50 },       // F2
    "audio":  { "mute_behavior": "halve_all", "mute_level": 50 },   // F3
    "screenshot": { "dir": null, "after": "save",
                     "prtscr": "off", "capture": "full" },          // F4 (dir null = system default)
    "notifications": { "sound": "off", "use_windows_native": false },
    "ui": { "theme": "auto",           // auto follows Windows light/dark
             "sidebar_collapsed": false, "show_scrollbars": "auto",
             "reduce_motion": false, "close_action": "tray",
             "overlay_autohide": 2.5, "window": {},
             "quick_actions": [ {"label": "...", "command": "..."} ] },
    "hotkey": "ctrl+alt+space", "voice_hotkey": null,
    "report_intake_url": null, "update_manifest_url": null
  }
}
```

Everything stays in the **single** `%APPDATA%\Isha\config.json` (plus the
existing registry cache and logs) — local, minimal, one file, exactly as
requested. The A4 owner-only DACL continues to cover it.

---

## 6. Sidebar pages (beyond the dashboard)

Every page = header (title + one-line description) + scrollable body of
cards; all edits mutate the shared in-memory config then `save_config` —
same live-effect model `settings_window.py` proved.

1. **Modes** (§6.1) — card per mode: name, active toggle, app/website chips
   (add/remove inline), per-mode volume/theme rows, script row (raw or named,
   with the allow_scripts state visible), layout capture button, triggers
   list (time/battery/app-launch/idle — finally UI-editable, closing a C2
   leftover), delete (quiet confirm). "New mode" opens an inline creation
   card, not a wizard.
2. **Reminders** (§F5) — list sorted by next occurrence: text, when, repeat
   badge, enabled toggle, delete; inline "new reminder" row with natural
   date/time entry ("tomorrow 9am") parsed by the same code path as the
   typed command.
3. **Shortcuts** — table of every binding: quick-input hotkey, voice hotkey,
   PrtScr option, in-app keys (Ctrl+K/B/,). **Real rebinding UI** (finishes
   C2's deferred half): click → "press keys…" capture field → re-register
   via `hotkey_listener` live → conflict (`RegisterHotKey` failure) shown
   calmly with the old binding kept. This is safe to build now because
   Cycle 4 development happens *on Windows* (§8), removing C2's
   couldn't-verify-blind blocker.
4. **Customization** — sections: Quick actions (editor per §4.1), Aliases
   (migrated from settings tab), Snippets (ditto), **Scripts** (F6 editor),
   **Website allow-list** (F1 editor), Appearance (theme
   light/dark/auto with live preview swatch, scrollbar mode, reduce motion,
   sidebar default, overlay auto-hide).
5. **Settings** — General (default level F2, mute behavior F3, screenshot
   group F4, notifications, close action, start-with-Windows via `HKCU\...\Run`
   — new, small, opt-in), Voice (model status + the C4 guided model download:
   opt-in, checksum-verified, progress bar), Privacy (the promise, log
   folder link, "open config" button), License (port of existing tab),
   Updates (check/install via existing signed chain), About.
6. **Help / Docs** — inside Settings as requested: offline pages rendered
   from `docs/*.md` (already in repo) via `QTextBrowser` markdown: Getting
   started, Command cheat-sheet (superset of `show_help`'s text), Modes
   guide, Scripts & security explainer (why the opt-in exists — honesty as
   a feature), Privacy/threat model (user-readable `THREAT_MODEL.md`
   digest), Troubleshooting.

The onboarding wizard is rebuilt as a first-run **in-window** overlay (3
slides over the dashboard: welcome/privacy → the command bar + hotkey → make
a first mode), honoring the existing `settings.onboarded` flag.

---

## 7. Performance & efficiency track (runs through every milestone)

Targets (measured on the packaged build, mid-range Win 11 laptop):

| Metric | Target |
|---|---|
| Cold start → interactive main window | < 2.0 s |
| Quick-input overlay show (hotkey → focused input) | < 50 ms |
| Command submit → UI acknowledges (spinner/result) | < 30 ms (execution itself is async) |
| Idle CPU | ~0% (poll loops stay at 20 s; no busy timers) |
| Idle RAM (packaged, window open) | < 150 MB; tray-minimized < 120 MB |
| Suggestion latency while typing | < 30 ms per keystroke (debounced 120 ms) |

Workstreams:

- **P1 Async everywhere** — §3.2's runner; also move registry warm-up
  (`get_app_registry`) to a background thread at startup so first keystroke
  never pays the scan; screenshot save, report zip, update download already
  off-thread or made so.
- **P2 No rebuild refreshes** — pages update models in place; recent-actions
  and logs are virtualized lists.
- **P3 Startup discipline** — lazy page construction (§3.3), lazy `PySide6`
  submodule imports, defer pycaw/pywin32 imports to first use (already the
  codebase's pattern — keep it), profile with `-X importtime` and record the
  numbers in this file at M6.
- **P4 The scroll fix** — free with QScrollArea, but add an explicit
  regression check (wheel over every page, nested lists, and the logs view).
- **P5 Measurement, not vibes** — a `tools/perf_smoke.py` script that times
  cold start, overlay show, and 20 sequential commands, run before each
  milestone sign-off; numbers go in the milestone table below.

---

## 8. Development environment shift — build **on Windows** this cycle

Cycles 1–3 were built on Linux/WSL with every Win32 path "implemented but
never run" — the single biggest honesty gap (Track B1 is still open). Cycle 4
is UI-heavy and Windows-only-behavior-heavy, and **this repo now lives on a
real Windows 11 machine (`d:\Projects\windows_assistant`)** — so Cycle 4
development *is* the B1 verification pass, interleaved rather than deferred:

- Milestone M1 starts by running the *existing* app on this machine
  (`run.bat`) and filling in B1's results table for the pipeline-level
  handlers (volume, theme, hotkey, window ops, clipboard, battery, idle,
  SendInput) **before** building new UI on top of any broken one.
- Every new Qt surface is verified visually here as it's built — no more
  "syntax-checked only" caveats.
- `tests/` grows alongside: keep `test_security_hardening.py` green at every
  milestone; add `test_allow_list.py`, `test_reminders_engine.py`,
  `test_scripts_named.py`, `test_config_migration_v2.py`, `test_defaults_level.py`
  (all headless — the pipeline stays Qt-free), plus a manual UI checklist
  per §3.4 executed at M6.

---

## 9. Packaging — producing the `.exe` (the deliverable)

Builds on the existing `packaging/` work (Cycle 3), updated for Qt:

1. **`packaging/isha.spec`** — entry point changes `tray_app.py` → `app.py`;
   add PySide6 hooks; **exclude** QtWebEngine/QML/Quick/3D/Charts plugins,
   unused imageformat plugins, and translations except `en`; add
   `assets/*.svg`, `design/theme.qss`, `docs/*.md` as datas; keep one-folder
   mode (fast start). Expect `dist\Isha\Isha.exe` ≈ 120–160 MB folder.
2. **`packaging/isha.ico`** — create the sakura-blossom icon (§2.2); wire
   into spec + Inno + window/tray/overlay.
3. **`packaging/isha.iss`** — bump version (`version.py` → `2.0.0`), keep
   per-user no-admin install, add optional "Start Isha with Windows" task
   mapped to the new setting, and "Launch Isha" post-install (which now
   opens the full window — a much better first impression than a tray dot).
4. **`packaging/build.ps1`** — unchanged flow (PyInstaller → Inno →
   optional signtool); verify it runs end-to-end on this machine.
5. **Smoke matrix on the packaged build:** fresh install on a clean user
   account; first-run onboarding; 20-command sweep; mode with website
   (allow-list prompt); reminder fires; PrtScr on/off; both themes; scaling
   125%/150%; uninstall leaves `%APPDATA%\Isha` (documented) and nothing
   else.
6. **Unblocked-by-code, still-owner steps (unchanged from Cycle 3 runbook):**
   real keypairs (`generate_license.py keygen`), code-signing cert (D3 —
   until then SmartScreen warns, expected), MoR account, hosting. The `.exe`
   itself does **not** wait on these.

---

## 10. Milestones, order, and acceptance

Strict order; each milestone ends with: security suite green, perf smoke
recorded, and a short status note appended to this file (the ROADMAP.md
convention).

| # | Milestone | Contents | Done when |
|---|---|---|---|
| **M0** | Foundations | §8 environment check + existing-app B1 sweep on this machine; config schema v2 + migration (F7) + its tests; `design/tokens.py` + QSS + the two SVGs + icon; PySide6 pinned | old app runs here with results table filled; migration tests green; a bare themed QMainWindow renders both themes |
| **M1** | Shell | `app.py` (single instance, tray, hotkeys wired), MainWindow + sidebar + page stack + scrolling + theme switching; async command runner; quiet-prompt + toast widgets | window launches full-size, navigates, scrolls by wheel, minimizes to tray; a destructive command confirms via quiet prompt end-to-end |
| **M2** | Dashboard | Command bar + suggestions + inline results; quick actions (+ customization editor); modes strip; recent; logs view | every Cycle-1 command usable from the bar; nothing blocks the UI thread (3 s mode-activate stays responsive) |
| **M3** | Overlay + voice | Quick-input overlay; streaming voice into both bars; voice hotkey → overlay pre-listening | overlay < 50 ms, on top of a fullscreen app; spoken words appear live and are editable before Enter |
| **M4** | Features | F1 allow-list, F2 default level, F3 mute, F4 screenshots (+ PrtScr), F5 reminders engine, F6 named scripts — each with its tests | all six acceptance blocks in §5 pass |
| **M5** | Pages | Modes / Reminders / Shortcuts (real rebinding) / Customization / Settings + Help docs; in-window onboarding; delete `command_palette.py`, `settings_window.py`, `dashboard_window.py`, `onboarding_wizard.py`, `ui_theme.py`, `tray_app.py` | every config key editable from UI; no Tkinter import remains; hotkey rebind survives restart |
| **M6** | Quality gate | §3.4 behaviors checklist; §7 perf targets measured & recorded; accessibility pass (keyboard-only full traversal, contrast check both themes, reduce-motion); full regression of pipeline tests + security suite | all targets met or consciously waived in writing here |
| **M7** | Ship | §9 packaging; installer smoke matrix; ROADMAP.md cross-link + status update | **`IshaSetup-2.0.0.exe` installs and runs the full experience on a clean Windows account** |

Rough effort: M0–M1 are the heavy lifts (~30% of the cycle), M2–M5 the wide
middle (~50%), M6–M7 the disciplined tail (~20%). Nothing in M2+ starts
before M1's runner exists — building pages on a synchronous shell would
recreate the exact slowness this cycle exists to kill.

---

## 11. Risks & mitigations

- **Qt learning curve / QSS fights** → keep widgets simple (no custom
  paint except the branch backdrop and toast cards); tokens-first so
  restyling never touches logic.
- **Bundle/RAM growth** → measured at every milestone (§7); Essentials-only
  install + plugin excludes; if idle RAM exceeds 150 MB, the fallback is
  trimming plugins/fonts, **not** reverting the framework.
- **PrtScr conflicts with Snipping Tool** → default off, honest Settings
  copy, fail-closed registration (F4).
- **Streaming voice partials misbehave per-microphone** → the fixed-record
  path stays as fallback (`voice.streaming: false`).
- **Two config writers during migration window** (old Tk app + new app run
  once each) → schema v2 migration is idempotent and version-gated; v1 app
  refuses v2 files gracefully via the existing corrupt-backup path — and the
  Tk surfaces are deleted at M5 anyway.
- **Scope creep on "amazing UI"** → the design system (§2) is the contract;
  anything not expressible in its tokens/motion rules is out by definition
  ("never going over the board", as specified).

## 12. Explicitly out of scope for Cycle 4

Region-snip overlay (F4 note); notification history persisted to disk;
cloud/sync anything; localization beyond the existing English+Hinglish
parsing; online activation server (D4); auto-update *background* polling
(stays manual/opt-in); mobile/companion apps.

---

*Written 2026-07-07 against commit 2580221. Companion to `ROADMAP.md`
(Cycles 1–3) — status updates for Cycle 4 land here, in the same
append-a-dated-note convention.*

---

## Status — 2026-07-07: Cycle 4 executed (M0–M7)

All milestones implemented in one pass on this Windows 11 machine.

**M0.** B1 sweep surfaced a real hole on first run: `%TEMP%` lives inside
`%LocalAppData%`, so the A4 path-trust check accepted planted executables in
the user's temp dir — fixed in `executor._is_path_trustworthy` (temp subtree
carved out before the root allow-list). Config schema v2 + idempotent
migration landed in `config_store.py` (`tests/test_config_migration_v2.py`,
11 tests). `design/tokens.py` + `design/theme.qss` (both themes from one
template) + `assets/branch.svg` / `assets/sprig.svg` created.

**M1–M3.** `app.py` (single-instance mutex, tray via QSystemTrayIcon, hotkeys,
schedulers, live hotkey rebinding hook), `shell/main_window.py` (lazy page
stack, branch backdrop, geometry persistence, close-to-tray asked once
quietly), `shell/sidebar.py`, `services/command_runner.py` (worker thread +
confirmation futures — the UI never blocks), `services/notifier.py` (silent
top-right toasts, session ring of 50), `widgets/quiet_prompt.py` (every
confirmation; messagebox is gone), `widgets/command_bar.py` (shared by
dashboard + overlay, 120 ms-debounced suggestions),
`pages/overlay.py` (frameless always-on-top quick input),
`services/voice_controller.py` (Vosk streaming partials; voice never
auto-executes), `pages/onboarding.py` (3 quiet in-window slides).

**M4.** F1 `a_allow_list.py` (+ gate in `executor.open_url` and mode website
opens; hostname-parsed matching; scheduler paths skip with a toast; Open
once / Always allow / Not now prompt) — `tests/test_allow_list.py`.
F2 default level in `c_resolver_validator.validate` — `tests/test_defaults_level.py`.
F3 `a_audio.py` multi-device mute (halve_all default, in-memory snapshot
restore, media-key fallback). F4 `a_screenshot.py` (SHGetKnownFolderPath
Pictures\Screenshots default, dir override, save_and_open, window capture,
PrtScr via `hotkey_listener` VK_SNAPSHOT — default off, fail-closed).
F5 `a_reminders.py` engine riding mode_scheduler's 20 s loop (missed-fire
recovery, snooze) — `tests/test_reminders_engine.py`. F6 `a_scripts.py`
(save/run/delete/show; `run <name>` exact-match upgrade in the resolver;
mode script field resolves one level; all three A1 gates inherited) —
`tests/test_scripts_named.py`. Parser vocabulary + shapes added for all of it.

**M5.** All six pages (`pages/dashboard|modes|reminders|shortcuts|
customization|settings.py`) + offline help (`docs/help/*.md` via
QTextBrowser). Deleted: `command_palette.py`, `settings_window.py`,
`dashboard_window.py`, `onboarding_wizard.py`, `ui_theme.py`, `tray_app.py`.
No tkinter/pystray import remains; `run.bat` → `app.py`; version → 2.0.0.

**M6.** Test suite: **66 passed** (15 security + 51 new/existing). Perf smoke
(`tools/perf_smoke.py`, dev machine, unpackaged): window construct+show
1 929 ms (target < 2 000 — dashboard build deferred one event-loop turn past
first paint; Qt's one-time first-QLineEdit init is ~750 ms of it), overlay
re-show 46–54 ms (target < 50, run-to-run noise straddles it), pipeline
5.3 ms/command. Idle CPU ~0% (20 s poll loops unchanged).

**M7.** `packaging/isha.spec` → entry `app.py`, Qt excludes (no QML/Quick/
WebEngine/Multimedia/…), assets/QSS/help-docs as datas; sakura-blossom
`packaging/isha.ico` generated; Inno Setup 6 installed; `build.ps1` run on
this machine → `dist\Isha\Isha.exe` and `dist\installer\IshaSetup-2.0.0.exe`.

> **Superseded by Cycle 5.** This pass shipped with an "Isha Lite" free-tier
> gate and an offline signed-license system. Cycle 5 (below) removed all of it —
> every feature is now unconditionally available. The licensing notes in the
> sections above are retained only as a historical record of what Cycle 4 built.

**Still owner steps (unchanged from the Cycle 3 runbook):** code-signing cert
(SmartScreen warns until then), hosting. **Deferred honestly:** streaming-voice fallback flag exists but the
streaming path hasn't been exercised against a real microphone+model here;
the §3.4 manual behaviors checklist and installer smoke matrix on a *clean*
user account remain to be walked through by hand.


---

# Cycle 5 — Licensing removal (complete 2026-07-08)

> **Why.** The offline signed-license system (Cycle 1 §6, hardened in Cycle 2
> Track A5, fulfilled by the Cycle 3 webhook) turned out to be net-negative in
> practice: the shipped build carried only a *placeholder* public key, so every
> real key failed verification by design, and the "Isha Lite" free-tier gate
> then blocked most actions behind that unusable key. The product is now simply
> **free and fully unlocked** — no keys, no tiers, no gate.

## What was removed

- **`a_licensing.py`** — deleted in full (Ed25519 verification, DPAPI record
  store, device fingerprint, `is_licensed`, the `FREE_ACTIONS`/`META_ACTIONS`
  free-tier gate, and `free_tier_upgrade_message`).
- **The enforcement point** in `executor.execute` — the `is_action_free_tier`
  check that returned `upgrade_required` is gone; every resolved action now
  dispatches straight to its handler (confirmation gates for destructive
  actions are untouched).
- **Executor actions** `activate_license` / `license_status` /
  `deactivate_license` and their `ACTION_HANDLER_MAP` entries.
- **Parser vocabulary + shapes** — `activate/enter/check/deactivate license`
  verb map entries and `license_key_shape`. These commands now resolve to
  "No Action Found!" like any other unknown phrase.
- **UI** — the "License" card and `_activate_license` handler in
  `pages/settings.py`; the unlicensed-reminder toast in `app.py` and the CLI
  reminder in `main.py`.
- **Config** — the `license` key dropped from the default config
  (`config_store.py`). Stale `license` values in existing config files are
  simply ignored; no migration is needed.
- **Logging** — `activate_license`/`license_status` removed from
  `logger.SENSITIVE_ACTIONS` (there is no longer any buyer email/key to redact).
- **Fulfilment + tooling** — `server/` (the license webhook + its README/reqs)
  and `tools/generate_license.py` deleted.
- **Docs** — license mentions removed from `docs/help/*.md`, `THREAT_MODEL.md`
  (A5 at-rest row, the separate-keypairs row, the "soft gate" note), and
  `packaging/README.md` / `packaging/isha.iss` comments.
- **Tests** — `LicenseAtRestTests` dropped from `test_security_hardening.py`;
  `license status` swapped for `check internet` in `tools/perf_smoke.py`; the
  `license` key removed from the `test_config_migration_v2.py` fixture.

## What stayed

- The **update** signing path (`a_updater.py` + `tools/sign_manifest.py`) is
  untouched — it was always a separate keypair and a separate concern
  (authenticity of a downloaded installer, not payment).
- All Cycle 2 Track A security invariants except the license-store one.

## Status

**Complete 2026-07-08.** Test suite: **64 passed**. `activate/license status`
verbs confirmed dead-ended through the full `process_command_safe` pipeline;
all functional commands unaffected. Remaining owner steps reduce to: real
update-signing keypair, code-signing cert, hosting. No payment/MoR/webhook
work remains — the product ships free.
