#!/bin/bash
echo "⚠️  console/start.sh is deprecated. Use ./start.sh from the project root instead."
exit 1
# ─────────────────────────────────────────────
#  AI Media Management Console — Startup Script
# ─────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "🚀  Starting AI Media Management Console..."

# 1. Load .env
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
  echo "✅  Environment loaded"
else
  echo "⚠️   No .env found — copy .env.example to .env and fill in values"
  exit 1
fi

# Validate Fernet key early so OAuth/token refresh paths don't fail later at runtime.
if [ -z "$FERNET_KEY" ]; then
  echo ""
  echo "❌  FERNET_KEY is not set in console/.env"
  echo ""
  echo "   Generate one with:"
  echo "     python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
  echo ""
  echo "   Then set FERNET_KEY in console/.env and re-run: ./console/start.sh"
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
from cryptography.fernet import Fernet
import os
Fernet(os.environ["FERNET_KEY"].encode())
PY
then
  echo ""
  echo "❌  FERNET_KEY in console/.env is invalid"
  echo ""
  echo "   It must be a Fernet-generated url-safe base64 key. Generate one with:"
  echo "     python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
  echo ""
  echo "   Then update console/.env and re-run: ./console/start.sh"
  exit 1
fi

# 2. Check PostgreSQL is installed and running
echo "🔄  Checking PostgreSQL..."

# Parse DATABASE_URL → postgresql://user:pass@host:port/dbname
DB_URL="${DATABASE_URL}"
DB_USER=$(echo "$DB_URL" | sed -E 's|postgresql://([^:]+):.*|\1|')
DB_PASS=$(echo "$DB_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
DB_HOST=$(echo "$DB_URL" | sed -E 's|.*@([^:/]+)[:/].*|\1|')
DB_PORT=$(echo "$DB_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_NAME=$(echo "$DB_URL" | sed -E 's|.*/([^/]+)$|\1|')

# Check if postgresql@16 is installed
if ! command -v pg_isready &>/dev/null; then
  echo ""
  echo "❌  PostgreSQL is not installed."
  echo ""
  echo "   Install it with Homebrew:"
  echo "     brew install postgresql@16"
  echo "     echo 'export PATH=\"/opt/homebrew/opt/postgresql@16/bin:\$PATH\"' >> ~/.zshrc"
  echo "     source ~/.zshrc"
  echo ""
  echo "   Then re-run: ./console/start.sh"
  exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready -q 2>/dev/null; then
  echo ""
  echo "❌  PostgreSQL is not running on localhost:5432"
  echo ""
  echo "   Start it with:"
  echo "     brew services start postgresql@16"
  echo ""
  echo "   Then re-run: ./console/start.sh"
  exit 1
fi

# Check if the database exists; if not, print setup instructions
if ! psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
  echo ""
  echo "❌  Database \"$DB_NAME\" does not exist."
  echo ""
  echo "   Run these commands once to set up PostgreSQL:"
  echo ""
  echo "     psql postgres"
  echo ""
  echo "     -- Inside psql:"
  echo "     CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
  echo "     CREATE DATABASE $DB_NAME OWNER $DB_USER;"
  echo "     \\q"
  echo ""
  echo "   Then re-run: ./console/start.sh"
  exit 1
fi

echo "✅  PostgreSQL ready"

# 3. Run Alembic migrations
echo "🔄  Running database migrations..."
cd "$BACKEND_DIR"
alembic upgrade head
echo "✅  Migrations complete"

# Return to project root (alembic cd'd into backend/)
cd "$SCRIPT_DIR/.."

# 3. Start Redis (if not running)
if ! redis-cli ping &>/dev/null; then
  echo "🔄  Starting Redis..."
  redis-server --daemonize yes
  sleep 1
fi
echo "✅  Redis ready"

# 4. Kill any already-running services
CELERY_PID="$SCRIPT_DIR/logs/celery.pid"
CELERY_BEAT_PID="$SCRIPT_DIR/logs/celery_beat.pid"

if [ -f "$CELERY_PID" ]; then
  OLD_PID=$(cat "$CELERY_PID")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "⚠️   Celery worker already running (pid $OLD_PID) — stopping it..."
    kill "$OLD_PID" && sleep 1
  fi
  rm -f "$CELERY_PID"
fi

if [ -f "$CELERY_BEAT_PID" ]; then
  OLD_PID=$(cat "$CELERY_BEAT_PID")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "⚠️   Celery beat already running (pid $OLD_PID) — stopping it..."
    kill "$OLD_PID" && sleep 1
  fi
  rm -f "$CELERY_BEAT_PID"
fi

# Kill any stale uvicorn / vite processes on our ports
lsof -ti :${CONSOLE_PORT:-8080} | xargs kill 2>/dev/null && echo "⚠️   Stopped previous backend on :${CONSOLE_PORT:-8080}" || true
lsof -ti :5173 | xargs kill 2>/dev/null && echo "⚠️   Stopped previous frontend on :5173" || true

# 5. Start Celery workers
echo "🔄  Starting Celery workers..."
celery -A console.backend.celery_app worker \
  -Q scrape_q,script_q,render_q,upload_q \
  --concurrency=4 \
  --loglevel=info \
  --detach \
  --logfile="$SCRIPT_DIR/logs/celery.log" \
  --pidfile="$CELERY_PID"
echo "✅  Celery workers started"

# 6. Start Celery Beat (scheduled tasks — token refresh, etc.)
celery -A console.backend.celery_app beat \
  --loglevel=info \
  --detach \
  --logfile="$SCRIPT_DIR/logs/celery_beat.log" \
  --pidfile="$CELERY_BEAT_PID"
echo "✅  Celery beat started"

# 8. Start FastAPI
echo "🔄  Starting FastAPI backend on :${CONSOLE_PORT:-8080}..."
cd "$SCRIPT_DIR/.."
uvicorn console.backend.main:app \
  --host 0.0.0.0 \
  --port "${CONSOLE_PORT:-8080}" \
  --reload \
  >> "$SCRIPT_DIR/logs/backend.log" 2>&1 &
echo "✅  Backend started at http://localhost:${CONSOLE_PORT:-8080}"

# 9. Start Vite frontend dev server
echo "🔄  Starting frontend dev server on :5173..."
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "   Installing frontend dependencies..."
  cd "$FRONTEND_DIR" && npm install
fi
cd "$FRONTEND_DIR"
npm run dev >> "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
echo "✅  Frontend started at http://localhost:5173"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Console running:"
echo "  API  → http://localhost:${CONSOLE_PORT:-8080}/api"
echo "  Docs → http://localhost:${CONSOLE_PORT:-8080}/docs"
echo "  UI   → http://localhost:5173"
echo ""
echo "  Logs:"
echo "  Backend  → console/logs/backend.log"
echo "  Frontend → console/logs/frontend.log"
echo "  Celery   → console/logs/celery.log"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
