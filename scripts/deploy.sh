#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/sites/DCS"
API_DIR="$APP_ROOT/services/api"
UI_DIR="$APP_ROOT/services/ui"
VENV_PYTHON="python3.11"
SERVICE_USER="www-data"
SERVICE_GROUP="dcs"

NODE_DIR=$(dirname "$(command -v node)")
echo "=== DCS Deploy — $(date) ==="

# 1. Stop services
echo "[1/7] Stopping services..."
sudo systemctl stop dcs-ui dcs-api

# 2. Pull latest code (uncomment if using git)
# echo "[2/7] Pulling latest code..."
# cd "$APP_ROOT"
# sudo -u "$SERVICE_USER" git pull origin main
echo "[2/7] Skipping git pull (manual upload). Uncomment above if using git."

# 3. Fix ownership after upload
echo "[3/7] Fixing file ownership..."
sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$APP_ROOT"
sudo find "$APP_ROOT" -type d -exec chmod 2775 {} \;
sudo find "$APP_ROOT" -type f -exec chmod 664 {} \;

# 4. Rebuild API venv
echo "[4/7] Rebuilding Python venv..."
sudo -u "$SERVICE_USER" bash -c "
    cd '$API_DIR'
    rm -rf venv
    $VENV_PYTHON -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
"
sudo find "$API_DIR/venv/bin" -type f -exec chmod 775 {} \;

# 5. Run database migrations + reseed policy-pack drafts
echo "[5/7] Running database migrations + policy-pack draft reseed..."
sudo -u "$SERVICE_USER" bash -c "
    cd '$API_DIR'
    source venv/bin/activate
    alembic upgrade head
    # Idempotent. Updates DRAFT packs only; never mutates ACTIVE packs.
    # Use scripts/seed-policy-packs.sh --activate to flip a draft live.
    python scripts/seed_policy_packs.py
"

# 6. Rebuild frontend
echo "[6/7] Rebuilding frontend..."
sudo -u "$SERVICE_USER" bash -c "
    export PATH='$NODE_DIR:/usr/local/bin:/usr/bin:/bin'
    cd '$UI_DIR'
    npm ci
    npm run build
"
sudo find "$UI_DIR/node_modules/.bin" -type f -exec chmod 775 {} \;

# 7. Start services
echo "[7/7] Starting services..."
sudo systemctl start dcs-api
sleep 3
sudo systemctl start dcs-ui

echo ""
echo "=== Deploy complete ==="
sudo systemctl status dcs-api --no-pager -l
echo ""
sudo systemctl status dcs-ui --no-pager -l
echo ""
echo "Health check:"
curl -sf http://127.0.0.1:8000/health && echo " API OK" || echo " API FAILED"
curl -sf http://127.0.0.1:3000 > /dev/null && echo " UI OK" || echo " UI FAILED"
