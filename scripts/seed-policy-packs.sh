#!/usr/bin/env bash
set -euo pipefail

#
# Seed jurisdiction policy packs (NJ + NY) into the active database.
# Idempotent. Drafts can be re-seeded; ACTIVE packs are never overwritten.
#
# Usage:
#   sudo bash /opt/sites/DCS/scripts/seed-policy-packs.sh            # draft only
#   sudo bash /opt/sites/DCS/scripts/seed-policy-packs.sh --activate # also activate
#

APP_ROOT="/opt/sites/DCS"
API_DIR="$APP_ROOT/services/api"
SERVICE_USER="www-data"

ACTIVATE_FLAG=""
if [[ "${1:-}" == "--activate" ]]; then
    ACTIVATE_FLAG="--activate"
fi

echo "=== DCS Policy-Pack Seed ($(date)) ==="
echo "    Mode: ${ACTIVATE_FLAG:-draft only}"

sudo -u "$SERVICE_USER" bash -c "
    cd '$API_DIR'
    source venv/bin/activate
    python scripts/seed_policy_packs.py $ACTIVATE_FLAG
"

echo "=== Policy-pack seed complete ==="
