#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  AI Media Automation — Unified Startup Script
#  Run from project root: ./start.sh
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/console/backend"
LOGS_DIR="$SCRIPT_DIR/logs"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"
CELERY="$VENV_DIR/bin/celery"
UVICORN="$VENV_DIR/bin/uvicorn"
mkdir -p "$LOGS_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI Media Automation — Starting"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Ensure .venv exists ────────────────────────────────────────
if [ ! -f "$PYTHON" ]; then
  echo "🔄  Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
  echo "✅  Virtual environment created"
fi

# ── 2. Install / sync dependencies ───────────────────────────────
echo "🔄  Installing dependencies..."
# av and psycopg2-binary must come from pre-built wheels — they fail to
# compile from source on Python 3.14 due to removed/changed C-level APIs.
# greenlet resolves correctly via playwright>=1.48.0 (greenlet>=3.1.1).
BINARY_PKGS="av,psycopg2-binary"
"$PIP" install -r "$SCRIPT_DIR/console/requirements.txt" \
  --only-binary="$BINARY_PKGS" -q
echo "✅  Dependencies ready"

# ── 3. Load .env ──────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo ""
  echo "❌  .env not found at project root."
  echo "   Copy the example and fill in your values:"
  echo "     cp .env.example .env"
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$SCRIPT_DIR/.env"
set +a
echo "✅  Environment loaded"

# ── 4. Validate required vars ─────────────────────────────────────
# API keys (Gemini, Pexels, ElevenLabs, Suno) are now in config/api_keys.json
MISSING=""
for var in DATABASE_URL FERNET_KEY; do
  if [ -z "$(printenv "$var" 2>/dev/null)" ]; then
    MISSING="$MISSING $var"
  fi
done
if [ -n "$MISSING" ]; then
  echo "❌  Missing required .env vars:$MISSING"
  exit 1
fi

# Validate Fernet key
if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
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

# ── 5. Check PostgreSQL ───────────────────────────────────────────
if ! command -v pg_isready &>/dev/null; then
  echo "❌  PostgreSQL not found. Install: brew install postgresql@16"
  exit 1
fi
DB_NAME=$(echo "$DATABASE_URL" | sed -E 's|.*/([^/]+)$|\1|')
DB_USER=$(echo "$DATABASE_URL" | sed -E 's|postgresql://([^:]+):.*|\1|')
DB_PASS=$(echo "$DATABASE_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+)[:/].*|\1|')
DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_PORT="${DB_PORT:-5432}"
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
  echo "❌  PostgreSQL not running on $DB_HOST:$DB_PORT. Start: brew services start postgresql@16"
  exit 1
fi
if ! PGPASSWORD="$DB_PASS" psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
  echo "❌  Database \"$DB_NAME\" does not exist."
  echo "   Run once: psql postgres -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASS'; CREATE DATABASE $DB_NAME OWNER $DB_USER;\""
  exit 1
fi
echo "✅  PostgreSQL ready (db: $DB_NAME)"

# ── 6. Run Alembic migrations ─────────────────────────────────────
echo "🔄  Running migrations..."
(cd "$BACKEND_DIR" && "$VENV_DIR/bin/alembic" upgrade head 2>&1 | tail -3)
echo "✅  Migrations up to date"

# ── 7. Start Redis ────────────────────────────────────────────────
if ! redis-cli ping &>/dev/null 2>&1; then
  if ! command -v redis-server &>/dev/null; then
    echo "❌  Redis not found. Install: brew install redis"
    exit 1
  fi
  redis-server --daemonize yes --logfile "$LOGS_DIR/redis.log"
  for i in 1 2 3 4 5; do
    redis-cli ping &>/dev/null && break
    sleep 1
  done
  if ! redis-cli ping &>/dev/null; then
    echo "❌  Redis did not start within 5 s. Check $LOGS_DIR/redis.log"
    exit 1
  fi
fi
echo "✅  Redis ready"

# ── 8. Check ffmpeg ───────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
  echo "❌  ffmpeg not found. Install: brew install ffmpeg"
  exit 1
fi
echo "✅  ffmpeg ready"

# ── 9. Kill stale processes ───────────────────────────────────────
for pidfile in "$LOGS_DIR/celery.pid" "$LOGS_DIR/celery_beat.pid" "$LOGS_DIR/pipeline_celery.pid" "$LOGS_DIR/uvicorn.pid"; do
  if [ -f "$pidfile" ]; then
    OLD_PID=$(cat "$pidfile")
    kill "$OLD_PID" 2>/dev/null && echo "⚠️   Stopped stale process (pid $OLD_PID)"
    rm -f "$pidfile"
  fi
done
lsof -ti :"${CONSOLE_PORT:-8080}" | xargs kill 2>/dev/null || true

# ── 10. Start Celery worker (all queues) ──────────────────────────
echo "🔄  Starting Celery worker..."
# Celery must run from the project root so Python can find the 'console' package.
# Set PYTHONPATH explicitly and cd back to SCRIPT_DIR to be safe.
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR"
"$CELERY" -A console.backend.celery_app worker \
  -Q scrape_q,script_q,render_q,upload_q \
  --concurrency=4 \
  --loglevel=info \
  --detach \
  --logfile="$LOGS_DIR/celery.log" \
  --pidfile="$LOGS_DIR/celery.pid"
echo "✅  Celery worker started (all queues)"

# ── 11. Start Celery beat ─────────────────────────────────────────
"$CELERY" -A console.backend.celery_app beat \
  --loglevel=info \
  --detach \
  --logfile="$LOGS_DIR/celery_beat.log" \
  --pidfile="$LOGS_DIR/celery_beat.pid"
echo "✅  Celery beat started"

# ── 12. Start FastAPI backend ─────────────────────────────────────
echo "🔄  Starting FastAPI backend on :${CONSOLE_PORT:-8080}..."
RELOAD_FLAG=""
[[ "${DEV_MODE:-1}" == "1" ]] && RELOAD_FLAG="--reload --reload-dir console"
"$UVICORN" console.backend.main:app \
  --host 0.0.0.0 \
  --port "${CONSOLE_PORT:-8080}" \
  ${RELOAD_FLAG} \
  >> "$LOGS_DIR/backend.log" 2>&1 &
echo $! > "$LOGS_DIR/uvicorn.pid"
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

