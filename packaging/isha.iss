; Inno Setup script for Isha (Cycle 3 / Track B2).
; Wraps the PyInstaller one-folder build (dist\Isha\) into a single
; IshaSetup-x.y.z.exe installer.
;
; Build (on Windows, after PyInstaller has produced dist\Isha\):
;   1. Install Inno Setup 6:  https://jrsoftware.org/isdl.php
;   2. iscc packaging\isha.iss
;   (packaging\build.ps1 does both steps for you.)
;
; Design choices, matching packaging\isha.manifest:
;   - PrivilegesRequired=lowest  -> per-user install, NO admin/UAC prompt. Isha
;     is a single-user app; a per-user install is the honest, friction-free
;     default and keeps "start with Windows" working (elevated autostart is
;     blocked by default).
;   - "Start Isha when I sign in" is an OPT-IN checkbox, unchecked by default,
;     implemented as a per-user Run registry value (no admin needed).

#define MyAppName "Isha"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Isha"
#define MyAppURL "https://YOUR-DOMAIN.com"
#define MyAppExeName "Isha.exe"

[Setup]
AppId={{A7E4F2C1-3B5D-4E8A-9C21-ISHA00000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=IshaSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=isha.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; When you have a code-signing cert (Track D3), uncomment and configure:
; SignTool=signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 $f

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startupicon"; Description: "Start {#MyAppName} automatically when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; The entire PyInstaller one-folder output. "*" + recursesubdirs grabs the exe,
; the Python runtime, and every bundled dependency.
Source: "..\dist\Isha\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Opt-in "start with Windows" — per-user Run key, only if the task is ticked.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; \
  Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Leave user data (%APPDATA%\Isha: config, logs) in place on uninstall by
; default — do NOT auto-delete it, so a reinstall keeps the user's modes and
; settings. A user who wants a clean wipe can delete %APPDATA%\Isha by hand.
