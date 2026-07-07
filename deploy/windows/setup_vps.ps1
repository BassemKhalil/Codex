# Polymarket Weather Bot - Windows VPS setup
#
# Designed for the MyForexVPS box that also runs Aureum. Fully isolated:
# own folder (C:\polymarket-bot), own venv, own scheduled tasks. Never
# touches C:\aureum-v1.
#
# Run as Administrator from the repo root:
#   powershell -ExecutionPolicy Bypass -File deploy\windows\setup_vps.ps1

$ErrorActionPreference = "Stop"

$AppDir   = "C:\polymarket-bot"
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

Write-Host "==> Checking Python"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "Python not found on PATH. Install Python 3.11-3.13 (3.13 is already on this VPS for Aureum)." }
python --version

Write-Host "==> Copying app to $AppDir"
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
Copy-Item -Recurse -Force "$RepoRoot\polymarket_bot" $AppDir
Copy-Item -Force "$RepoRoot\run_bot.py" $AppDir
Copy-Item -Force "$RepoRoot\requirements-bot.txt" $AppDir

Write-Host "==> Creating virtualenv"
if (-not (Test-Path "$AppDir\.venv")) {
    python -m venv "$AppDir\.venv"
}
& "$AppDir\.venv\Scripts\pip.exe" install -q -r "$AppDir\requirements-bot.txt" waitress

if (-not (Test-Path "$AppDir\.env")) {
    $token = [guid]::NewGuid().ToString("N")
    @"
DASHBOARD_TOKEN=$token
DASHBOARD_PORT=5000
BOT_DB_PATH=C:\polymarket-bot\polymarket_bot.db
PYTHONUTF8=1
PYTHONIOENCODING=utf-8
"@ | Set-Content -Encoding ascii "$AppDir\.env"
    Write-Host "==> Generated dashboard token: $token"
}

Write-Host "==> Writing bat wrappers"
@"
@echo off
cd /d C:\polymarket-bot
:loop
for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
.venv\Scripts\waitress-serve.exe --listen=127.0.0.1:5000 polymarket_bot.dashboard:app
echo Dashboard exited (%ERRORLEVEL%). Restarting in 15s...
timeout /t 15 /nobreak >nul
goto loop
"@ | Set-Content -Encoding ascii "$AppDir\run_dashboard.bat"

@"
@echo off
cd /d C:\polymarket-bot
:loop
for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
.venv\Scripts\python.exe -u run_bot.py run --interval 360 >> bot.log 2>&1
echo Bot exited (%ERRORLEVEL%). Restarting in 60s...
timeout /t 60 /nobreak >nul
goto loop
"@ | Set-Content -Encoding ascii "$AppDir\run_trader.bat"

Write-Host "==> Registering scheduled tasks (SYSTEM, at startup - no desktop session needed)"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

foreach ($t in @(
    @{ Name = "Polymarket Dashboard"; Bat = "run_dashboard.bat" },
    @{ Name = "Polymarket Bot";       Bat = "run_trader.bat" }
)) {
    $action  = New-ScheduledTaskAction -Execute "$AppDir\$($t.Bat)" -WorkingDirectory $AppDir
    $trigger = New-ScheduledTaskTrigger -AtStartup
    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger `
        -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
    Start-ScheduledTask -TaskName $t.Name
    Write-Host "    started task: $($t.Name)"
}

Start-Sleep -Seconds 5
try {
    $health = Invoke-RestMethod "http://127.0.0.1:5000/health" -TimeoutSec 10
    Write-Host "==> Dashboard health check: $($health.status)"
} catch {
    Write-Warning "Dashboard not responding yet - check: schtasks /query /tn `"Polymarket Dashboard`""
}

Write-Host "==> Publishing over Tailscale (HTTPS port 8443; Aureum keeps 443)"
$ts = Get-Command tailscale -ErrorAction SilentlyContinue
if ($ts) {
    tailscale serve --bg --https=8443 5000
    tailscale serve status
} else {
    Write-Warning "tailscale CLI not on PATH. Run manually:  tailscale serve --bg --https=8443 5000"
}

$envToken = (Get-Content "$AppDir\.env" | Where-Object { $_ -match "^DASHBOARD_TOKEN=" }) -replace "DASHBOARD_TOKEN=", ""
Write-Host ""
Write-Host "=========================================================="
Write-Host "  Done. On your phone (Tailscale on), open:"
Write-Host "  https://<machine>.<tailnet>.ts.net:8443/?token=$envToken"
Write-Host "  (exact hostname shown by 'tailscale serve status' above)"
Write-Host ""
Write-Host "  Bookmark it - the token sticks in a cookie for 90 days."
Write-Host "=========================================================="
