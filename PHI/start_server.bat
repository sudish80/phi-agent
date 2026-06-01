@echo off
cd /d "%~dp0"
echo Starting PHI Agent Server...
python -m uvicorn minimal_server:app --host 0.0.0.0 --port 8000
pause
