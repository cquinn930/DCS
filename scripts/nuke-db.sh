#!/usr/bin/env bash
set -euo pipefail

API_DIR="/opt/sites/DCS/services/api"
SERVICE_USER="www-data"

echo "=== DCS Database RESET — $(date) ==="
echo "WARNING: This will DROP ALL TABLES and recreate the schema."
echo "All data will be permanently lost."
read -rp "Type 'RESET' to confirm: " confirm
[[ "$confirm" = "RESET" ]] || { echo "Aborted."; exit 0; }

sudo systemctl stop dcs-api dcs-ui

sudo -u "$SERVICE_USER" bash -c "
    cd '$API_DIR'
    source venv/bin/activate
    python -c \"
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dcs_api.config import get_settings

async def reset():
    s = get_settings()
    engine = create_async_engine(s.database_url)
    async with engine.begin() as conn:
        await conn.execute(text('DROP SCHEMA public CASCADE'))
        await conn.execute(text('CREATE SCHEMA public'))
    await engine.dispose()
    print('Schema reset complete.')

asyncio.run(reset())
\"
    # Remove old migration versions and generate fresh
    rm -f alembic/versions/*.py
    alembic revision --autogenerate -m 'fresh schema'
    alembic upgrade head
    python scripts/seed.py
"

sudo systemctl start dcs-api
sleep 2
sudo systemctl start dcs-ui

echo "=== Database reset and reseeded ==="
