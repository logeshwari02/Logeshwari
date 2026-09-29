@echo off
cd /d "%~dp0"
echo Starting PocketSmart AI frontend at http://127.0.0.1:5173/
python -m http.server 5173
