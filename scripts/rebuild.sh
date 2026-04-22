#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/sites/DCS"
API_DIR="$APP_ROOT/services/api"
UI_DIR="$APP_ROOT/services/ui"
SERVICE_USER="www-data"
NODE_DIR=$(dirname "$(command -v node)")

echo "=== DCS Rebuild & Restart — $(date) ==="

# 1. Stop both services
echo "[1/4] Stopping services..."
sudo systemctl stop dcs-ui dcs-api 2>/dev/null || true

# 2. Fix permissions on changed files
echo "[2/4] Fixing permissions..."
sudo chown -R "$SERVICE_USER:www-data" "$API_DIR" "$UI_DIR"

# 3. Rebuild UI
echo "[3/4] Rebuilding frontend..."
sudo -u "$SERVICE_USER" bash -c "
    export PATH='$NODE_DIR:/usr/local/bin:/usr/bin:/bin'
    cd '$UI_DIR'
    node node_modules/next/dist/bin/next build
"

# 4. Start services
echo "[4/4] Starting services..."
sudo systemctl start dcs-api
sleep 5
sudo systemctl start dcs-ui
sleep 3

echo ""
echo "=== Status ==="
sudo systemctl status dcs-api --no-pager --lines=3
echo ""
sudo systemctl status dcs-ui --no-pager --lines=3
echo ""
echo "Health checks:"
curl -sf http://127.0.0.1:8000/health && echo " API OK" || echo " API FAILED"
curl -sf http://127.0.0.1:3000 > /dev/null && echo " UI OK" || echo " UI FAILED"
