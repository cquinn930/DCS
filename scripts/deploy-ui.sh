#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/sites/DCS"
UI_DIR="$APP_ROOT/services/ui"
SERVICE_USER="www-data"
SERVICE_GROUP="dcs"

NODE_DIR=$(dirname "$(command -v node)")
echo "=== DCS UI Deploy — $(date) ==="

sudo systemctl stop dcs-ui

echo "[1/3] Fixing ownership..."
sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$UI_DIR"
sudo find "$UI_DIR" -type d -exec chmod 2775 {} \;
sudo find "$UI_DIR" -type f -exec chmod 664 {} \;

echo "[2/3] Rebuilding frontend..."
sudo -u "$SERVICE_USER" bash -c "
    export PATH='$NODE_DIR:/usr/local/bin:/usr/bin:/bin'
    cd '$UI_DIR'
    npm ci
    npm run build
"
sudo find "$UI_DIR/node_modules/.bin" -type f -exec chmod 775 {} \;

echo "[3/3] Starting UI..."
sudo systemctl start dcs-ui
sleep 2

sudo systemctl status dcs-ui --no-pager -l
curl -sf http://127.0.0.1:3000 > /dev/null && echo "Health: OK" || echo "Health: FAILED"
