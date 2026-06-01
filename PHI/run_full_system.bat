@echo off
title PHI Agent - Full System
cd /d "%~dp0"

echo ========================================
echo   PHI AGENT - Full System Launch
echo ========================================
echo.
echo Loading all 650 tools + TTS + WebSocket...
echo.

python -m uvicorn backend.orchestrator.main:app --host 0.0.0.0 --port 8000 --log-level info

echo.
echo Server stopped.
pause
