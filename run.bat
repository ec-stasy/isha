@echo off
REM ---------------------------------------------------------------------------
REM run.bat — run Isha from source on Windows, for development / your own use.
REM Double-click it, or run it from a terminal in the project folder.
REM
REM This runs the TRAY app (tray_app.py) the way end users experience it.
REM For the CLI instead, run:  python main.py
REM
REM Isha does NOT need Administrator rights — just run it normally (see
REM packaging\isha.manifest for why). If you ever want to test elevated
REM behavior, right-click this file -> "Run as administrator".
REM ---------------------------------------------------------------------------
setlocal

REM First run only: create a local virtual env and install dependencies.
if not exist ".venv\" (
    echo First run: creating virtual environment and installing dependencies...
    py -3 -m venv .venv || python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo Starting Isha (tray app). Look for the tray icon; press the palette hotkey to open it.
python tray_app.py

endlocal
