# Windows VPS deployment (shared with Aureum)

Deploys the Polymarket weather bot alongside the Aureum gold bot on the
MyForexVPS Windows Server box. Fully isolated from Aureum: own folder
(`C:\polymarket-bot`), own venv, own scheduled tasks, dashboard on port
5000 (loopback) published via Tailscale Serve on HTTPS **8443** — Aureum's
UI keeps the default 443.

Unlike Aureum, this bot needs no desktop session (no MT5 GUI), so its
tasks run as SYSTEM at boot — it survives reboots with no Autologon
dependency and never conflicts with the "one console only" rule.

## Install

In an RDP session (or over SSH), as Administrator:

```powershell
cd C:\
git clone <repo-url> polymarket-src        # or copy the repo any other way
cd polymarket-src
powershell -ExecutionPolicy Bypass -File deploy\windows\setup_vps.ps1
```

The script:

1. Copies the app to `C:\polymarket-bot`, creates a venv, installs deps
   (+ `waitress`, the Windows WSGI server — gunicorn is Unix-only)
2. Generates a random `DASHBOARD_TOKEN` in `C:\polymarket-bot\.env`
3. Writes crash-loop bat wrappers (same pattern as Aureum's `run_bot.bat`)
4. Registers + starts two Task Scheduler tasks (SYSTEM, at startup,
   no time limit): **Polymarket Dashboard** and **Polymarket Bot**
5. Runs `tailscale serve --bg --https=8443 5000` and prints your phone URL

## Phone access

With Tailscale active on your phone, open the printed URL:

```
https://<machine>.<tailnet>.ts.net:8443/?token=XXXX
```

Add to home screen. Token persists in a cookie; page auto-refreshes.

## Day-2 operations

```powershell
Get-Content C:\polymarket-bot\bot.log -Tail 50 -Wait     # live bot logs
Get-ScheduledTask "Polymarket*" | Get-ScheduledTaskInfo   # task status
Restart:  Stop-ScheduledTask "Polymarket Bot"; Start-ScheduledTask "Polymarket Bot"
Config:   notepad C:\polymarket-bot\polymarket_bot\config.py   # then restart both tasks
```

Redeploy after a `git pull` in `C:\polymarket-src`:

```powershell
Stop-ScheduledTask "Polymarket Bot"; Stop-ScheduledTask "Polymarket Dashboard"
Copy-Item -Recurse -Force C:\polymarket-src\polymarket_bot, C:\polymarket-src\run_bot.py C:\polymarket-bot
Start-ScheduledTask "Polymarket Bot"; Start-ScheduledTask "Polymarket Dashboard"
```

## Notes

- No new inbound firewall rules are needed or created: the dashboard
  listens on loopback only and is reached exclusively through Tailscale.
- The SQLite DB lives at `C:\polymarket-bot\polymarket_bot.db` (paper
  trades, balance history, analysis log). Back it up if you care about
  the paper-trading track record.
- Saturday-update habit from the Aureum runbook applies here too; this
  bot tolerates reboots (tasks are at-startup), so no special care needed.
