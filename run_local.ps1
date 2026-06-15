# Локальный запуск dev-бота. Требует DEV=1 и BOT_TOKEN_DEV в .env
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = "C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "=== Unit-тесты ===" -ForegroundColor Cyan
& $python test_validation.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python test_reminder_flow.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Связь с Telegram ===" -ForegroundColor Cyan
& $python test_connection.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Dev-бот (Ctrl+C для остановки) ===" -ForegroundColor Cyan
& $python main.py
