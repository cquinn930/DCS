#!/usr/bin/env bash
set -euo pipefail

#
# First-time server setup for DCS
# Run once after copying DCS to /opt/sites/DCS
#
# Usage: sudo bash /opt/sites/DCS/scripts/setup-server.sh
#

APP_ROOT="/opt/sites/DCS"
SCRIPTS_DIR="$APP_ROOT/scripts"
SERVICE_USER="www-data"
SERVICE_GROUP="dcs"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (use sudo)."
    exit 1
fi

echo "=== DCS Server Setup — $(date) ==="

# Pre-flight: verify system-wide node is available
NODE_BIN=$(command -v node 2>/dev/null || true)
NPM_BIN=$(command -v npm 2>/dev/null || true)
if [ -z "$NODE_BIN" ] || [ -z "$NPM_BIN" ]; then
    echo "ERROR: node/npm not found in system PATH."
    echo "Install Node.js system-wide (not via nvm):"
    echo "  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -"
    echo "  sudo apt install -y nodejs"
    exit 1
fi
NODE_DIR=$(dirname "$NODE_BIN")
echo "  Using node: $NODE_BIN ($(node --version))"
echo "  Using npm:  $NPM_BIN ($(npm --version))"

# 1. Create the dcs group and add users
echo "[1/8] Setting up users and groups..."
groupadd -f "$SERVICE_GROUP"
usermod -aG "$SERVICE_GROUP" "$SERVICE_USER"
usermod -aG "$SERVICE_GROUP" cquinn
echo "  Group '$SERVICE_GROUP' ready. Members: $SERVICE_USER, cquinn"

# 2. Fix ownership and permissions
echo "[2/8] Setting file ownership and permissions..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$APP_ROOT"
find "$APP_ROOT" -type d -exec chmod 2775 {} \;
find "$APP_ROOT" -type f -exec chmod 664 {} \;
find "$SCRIPTS_DIR" -name "*.sh" -exec chmod 775 {} \;

# 3. Install nginx if not present
echo "[3/8] Installing nginx..."
if ! command -v nginx &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq nginx
fi

# 4. Deploy nginx config
echo "[4/8] Configuring nginx..."
cp "$SCRIPTS_DIR/nginx/dcs.conf" /etc/nginx/sites-available/dcs
ln -sf /etc/nginx/sites-available/dcs /etc/nginx/sites-enabled/dcs
nginx -t
systemctl restart nginx
systemctl enable nginx

# 5. Deploy systemd services
echo "[5/8] Installing systemd services..."
cp "$SCRIPTS_DIR/systemd/dcs-api.service" /etc/systemd/system/
cp "$SCRIPTS_DIR/systemd/dcs-ui.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable dcs-api dcs-ui

# 6. Build API venv
echo "[6/8] Building Python venv with python3.11..."
sudo -u "$SERVICE_USER" bash -c "
    cd '$APP_ROOT/services/api'
    rm -rf venv
    python3.11 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
"
find "$APP_ROOT/services/api/venv/bin" -type f -exec chmod 775 {} \;

# 7. Build frontend
echo "[7/8] Building frontend..."
sudo -u "$SERVICE_USER" bash -c "
    export PATH='$NODE_DIR:/usr/local/bin:/usr/bin:/bin'
    cd '$APP_ROOT/services/ui'
    npm ci
    npm run build
"
find "$APP_ROOT/services/ui/node_modules/.bin" -type f -exec chmod 775 {} \;

# 8. Start everything
echo "[8/8] Starting services..."
systemctl start dcs-api
sleep 3
systemctl start dcs-ui

echo ""
echo "========================================"
echo "  DCS Setup Complete"
echo "========================================"
echo ""
echo "Services:"
systemctl is-active dcs-api && echo "  API:   running" || echo "  API:   FAILED"
systemctl is-active dcs-ui  && echo "  UI:    running" || echo "  UI:    FAILED"
systemctl is-active nginx   && echo "  nginx: running" || echo "  nginx: FAILED"
echo ""
echo "Next steps:"
echo "  1. Verify .env files in services/api/.env and services/ui/.env.local"
echo "  2. Run migrations:           $SCRIPTS_DIR/deploy-api.sh"
echo "  3. Seed sample data:         $SCRIPTS_DIR/seed-db.sh"
echo "     (also activates NJ + NY policy packs)"
echo "  4. Or seed packs only:       sudo bash $SCRIPTS_DIR/seed-policy-packs.sh --activate"
echo "  5. Self-signed SSL:          sudo bash $SCRIPTS_DIR/setup-ssl.sh"
echo ""
echo "Log out and back in so group membership takes effect for cquinn."
