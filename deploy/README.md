# Deploying to a VPS

Everything you need to run the bot + dashboard 24/7 on any Ubuntu/Debian VPS
and check it from your phone.

## Quick start

```bash
# on the VPS
git clone <your-repo-url> polymarket-bot-src
cd polymarket-bot-src
sudo bash deploy/setup_vps.sh
```

The script:

1. Installs Python + venv, creates a `polymarket` service user
2. Copies the app to `/opt/polymarket-bot` and installs dependencies
3. Generates a random `DASHBOARD_TOKEN` in `/opt/polymarket-bot/.env`
4. Installs and starts two systemd services:
   - **polymarket-bot** — the trading loop (`run --interval 360`, i.e. every 6 h)
   - **polymarket-dashboard** — gunicorn serving the dashboard on port 5000
5. Opens port 5000 in ufw (if active) and prints your personal dashboard URL

## Phone access

Open the URL the script prints — `http://YOUR_VPS_IP:5000/?token=XXXX` — and
bookmark it / add to home screen. The token is stored in a cookie, so
subsequent visits need no token. The page auto-refreshes every 5 minutes.

## Day-2 operations

```bash
journalctl -u polymarket-bot -f          # live bot logs
journalctl -u polymarket-dashboard -f    # dashboard logs
systemctl restart polymarket-bot         # apply config changes
sudo nano /opt/polymarket-bot/polymarket_bot/config.py   # edit contracts
```

After editing contracts/config on the VPS, restart both services.

To redeploy after a git pull:

```bash
sudo cp -r polymarket_bot run_bot.py /opt/polymarket-bot/
sudo chown -R polymarket:polymarket /opt/polymarket-bot
sudo systemctl restart polymarket-bot polymarket-dashboard
```

## Optional hardening

- Put nginx + HTTPS in front (certbot), proxying to 127.0.0.1:5000,
  and close port 5000 externally.
- Rotate the token any time by editing `/opt/polymarket-bot/.env` and
  restarting the dashboard service.
