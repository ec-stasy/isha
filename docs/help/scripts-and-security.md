# Scripts & security — why the extra switch exists

Scripts are the one place Isha can run an arbitrary command line, which makes
them as powerful as anything you could type into a terminal yourself. So they
are guarded honestly rather than hidden:

1. **Off by default.** Nothing script-related runs until you turn on
   *allow scripts* in Settings ▸ General. Most people never need it.
2. **You see the exact command.** The first time a script runs, Isha shows
   its literal text in a quiet card and waits for your yes. A config-file
   edit can't smuggle a command past you.
3. **Automations never run scripts.** A mode activated by a schedule or
   trigger skips its script step every time — only you, present at the
   keyboard, can approve one.

The same idea runs through the rest of Isha:

- **Website allow-list** — hosts are compared by real parsed hostname, so
  `evil.com/?q=youtube.com` can never ride on your `youtube.com` entry.
- **App launches** are re-validated at launch time; a poisoned cache file
  can't make "open chrome" start something else.
- **Updates and licenses** are signature-checked and fail closed.
- **Logs are redacted** and stay on this machine; the config file is
  owner-only.

Privacy in one line: **nothing leaves this machine unless you explicitly
send an issue report.**
