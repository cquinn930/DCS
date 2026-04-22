#!/usr/bin/env bash
set -euo pipefail

#
# DCS unified installer / redeploy.
#
# Usage from the unzipped staging directory (e.g. /tmp/DCS):
#   sudo bash install.sh                    # auto-detect first-install vs redeploy
#   sudo bash install.sh --first-install    # force first-install path
#   sudo bash install.sh --redeploy         # force redeploy path
#   sudo bash install.sh --skip-seed        # do not seed sample data on first install
#   sudo bash install.sh --no-cleanup       # keep staging dir after install (for debugging)
#
# What it does:
#   1. Validates we are running from an unzipped DCS staging directory.
#   2. Syncs the staging tree into APP_ROOT (/opt/sites/DCS), preserving
#      existing .env files, the venv, and node_modules.
#   3. On first install: runs setup-server.sh, generates the initial
#      alembic revision, runs migrations, seeds sample data + activates
#      NJ + NY policy packs.
#   4. On redeploy: runs scripts/deploy.sh (stops services, refreshes
#      deps, runs migrations, reseeds policy-pack drafts, restarts).
#   5. Removes the staging directory (unless --no-cleanup) so /tmp is
#      left with only the zip file you uploaded.
#
# Non-legal guidance: activating policy packs (NJ + NY 2026.1) marks
# them ACTIVE in the database. Verify rates and citations in
# docs/08_nj_policy_pack.md and docs/09_ny_policy_pack.md before
# activating in production.
#

APP_ROOT="/opt/sites/DCS"
SERVICE_USER="www-data"
SERVICE_GROUP="dcs"

MODE="auto"
DO_SEED=1
DO_CLEANUP=1
while [[ $# -gt 0 ]]; do
    case "$1" in
        --first-install) MODE="first" ;;
        --redeploy)      MODE="redeploy" ;;
        --skip-seed)     DO_SEED=0 ;;
        --no-cleanup)    DO_CLEANUP=0 ;;
        -h|--help)
            sed -n '3,30p' "$0"
            exit 0
            ;;
        *) echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
    shift
done

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: install.sh must run as root (use sudo)." >&2
    exit 1
fi

STAGING_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -d "$STAGING_DIR/services/api" ] || [ ! -f "$STAGING_DIR/scripts/setup-server.sh" ]; then
    echo "ERROR: $STAGING_DIR does not look like a DCS staging tree." >&2
    echo "       Expected services/api and scripts/setup-server.sh to exist." >&2
    exit 1
fi

if [ "$STAGING_DIR" = "$APP_ROOT" ]; then
    echo "ERROR: refusing to run install.sh from $APP_ROOT (it would self-delete)." >&2
    echo "       Unzip into /tmp or another staging path and re-run." >&2
    exit 1
fi

# Auto-detect mode if not forced.
if [ "$MODE" = "auto" ]; then
    if [ -d "$APP_ROOT/services/api/venv" ] && systemctl list-unit-files | grep -q '^dcs-api\.service'; then
        MODE="redeploy"
    else
        MODE="first"
    fi
fi

echo "============================================================"
echo "  DCS install.sh  ($(date))"
echo "  Staging:  $STAGING_DIR"
echo "  Target:   $APP_ROOT"
echo "  Mode:     $MODE"
echo "============================================================"

# ---------------------------------------------------------------------------
# 1. Sync staging tree into /opt/sites/DCS
# ---------------------------------------------------------------------------
echo ""
echo "[1/4] Syncing files into $APP_ROOT ..."
mkdir -p "$APP_ROOT"

# rsync preserves the venv, node_modules, .next, and .env files in the
# target by excluding them from the transfer. The redeploy scripts
# (deploy.sh / deploy-api.sh) refresh deps in place.
RSYNC_EXCLUDES=(
    --exclude='services/api/venv/'
    --exclude='services/api/.venv/'
    --exclude='services/api/.env'
    --exclude='services/ui/node_modules/'
    --exclude='services/ui/.next/'
    --exclude='services/ui/.env'
    --exclude='services/ui/.env.local'
    --exclude='migration/flg-data/'
    --exclude='__pycache__/'
    --exclude='*.pyc'
    --exclude='.DS_Store'
    --exclude='.git/'
    --exclude='install.sh'
)
rsync -a --delete-after --omit-dir-times \
    "${RSYNC_EXCLUDES[@]}" \
    "$STAGING_DIR/" "$APP_ROOT/"

# Copy install.sh itself to the target so operators can re-run it later
# from /opt/sites/DCS (it will refuse, by design — see check above — but
# it serves as a self-documenting reference of what was deployed).
cp "$STAGING_DIR/install.sh" "$APP_ROOT/install.sh.last-deployed"
chmod 444 "$APP_ROOT/install.sh.last-deployed"

# Make sure shell scripts are executable on the target.
find "$APP_ROOT/scripts" -name '*.sh' -exec chmod 775 {} \;

# ---------------------------------------------------------------------------
# 2. Branch on first-install vs redeploy
# ---------------------------------------------------------------------------
if [ "$MODE" = "first" ]; then
    # Check that the operator created the .env files first.
    if [ ! -f "$APP_ROOT/services/api/.env" ]; then
        echo ""
        echo "ERROR: $APP_ROOT/services/api/.env not found." >&2
        echo "       Copy from .env.example and edit before re-running:" >&2
        echo "         sudo cp $APP_ROOT/services/api/.env.example $APP_ROOT/services/api/.env" >&2
        echo "         sudo -e $APP_ROOT/services/api/.env" >&2
        echo "         sudo cp $APP_ROOT/services/ui/.env.example $APP_ROOT/services/ui/.env.local" >&2
        echo "         sudo -e $APP_ROOT/services/ui/.env.local" >&2
        echo "       Then re-run: sudo bash $0" >&2
        exit 2
    fi

    echo ""
    echo "[2/4] Running first-install bootstrap (setup-server.sh) ..."
    bash "$APP_ROOT/scripts/setup-server.sh"

    echo ""
    echo "[3/4] Generating initial Alembic revision + running migrations ..."
    sudo -u "$SERVICE_USER" bash -c "
        cd '$APP_ROOT/services/api'
        source venv/bin/activate
        if [ -z \"\$(ls alembic/versions/*.py 2>/dev/null)\" ]; then
            alembic revision --autogenerate -m 'initial schema'
        fi
        alembic upgrade head
    "

    if [ "$DO_SEED" -eq 1 ]; then
        echo ""
        echo "[4/4] Seeding sample data + activating NJ/NY policy packs ..."
        sudo -u "$SERVICE_USER" bash -c "
            cd '$APP_ROOT/services/api'
            source venv/bin/activate
            python scripts/seed.py
            python scripts/seed_policy_packs.py --activate
        "
    else
        echo ""
        echo "[4/4] --skip-seed: skipping seed.py and policy-pack activation."
        echo "      Activate packs later with:"
        echo "        sudo bash $APP_ROOT/scripts/seed-policy-packs.sh --activate"
    fi

else  # redeploy
    echo ""
    echo "[2/4] Running redeploy (scripts/deploy.sh) ..."
    bash "$APP_ROOT/scripts/deploy.sh"
    echo ""
    echo "[3/4] (no-op for redeploys — deploy.sh handled migrations + draft reseed)"
    echo ""
    echo "[4/4] (no-op — sample data and pack activation are NOT re-run on redeploy)"
fi

# ---------------------------------------------------------------------------
# 3. Smoke tests
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Smoke tests"
echo "============================================================"
sleep 2
if curl -fsS http://127.0.0.1:8000/health > /dev/null; then
    echo "  API:   OK   (http://127.0.0.1:8000/health)"
else
    echo "  API:   FAILED — check 'journalctl -u dcs-api -e'"
fi
if curl -fsS http://127.0.0.1:3000 > /dev/null; then
    echo "  UI:    OK   (http://127.0.0.1:3000)"
else
    echo "  UI:    FAILED — check 'journalctl -u dcs-ui -e'"
fi
echo ""
sudo -u "$SERVICE_USER" bash -c "
    cd '$APP_ROOT/services/api' && source venv/bin/activate
    python -c 'from dcs_api.notices import list_templates; \
print(\"  Notice templates registered:\", len(list_templates()))'
" || true

# ---------------------------------------------------------------------------
# 4. Cleanup the staging directory
# ---------------------------------------------------------------------------
if [ "$DO_CLEANUP" -eq 1 ]; then
    echo ""
    echo "[cleanup] Removing staging directory $STAGING_DIR ..."
    cd /
    rm -rf "$STAGING_DIR"
    echo "          Done. Only the original .zip remains."
else
    echo ""
    echo "[cleanup] --no-cleanup: leaving $STAGING_DIR in place."
fi

echo ""
echo "============================================================"
echo "  DCS install complete."
echo "============================================================"
echo ""
echo "  App root:   $APP_ROOT"
echo "  Logs:       sudo bash $APP_ROOT/scripts/logs.sh"
echo "  Status:     sudo bash $APP_ROOT/scripts/status.sh"
echo "  Re-deploy:  re-upload the zip and run 'sudo bash install.sh' again."
echo ""
