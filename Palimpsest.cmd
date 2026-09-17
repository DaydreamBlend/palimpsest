@echo off
setlocal
set "PALIMPSEST_WORKSPACE=%~dp0"
set "PALIMPSEST_UI_TEST="
set "PALIMPSEST_DESKTOP_CONFIG="
set "PALIMPSEST_DESKTOP_STORES=%~dp0.local\electron-ui\stores.json"
set "PALIMPSEST_DESKTOP_REALM_CONFIG=%~dp0.local\electron-ui\realm.json"
if not exist "%~dp0desktop\node_modules\electron\dist\electron.exe" (
  echo Palimpsest Electron runtime is missing. See docs\interfaces\UNIFIED_DESKTOP.md.
  pause
  exit /b 1
)
if not exist "%~dp0output\t24-wisdom-realm\release-final\app.asar" (
  echo Palimpsest desktop package is missing. See docs\interfaces\DESKTOP_UI.md.
  pause
  exit /b 1
)
start "" "%~dp0desktop\node_modules\electron\dist\electron.exe" "%~dp0output\t24-wisdom-realm\release-final\app.asar"
