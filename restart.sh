#!/usr/bin/env bash
# restart.sh — kill hung server/workers and restart cleanly
# Usage: ./restart.sh [--workers] [--all]
#   (no flags)  restart uvicorn only
#   --workers   restart Celery workers only
#   --all       restart both uvicorn and Celery workers

set -e
cd "$(dirname "$0")"

RESTART_API=true
RESTART_WORKERS=false

for arg in "$@"; do
  case $arg in
    --workers) RESTART_API=false; RESTART_WORKERS=true ;;
    --all)     RESTART_API=true;  RESTART_WORKERS=true ;;
  esac
done

# ── helpers ──────────────────────────────────────────────────────────────────

kill_pids() {
  local label=$1; shift
  local pids=("$@")
  if [ ${#pids[@]} -eq 0 ]; then
    echo "  [$label] nothing running"
    return
  fi
  echo "  [$label] killing PIDs: ${pids[*]}"
  kill -9 "${pids[@]}" 2>/dev/null || true
  sleep 1
}

# ── uvicorn ───────────────────────────────────────────────────────────────────

if $RESTART_API; then
  echo "→ Restarting uvicorn..."
  UVICORN_PIDS=($(pgrep -f "uvicorn console.backend.main:app" 2>/dev/null || true))
  kill_pids "uvicorn" "${UVICORN_PIDS[@]}"

  sleep 1
  nohup .venv/bin/uvicorn console.backend.main:app \
    --host 0.0.0.0 --port 8080 \
    --reload --reload-dir console \
    >> logs/uvicorn.log 2>&1 &
  echo "  [uvicorn] started PID $!"

  echo -n "  [uvicorn] waiting for startup"
  for i in $(seq 1 15); do
    sleep 1
    if curl -s --max-time 2 http://localhost:8080/docs > /dev/null 2>&1; then
      echo " ✓"
      break
    fi
    echo -n "."
    if [ $i -eq 15 ]; then
      echo " ✗ — check logs/uvicorn.log"
      exit 1
    fi
  done
fi

# ── celery workers ────────────────────────────────────────────────────────────

if $RESTART_WORKERS; then
  echo "→ Restarting Celery workers..."
  CELERY_PIDS=($(pgrep -f "celery.*celery_app" 2>/dev/null || true))
  kill_pids "celery" "${CELERY_PIDS[@]}"

  sleep 2
  nohup .venv/bin/python3 -m celery \
    -A console.backend.celery_app worker \
    -Q scrape_q,script_q,render_q,upload_q \
    --concurrency=4 --loglevel=info \
    --logfile=logs/celery.log \
    --pidfile=logs/celery.pid \
    >> logs/celery.log 2>&1 &
  echo "  [celery] started PID $!"

  echo -n "  [celery] waiting for startup"
  for i in $(seq 1 10); do
    sleep 1
    RESULT=$(.venv/bin/python3 -c "
from console.backend.celery_app import celery_app
r = celery_app.control.ping(timeout=2)
print('ok' if r else 'no')
" 2>/dev/null)
    if [ "$RESULT" = "ok" ]; then
      echo " ✓"
      break
    fi
    echo -n "."
    if [ $i -eq 10 ]; then
      echo " ✗ — check logs/celery.log"
      exit 1
    fi
  done
fi

echo ""
echo "Done. Services running:"
$RESTART_API     && echo "  API  → http://localhost:8080" || true
$RESTART_WORKERS && echo "  Jobs → celery workers (scrape_q, script_q, render_q, upload_q)" || true
