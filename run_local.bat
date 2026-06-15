@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

echo === Unit-tests ===
"%PY%" test_validation.py
if errorlevel 1 exit /b 1
"%PY%" test_reminder_flow.py
if errorlevel 1 exit /b 1

echo.
echo === Telegram connection ===
"%PY%" test_connection.py
if errorlevel 1 (
    echo.
    echo Unit-tests passed. Telegram blocked on this PC — use Railway for UI test.
    echo To skip this step: set SKIP_CONNECTION=1
    if not "%SKIP_CONNECTION%"=="1" exit /b 1
)

echo.
echo === Dev bot (Ctrl+C to stop) ===
"%PY%" main.py
