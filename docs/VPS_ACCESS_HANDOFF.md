# VPS Access Handoff — for a new Claude Code session

Paste this file (plus a fresh ephemeral Tailscale auth key and the
Administrator password) into any session that needs to work on the VPS.

## The box

- MyForexVPS GOLD, **Windows Server 2022**, ~4 GB RAM, Amsterdam.
- Tailscale node **vps49745378**, tailnet IP **100.111.12.20**.
- Public IP 45.67.222.167, custom RDP port 42020 (not useful to an agent — use SSH).
- **SSH (OpenSSH for Windows) on port 22, restricted to the tailnet** — this is
  the agent path in. Login: `Administrator` (plain local account — never
  `MicrosoftAccount\Administrator`).
- Break-glass if connectivity is ever lost: MyForexVPS client-area Console/VNC.

## Connecting from a Claude Code cloud sandbox

Sandboxes have no TUN device and route through an HTTPS proxy; Tailscale works
in userspace mode via DERP relays:

```bash
curl -sSL https://pkgs.tailscale.com/stable/tailscale_1.86.2_amd64.tgz | tar xz
./tailscale*/tailscaled --tun=userspace-networking \
    --socks5-server=localhost:1055 --statedir=/var/lib/tailscale &
./tailscale*/tailscale up --authkey=<EPHEMERAL_KEY> \
    --hostname=claude-session --accept-dns=false
apt-get install -y sshpass
export SSHPASS='<ADMIN_PASSWORD>'
sshpass -e ssh -o "ProxyCommand=nc -X 5 -x localhost:1055 %h %p" \
    -o StrictHostKeyChecking=accept-new Administrator@100.111.12.20 "whoami"
```

Windows-side gotchas learned the hard way:
- Default SSH shell is **cmd.exe**. Wrap anything nontrivial in
  `powershell -Command "..."` — but multi-line quoting over SSH is fragile;
  prefer building files locally and `scp`-ing them over.
- cmd parses `echo X=1>> file` as a file-descriptor redirect — the `1` vanishes.
- `.bat` files MUST have CRLF line endings (a LF-only bat silently no-ops).
- Console codepage is cp1252: set `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`
  for any Python that prints Unicode, and `python -u` for live log files.
- gunicorn doesn't run on Windows — use `waitress`.
- `tailscale logout` from your sandbox when done (ephemeral node evaporates).

## ⚠️ What already runs here — do not disturb

**1. Aureum (gold copy-trading bot, C:\aureum-v1)** — REAL trading system
(demo account today, live eventually):
- Scheduled task **"Aureum Bot"** (at-logon, needs the interactive desktop
  session because of the MT5 GUI). Never run `main.py` by hand while the task
  is alive — two instances place duplicate orders.
- FastAPI UI on **port 8000** (loopback), MT5 terminal64.exe must stay up.
- Only ever touch MT5 orders tagged magic `20260601` — but preferably don't
  touch MT5 at all.
- Leaving RDP: **Disconnect**, never Sign Out (kills the desktop session and
  the bot).

**2. Polymarket weather bot (C:\polymarket-bot)** — paper trading:
- Scheduled tasks **"Polymarket Bot"** + **"Polymarket Dashboard"**
  (SYSTEM, at-startup). Flask/waitress on **port 5000** (loopback).
- SQLite DB at C:\polymarket-bot\polymarket_bot.db holds the trading track
  record — don't delete.
- Source staging copy in C:\polymarket-src.

**3. Tailscale Serve mappings (don't clobber):**
- `443  → 127.0.0.1:8000` (Aureum UI)
- `8443 → 127.0.0.1:5000` (Polymarket dashboard)
- A new web service should bind loopback on a free port and claim a NEW
  HTTPS port, e.g. `tailscale serve --bg --https=9443 <port>`.

**4. Housekeeping conventions:**
- Windows updates only on Saturdays (gold market closed).
- Tailscale runs in unattended mode + a SYSTEM watchdog task; don't "fix" it.
- Python 3.13 is on PATH; per-project venvs, never pip-install globally.
- Timezone: Beirut (UTC+3 summer). Server clock ≈ broker clock.

## After the session

Revoke the auth key at login.tailscale.com/admin/settings/keys and rotate the
Administrator password if it transited chat.
