@echo off
cd /d "%~dp0\.."
title OneShot-Frontend
echo Web editor: http://localhost:3000
set "NEXT_PUBLIC_API_URL="
call npm run dev -- -H 127.0.0.1 -p 3000
