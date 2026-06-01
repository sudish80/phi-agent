@echo off
TITLE PHI Agent Desktop
cd /d "%~dp0"

:: Ensure Python server is running
echo Checking if orchestrator is running...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo Orchestrator not running. Starting it first...
    start "Orchestrator" /MIN cmd /c "uvicorn backend.orchestrator.main:app --host 0.0.0.0 --port 8000 --log-level info"
    timeout /t 8 /nobreak >nul
)

echo Starting Electron app...
npx electron .
