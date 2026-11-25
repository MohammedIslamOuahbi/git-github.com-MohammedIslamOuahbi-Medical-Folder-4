@echo off
setlocal

set "FRONTEND_DIR=%~dp0.."
for %%I in ("%FRONTEND_DIR%") do set "FRONTEND_DIR=%%~fI"
for %%I in ("%FRONTEND_DIR%\..") do set "ROOT_DIR=%%~fI"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe"
set "SIDE_CAR_NAME=medical-backend-sidecar"
set "TARGET_TRIPLE=x86_64-pc-windows-msvc"
set "OUTPUT_DIR=%FRONTEND_DIR%\src-tauri\bin"
set "OUTPUT_EXE=%OUTPUT_DIR%\%SIDE_CAR_NAME%-%TARGET_TRIPLE%.exe"

if not exist "%PYTHON_EXE%" (
  echo Backend virtualenv Python not found at "%PYTHON_EXE%".
  exit /b 1
)

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

pushd "%BACKEND_DIR%"
"%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --name "%SIDE_CAR_NAME%" ^
  --paths "%BACKEND_DIR%" ^
  --add-data "%BACKEND_DIR%\app;app" ^
  --add-data "%BACKEND_DIR%\alembic;alembic" ^
  --add-data "%BACKEND_DIR%\alembic.ini;." ^
  --add-data "%BACKEND_DIR%\.env.example;." ^
  --collect-all fastapi ^
  --collect-all uvicorn ^
  --collect-all sqlalchemy ^
  --collect-all alembic ^
  run_tauri_sidecar.py
if errorlevel 1 (
  popd
  exit /b 1
)

copy /Y "%BACKEND_DIR%\dist\%SIDE_CAR_NAME%.exe" "%OUTPUT_EXE%" >nul
popd

if not exist "%OUTPUT_EXE%" (
  echo Failed to create backend sidecar executable.
  exit /b 1
)

echo Built backend sidecar: "%OUTPUT_EXE%"
exit /b 0

