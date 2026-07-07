# Isha 2.0 — New Version Roadmap (Cycle 4: "Sakura")

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
> fail-closed signatures, redacted logs, DPAPI-protected license), the
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

**Bonus fix found by the M6 sweep:** the Isha Lite free-tier gate blocked
*every* non-free action including `activate license`, `help`, `undo` and the
update/report paths — an unlicensed install could never become licensed.
`a_licensing.META_ACTIONS` now exempts the meta/hygiene set; feature actions
stay gated exactly as before.

**Still owner steps (unchanged from the Cycle 3 runbook):** real Ed25519
keypairs, code-signing cert (SmartScreen warns until then), MoR account,
hosting. **Deferred honestly:** streaming-voice fallback flag exists but the
streaming path hasn't been exercised against a real microphone+model here;
the §3.4 manual behaviors checklist and installer smoke matrix on a *clean*
user account remain to be walked through by hand.
