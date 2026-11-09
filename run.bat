@echo off
setlocal
cd /d "%~dp0"
echo.
echo  =========================================
echo    One-Shot AI Video Editor - Local PC
echo  =========================================
echo.
where node >nul 2>&1 || (echo [ERROR] Node.js 22+ is required. & exit /b 1)
where npm >nul 2>&1 || (echo [ERROR] npm is required. & exit /b 1)
where python >nul 2>&1 || (echo [ERROR] Python 3.11+ is required. & exit /b 1)
where ffmpeg >nul 2>&1 || (echo [ERROR] FFmpeg must be in PATH. & exit /b 1)
where ffprobe >nul 2>&1 || (echo [ERROR] FFprobe must be in PATH. & exit /b 1)
echo [CHECK] Verifying that older editors have stopped...
python scripts\check_local_ports.py
if errorlevel 1 (
    echo [STOP] An old server may still be running. Close its terminal and retry run.bat.
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment...
    python -m venv .venv || exit /b 1
)
if not exist ".venv\.installed" (
    echo [SETUP] Installing Python dependencies and local speech recognition...
    ".venv\Scripts\python.exe" -m pip install -r backend\requirements-whisper.txt || exit /b 1
    echo ok> ".venv\.installed"
)
if not exist "node_modules" (
    echo [SETUP] Installing Next.js dependencies...
    call npm install --no-audit --no-fund || exit /b 1
)
echo [START] Launching local Python and Next.js servers...
start "OneShot-Backend" "%ComSpec%" /k "call scripts\start-backend.bat"
start "OneShot-Frontend" "%ComSpec%" /k "call scripts\start-frontend.bat"
timeout /t 6 /nobreak >nul
start "" "http://127.0.0.1:3000"
echo.
echo When finished, run stop.bat to close and erase temporary work files.
echo.
