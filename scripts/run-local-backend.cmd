@echo off
setlocal
if "%DATABASE_URL%"=="" (
  echo ERROR: Set DATABASE_URL to a local PostgreSQL URL before starting the server.
  exit /b 2
)
if "%PREVIEW_PASSWORD%"=="" (
  echo ERROR: Set PREVIEW_PASSWORD before preparing the preview account.
  exit /b 2
)
where python >nul 2>nul || (echo ERROR: Python was not found on PATH.& exit /b 2)
cd /d "%~dp0..\backend"
python recovery_tests\prepare_local_preview_account.py || exit /b 1
echo Starting local preview API at http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
