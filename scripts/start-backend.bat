@echo off
cd /d "%~dp0\.."
title OneShot-Backend
echo Python FastAPI: http://127.0.0.1:8000/api/health
".venv\Scripts\python.exe" -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
