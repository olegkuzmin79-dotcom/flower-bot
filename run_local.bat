@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"

echo === Локальные тесты (без Telegram) ===
"%PY%" test_validation.py
if errorlevel 1 exit /b 1
"%PY%" test_reminder_flow.py
if errorlevel 1 exit /b 1

echo.
echo OK. Логика бота проверена.
echo.
echo Telegram с этого ПК не тестируем (РФ + Happ не помогли).
echo Полный бот: git push -^> Railway -^> тест в Telegram у прод-бота.
echo Dev-бот @flower_dev_bot на Railway можно подключить позже, если понадобится.
