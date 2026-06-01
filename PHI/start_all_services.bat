@echo off
TITLE PHI Agent - All Services
cd /d "%~dp0"

echo ============================================
echo  PHI Agent - Starting All Microservices
echo ============================================
echo.

:: Kill any existing Python on our ports
for %%p in (8000 8001 8002 8003 8004) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
)
timeout /t 2 /nobreak >nul

echo [1/5] Starting Orchestrator (port 8000)...
start "Orchestrator" /MIN cmd /c "uvicorn backend.orchestrator.main:app --host 0.0.0.0 --port 8000 --log-level info 2>&1"

echo [2/5] Starting Vision Service (port 8001)...
start "Vision" /MIN cmd /c "uvicorn backend.vision.service:app --host 0.0.0.0 --port 8001 --log-level info 2>&1"

echo [3/5] Starting Hearing Service (port 8002)...
start "Hearing" /MIN cmd /c "uvicorn backend.hearing.service:app --host 0.0.0.0 --port 8002 --log-level info 2>&1"

echo [4/5] Starting Speech Service (port 8003)...
start "Speech" /MIN cmd /c "uvicorn backend.speech.service:app --host 0.0.0.0 --port 8003 --log-level info 2>&1"

echo [5/5] Starting Action Service (port 8004)...
start "Action" /MIN cmd /c "uvicorn backend.actions.service:app --host 0.0.0.0 --port 8004 --log-level info 2>&1"

echo.
echo All services started! Waiting for orchestrator...
timeout /t 5 /nobreak >nul

:check
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto check
)

echo.
echo ============================================
echo  ALL SERVICES RUNNING
echo ============================================
echo.
echo  Orchestrator : http://127.0.0.1:8000
echo  Vision       : http://127.0.0.1:8001
echo  Hearing      : http://127.0.0.1:8002
echo  Speech       : http://127.0.0.1:8003
echo  Action       : http://127.0.0.1:8004
echo.
echo  Web UI       : http://127.0.0.1:8000/app/
echo  Chat UI      : http://127.0.0.1:8000/app/chat.html
echo  API Docs     : http://127.0.0.1:8000/docs
echo.
echo  Tools        : http://127.0.0.1:8000/tools
echo  Status       : http://127.0.0.1:8000/status
echo.
echo Press any key to stop all services...
pause >nul

echo Stopping all services...
taskkill /F /FI "WINDOWTITLE eq Orchestrator" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Vision" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Hearing" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Speech" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Action" >nul 2>&1

for %%p in (8000 8001 8002 8003 8004) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo All services stopped.
pause
