@echo off
cd /d "%~dp0\.."
title OneShot-Frontend
echo Web editor: http://127.0.0.1:3000
call npm run dev -- -H 127.0.0.1
