#!/usr/bin/env bash
# run_extra_tests.sh — Run frontend (Vitest), MCP, and render (ffmpeg) tests.
#
# These suites are excluded from the standard CI backend job.  Run them
# locally when you need full coverage.
#
# Usage:
#   ./scripts/run_extra_tests.sh                  # all three suites
#   ./scripts/run_extra_tests.sh --frontend-only
#   ./scripts/run_extra_tests.sh --mcp-only
#   ./scripts/run_extra_tests.sh --render-only
#   ./scripts/run_extra_tests.sh --no-db-teardown  # keep test DB after render tests
#
# Prerequisites:
#   - Node / npm installed (for frontend)
#   - ffmpeg installed (for render tests)
#   - psql reachable on DATABASE_URL host (for render tests that need the DB)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Flags ─────────────────────────────────────────────────────────────────────
RUN_FRONTEND=true
RUN_MCP=true
RUN_RENDER=true
TEARDOWN=true

for arg in "$@"; do
    case "$arg" in
        --frontend-only) RUN_MCP=false;     RUN_RENDER=false ;;
        --mcp-only)      RUN_FRONTEND=false; RUN_RENDER=false ;;
        --render-only)   RUN_FRONTEND=false; RUN_MCP=false ;;
        --no-db-teardown) TEARDOWN=false ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: $0 [--frontend-only|--mcp-only|--render-only] [--no-db-teardown]" >&2
            exit 1
            ;;
    esac
done

# Track per-suite results
FRONTEND_RESULT=0
MCP_RESULT=0
RENDER_RESULT=0

# ── DB setup/teardown — only needed for render tests ─────────────────────────
TEST_DB_NAME="ai_media_test"
DB_READY=false

setup_db() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Setting up test database (render tests)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    "$SCRIPT_DIR/setup_test_db.sh"

    # Derive TEST_DATABASE_URL in this process (setup_test_db.sh runs in a subshell)
    if [[ -z "${DATABASE_URL:-}" ]]; then
        for env_file in "$PROJECT_ROOT/console/.env" "$PROJECT_ROOT/.env"; do
            if [[ -f "$env_file" ]] && grep -q '^DATABASE_URL=' "$env_file"; then
                DATABASE_URL=$(grep '^DATABASE_URL=' "$env_file" | head -1 | cut -d= -f2-)
                export DATABASE_URL
                break
            fi
        done
    fi
    TEST_DATABASE_URL=$(echo "$DATABASE_URL" | sed -E 's|/[^/?]+([?].*)?$|/'"$TEST_DB_NAME"'\1|')
    export TEST_DATABASE_URL
    DB_READY=true
}

teardown_db() {
    [[ "$DB_READY" == "false" ]] && return
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Tearing down test database: $TEST_DB_NAME"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    DB_USER=$(echo "$DATABASE_URL" | sed -E 's|postgresql://([^:@]+).*|\1|')
    DB_PASS=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^@]+@([^:/]+).*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*@[^:]+:([0-9]+)/.*|\1|')
    PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '$TEST_DB_NAME' AND pid <> pg_backend_pid()
    " > /dev/null 2>&1 || true
    PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS $TEST_DB_NAME" || true
    echo "  → dropped."
}

if $RUN_RENDER && $TEARDOWN; then
    trap teardown_db EXIT
fi

# ── 1. Frontend tests (Vitest) ────────────────────────────────────────────────
if $RUN_FRONTEND; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Frontend tests (Vitest)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    FRONTEND_DIR="$PROJECT_ROOT/console/frontend"

    if ! command -v node &>/dev/null; then
        echo "  SKIP: node not found in PATH"
        FRONTEND_RESULT=1
    elif [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        echo "  Installing npm dependencies..."
        npm --prefix "$FRONTEND_DIR" install --silent
        npm --prefix "$FRONTEND_DIR" run test && FRONTEND_RESULT=0 || FRONTEND_RESULT=$?
    else
        npm --prefix "$FRONTEND_DIR" run test && FRONTEND_RESULT=0 || FRONTEND_RESULT=$?
    fi

    if [[ $FRONTEND_RESULT -eq 0 ]]; then
        echo "  ✓ Frontend tests passed"
    else
        echo "  ✗ Frontend tests FAILED (exit $FRONTEND_RESULT)"
    fi
fi

# ── 2. MCP tests (pytest, no real DB) ────────────────────────────────────────
if $RUN_MCP; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  MCP tests (pytest)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    cd "$PROJECT_ROOT"
    pytest console/mcp/tests/ -v && MCP_RESULT=0 || MCP_RESULT=$?

    if [[ $MCP_RESULT -eq 0 ]]; then
        echo "  ✓ MCP tests passed"
    else
        echo "  ✗ MCP tests FAILED (exit $MCP_RESULT)"
    fi
fi

# ── 3. Render tests (pytest -m render, needs ffmpeg + optional DB) ────────────
if $RUN_RENDER; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Render tests (pytest -m render)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if ! command -v ffmpeg &>/dev/null; then
        echo "  SKIP: ffmpeg not found in PATH (required for render tests)"
        RENDER_RESULT=1
    else
        setup_db
        cd "$PROJECT_ROOT"
        TEST_DATABASE_URL="$TEST_DATABASE_URL" \
        DATABASE_URL="$TEST_DATABASE_URL" \
            pytest -m render tests/ console/backend/tests/ -v \
            && RENDER_RESULT=0 || RENDER_RESULT=$?
    fi

    if [[ $RENDER_RESULT -eq 0 ]]; then
        echo "  ✓ Render tests passed"
    else
        echo "  ✗ Render tests FAILED (exit $RENDER_RESULT)"
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$RUN_FRONTEND && { [[ $FRONTEND_RESULT -eq 0 ]] && echo "  Frontend : PASS" || echo "  Frontend : FAIL"; }
$RUN_MCP      && { [[ $MCP_RESULT      -eq 0 ]] && echo "  MCP      : PASS" || echo "  MCP      : FAIL"; }
$RUN_RENDER   && { [[ $RENDER_RESULT   -eq 0 ]] && echo "  Render   : PASS" || echo "  Render   : FAIL"; }
echo ""

OVERALL=$(( FRONTEND_RESULT + MCP_RESULT + RENDER_RESULT ))
if [[ $OVERALL -eq 0 ]]; then
    echo "  All suites passed."
else
    echo "  One or more suites failed."
fi

exit $OVERALL
