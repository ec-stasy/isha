# Troubleshooting

**The hotkey doesn't open the quick input box.**
Another app may hold Ctrl+Alt+Space. Pick a different combo in Shortcuts —
if registration fails, Isha keeps the old one and tells you.

**Print Screen doesn't trigger Isha.**
Windows 11's "Use Print Screen to open Snipping Tool" wins when enabled —
turn it off under Windows Settings ▸ Accessibility ▸ Keyboard, or leave
PrtScr to Windows and use `take screenshot` instead.

**Voice input says it's unavailable.**
Voice needs the optional vosk + sounddevice packages and a downloaded model
(Settings ▸ Voice). It's fully offline — nothing you say leaves the machine.

**"Couldn't confidently match … to an installed app."**
Isha only launches apps it can verify. Try the app's exact name, or add an
alias (Customization ▸ Aliases). The app index refreshes on startup.

**A reminder didn't fire.**
Reminders fire while Isha is running (window open or in the tray). Ones that
came due while it was closed fire once at next launch, marked "(missed)".

**Where is my data?**
One JSON file: `%APPDATA%\Isha\config.json`, plus logs next to it. Delete
that folder and Isha forgets everything. Nothing is stored anywhere else.

**Something crashed.**
Isha logs a report ID locally. `report issue` builds a zip you can inspect
before anything is sent — sending is always your explicit choice.
