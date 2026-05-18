#!/usr/bin/env bash
# setup_test_db.sh — Create and migrate the isolated test database.
#
# Run from the project root before running pytest locally:
#   ./setup_test_db.sh
#   TEST_DATABASE_URL=... pytest tests/ -v
#
# The script derives the test DB URL from DATABASE_URL by replacing the
# database name with "ai_media_test".  It never touches the production DB.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_DB_NAME="ai_media_test"

# ── 1. Load DATABASE_URL ──────────────────────────────────────────────────────
# Prefer explicit env var; fall back to console/.env, then project root .env.
if [[ -z "${DATABASE_URL:-}" ]]; then
    for env_file in "$PROJECT_ROOT/console/.env" "$PROJECT_ROOT/.env"; do
        if [[ -f "$env_file" ]] && grep -q '^DATABASE_URL=' "$env_file"; then
            DATABASE_URL=$(grep '^DATABASE_URL=' "$env_file" | head -1 | cut -d= -f2-)
            break
        fi
    done
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL not found. Set it in console/.env or export it." >&2
    exit 1
fi

# ── 2. Derive test DB URL ─────────────────────────────────────────────────────
# Strip trailing slash / fragment, then replace the last path segment (db name).
TEST_DATABASE_URL=$(echo "$DATABASE_URL" | sed -E 's|/[^/?]+([?].*)?$|/'"$TEST_DB_NAME"'\1|')
export TEST_DATABASE_URL

echo "Production DB : $DATABASE_URL"
echo "Test DB       : $TEST_DATABASE_URL"
echo ""

# ── 3. Guard: refuse if they somehow point at the same DB ─────────────────────
if [[ "${DATABASE_URL%/}" == "${TEST_DATABASE_URL%/}" ]]; then
    echo "ERROR: TEST_DATABASE_URL resolves to the same URL as DATABASE_URL." >&2
    echo "       Something went wrong with the db-name substitution." >&2
    exit 1
fi

# ── 4. Parse connection components ───────────────────────────────────────────
DB_USER=$(echo "$DATABASE_URL" | sed -E 's|postgresql://([^:@]+).*|\1|')
DB_PASS=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^@]+@([^:/]+).*|\1|')
DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*@[^:]+:([0-9]+)/.*|\1|')

export PGPASSWORD="$DB_PASS"

# ── 5. Create test database if it doesn't exist ───────────────────────────────
echo "Checking for database '$TEST_DB_NAME'..."
DB_EXISTS=$(
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
         -tAc "SELECT 1 FROM pg_database WHERE datname='$TEST_DB_NAME'" 2>/dev/null \
    || true
)
if [[ "$DB_EXISTS" == "1" ]]; then
    echo "  → already exists, skipping CREATE."
else
    echo "  → creating..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
         -c "CREATE DATABASE $TEST_DB_NAME OWNER $DB_USER"
    echo "  → created."
fi

# ── 6. Run Alembic migrations against test DB ─────────────────────────────────
echo ""
echo "Running Alembic migrations..."
pushd "$PROJECT_ROOT/console/backend" > /dev/null
DATABASE_URL="$TEST_DATABASE_URL" alembic upgrade head
popd > /dev/null

# ── 7. Print usage ────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Test database is ready: $TEST_DB_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Run tests:"
echo "  TEST_DATABASE_URL='$TEST_DATABASE_URL' pytest tests/ -v"
echo ""
echo "Or export for your shell session:"
echo "  export TEST_DATABASE_URL='$TEST_DATABASE_URL'"
echo "  pytest tests/ -v"
echo ""
