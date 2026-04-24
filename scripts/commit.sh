#!/usr/bin/env bash
#
# commit.sh — default commit/push helper for this repo.
#
# Stages whatever has changed, commits with a message, and (optionally)
# pushes to origin. Works the same on macOS bash 3.2 and modern bash.
#
# Examples
# --------
#   # Stage tracked changes, commit, do not push.
#   scripts/commit.sh -m "fix(api): null-check tenant in /me"
#
#   # Stage tracked changes, commit, push to origin/<current branch>.
#   scripts/commit.sh -m "fix(api): null-check tenant in /me" --push
#
#   # Same, but also include untracked files (new files) in the commit.
#   scripts/commit.sh -m "feat(ui): add masking page" --all --push
#
#   # Use a multi-line body. Title via -m, body read from a file.
#   scripts/commit.sh -m "feat(auth): SSO group sync" -F /tmp/body.txt --push
#
#   # Preview only — show what would happen, do not stage / commit / push.
#   scripts/commit.sh -m "anything" --push --dry-run
#
#   # Just show the staged plan, do not commit.
#   scripts/commit.sh --status
#
# Flags
# -----
#   -m TITLE        Commit title (required for committing).
#   -F BODY_FILE    Path to a file whose contents become the commit body.
#                   The full message will be: "<title>\n\n<body>".
#   --all           Also stage untracked files (`git add -A` semantics).
#                   Default stages tracked changes only (`git add -u`).
#   --push          Push to origin/<current branch> after committing.
#   --dry-run       Print everything that would happen, but do nothing.
#   --status        Show what is currently staged + working-tree status,
#                   then exit. Implies --dry-run, ignores -m / --push.
#   --no-verify     Pass --no-verify to git commit (skip pre-commit hooks).
#   --branch NAME   Require current branch to equal NAME (default: main).
#                   Use --branch '*' to disable the check.
#   -y / --yes      Skip the "proceed?" confirmation prompt.
#   -h / --help     Show this help and exit.
#
# Safety rails
# ------------
#   - Bails out if a rebase or merge is in progress.
#   - Bails out if the current branch is not the expected one (default
#     `main`); override with --branch.
#   - Bails out if -m is missing when committing.
#   - Skips the commit (rather than failing) if there are no staged
#     changes after staging — safe to re-run.
#
set -euo pipefail

cd "$(dirname "$0")/.."

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------

TITLE=""
BODY_FILE=""
STAGE_MODE="tracked"     # tracked | all
PUSH=0
DRY_RUN=0
STATUS_ONLY=0
NO_VERIFY=0
EXPECTED_BRANCH="main"
ASSUME_YES=0

print_help() {
    sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//' | sed '$d'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -m)            TITLE=${2:-};            shift 2 ;;
        -F)            BODY_FILE=${2:-};        shift 2 ;;
        --all)         STAGE_MODE="all";        shift   ;;
        --push)        PUSH=1;                  shift   ;;
        --dry-run)     DRY_RUN=1;               shift   ;;
        --status)      STATUS_ONLY=1; DRY_RUN=1; shift  ;;
        --no-verify)   NO_VERIFY=1;             shift   ;;
        --branch)      EXPECTED_BRANCH=${2:-};  shift 2 ;;
        -y|--yes)      ASSUME_YES=1;            shift   ;;
        -h|--help)     print_help; exit 0 ;;
        *)
            echo "Unknown flag: $1" >&2
            echo "Try: $0 --help" >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$EXPECTED_BRANCH" != "*" && "$current_branch" != "$EXPECTED_BRANCH" ]]; then
    echo "ERROR: expected branch '$EXPECTED_BRANCH', currently on '$current_branch'." >&2
    echo "       Pass --branch '$current_branch' or --branch '*' to override." >&2
    exit 1
fi
if [[ -d .git/rebase-merge || -d .git/rebase-apply || -f .git/MERGE_HEAD ]]; then
    echo "ERROR: a rebase or merge is in progress. Resolve it first." >&2
    exit 1
fi
if [[ -n "$BODY_FILE" && ! -f "$BODY_FILE" ]]; then
    echo "ERROR: body file not found: $BODY_FILE" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

remote_url=$(git remote get-url origin 2>/dev/null || echo '(no remote)')
echo "============================================================"
echo "Repo:        $remote_url"
echo "Branch:      $current_branch"
echo "HEAD:        $(git log -1 --oneline)"
echo "Stage mode:  $STAGE_MODE  ($([[ $STAGE_MODE == all ]] \
        && echo 'tracked + untracked' \
        || echo 'tracked only'))"
echo "Push:        $([[ $PUSH -eq 1 ]] && echo 'YES' || echo 'no')"
echo "Dry run:     $([[ $DRY_RUN -eq 1 ]] && echo 'YES' || echo 'no')"
echo "Verify:      $([[ $NO_VERIFY -eq 1 ]] && echo 'skip hooks' || echo 'run hooks')"
echo "============================================================"
echo
echo "Working tree (before staging):"
git status --short
echo

if [[ $STATUS_ONLY -eq 1 ]]; then
    exit 0
fi

if [[ -z "$TITLE" ]]; then
    echo "ERROR: commit title required. Use -m \"your message\"." >&2
    echo "       Or use --status to inspect without committing." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

echo "------------------------------------------------------------"
case "$STAGE_MODE" in
    tracked) echo "Staging tracked changes (git add -u)" ;;
    all)     echo "Staging tracked + untracked changes (git add -A)" ;;
esac
echo "------------------------------------------------------------"

if [[ $DRY_RUN -eq 1 ]]; then
    if [[ "$STAGE_MODE" == "all" ]]; then
        echo "[dry-run] git add -A"
    else
        echo "[dry-run] git add -u"
    fi
else
    if [[ "$STAGE_MODE" == "all" ]]; then
        git add -A
    else
        git add -u
    fi
fi

if [[ $DRY_RUN -eq 0 ]] && git diff --cached --quiet; then
    echo
    echo "Nothing was staged — working tree had no $STAGE_MODE changes."
    if [[ $PUSH -eq 1 ]]; then
        # Allow push of pre-existing local commits even when there is
        # nothing new to commit.
        unpushed=$(git log --oneline @{u}..HEAD 2>/dev/null || true)
        if [[ -n "$unpushed" ]]; then
            echo
            echo "Local commits not on origin/$current_branch:"
            echo "$unpushed"
            echo
            if [[ $ASSUME_YES -eq 0 ]]; then
                read -r -p "Push these to origin/$current_branch? [y/N] " ans
                if [[ ! "$ans" =~ ^[Yy]$ ]]; then
                    echo "Aborted."
                    exit 0
                fi
            fi
            echo "+ git push origin $current_branch"
            git push origin "$current_branch"
        fi
    fi
    exit 0
fi

echo
echo "Staged for commit:"
if [[ $DRY_RUN -eq 1 ]]; then
    # Show what *would* be staged: union of working-tree changes.
    if [[ "$STAGE_MODE" == "all" ]]; then
        git status --short
    else
        git diff --name-status
    fi
else
    git diff --cached --stat
fi
echo

# ---------------------------------------------------------------------------
# Build commit message
# ---------------------------------------------------------------------------

msg_file=$(mktemp -t dcs-commit-msg.XXXXXX)
trap 'rm -f "$msg_file"' EXIT
{
    printf '%s\n' "$TITLE"
    if [[ -n "$BODY_FILE" ]]; then
        printf '\n'
        cat "$BODY_FILE"
    fi
} > "$msg_file"

echo "Commit message:"
sed 's/^/  | /' "$msg_file"
echo

# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

if [[ $ASSUME_YES -eq 0 && $DRY_RUN -eq 0 ]]; then
    prompt="Proceed with commit"
    [[ $PUSH -eq 1 ]] && prompt="$prompt + push to origin/$current_branch"
    read -r -p "$prompt? [y/N] " ans
    if [[ ! "$ans" =~ ^[Yy]$ ]]; then
        echo "Aborted. Nothing committed."
        # Unstage what we just added so the working tree is back to
        # how the user found it.
        git reset --quiet HEAD -- .
        exit 0
    fi
fi

# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

commit_args=(-F "$msg_file")
[[ $NO_VERIFY -eq 1 ]] && commit_args+=(--no-verify)

if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] git commit ${commit_args[*]}"
else
    git commit "${commit_args[@]}"
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
    echo "Done. Re-run with --push to push to origin/$current_branch."
fi
