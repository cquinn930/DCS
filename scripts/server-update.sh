#!/usr/bin/env bash
#
# server-update.sh
#
# In-place update of an existing DCS deployment by pulling from GitHub.
# Designed to run on the deployment host (e.g. falreports) as a drop-in
# replacement for the upload-zip-and-rsync workflow.
#
# What it does:
#   1. Backs up .env files from the install dir so a hard reset can't
#      eat them (they're already gitignored, but belt + suspenders).
#   2. Bootstraps the install dir as a git checkout if it isn't one
#      already, then fetches origin/$BRANCH and hard-resets to it.
#   3. Restores the .env files.
#   4. Refreshes Python deps (only if requirements.txt changed) and
#      runs Alembic to head.
#   5. Refreshes Node deps (npm ci when a lockfile is present) and
#      builds Next.js.
#   6. Repairs file ownership / executable bits stripped by previous
#      bad deploys.
#   7. Restarts dcs-api and dcs-ui, then health-checks both.
#
# Requires: git, node, npm, python3, alembic (in the API venv), sudo.
# Must run as root (the script re-execs itself with sudo if not).
#
# Usage:
#   sudo bash scripts/server-update.sh
#   sudo bash scripts/server-update.sh --branch some-feature-branch
#   sudo bash scripts/server-update.sh --skip-build      # skip npm build
#   sudo bash scripts/server-update.sh --skip-migrate    # skip alembic
#   sudo bash scripts/server-update.sh --dry-run         # show, don't do
#
# First-time bootstrap on a server that doesn't yet have this script
# locally:
#
#   curl -fsSL https://raw.githubusercontent.com/cquinn930/DCS/main/scripts/server-update.sh \
#       -o /tmp/server-update.sh
#   sudo bash /tmp/server-update.sh
#
# Configuration (env vars override defaults):
#   DCS_REPO_URL    git URL to pull from (default: GitHub HTTPS)
#   DCS_INSTALL_DIR install path on the server (default: /opt/sites/DCS)
#   DCS_BRANCH      branch to track (default: main; --branch overrides)
#   DCS_OWNER_USER  unix user that owns the install (default: www-data)
#   DCS_OWNER_GROUP unix group that owns the install (default: dcs)
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults / arg parsing
# ---------------------------------------------------------------------------

REPO_URL="${DCS_REPO_URL:-https://github.com/cquinn930/DCS.git}"
INSTALL_DIR="${DCS_INSTALL_DIR:-/opt/sites/DCS}"
BRANCH="${DCS_BRANCH:-main}"
OWNER_USER="${DCS_OWNER_USER:-www-data}"
OWNER_GROUP="${DCS_OWNER_GROUP:-dcs}"

SKIP_BUILD=0
SKIP_MIGRATE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --branch)        BRANCH="${2:?--branch needs a value}"; shift 2 ;;
        --skip-build)    SKIP_BUILD=1; shift ;;
        --skip-migrate)  SKIP_MIGRATE=1; shift ;;
        --dry-run)       DRY_RUN=1; shift ;;
        -h|--help)
            sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
            exit 0
            ;;
        *)
            echo "Unknown flag: $1" >&2
            echo "Try: $0 --help" >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Re-exec as root if not already
# ---------------------------------------------------------------------------

if [[ $EUID -ne 0 ]]; then
    echo "Re-running with sudo..."
    exec sudo -E bash "$0" \
        ${BRANCH:+--branch "$BRANCH"} \
        $([[ $SKIP_BUILD -eq 1 ]] && echo --skip-build) \
        $([[ $SKIP_MIGRATE -eq 1 ]] && echo --skip-migrate) \
        $([[ $DRY_RUN -eq 1 ]] && echo --dry-run)
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[fatal]\033[0m %s\n' "$*" >&2; exit 1; }

run() {
    printf '+ %s\n' "$*"
    if [[ $DRY_RUN -eq 0 ]]; then
        eval "$@"
    fi
}

# Run a shell snippet as the install owner. Always sets -e so failures
# bubble up and the outer set -euo pipefail can react.
as_owner() {
    local script=$1
    if [[ $DRY_RUN -eq 1 ]]; then
        printf '+ sudo -u %s bash -c <<EOF\n%s\nEOF\n' "$OWNER_USER" "$script"
        return 0
    fi
    sudo -u "$OWNER_USER" bash -c "set -euo pipefail; $script"
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------

log "Pre-flight"

require_cmd git
require_cmd node
require_cmd npm
require_cmd python3
require_cmd sudo
require_cmd systemctl

id -u "$OWNER_USER" >/dev/null 2>&1 || die "user '$OWNER_USER' does not exist"
getent group "$OWNER_GROUP" >/dev/null 2>&1 || die "group '$OWNER_GROUP' does not exist"

if [[ ! -d "$INSTALL_DIR" ]]; then
    log "Install dir $INSTALL_DIR does not exist; creating"
    run "mkdir -p '$INSTALL_DIR'"
    run "chown '$OWNER_USER:$OWNER_GROUP' '$INSTALL_DIR'"
    run "chmod 2775 '$INSTALL_DIR'"
fi

cat <<INFO
  Repo:       $REPO_URL
  Branch:     $BRANCH
  Install:    $INSTALL_DIR
  Owner:      $OWNER_USER:$OWNER_GROUP
  Skip build: $SKIP_BUILD
  Skip migr.: $SKIP_MIGRATE
  Dry run:    $DRY_RUN
INFO

# ---------------------------------------------------------------------------
# Backup .env files
#
# Anything matching .env* anywhere under the install dir is preserved.
# We tar them so directory structure is intact for the restore.
# ---------------------------------------------------------------------------

ENV_BACKUP_DIR="/var/backups/dcs"
ENV_BACKUP_FILE="$ENV_BACKUP_DIR/env-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"

log "Backing up .env files"
run "mkdir -p '$ENV_BACKUP_DIR'"

env_paths=()
if [[ -d "$INSTALL_DIR" ]]; then
    while IFS= read -r -d '' p; do
        env_paths+=("$p")
    done < <(find "$INSTALL_DIR" \
        -path "$INSTALL_DIR/.git" -prune -o \
        -path "*/node_modules" -prune -o \
        -path "*/venv" -prune -o \
        -path "*/.venv" -prune -o \
        \( -name '.env' -o -name '.env.*' -o -name '*.env' \) -type f -print0 2>/dev/null)
fi

if [[ ${#env_paths[@]} -gt 0 ]]; then
    printf '  found:\n'
    printf '    %s\n' "${env_paths[@]}"
    if [[ $DRY_RUN -eq 0 ]]; then
        # Use -C so paths inside the tar are relative to the install dir,
        # which makes the restore step trivial.
        rel_paths=()
        for p in "${env_paths[@]}"; do
            rel_paths+=("${p#$INSTALL_DIR/}")
        done
        tar -czf "$ENV_BACKUP_FILE" -C "$INSTALL_DIR" "${rel_paths[@]}"
        echo "  backup: $ENV_BACKUP_FILE"
    fi
else
    warn "no .env files found in $INSTALL_DIR (first install? this is fine)"
fi

# ---------------------------------------------------------------------------
# Pull from GitHub
#
# Three states to handle:
#   A) Empty install dir         -> git clone
#   B) Existing checkout, .git/  -> git fetch + git reset --hard
#   C) Existing tree, no .git/   -> initialize git here, fetch, reset
#
# In (C) we have to be careful: git reset --hard will overwrite tracked
# files that exist locally with their version from origin, but will
# leave untracked / gitignored files alone. node_modules, venv, .next,
# alembic/versions/ etc. are all in .gitignore and survive.
# ---------------------------------------------------------------------------

log "Syncing $INSTALL_DIR to origin/$BRANCH"

if [[ ! -d "$INSTALL_DIR/.git" ]] && [[ -z "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
    # State A: empty
    log "Empty install dir, performing fresh clone"
    as_owner "git clone --branch '$BRANCH' '$REPO_URL' '$INSTALL_DIR'"
elif [[ ! -d "$INSTALL_DIR/.git" ]]; then
    # State C: tree exists but isn't a git checkout
    log "Install dir is not a git checkout; initializing in place"
    as_owner "
        cd '$INSTALL_DIR'
        git init -q
        git remote add origin '$REPO_URL' 2>/dev/null || git remote set-url origin '$REPO_URL'
        git fetch --depth=1 origin '$BRANCH'
        # Some files may locally exist that are also tracked at origin.
        # Use checkout -f to overwrite them in our working tree.
        git checkout -f -B '$BRANCH' 'origin/$BRANCH'
    "
else
    # State B: normal update
    as_owner "
        cd '$INSTALL_DIR'
        # Make sure the remote URL matches in case it changed.
        git remote set-url origin '$REPO_URL'
        git fetch --prune origin '$BRANCH'
        # Hard reset to origin. Untracked + ignored files (node_modules,
        # .env, venv, ...) are preserved.
        git checkout -f -B '$BRANCH' 'origin/$BRANCH'
        git reset --hard 'origin/$BRANCH'
    "
fi

NEW_REV="$(cd "$INSTALL_DIR" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
log "Now at $BRANCH @ $NEW_REV"

# ---------------------------------------------------------------------------
# Restore .env files
# ---------------------------------------------------------------------------

if [[ -f "$ENV_BACKUP_FILE" ]]; then
    log "Restoring .env files"
    run "tar -xzf '$ENV_BACKUP_FILE' -C '$INSTALL_DIR'"
    run "chown -R '$OWNER_USER:$OWNER_GROUP' '$INSTALL_DIR'"
    # Lock down env files; they contain secrets.
    if [[ $DRY_RUN -eq 0 ]]; then
        find "$INSTALL_DIR" \
            -path "$INSTALL_DIR/.git" -prune -o \
            -path "*/node_modules" -prune -o \
            \( -name '.env' -o -name '.env.*' -o -name '*.env' \) -type f \
            -exec chmod 640 {} \;
    fi
fi

# ---------------------------------------------------------------------------
# Python deps + Alembic
# ---------------------------------------------------------------------------

API_DIR="$INSTALL_DIR/services/api"

if [[ -d "$API_DIR" ]]; then
    # python3-saml has a build-time dependency on libxmlsec1 / libxml2
    # / pkg-config. Install the apt packages once so `pip install
    # python3-saml` doesn't blow up with cryptic "missing xmlsec1.h"
    # errors. Idempotent: apt is a no-op when everything is current.
    log "Ensuring SAML build-time system packages are present"
    if command -v apt-get >/dev/null 2>&1; then
        SAML_APT_PKGS=(libxmlsec1-dev libxml2-dev pkg-config)
        missing=()
        for pkg in "${SAML_APT_PKGS[@]}"; do
            if ! dpkg -s "$pkg" >/dev/null 2>&1; then
                missing+=("$pkg")
            fi
        done
        if [[ ${#missing[@]} -gt 0 ]]; then
            run "apt-get update -qq"
            run "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ${missing[*]}"
        else
            echo "  apt packages already installed: ${SAML_APT_PKGS[*]}"
        fi
    else
        warn "apt-get not found; if python3-saml install fails, install libxmlsec1-dev libxml2-dev pkg-config manually"
    fi

    log "Refreshing Python dependencies"
    as_owner "
        cd '$API_DIR'
        if [[ ! -d venv ]]; then
            python3 -m venv venv
        fi
        # shellcheck disable=SC1091
        source venv/bin/activate
        pip install --quiet --upgrade pip
        if [[ -f requirements.txt ]]; then
            pip install --quiet -r requirements.txt
        fi
    "

    if [[ $SKIP_MIGRATE -eq 0 ]]; then
        log "Running database migrations"
        as_owner "
            cd '$API_DIR'
            # shellcheck disable=SC1091
            source venv/bin/activate
            alembic upgrade head
            alembic current
        "
    else
        warn "skipping alembic upgrade (--skip-migrate)"
    fi
else
    warn "$API_DIR not found; skipping API steps"
fi

# ---------------------------------------------------------------------------
# Node deps + Next.js build
# ---------------------------------------------------------------------------

UI_DIR="$INSTALL_DIR/services/ui"

if [[ -d "$UI_DIR" ]]; then
    log "Refreshing Node dependencies"
    as_owner "
        cd '$UI_DIR'
        # Prefer reproducible install when a lockfile is present.
        if [[ -f package-lock.json ]]; then
            npm ci --silent --no-audit --no-fund
        else
            npm install --silent --no-audit --no-fund
        fi
    "

    # Past deploys have stripped exec bits from the npm bin shims via
    # an over-broad chmod 664. Restore them defensively.
    log "Repairing node_modules/.bin executable bits"
    if [[ -d "$UI_DIR/node_modules/.bin" ]]; then
        run "find '$UI_DIR/node_modules/.bin' -type f -exec chmod 0755 {} +"
    fi

    if [[ $SKIP_BUILD -eq 0 ]]; then
        log "Building Next.js bundle"
        as_owner "
            cd '$UI_DIR'
            npm run build
        "
    else
        warn "skipping next build (--skip-build)"
    fi
else
    warn "$UI_DIR not found; skipping UI steps"
fi

# ---------------------------------------------------------------------------
# Ownership sweep
#
# git operations as $OWNER_USER created files as $OWNER_USER, but a
# previous pre-update state may have had root-owned files that need
# to be normalized.
# ---------------------------------------------------------------------------

log "Normalizing ownership of $INSTALL_DIR"
run "chown -R '$OWNER_USER:$OWNER_GROUP' '$INSTALL_DIR'"

# ---------------------------------------------------------------------------
# Restart services + health check
# ---------------------------------------------------------------------------

log "Restarting services"
run "systemctl restart dcs-api"
run "systemctl restart dcs-ui"

# Wait up to ~30s for each service to come up. Uvicorn with 4 workers
# typically needs 5-8s to finish startup; Next.js standalone is faster
# but we keep the same budget for symmetry.
wait_for_url() {
    local url="$1"
    local label="$2"
    local tries=15  # 15 * 2s = 30s
    if [[ $DRY_RUN -ne 0 ]]; then
        return 0
    fi
    for ((i=1; i<=tries; i++)); do
        if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    return 1
}

api_ok=0
ui_ok=0
if wait_for_url "http://127.0.0.1:8000/health" "dcs-api"; then
    api_ok=1
fi
if wait_for_url "http://127.0.0.1:3000"        "dcs-ui"; then
    ui_ok=1
fi

echo
echo "============================================================"
echo "Update summary"
echo "============================================================"
echo "  Branch / rev:  $BRANCH @ $NEW_REV"
echo "  Install dir:   $INSTALL_DIR"
[[ -f "$ENV_BACKUP_FILE" ]] && echo "  .env backup:   $ENV_BACKUP_FILE"
echo "  dcs-api:       $([[ $api_ok -eq 1 ]] && echo 'OK (200 /health)' || echo 'NOT RESPONDING — check journalctl -u dcs-api -n 80')"
echo "  dcs-ui:        $([[ $ui_ok  -eq 1 ]] && echo 'OK (responded on :3000)' || echo 'NOT RESPONDING — check journalctl -u dcs-ui  -n 80')"
echo "============================================================"

if [[ $DRY_RUN -eq 0 && ( $api_ok -eq 0 || $ui_ok -eq 0 ) ]]; then
    exit 1
fi
