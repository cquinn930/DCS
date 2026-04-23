#!/usr/bin/env bash
#
# commit-hotfix-422-500.sh
#
# Commits the four hotfix files from the dashboard-422 / sso-config-500
# debugging session as two logical commits, then optionally pushes:
#
#   1. fix(api): add api_public_url + harden /sso-config (500 fix)
#   2. fix(ui):  send lowercase status_filter from dashboard (422 fix)
#               + bump server-update health-check timeout
#
# Re-running after a partial run is safe (a commit is skipped if its
# file group has nothing to stage).
#
# Usage:
#   bash scripts/commit-hotfix-422-500.sh           # commit only
#   bash scripts/commit-hotfix-422-500.sh --push    # commit + push origin main
#   bash scripts/commit-hotfix-422-500.sh --dry-run # print what would happen
#
set -euo pipefail
cd "$(dirname "$0")/.."

EXPECTED_BRANCH="main"
PUSH=0
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --push)    PUSH=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help)
            sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg" >&2
            echo "Try: $0 --help" >&2
            exit 2
            ;;
    esac
done

run() {
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "+ $*"
    else
        echo "+ $*"
        eval "$@"
    fi
}

# Sanity checks --------------------------------------------------------
branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "$EXPECTED_BRANCH" ]]; then
    echo "ERROR: expected branch '$EXPECTED_BRANCH', got '$branch'" >&2
    exit 1
fi

# Commit helper using a tempfile (avoids bash 3.2 heredoc quirks) ------
commit_if_staged() {
    local message_file="$1"
    if git diff --cached --quiet; then
        echo "  (no staged changes — skipping)"
        rm -f "$message_file"
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "+ git commit -F <message>"
        echo "----- begin message -----"
        cat "$message_file"
        echo "----- end message -----"
    else
        git commit -F "$message_file"
    fi
    rm -f "$message_file"
}

# ---------------------------------------------------------------------
# Commit 1 — API: 500 fix on /sso-config
# ---------------------------------------------------------------------
echo "==> Commit 1: API hotfix (sso-config 500)"
run "git add services/api/dcs_api/config.py services/api/dcs_api/routers/tenants.py"

msg1="$(mktemp)"
cat >"$msg1" <<'EOF'
fix(api): add api_public_url setting and harden tenant /sso-config

PATCH /api/v1/tenants/{id}/sso-config previously crashed with
HTTP 500 the first time a tenant saved OIDC settings without an
explicit redirect_uri. The handler tried to derive one from
settings.api_public_url, which was referenced in exactly one
place but defined nowhere in the Settings class — accessing the
missing attribute raised AttributeError → 500.

Changes:
  * config.py: declare api_public_url (env-overridable via
    API_PUBLIC_URL in the API .env). Defaults to
    http://localhost:8000 for dev parity with database_url.
  * routers/tenants.py:
      - Defensive getattr() so a missing api_public_url returns
        a clean HTTP 400 with a helpful message instead of 500.
      - Add GET /tenants/{id}/sso-config so the settings UI has
        a dedicated read endpoint that returns enabled=false for
        unconfigured tenants instead of forcing the UI to dig
        through /tenants/current. client_secret is intentionally
        never returned (write-only).

Operators must set API_PUBLIC_URL in services/api/.env to the
public base URL the IdP can reach (e.g. https://falreports.example.com)
so future SSO saves can derive the correct redirect_uri.
EOF
commit_if_staged "$msg1"

# ---------------------------------------------------------------------
# Commit 2 — UI: 422 fix + server-update health-check timeout
# ---------------------------------------------------------------------
echo
echo "==> Commit 2: UI hotfix (dashboard 422) + deploy script timeout"
run "git add services/ui/src/app/\(dashboard\)/dashboard/page.tsx scripts/server-update.sh scripts/commit-hotfix-422-500.sh"

msg2="$(mktemp)"
cat >"$msg2" <<'EOF'
fix(ui): send lowercase status_filter from dashboard; widen deploy health-check window

Two unrelated deploy-time bugs surfaced in the same pull:

1. Dashboard 422s on /api/v1/accounts?status_filter=ACTIVE
   The AccountStatus enum stores LOWERCASE values
   (active, hold, legal_hold, paid_in_full, settled, closed).
   FastAPI/Pydantic match enum query params by VALUE, not name,
   so every uppercase request returned 422 Unprocessable Entity.
   The dashboard was the lone uppercase caller; the rest of the
   UI already uses lowercase.

   Fix: send lowercase values, uppercase the label client-side
   for the existing status-color conditionals (s.toUpperCase()).

2. server-update.sh false-negative on dcs-api health
   The script slept 3s after `systemctl restart dcs-api` before
   curling /health, but uvicorn with 4 workers takes ~6s to
   finish startup. The race produced a misleading
   "NOT RESPONDING" line in the update summary even when the
   API was healthy moments later.

   Fix: replace the fixed sleep with a 30s retry loop
   (15 attempts × 2s) for both /health and the UI port.
EOF
commit_if_staged "$msg2"

# ---------------------------------------------------------------------
echo
git log --oneline -5

if [[ $PUSH -eq 1 ]]; then
    echo
    echo "==> Pushing to origin/$EXPECTED_BRANCH"
    run "git push origin $EXPECTED_BRANCH"
else
    echo
    echo "==> Done. Review with: git log -p -2"
    echo "    Then push with:    git push origin $EXPECTED_BRANCH"
    echo "    Or re-run me with: $0 --push"
fi
