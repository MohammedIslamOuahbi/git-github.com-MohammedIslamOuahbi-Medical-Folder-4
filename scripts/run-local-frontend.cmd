@echo off
setlocal
where npm.cmd >nul 2>nul || (echo ERROR: npm was not found on PATH.& exit /b 2)
cd /d "%~dp0..\frontend"
if not exist node_modules (echo ERROR: Run npm.cmd install in frontend first.& exit /b 2)
echo Starting local preview UI at http://127.0.0.1:5173
npm.cmd run dev -- --host 127.0.0.1
