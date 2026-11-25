@echo off
setlocal

pushd "%~dp0.."
node .\scripts\ensure-tauri-updater-key.mjs
if errorlevel 1 (
  popd
  exit /b 1
)
popd

call "%~dp0build-backend-sidecar.cmd"
if errorlevel 1 exit /b 1

set "FRONTEND_DIR=%~dp0.."
for %%I in ("%FRONTEND_DIR%") do set "FRONTEND_DIR=%%~fI"
set "TAURI_SIGNING_PRIVATE_KEY_PATH=%FRONTEND_DIR%\.tauri\updater.key"
if not defined TAURI_SIGNING_PRIVATE_KEY_PASSWORD set "TAURI_SIGNING_PRIVATE_KEY_PASSWORD=codextauri"
for /f "usebackq delims=" %%K in (`powershell -NoProfile -Command "Get-Content -Raw '%TAURI_SIGNING_PRIVATE_KEY_PATH%'"`) do set "TAURI_SIGNING_PRIVATE_KEY=%%K"

pushd "%FRONTEND_DIR%"
call .\node_modules\.bin\tauri.cmd build --config src-tauri\tauri.conf.json -- --offline
if errorlevel 1 (
  set "EXIT_CODE=%ERRORLEVEL%"
  popd
  exit /b %EXIT_CODE%
)

node .\scripts\create-tauri-release-manifest.mjs
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
