# start_all_background.ps1
# ---------------------------
# Runs all 3 live trading scripts as BACKGROUND JOBS inside this ONE
# terminal - no extra windows popping up. You watch progress through the
# dashboard (visual) instead of reading 3 separate terminal logs.
#
# Usage:
#   .\start_all_background.ps1        (starts everything, opens dashboard)
#   .\start_all_background.ps1 -Stop  (stops all 3 background jobs)
#   .\start_all_background.ps1 -Status (shows whether jobs are running + recent output)

param(
    [switch]$Stop,
    [switch]$Status
)

$projectDir = $PSScriptRoot
$jobNames = @("LiquiditySweep_AAPL", "LiquiditySweep_BTC", "LiquiditySweep_ETH")

if ($Stop) {
    Write-Host "Stopping all background jobs..."
    foreach ($name in $jobNames) {
        $job = Get-Job -Name $name -ErrorAction SilentlyContinue
        if ($job) {
            Stop-Job -Name $name
            Remove-Job -Name $name -Force
            Write-Host "  Stopped: $name"
        }
    }
    Write-Host "Done. All jobs stopped."
    exit 0
}

if ($Status) {
    Write-Host "Job status:"
    Get-Job | Where-Object { $jobNames -contains $_.Name } | Format-Table Name, State, HasMoreData
    Write-Host ""
    Write-Host "Recent output from each job (last 5 lines):"
    foreach ($name in $jobNames) {
        $job = Get-Job -Name $name -ErrorAction SilentlyContinue
        if ($job) {
            Write-Host "--- $name ---"
            Receive-Job -Name $name -Keep | Select-Object -Last 5
        }
    }
    exit 0
}

# ---- default: start everything ----

# clean up any stale jobs from a previous run first
foreach ($name in $jobNames) {
    Get-Job -Name $name -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
}

Write-Host "Starting AAPL (stocks) as background job..."
Start-Job -Name "LiquiditySweep_AAPL" -ScriptBlock {
    param($dir)
    Set-Location $dir
    python live_trading.py --ticker AAPL
} -ArgumentList $projectDir | Out-Null

Write-Host "Starting BTC/USD (crypto) as background job..."
Start-Job -Name "LiquiditySweep_BTC" -ScriptBlock {
    param($dir)
    Set-Location $dir
    python live_trading_crypto.py --symbol BTC/USD
} -ArgumentList $projectDir | Out-Null

Write-Host "Starting ETH/USD (crypto) as background job..."
Start-Job -Name "LiquiditySweep_ETH" -ScriptBlock {
    param($dir)
    Set-Location $dir
    python live_trading_crypto.py --symbol ETH/USD
} -ArgumentList $projectDir | Out-Null

Write-Host "Waiting for first charts to generate..."
Start-Sleep -Seconds 10

Write-Host "Opening dashboard..."
$dashboardPath = "$projectDir\output\dashboard.html"
Start-Process "cmd.exe" "/c start `"`" `"$dashboardPath`""

Write-Host ""
Write-Host "All 3 jobs running in the background of THIS terminal." -ForegroundColor Green
Write-Host "You can keep using this terminal for other commands - the jobs keep running."
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  .\start_all_background.ps1 -Status   -> check if jobs are alive plus see recent output"
Write-Host "  .\start_all_background.ps1 -Stop     -> stop everything"
Write-Host "  Get-Job                              -> quick built-in job list"
Write-Host ""
Write-Host "NOTE: closing this terminal window entirely WILL stop the background jobs too" -ForegroundColor Yellow
Write-Host "(they belong to this PowerShell session) - minimize it instead of closing it."
