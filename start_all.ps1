# start_all.ps1
# ---------------
# Launches all 3 live trading loops in their own separate windows,
# plus opens the unified dashboard - one command instead of manually
# opening and setting up 3 terminals every time.
#
# IMPORTANT: run the setx commands (see setup_keys_permanent.ps1) ONCE first
# so ALPACA_API_KEY / ALPACA_SECRET_KEY are permanently available to every
# new window this script opens. Without that, each new window this launches
# will fail with the "environment variables not set" error.
#
# Usage:
#   Right-click this file > Run with PowerShell
#   OR from an existing terminal already in this folder: .\start_all.ps1

$projectDir = $PSScriptRoot

Write-Host "Launching AAPL (stocks)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; python live_trading.py --ticker AAPL"

Start-Sleep -Seconds 2

Write-Host "Launching BTC/USD (crypto)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; python live_trading_crypto.py --symbol BTC/USD"

Start-Sleep -Seconds 2

Write-Host "Launching ETH/USD (crypto)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; python live_trading_crypto.py --symbol ETH/USD"

Write-Host "Waiting a moment for the first charts to generate before opening the dashboard..."
Start-Sleep -Seconds 8

Write-Host "Opening dashboard..."
$dashboardPath = "$projectDir\output\dashboard.html"
Start-Process "cmd.exe" "/c start `"`" `"$dashboardPath`""

Write-Host ""
Write-Host "All 3 windows launched. Close this window if you like - it's not needed anymore."
Write-Host "To stop everything, close the 3 new PowerShell windows individually (Ctrl+C in each, or just close them)."
