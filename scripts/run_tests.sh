#!/usr/bin/env bash
# run_tests.sh — Set up isolated test DB, run pytest, tear down test DB.
#
# Usage:
#   ./scripts/run_tests.sh                        # full suite (mirrors CI)
#   ./scripts/run_tests.sh tests/test_foo.py -v   # specific file
#   ./scripts/run_tests.sh -k "test_update"        # filter by name
#   ./scripts/run_tests.sh --no-db-teardown        # keep DB for inspection
#
# The test DB is always recreated/migrated before each run and dropped after
# (unless --no-db-teardown is given).  The production DB is never touched.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_DB_NAME="ai_media_test"
TEARDOWN=true
PYTEST_ARGS=()

# ── Parse flags ───────────────────────────────────────────────────────────────
for arg in "$@"; do
    if [[ "$arg" == "--no-db-teardown" ]]; then
        TEARDOWN=false
    else
        PYTEST_ARGS+=("$arg")
    fi
done

# ── Load DATABASE_URL (same logic as setup_test_db.sh) ───────────────────────
if [[ -z "${DATABASE_URL:-}" ]]; then
    for env_file in "$PROJECT_ROOT/console/.env" "$PROJECT_ROOT/.env"; do
        if [[ -f "$env_file" ]] && grep -q '^DATABASE_URL=' "$env_file"; then
            DATABASE_URL=$(grep '^DATABASE_URL=' "$env_file" | head -1 | cut -d= -f2-)
            export DATABASE_URL
            break
        fi
    done
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL not found. Set it in console/.env or export it." >&2
    exit 1
fi

# Derive test DB URL: replace db name with ai_media_test
TEST_DATABASE_URL=$(echo "$DATABASE_URL" | sed -E 's|/[^/?]+([?].*)?$|/'"$TEST_DB_NAME"'\1|')
export TEST_DATABASE_URL

# Parse connection components for psql teardown
DB_USER=$(echo "$DATABASE_URL" | sed -E 's|postgresql://([^:@]+).*|\1|')
DB_PASS=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^@]+@([^:/]+).*|\1|')
DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*@[^:]+:([0-9]+)/.*|\1|')
export PGPASSWORD="$DB_PASS"

# ── Tear-down function (registered as EXIT trap when enabled) ─────────────────
teardown_db() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Tearing down test database: $TEST_DB_NAME"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    # Terminate any open connections first so DROP DATABASE doesn't block.
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '$TEST_DB_NAME' AND pid <> pg_backend_pid()
    " > /dev/null 2>&1 || true
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
         -c "DROP DATABASE IF EXISTS $TEST_DB_NAME" || true
    echo "  → dropped."
}

if $TEARDOWN; then
    trap teardown_db EXIT
fi

# ── 1. Set up test database ───────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setting up test database"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# Pass DATABASE_URL through so setup_test_db.sh doesn't re-read .env files.
DATABASE_URL="$DATABASE_URL" "$SCRIPT_DIR/setup_test_db.sh"

# ── 2. Run pytest ─────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Running tests"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Default: mirror the CI test command.  Pass-through if the caller supplied args.
if [[ ${#PYTEST_ARGS[@]} -eq 0 ]]; then
    PYTEST_ARGS=(
        -m "not render and not slow and not manual"
        tests/ console/backend/tests/
        -v
    )
fi

cd "$PROJECT_ROOT"
TEST_DATABASE_URL="$TEST_DATABASE_URL" \
DATABASE_URL="$TEST_DATABASE_URL" \
    pytest "${PYTEST_ARGS[@]}"
