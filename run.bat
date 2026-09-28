@echo off
:: Inventory Management Agent — Startup Script (Windows)
echo Starting Inventory Management Agent - I1 Stock Monitor...
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Install dependencies if needed
if not exist ".deps_installed" (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo. > .deps_installed
)

echo.
echo Server starting at: http://localhost:8000
echo API Docs:           http://localhost:8000/docs
echo Dashboard:          http://localhost:8000/dashboard
echo Alerts:             http://localhost:8000/alerts
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
