@echo off
setlocal

call "%~dp0build-backend-sidecar.cmd"
if errorlevel 1 exit /b 1

pushd "%~dp0.."
cargo check --offline --manifest-path src-tauri\Cargo.toml
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
