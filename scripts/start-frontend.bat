@echo off
cd /d "%~dp0\.."
title OneShot-Frontend
echo Web editor: http://127.0.0.1:3100
set "NEXT_PUBLIC_API_URL=http://127.0.0.1:8100"
call npm run dev -- -H 127.0.0.1 -p 3100
