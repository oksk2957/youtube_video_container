@echo off
setlocal
cd /d "%~dp0"
echo [STOP] Stopping editing services...
taskkill /FI "WINDOWTITLE eq OneShot-Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq OneShot-Frontend*" /T /F >nul 2>&1
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" backend\cleanup.py
) else (
    python backend\cleanup.py
)
echo [DONE] Stopped services and requested temporary work cleanup.
pause
