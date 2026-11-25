@echo off
setlocal

call "%~dp0build-backend-sidecar.cmd"
if errorlevel 1 exit /b 1

pushd "%~dp0.."
call .\node_modules\.bin\tauri.cmd dev --config src-tauri\tauri.conf.json -- --offline
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
