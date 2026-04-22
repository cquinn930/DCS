#!/usr/bin/env bash
set -euo pipefail

API_DIR="/opt/sites/DCS/services/api"
SERVICE_USER="www-data"

echo "=== DCS Database Seed — $(date) ==="
echo "WARNING: This will reseed the database with sample data."
read -rp "Continue? (y/N): " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

sudo -u "$SERVICE_USER" bash -c "
    cd '$API_DIR'
    source venv/bin/activate
    python scripts/seed.py
    python scripts/seed_policy_packs.py --activate
"

echo "=== Seed complete (sample data + NJ/NY policy packs ACTIVE) ==="
