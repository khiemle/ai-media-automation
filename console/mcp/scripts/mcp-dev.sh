#!/usr/bin/env bash
# Local-dev launcher for the AI Media Console MCP server.
#
# What this does:
#   - Verifies Postgres, Redis, console FastAPI are reachable
#   - Verifies the mcp_server_tables migration is applied + mcp-system user is seeded
#   - Mints a 90-day JWT for the mcp-system service account
#   - Prints a ready-to-paste Claude Code mcp.json block (stdio transport)
#   - If --http is passed, also starts the HTTP transport with a fresh dev API key
#
# Usage:
#   ./console/mcp/scripts/mcp-dev.sh           # stdio setup only
#   ./console/mcp/scripts/mcp-dev.sh --http    # also start HTTP server
set -euo pipefail

# ─── Resolve project root regardless of where the script is invoked ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$ROOT"

START_HTTP=0
for arg in "$@"; do
    case "$arg" in
        --http) START_HTTP=1 ;;
        -h|--help)
            sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "Unknown arg: $arg" >&2; exit 2 ;;
    esac
done

# ─── Load console/.env so DATABASE_URL / REDIS_URL / JWT_SECRET are available ─
if [[ ! -f console/.env ]]; then
    echo "  x console/.env not found. Copy from console/.env.example first." >&2
    exit 1
fi
set -a
# shellcheck source=/dev/null
source console/.env
set +a

ok()    { printf "  ok  %s\n" "$1"; }
fail()  { printf "  FAIL  %s\n" "$1" >&2; exit 1; }

echo "Pre-flight checks:"

# Postgres
if [[ -z "${DATABASE_URL:-}" ]]; then fail "DATABASE_URL not set in console/.env"; fi
if ! python3 - <<PY 2>/dev/null
import os, psycopg2
psycopg2.connect(os.environ["DATABASE_URL"]).close()
PY
then fail "Postgres unreachable at \$DATABASE_URL — is brew services start postgresql@16 running?"
fi
ok "Postgres reachable"

# Redis
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
if ! python3 - <<PY 2>/dev/null
import os, redis
redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0")).ping()
PY
then fail "Redis unreachable at \$REDIS_URL — start it (e.g. brew services start redis)"
fi
ok "Redis reachable"

# Console FastAPI on :8080
CONSOLE_BASE="${MCP_CONSOLE_API_BASE:-http://localhost:8080}"
if ! curl -fsS -o /dev/null --max-time 3 "$CONSOLE_BASE/api/system/health" 2>/dev/null \
   && ! curl -fsS -o /dev/null --max-time 3 "$CONSOLE_BASE/docs" 2>/dev/null; then
    fail "Console FastAPI not responding at $CONSOLE_BASE — run ./console/start.sh"
fi
ok "Console FastAPI responding at $CONSOLE_BASE"

# mcp_server_tables migration applied + mcp-system user seeded
if ! python3 - <<PY 2>/dev/null
from console.backend.database import SessionLocal, engine
from console.backend.models.console_user import ConsoleUser
from sqlalchemy import inspect
insp = inspect(engine)
for t in ("mcp_api_keys", "mcp_tool_calls"):
    assert t in insp.get_table_names(), f"missing table: {t}"
cols = [c["name"] for c in insp.get_columns("audit_log")]
assert "actor_metadata" in cols, "audit_log.actor_metadata column missing"
db = SessionLocal()
try:
    user = db.query(ConsoleUser).filter(ConsoleUser.username == "mcp-system").one_or_none()
    assert user is not None, "mcp-system user not seeded"
finally:
    db.close()
PY
then fail "MCP migration not applied or mcp-system user missing — run: cd console/backend && alembic upgrade head"
fi
ok "Migration applied + mcp-system user seeded"

# ─── Mint a 90-day token ─────────────────────────────────────────────────────
echo
echo "Minting 90-day JWT for mcp-system..."
TOKEN="$(python3 -m console.mcp.scripts.mint_token)"
echo "  ok  Token minted (90 days)"

# ─── Print Claude Code mcp.json snippet ──────────────────────────────────────
echo
echo "---- Claude Code config ----"
echo "Add to ~/.config/claude-code/mcp.json (or your project-level mcp.json):"
echo
cat <<JSON
{
  "mcpServers": {
    "ai-media-console": {
      "command": "python",
      "args": ["-m", "console.mcp.stdio"],
      "cwd": "$ROOT",
      "env": {
        "MCP_API_TOKEN": "$TOKEN",
        "MCP_CONSOLE_API_BASE": "$CONSOLE_BASE"
      }
    }
  }
}
JSON
echo
echo "Then restart Claude Code; the 'ai-media-console' MCP server will appear."

# ─── HTTP transport (optional) ───────────────────────────────────────────────
if [[ "$START_HTTP" -eq 1 ]]; then
    DEV_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    HTTP_PORT="${MCP_HTTP_PORT:-8765}"

    echo
    echo "---- HTTP transport ----"
    echo "Starting on http://127.0.0.1:$HTTP_PORT"
    echo "Dev API key (use in X-API-Key header): $DEV_KEY"
    echo "Test command:"
    echo "  curl -H \"X-API-Key: $DEV_KEY\" http://127.0.0.1:$HTTP_PORT/mcp/tools | jq"
    echo
    echo "Press Ctrl-C to stop."
    echo

    export MCP_API_TOKEN="$TOKEN"
    export MCP_HTTP_DEV_API_KEY="$DEV_KEY"
    export MCP_HTTP_HOST="${MCP_HTTP_HOST:-127.0.0.1}"
    export MCP_HTTP_PORT="$HTTP_PORT"
    export MCP_CONSOLE_API_BASE="$CONSOLE_BASE"

    exec python3 -m console.mcp.http
fi

echo
echo "Done. For HTTP transport instead, re-run with: $0 --http"
