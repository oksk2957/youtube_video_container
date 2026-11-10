@echo off
cd /d "%~dp0\.."
title OneShot-Backend
echo Python FastAPI: http://127.0.0.1:8100/api/health
if /I "%ALLOW_LOCAL_AI_HTTP%"=="0" (
    echo [AI] Local HTTP AI is disabled by ALLOW_LOCAL_AI_HTTP=0.
    echo [FIX] Remove this environment variable or set it to 1, then restart.
) else (
    echo [AI] Localhost HTTP AI is allowed. External AI must use HTTPS.
)
".venv\Scripts\python.exe" -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8100 --no-access-log
