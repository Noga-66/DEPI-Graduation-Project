@echo off
setlocal

cd /d "%~dp0"
set "PYTHON=C:\Anaconda\envs\venv_xai\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: Python environment not found: %PYTHON%
    pause
    exit /b 1
)

echo ==========================================
echo         DEPI Grid Microservices 
echo ==========================================
echo.

echo [1/5] Waking up TimescaleDB
docker start depi_timescale
timeout /t 5 >nul

echo [2/5] Starting API Orchestrator
start "DEPI API" cmd /k ""%PYTHON%" "%CD%\src\api\main.py""
timeout /t 8 >nul

echo [3/5] Starting Smart Receiver
start "DEPI Receiver" cmd /k ""%PYTHON%" "%CD%\src\simulation\receiver.py""
timeout /t 3 >nul

echo [4/5] Starting Multi-Modal Sender
start "DEPI Sender" cmd /k ""%PYTHON%" "%CD%\src\simulation\sender.py""
timeout /t 2 >nul

echo [5/5] Starting Streamlit Control Center
start "DEPI Dashboard" cmd /k ""%PYTHON%" -m streamlit run "%CD%\src\ui\dashboard.py""

echo.
echo ==========================================
echo                SYSTEM ONLINE
echo ==========================================
pause