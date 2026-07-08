# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Isha (Cycle 3 / Track B2).

Build from the PROJECT ROOT, on Windows, with the app's dependencies installed:

    pip install -r requirements.txt pyinstaller
    pyinstaller packaging/isha.spec --noconfirm

Produces a one-FOLDER build under dist/Isha/ (fast cold-start, per the roadmap's
Stack notes — Nuitka one-file is a later size/speed optimization, not a blocker).
The folder is what packaging/isha.iss wraps into an installer.

Entry point is app.py (the Qt desktop app, Cycle 4), NOT main.py (the CLI).
Console is off. Optional dependencies are listed as hiddenimports so the
bundle includes them; every one of them is still guarded by a try/except at
runtime, so a missing-at-runtime case still degrades gracefully.

Qt discipline: Essentials-only install, and QML/Quick/WebEngine/3D/etc. are
explicitly excluded below — none of them is imported anywhere in the code.
"""
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# SPECPATH (injected by PyInstaller) is this file's own directory
# (packaging/), not the invocation cwd — Analysis()'s script path is resolved
# relative to SPECPATH, so it must point one level up at the project root.
_project_root = os.path.dirname(SPECPATH)

# Optional/dynamically-imported packages. These are imported lazily or behind
# try/except in the app, so PyInstaller's static graph can miss them — list them
# explicitly. Harmless if a given package isn't installed at build time: drop the
# ones you don't ship (e.g. voice) to slim the bundle.
_optional = [
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageGrab",
    "win32gui", "win32con", "win32clipboard", "win32api", "win32process",
    "win32com", "win32com.client", "pywintypes", "pythoncom",
    "pycaw", "comtypes",
    "rapidfuzz",
    "cryptography", "cryptography.hazmat.primitives.asymmetric.ed25519",
    # Voice (Cycle 6): the online pipeline is small enough to bundle —
    # sounddevice for mic capture, SpeechRecognition for the web speech API.
    # (The old Vosk offline model approach is gone; nothing to download.)
    "sounddevice", "speech_recognition",
]
hiddenimports = []
for mod in _optional:
    try:
        hiddenimports += collect_submodules(mod)
    except Exception:
        hiddenimports.append(mod)

datas = [
    (os.path.join(_project_root, "assets", "branch.svg"), "assets"),
    (os.path.join(_project_root, "assets", "sprig.svg"), "assets"),
    (os.path.join(_project_root, "assets", "mic.svg"), "assets"),
    (os.path.join(_project_root, "assets", "mic_active.svg"), "assets"),
    (os.path.join(_project_root, "assets", "check_light.svg"), "assets"),
    (os.path.join(_project_root, "assets", "check_dark.svg"), "assets"),
    (os.path.join(_project_root, "design", "theme.qss"), "design"),
    (os.path.join(_project_root, "docs", "help"), os.path.join("docs", "help")),
]
_icon = os.path.join(_project_root, "packaging", "isha.ico")
if os.path.exists(_icon):
    datas.append((_icon, "."))

_version_info = os.path.join(_project_root, "packaging", "version_info.txt")
_manifest = os.path.join(_project_root, "packaging", "isha.manifest")

a = Analysis(
    [os.path.join(_project_root, "app.py")],
    pathex=[_project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "tkinter.test", "test", "unittest", "pydoc_data",
        # Qt we never import — keeps the bundle at Widgets+Svg only
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebChannel", "PySide6.QtWebSockets",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSql",
        "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtNfc",
        "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtSerialPort",
        "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
        "PySide6.QtTextToSpeech", "PySide6.QtHelp", "PySide6.QtDesigner",
        "PySide6.QtUiTools", "PySide6.QtNetworkAuth",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Isha",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                       # tray app — no console window
    disable_windowed_traceback=False,
    icon=_icon if os.path.exists(_icon) else None,
    version=_version_info if os.path.exists(_version_info) else None,
    # manifest: asInvoker (NOT requireAdmin). Isha is a per-user app; requiring
    # elevation would add a UAC prompt on every launch and make SmartScreen
    # warier. See packaging/isha.manifest and packaging/README.md.
    manifest=_manifest if os.path.exists(_manifest) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Isha",
)
