<#
    build.ps1 — one-command release build for Isha (run on Windows, PowerShell).

    From the PROJECT ROOT:
        powershell -ExecutionPolicy Bypass -File packaging\build.ps1

    Steps:
      1. Sync version_info.txt to version.py's VERSION.
      2. PyInstaller  -> dist\Isha\        (one-folder app bundle)
      3. Inno Setup   -> dist\installer\IshaSetup-<version>.exe
      4. (optional) code-sign both, if a cert is configured (see -SignThumbprint).

    Prereqs (install once):
        pip install -r requirements.txt pyinstaller
        Inno Setup 6:  https://jrsoftware.org/isdl.php  (iscc on PATH, or set -Iscc)
#>
param(
    [string]$Iscc = "iscc",                 # path to Inno Setup's iscc.exe if not on PATH
    [string]$SignThumbprint = "",           # cert thumbprint to sign with (Track D3); empty = skip signing
    [switch]$SkipInstaller                  # build the app folder only, not the installer
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")   # project root

# --- 1. read VERSION from version.py and rewrite version_info.txt -------------
$verLine = Select-String -Path "version.py" -Pattern 'VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"'
if (-not $verLine) { throw "Could not read VERSION from version.py" }
$version = $verLine.Matches[0].Groups[1].Value
$parts = $version.Split(".")
$tuple = "($($parts[0]), $($parts[1]), $($parts[2]), 0)"
$dotted = "$version.0"
Write-Host "Building Isha $version" -ForegroundColor Cyan

$vi = Get-Content "packaging\version_info.txt" -Raw
$vi = $vi -replace 'filevers=\([0-9, ]+\)', "filevers=$tuple"
$vi = $vi -replace 'prodvers=\([0-9, ]+\)', "prodvers=$tuple"
$vi = $vi -replace '"FileVersion", "[0-9.]+"', "`"FileVersion`", `"$dotted`""
$vi = $vi -replace '"ProductVersion", "[0-9.]+"', "`"ProductVersion`", `"$dotted`""
Set-Content "packaging\version_info.txt" -Value $vi -NoNewline

# keep the Inno version in sync too
$iss = Get-Content "packaging\isha.iss" -Raw
$iss = $iss -replace '#define MyAppVersion "[0-9.]+"', "#define MyAppVersion `"$version`""
Set-Content "packaging\isha.iss" -Value $iss -NoNewline

# --- 2. PyInstaller -----------------------------------------------------------
Write-Host "==> PyInstaller" -ForegroundColor Cyan
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist\Isha") { Remove-Item "dist\Isha" -Recurse -Force }
python -m PyInstaller "packaging\isha.spec" --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# --- 3. optional: sign the app exe --------------------------------------------
function Sign-File($path) {
    if ($SignThumbprint) {
        Write-Host "==> signing $path" -ForegroundColor Cyan
        signtool sign /sha1 $SignThumbprint /fd sha256 /tr http://timestamp.digicert.com /td sha256 $path
        if ($LASTEXITCODE -ne 0) { throw "signtool failed on $path" }
    }
}
Sign-File "dist\Isha\Isha.exe"

if ($SkipInstaller) { Write-Host "Done (app folder only): dist\Isha\" -ForegroundColor Green; exit 0 }

# --- 4. Inno Setup ------------------------------------------------------------
Write-Host "==> Inno Setup" -ForegroundColor Cyan
& $Iscc "packaging\isha.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup (iscc) failed — is it installed and on PATH?" }

Sign-File "dist\installer\IshaSetup-$version.exe"

Write-Host ""
Write-Host "Done. Installer: dist\installer\IshaSetup-$version.exe" -ForegroundColor Green
if (-not $SignThumbprint) {
    Write-Host "NOTE: unsigned build — SmartScreen will warn on first run until you code-sign (Track D3)." -ForegroundColor Yellow
}
