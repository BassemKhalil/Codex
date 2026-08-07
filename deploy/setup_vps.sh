#!/usr/bin/env bash
#
# One-shot VPS setup for the Polymarket Weather Bot.
# Tested on Ubuntu/Debian. Run as root (or with sudo) from the repo root:
#
#   sudo bash deploy/setup_vps.sh
#
set -euo pipefail

APP_DIR=/opt/polymarket-bot
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y -qq python3 python3-venv

echo "==> Creating service user"
id -u polymarket &>/dev/null || useradd --system --create-home polymarket

echo "==> Copying app to ${APP_DIR}"
mkdir -p "${APP_DIR}"
cp -r "${REPO_DIR}/polymarket_bot" "${REPO_DIR}/run_bot.py" \
      "${REPO_DIR}/requirements-bot.txt" "${APP_DIR}/"

echo "==> Creating virtualenv"
python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install -q -r "${APP_DIR}/requirements-bot.txt"

if [ ! -f "${APP_DIR}/.env" ]; then
  TOKEN=$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)
  cat > "${APP_DIR}/.env" <<EOF
DASHBOARD_TOKEN=${TOKEN}
DASHBOARD_PORT=5000
EOF
  echo "==> Generated dashboard token: ${TOKEN}"
  echo "    (saved in ${APP_DIR}/.env)"
fi

chown -R polymarket:polymarket "${APP_DIR}"

echo "==> Installing systemd services"
cp "${REPO_DIR}/deploy/polymarket-dashboard.service" /etc/systemd/system/
cp "${REPO_DIR}/deploy/polymarket-bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polymarket-dashboard polymarket-bot

echo "==> Opening firewall port 5000 (if ufw is active)"
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 5000/tcp
fi

TOKEN=$(grep DASHBOARD_TOKEN "${APP_DIR}/.env" | cut -d= -f2)
IP=$(hostname -I | awk '{print $1}')
echo
echo "=========================================================="
echo "  Done. Dashboard:  http://${IP}:5000/?token=${TOKEN}"
echo "  (bookmark that URL on your phone - the token is"
echo "   remembered in a cookie after the first visit)"
echo
echo "  Bot status:   systemctl status polymarket-bot"
echo "  Bot logs:     journalctl -u polymarket-bot -f"
echo "  Dashboard:    journalctl -u polymarket-dashboard -f"
echo "=========================================================="
