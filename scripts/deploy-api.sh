#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/sites/DCS"
API_DIR="$APP_ROOT/services/api"
VENV_PYTHON="python3.11"
SERVICE_USER="www-data"
SERVICE_GROUP="dcs"

echo "=== DCS API Deploy — $(date) ==="

sudo systemctl stop dcs-api

echo "[1/4] Fixing ownership..."
sudo chown -R "$SERVICE_USER:$SERVICE_GROUP" "$API_DIR"
sudo find "$API_DIR" -type d -exec chmod 2775 {} \;
sudo find "$API_DIR" -type f -exec chmod 664 {} \;

echo "[2/4] Updating Python dependencies..."
sudo -u "$SERVICE_USER" bash -c "
    cd '$API_DIR'
    source venv/bin/activate
    pip install -r requirements.txt
"
sudo find "$API_DIR/venv/bin" -type f -exec chmod 775 {} \;

echo "[3/4] Running migrations + reseeding policy-pack drafts..."
sudo -u "$SERVICE_USER" bash -c "
    cd '$API_DIR'
    source venv/bin/activate
    alembic upgrade head
    # Idempotent. Updates DRAFT packs in place; never mutates ACTIVE packs.
    # Pass --activate manually via scripts/seed-policy-packs.sh when you
    # want to flip a new draft to ACTIVE.
    python scripts/seed_policy_packs.py
"

echo "[4/4] Starting API..."
sudo systemctl start dcs-api
sleep 2

sudo systemctl status dcs-api --no-pager -l
curl -sf http://127.0.0.1:8000/health && echo "Health: OK" || echo "Health: FAILED"
