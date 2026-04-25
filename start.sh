#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  AI Media Automation — Unified Startup Script
#  Run from project root: ./start.sh
# ═══════════════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/console/backend"
FRONTEND_DIR="$SCRIPT_DIR/console/frontend"
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI Media Automation — Starting"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Load .env ──────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo ""
  echo "❌  .env not found at project root."
  echo "   Copy the example and fill in your values:"
  echo "     cp .env.example .env"
  exit 1
fi
export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -v '^$' | xargs)
echo "✅  Environment loaded"

# ── 2. Validate required vars ─────────────────────────────────────
MISSING=""
for var in DATABASE_URL GEMINI_API_KEY FERNET_KEY PEXELS_API_KEY; do
  if [ -z "${!var}" ]; then
    MISSING="$MISSING $var"
  fi
done
if [ -n "$MISSING" ]; then
  echo "❌  Missing required .env vars:$MISSING"
  exit 1
fi

# Validate Fernet key
if ! python3 - <<'PY' >/dev/null 2>&1
from cryptography.fernet import Fernet
import os
Fernet(os.environ["FERNET_KEY"].encode())
PY
then
  echo "❌  FERNET_KEY is invalid. Generate one:"
  echo "    python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
  exit 1
fi
echo "✅  Config validated"

# ── 3. Check PostgreSQL ───────────────────────────────────────────
if ! command -v pg_isready &>/dev/null; then
  echo "❌  PostgreSQL not found. Install: brew install postgresql@16"
  exit 1
fi
if ! pg_isready -q 2>/dev/null; then
  echo "❌  PostgreSQL not running. Start: brew services start postgresql@16"
  exit 1
fi
DB_NAME=$(echo "$DATABASE_URL" | sed -E 's|.*/([^/]+)$|\1|')
DB_USER=$(echo "$DATABASE_URL" | sed -E 's|postgresql://([^:]+):.*|\1|')
DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+)[:/].*|\1|')
DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
if ! psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
  echo "❌  Database \"$DB_NAME\" does not exist."
  echo "   Run once: psql postgres -c \"CREATE USER $DB_USER WITH PASSWORD 'yourpass'; CREATE DATABASE $DB_NAME OWNER $DB_USER;\""
  exit 1
fi
echo "✅  PostgreSQL ready (db: $DB_NAME)"

# ── 4. Run Alembic migrations ─────────────────────────────────────
echo "🔄  Running migrations..."
cd "$BACKEND_DIR" && alembic upgrade head 2>&1 | tail -3 && cd "$SCRIPT_DIR"
echo "✅  Migrations up to date"

# ── 5. Start Redis ────────────────────────────────────────────────
if ! redis-cli ping &>/dev/null 2>&1; then
  if ! command -v redis-server &>/dev/null; then
    echo "❌  Redis not found. Install: brew install redis"
    exit 1
  fi
  redis-server --daemonize yes --logfile "$LOGS_DIR/redis.log"
  sleep 1
fi
echo "✅  Redis ready"

# ── 6. Check ffmpeg ───────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
  echo "❌  ffmpeg not found. Install: brew install ffmpeg"
  exit 1
fi
echo "✅  ffmpeg ready"

# ── 7. Kill stale processes ───────────────────────────────────────
for pidfile in "$LOGS_DIR/celery.pid" "$LOGS_DIR/celery_beat.pid" "$LOGS_DIR/pipeline_celery.pid"; do
  if [ -f "$pidfile" ]; then
    OLD_PID=$(cat "$pidfile")
    kill "$OLD_PID" 2>/dev/null && echo "⚠️   Stopped stale process (pid $OLD_PID)"
    rm -f "$pidfile"
  fi
done
lsof -ti :"${CONSOLE_PORT:-8080}" | xargs kill 2>/dev/null || true

# ── 8. Start Celery worker (all queues) ───────────────────────────
echo "🔄  Starting Celery worker..."
celery -A console.backend.celery_app worker \
  -Q scrape_q,script_q,render_q,upload_q \
  --concurrency=4 \
  --loglevel=info \
  --detach \
  --logfile="$LOGS_DIR/celery.log" \
  --pidfile="$LOGS_DIR/celery.pid"
echo "✅  Celery worker started (all queues)"

# ── 9. Start Celery beat ─────────────────────────────────────────
celery -A console.backend.celery_app beat \
  --loglevel=info \
  --detach \
  --logfile="$LOGS_DIR/celery_beat.log" \
  --pidfile="$LOGS_DIR/celery_beat.pid"
echo "✅  Celery beat started"

# ── 10. Start FastAPI backend ─────────────────────────────────────
echo "🔄  Starting FastAPI backend on :${CONSOLE_PORT:-8080}..."
uvicorn console.backend.main:app \
  --host 0.0.0.0 \
  --port "${CONSOLE_PORT:-8080}" \
  --reload \
  >> "$LOGS_DIR/backend.log" 2>&1 &
echo "✅  Backend started"

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Backend  → http://localhost:${CONSOLE_PORT:-8080}"
echo "  API docs → http://localhost:${CONSOLE_PORT:-8080}/docs"
echo ""
echo "  Start the frontend (separate terminal):"
echo "    cd console/frontend && npm run dev"
echo "    → http://localhost:5173"
echo ""
echo "  Logs → logs/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
