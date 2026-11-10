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
where ffmpeg >nul 2>&1 || (echo [ERROR] FFmpeg must be in PATH. & exit /b 1)
where ffprobe >nul 2>&1 || (echo [ERROR] FFprobe must be in PATH. & exit /b 1)

rem Prefer the Windows Python launcher to avoid the broken WindowsApps "python" alias.
set "PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3"
)
if not defined PYTHON (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
    echo [ERROR] A working Python 3.11+ interpreter is required.
    echo [FIX] Install Python 3.11+ and run: py -3 --version
    echo [FIX] Disable the WindowsApps python.exe alias if it only prints "Python".
    exit /b 1
)
echo [OK] Using %PYTHON%

echo [CHECK] Checking editor ports (3000 web / 8100 Python)...
%PYTHON% scripts\check_local_ports.py
if errorlevel 1 (
    echo [STOP] Port check failed, or port 3000/8100 is busy.
    echo [FIX] Close old dev servers on these ports, then retry run.bat.
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating Python virtual environment...
    %PYTHON% -m venv .venv || exit /b 1
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
%PYTHON% scripts\verify_running_editor.py
if errorlevel 1 (
    echo [ERROR] The local editor is not healthy. Inspect the two server windows.
    exit /b 1
)
start "" "http://localhost:3000/"
echo.
echo When finished, run stop.bat to close and erase temporary work files.
echo.
