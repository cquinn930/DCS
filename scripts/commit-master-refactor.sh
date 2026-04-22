#!/usr/bin/env bash
#
# commit-master-refactor.sh
#
# Stages, commits, and (optionally) pushes work from the master-tenant
# refactor session. Three logical commits are produced:
#
#   1. fix(ui):       restore services/ui/src/lib/ (gitignore fix)
#   2. feat(master):  Phase 1 master control-plane refactor
#   3. chore(scripts): add commit + server-update helper scripts
#
# Each commit is skipped if its file group has no staged changes, so
# re-running after a partial run is safe.
#
# Usage:
#   bash scripts/commit-master-refactor.sh           # commit only
#   bash scripts/commit-master-refactor.sh --push    # commit + push origin main
#   bash scripts/commit-master-refactor.sh --dry-run # show, don't run
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

current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current_branch" != "$EXPECTED_BRANCH" ]]; then
    echo "ERROR: expected branch '$EXPECTED_BRANCH', currently on '$current_branch'." >&2
    exit 1
fi
if [[ -d .git/rebase-merge || -d .git/rebase-apply || -f .git/MERGE_HEAD ]]; then
    echo "ERROR: a rebase or merge is in progress. Resolve it first." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# File groups
# ---------------------------------------------------------------------------

GITIGNORE_FILES=(
    .gitignore
)
UI_LIB_RECOVERY_FILES=(
    services/ui/src/lib
)
MASTER_BACKEND_FILES=(
    services/api/dcs_api/auth/jwt.py
    services/api/dcs_api/auth/rbac.py
    services/api/dcs_api/main.py
    services/api/dcs_api/routers/master.py
)
MASTER_UI_FILES=(
    services/ui/src/stores/auth.ts
    "services/ui/src/app/(dashboard)/layout.tsx"
    services/ui/src/components/master
    services/ui/src/app/master
)
SCRIPT_FILES=(
    scripts/commit-master-refactor.sh
    scripts/server-update.sh
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Stage a list of paths, silently skipping any that don't exist.
# Returns 0 if at least one path was staged, 1 if none.
stage_paths() {
    local existing=()
    for p in "$@"; do
        if [[ -e "$p" ]]; then
            existing+=("$p")
        else
            echo "  skip (missing): $p"
        fi
    done
    if [[ ${#existing[@]} -eq 0 ]]; then
        echo "  nothing to stage"
        return 1
    fi
    echo "+ git add -- ${existing[*]}"
    if [[ $DRY_RUN -eq 0 ]]; then
        git add -- "${existing[@]}"
    fi
    return 0
}

# Commit using a message file written by the caller via stdin. Sidesteps
# all of bash's heredoc-inside-command-substitution quoting headaches
# (which is what bit us on bash 3.2 / macOS).
#
# Usage:
#   write_msg_and_commit "Title here" <<'MSG'
#   Body line 1.
#
#   Body line 2 with parens (totally fine here).
#   MSG
write_msg_and_commit() {
    local title=$1
    local tmp
    tmp=$(mktemp -t dcs-commit-msg.XXXXXX)
    {
        printf '%s\n\n' "$title"
        cat
    } > "$tmp"

    if [[ $DRY_RUN -eq 1 ]]; then
        echo "  [dry-run] would commit with message:"
        sed 's/^/    | /' "$tmp"
        rm -f "$tmp"
        return 0
    fi

    if git diff --cached --quiet; then
        echo "  no staged changes; skipping commit"
        rm -f "$tmp"
        return 0
    fi

    git commit -F "$tmp"
    rm -f "$tmp"
}

# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

echo "============================================================"
echo "Repo:    $(git remote get-url origin 2>/dev/null || echo '(no remote)')"
echo "Branch:  $current_branch"
echo "HEAD:    $(git log -1 --oneline)"
echo "Push:    $([[ $PUSH -eq 1 ]] && echo 'YES' || echo 'no (run with --push to push)')"
echo "Dry run: $([[ $DRY_RUN -eq 1 ]] && echo 'YES' || echo 'no')"
echo "============================================================"
echo
echo "Current git status:"
git status --short
echo

# ---------------------------------------------------------------------------
# Commit 1 — UI lib recovery + .gitignore fix
# ---------------------------------------------------------------------------

echo "------------------------------------------------------------"
echo "Commit 1: fix(ui): restore services/ui/src/lib/"
echo "------------------------------------------------------------"

if stage_paths "${GITIGNORE_FILES[@]}" "${UI_LIB_RECOVERY_FILES[@]}"; then
    write_msg_and_commit "fix(ui): restore services/ui/src/lib/ excluded by stray lib/ ignore" <<'MSG'
The top-level .gitignore had unanchored 'lib/' and 'lib64/' entries left
over from a Python venv template. Because they were unanchored, git was
silently excluding services/ui/src/lib/ as well, so api.ts, electron.ts,
and utils.ts never made it into deploy zips. Next.js builds on the server
then failed with "Module not found: Can't resolve '@/lib/api'".

Removes the unanchored 'lib/' and 'lib64/' rules and adds the
previously-untracked services/ui/src/lib/ source files so they ship in
subsequent deploys. The 'venv/' and '.venv/' rules below already cover
real Python virtualenv directories.
MSG
fi

# ---------------------------------------------------------------------------
# Commit 2 — Master control plane (Phase 1)
# ---------------------------------------------------------------------------

echo
echo "------------------------------------------------------------"
echo "Commit 2: feat(master): control-plane refactor (Phase 1)"
echo "------------------------------------------------------------"

if stage_paths "${MASTER_BACKEND_FILES[@]}" "${MASTER_UI_FILES[@]}"; then
    write_msg_and_commit "feat(master): make master tenant a control plane (Phase 1)" <<'MSG'
Master users were inadvertently seeing other tenants' operational data
(dashboards, accounts, money) because tenant-scoped queries skipped the
WHERE tenant_id = ... clause whenever is_master was true. This commit
inverts the model: master is now a control plane that must explicitly
"enter" a tenant via an audited impersonation flow before any
tenant-scoped endpoint will respond.

Backend
-------
- auth/jwt.py: extend TokenData with acting_as_master, acting_can_write,
  master_user_id, master_tenant_id, impersonation_id; add
  create_impersonation_token() that mints short-lived 30-minute tokens
  whose tenant_id claim is the target tenant. Refresh of impersonation
  tokens is intentionally not supported.

- auth/rbac.py: extend CurrentUser with the new claims; add
  require_operational_scope (403s master users without an impersonation
  token) and require_master (control-plane only).

- routers/master.py: new control-plane router with system-status,
  tenants, impersonate, exit-impersonation, and audit endpoints. Every
  enter and exit is recorded in audit_logs with master identity, target
  tenant, mode read or write, and a session-scoped impersonation_id.

- main.py: register the master router; apply require_operational_scope
  as a router-level dependency on every operational include_router so
  we don't have to touch ~40 router files individually. Add
  ImpersonationWriteGuardMiddleware that rejects non-GET requests when
  the active token is acting_as_master with acting_can_write false.

Frontend
--------
- stores/auth.ts: add enterTenant and exitImpersonation actions. Stash
  the master's regular tokens during impersonation so exit doesn't
  require re-login. Persist impersonation state across page reloads.

- app/dashboard/layout.tsx: redirect master users to /master unless
  they're actively impersonating; render the impersonation banner above
  all operational pages.

- components/master/impersonation-banner.tsx: sticky banner with
  read/write mode, tenant slug, live countdown, and exit button.

- app/master/{layout,page,tenants/page,audit/page}.tsx: dedicated
  master shell. Overview shows system health and tenant counts only.
  Tenants page lists every tenant with an Enter modal that requires a
  reason and an explicit read/write choice. Audit page shows every
  master sign-in and impersonation event, filterable by tenant slug.

Notes / deferred to Phase 2
---------------------------
- Per-write audit rows during write-mode impersonation. Currently only
  start/end are stamped with master identity and impersonation_id;
  individual mutations during the session are audited under
  master_user_id but without the impersonation_id link.

- New AuditAction enum values such as MASTER_LOGIN, IMPERSONATION_START,
  IMPERSONATION_END. For now the discriminator lives in
  audit_logs.new_values.event so no Alembic migration is required.

- Tenant-owner approval flow. The hook is in place at
  tenants.settings.master_access.auto_approve and defaults to true
  since the master tenant is currently internal-only.

No DB migration required. Existing non-master tokens are unaffected.
MSG
fi

# ---------------------------------------------------------------------------
# Commit 3 — Helper scripts
# ---------------------------------------------------------------------------

echo
echo "------------------------------------------------------------"
echo "Commit 3: chore(scripts): add commit + server-update helpers"
echo "------------------------------------------------------------"

if stage_paths "${SCRIPT_FILES[@]}"; then
    write_msg_and_commit "chore(scripts): add commit-master-refactor and server-update helpers" <<'MSG'
- scripts/commit-master-refactor.sh: workstation script that stages,
  commits, and optionally pushes the master refactor in three logical
  commits. Uses git commit -F with tempfiles to avoid bash 3.2
  heredoc-inside-command-substitution quoting issues.

- scripts/server-update.sh: server-side update script. Backs up env
  files, syncs the install dir to origin/main (handles fresh clone,
  initialize-in-place, and update modes), restores env files, refreshes
  Python deps, runs alembic, refreshes Node deps, builds Next.js,
  repairs node_modules/.bin executable bits, restarts dcs-api and
  dcs-ui, and health-checks both. Replaces the upload-zip-and-rsync
  workflow.
MSG
fi

# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------

echo
echo "------------------------------------------------------------"
echo "Resulting log:"
echo "------------------------------------------------------------"
git log --oneline -6

if [[ $PUSH -eq 1 ]]; then
    echo
    echo "------------------------------------------------------------"
    echo "Pushing to origin/$current_branch"
    echo "------------------------------------------------------------"
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "[dry-run] git push origin $current_branch"
    else
        git push origin "$current_branch"
    fi
else
    echo
    echo "Done. Run with --push to push to origin/$current_branch when ready:"
    echo "    bash scripts/commit-master-refactor.sh --push"
fi
