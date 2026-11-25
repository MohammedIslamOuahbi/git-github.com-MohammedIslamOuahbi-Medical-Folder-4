@echo off
setlocal

set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo Backend virtualenv Python not found at "%PYTHON_EXE%".
  echo Create or repair the backend virtualenv first.
  exit /b 1
)

pushd "%~dp0"
"%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
set "EXIT_CODE=%ERRORLEVEL%"
popd

exit /b %EXIT_CODE%
