#!/bin/bash
echo "⚠️  pipeline_start.sh is deprecated. Use ./start.sh from the project root instead."
exit 1
# ═══════════════════════════════════════════════════════════════════════
#  AI Media Automation — Core Pipeline Startup Script
#  Run from project root: ./pipeline_start.sh
# ═══════════════════════════════════════════════════════════════════════
#
# ┌─────────────────────────────────────────────────────────────────────┐
# │                     FIRST-TIME SETUP GUIDE                          │
# └─────────────────────────────────────────────────────────────────────┘
#
# ── Step 1: System Dependencies ────────────────────────────────────────
#
#   macOS (Homebrew):
#     brew install postgresql@16 redis ffmpeg
#     brew services start postgresql@16
#     brew services start redis
#
#   Ubuntu/Debian:
#     sudo apt-get install -y postgresql-16 redis-server ffmpeg
#     sudo systemctl start postgresql redis
#
#   Add postgres CLI to PATH (macOS only):
#     echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
#     source ~/.zshrc
#
# ── Step 2: PostgreSQL Database Setup ──────────────────────────────────
#
#   Run once to create the user and database:
#
#     psql postgres
#
#     -- Inside psql:
#     CREATE USER admin WITH PASSWORD '123456';
#     CREATE DATABASE ai_media OWNER admin;
#     GRANT ALL PRIVILEGES ON DATABASE ai_media TO admin;
#     \q
#
#   Verify connection:
#     psql -U admin -d ai_media -c "SELECT 1;"
#
# ── Step 3: Python Environment ─────────────────────────────────────────
#
#   Create and activate virtualenv:
#     python3.11 -m venv .venv
#     source .venv/bin/activate
#
#   Install all dependencies:
#     pip install -r console/requirements.txt
#     pip install -r requirements.pipeline.txt    # (created below)
#
#   requirements.pipeline.txt contains:
#     chromadb==0.5.3
#     sentence-transformers==3.0.1        # vietnamese-sbert embeddings
#     google-generativeai==0.8.3          # Gemini API + Veo
#     httpx==0.27.0                       # Ollama API calls
#     playwright==1.44.0                  # TikTok browser scraper
#     apify-client==1.7.1                 # Apify cloud scraper
#     kokoro-onnx==0.4.0                  # TTS engine
#     openai-whisper==20240930            # Caption generation
#     moviepy==2.0.0                      # Video composition
#     pillow==10.3.0                      # Overlay rendering
#     opencv-python==4.9.0.80             # Video processing
#     pexels-python==1.0.0                # Pexels stock footage
#     requests==2.31.0                    # HTTP requests
#     onnxruntime==1.18.0                 # ONNX model inference
#     numpy==1.26.4                       # Audio/video array ops
#     scipy==1.13.0                       # Audio resampling
#     soundfile==0.12.1                   # WAV file I/O
#
#   Install Playwright browsers (required for TikTok scraper):
#     playwright install chromium
#     playwright install-deps chromium    # Linux only
#
# ── Step 4: Ollama + Local LLM ─────────────────────────────────────────
#
#   Install Ollama:
#     macOS:  curl -fsSL https://ollama.com/install.sh | sh
#     Linux:  curl -fsSL https://ollama.com/install.sh | sh
#
#   Pull model (set OLLAMA_MODEL in pipeline.env):
#     ollama pull qwen2.5:3b   # local testing (~2 GB, fast)
#     ollama pull qwen2.5:7b   # production   (~4.4 GB, better quality)
#
#   Verify Ollama is running:
#     curl http://localhost:11434/api/tags
#
# ── Step 5: Kokoro TTS Model ───────────────────────────────────────────
#
#   Download the ONNX model file (~82 MB):
#     mkdir -p models/kokoro
#     # Download from: https://github.com/thewh1teagle/kokoro-onnx/releases
#     # File: kokoro.onnx → place in models/kokoro/
#
#   Download voice files:
#     # voices/ directory from kokoro-onnx releases → place in models/kokoro/voices/
#
#   Verify:
#     python3 -c "from kokoro_onnx import Kokoro; k = Kokoro('models/kokoro/kokoro.onnx', 'models/kokoro/voices'); print('Kokoro OK')"
#
# ── Step 6: ChromaDB Setup ─────────────────────────────────────────────
#
#   ChromaDB runs embedded (no separate server needed).
#   Data is stored in: ./chroma_db/
#
#   Initialize collections (run once):
#     python3 database/setup_chromadb.py
#
#   Verify:
#     python3 -c "import chromadb; c = chromadb.PersistentClient('./chroma_db'); print([col.name for col in c.list_collections()])"
#
# ── Step 7: Environment Variables ──────────────────────────────────────
#
#   Copy and fill in the pipeline .env:
#     cp pipeline.env.example pipeline.env
#
#   Required values:
#     DATABASE_URL       — same as console/.env
#     REDIS_URL          — same as console/.env
#     GEMINI_API_KEY     — from https://aistudio.google.com/app/apikey
#     PEXELS_API_KEY     — from https://www.pexels.com/api/ (free)
#     TIKTOK_CLIENT_KEY  — TikTok Research API app credentials
#     TIKTOK_CLIENT_SECRET
#     APIFY_API_TOKEN    — from https://console.apify.com/account/integrations
#     OLLAMA_URL         — http://localhost:11434 (default)
#     LLM_MODE           — local | gemini | auto | hybrid
#
# ── Step 8: Asset Directories ──────────────────────────────────────────
#
#   Create required directories:
#     mkdir -p assets/video_db/{pexels,veo,manual}
#     mkdir -p assets/output
#     mkdir -p logs
#
# ── Step 9: Alembic Migrations ─────────────────────────────────────────
#
#   Run from console/backend (applies all migrations including pipeline tables):
#     cd console/backend
#     alembic upgrade head
#     cd ../..
#
# ── Step 10: Run the pipeline ──────────────────────────────────────────
#
#   Full system (console + pipeline):
#     ./console/start.sh      # terminal 1 — starts console UI + Celery workers
#     ./pipeline_start.sh     # terminal 2 — starts pipeline services + batch runner
#
#   Manual one-off run (skips cron):
#     python3 batch_runner.py --run-now
#
#   Just the scraper:
#     python3 -m scraper.main
#
#   Just script generation (needs topic):
#     python3 -m rag.script_writer --topic "5 thói quen buổi sáng" --niche lifestyle
#
# ═══════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI Media Automation — Core Pipeline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Load pipeline .env ─────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/pipeline.env" ]; then
  while IFS='=' read -r key value; do
    # Skip comments and blank lines
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$key" ]] && continue
    # Strip inline comments and surrounding whitespace/quotes from value
    value="${value%%#*}"          # remove inline comment
    value="${value%"${value##*[! ]}"}"  # rtrim
    value="${value#\"}" ; value="${value%\"}"  # strip double quotes
    value="${value#\'}" ; value="${value%\'}"  # strip single quotes
    export "$key=$value"
  done < "$SCRIPT_DIR/pipeline.env"
  echo "✅  Pipeline environment loaded"
else
  echo ""
  echo "❌  pipeline.env not found."
  echo ""
  echo "   Copy the example and fill in your keys:"
  echo "     cp pipeline.env.example pipeline.env"
  echo ""
  echo "   Required: DATABASE_URL, REDIS_URL, GEMINI_API_KEY,"
  echo "             PEXELS_API_KEY, LLM_MODE"
  exit 1
fi

# ── Check Python virtualenv ────────────────────────────────────────────
if [ -z "$VIRTUAL_ENV" ] && [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
  source "$SCRIPT_DIR/.venv/bin/activate"
  echo "✅  Virtualenv activated (.venv)"
elif [ -z "$VIRTUAL_ENV" ]; then
  echo "⚠️   No virtualenv active. Recommended:"
  echo "      python3.11 -m venv .venv && source .venv/bin/activate"
  echo "    Continuing with system Python..."
fi

# ── Check PostgreSQL ───────────────────────────────────────────────────
echo "🔄  Checking PostgreSQL..."
if ! command -v pg_isready &>/dev/null; then
  echo ""
  echo "❌  PostgreSQL not found. Install with:"
  echo "      brew install postgresql@16"
  echo "      echo 'export PATH=\"/opt/homebrew/opt/postgresql@16/bin:\$PATH\"' >> ~/.zshrc"
  echo "      source ~/.zshrc"
  exit 1
fi

if ! pg_isready -q 2>/dev/null; then
  echo ""
  echo "❌  PostgreSQL not running. Start with:"
  echo "      brew services start postgresql@16"
  echo "    or: sudo systemctl start postgresql"
  exit 1
fi

DB_URL="${DATABASE_URL:-postgresql://admin:123456@localhost:5432/ai_media}"
DB_USER=$(echo "$DB_URL" | sed -E 's|postgresql://([^:]+):.*|\1|')
DB_PASS=$(echo "$DB_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
DB_HOST=$(echo "$DB_URL" | sed -E 's|.*@([^:/]+)[:/].*|\1|')
DB_PORT=$(echo "$DB_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_NAME=$(echo "$DB_URL" | sed -E 's|.*/([^/]+)$|\1|')

if ! PGPASSWORD="$DB_PASS" psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
  echo ""
  echo "❌  Database \"$DB_NAME\" does not exist."
  echo ""
  echo "   Create it once with:"
  echo "     psql postgres"
  echo "     CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
  echo "     CREATE DATABASE $DB_NAME OWNER $DB_USER;"
  echo "     \\q"
  exit 1
fi
echo "✅  PostgreSQL ready (db: $DB_NAME)"

# ── Run Alembic migrations ─────────────────────────────────────────────
echo "🔄  Running database migrations..."
cd "$SCRIPT_DIR/console/backend"
alembic upgrade head 2>&1 | tail -3
cd "$SCRIPT_DIR"
echo "✅  Migrations up to date"

# ── Check Redis ────────────────────────────────────────────────────────
echo "🔄  Checking Redis..."
if ! command -v redis-cli &>/dev/null; then
  echo ""
  echo "❌  Redis not found. Install with:"
  echo "      brew install redis"
  echo "    or: sudo apt-get install redis-server"
  exit 1
fi

if ! redis-cli ping &>/dev/null; then
  echo "   Redis not running — starting it..."
  redis-server --daemonize yes --logfile "$LOGS_DIR/redis.log"
  sleep 1
fi
echo "✅  Redis ready"

# ── Check Ollama (if LLM_MODE requires local) ─────────────────────────
LLM_MODE="${LLM_MODE:-auto}"
if [[ "$LLM_MODE" == "local" || "$LLM_MODE" == "auto" || "$LLM_MODE" == "hybrid" ]]; then
  echo "🔄  Checking Ollama ($LLM_MODE mode)..."
  OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
  if curl -sf "$OLLAMA_URL/api/tags" &>/dev/null; then
    echo "✅  Ollama running at $OLLAMA_URL"
  else
    echo "⚠️   Ollama not running at $OLLAMA_URL"
    echo ""
    echo "   Start Ollama:"
    echo "     ollama serve"
    echo ""
    echo "   Pull Qwen2.5 7B if not downloaded (~4.4 GB):"
    echo "     ollama pull qwen2.5:7b"
    echo ""
    if [[ "$LLM_MODE" == "local" ]]; then
      echo "❌  LLM_MODE=local requires Ollama. Exiting."
      exit 1
    else
      echo "   Continuing in auto/hybrid mode — will use Gemini when Ollama is offline."
    fi
  fi
fi

# ── Check Gemini API keys ──────────────────────────────────────────────
if [[ "$LLM_MODE" == "gemini" || "$LLM_MODE" == "auto" || "$LLM_MODE" == "hybrid" ]]; then
  if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️   GEMINI_API_KEY not set in pipeline.env (text generation)"
    echo "   Get a free key at: https://aistudio.google.com/app/apikey"
    if [[ "$LLM_MODE" == "gemini" ]]; then
      echo "❌  LLM_MODE=gemini requires GEMINI_API_KEY. Exiting."
      exit 1
    fi
  else
    echo "✅  Gemini text API key configured"
  fi
fi

# Media key (Veo + Imagen) is always checked — used regardless of LLM_MODE
if [ -z "$GEMINI_MEDIA_API_KEY" ]; then
  echo "⚠️   GEMINI_MEDIA_API_KEY not set in pipeline.env"
  echo "   Required for Veo video generation and Imagen photo/thumbnail generation."
  echo "   Use a DIFFERENT Google account/project from GEMINI_API_KEY for separate quota."
  echo "   Falling back to Pexels-only asset mode until configured."
else
  echo "✅  Gemini media API key configured (Veo + Imagen)"
fi

# ── Check ChromaDB data directory ─────────────────────────────────────
CHROMA_DIR="${CHROMA_DB_PATH:-$SCRIPT_DIR/chroma_db}"
if [ ! -d "$CHROMA_DIR" ]; then
  echo "🔄  Initializing ChromaDB..."
  python3 "$SCRIPT_DIR/database/setup_chromadb.py"
  echo "✅  ChromaDB collections created"
else
  echo "✅  ChromaDB ready ($CHROMA_DIR)"
fi

# ── Check Kokoro model ─────────────────────────────────────────────────
KOKORO_MODEL="${MODELS_PATH:-$SCRIPT_DIR/models}/kokoro/kokoro.onnx"
if [ ! -f "$KOKORO_MODEL" ]; then
  echo ""
  echo "⚠️   Kokoro TTS model not found at: $KOKORO_MODEL"
  echo ""
  echo "   Download the model (~82 MB):"
  echo "     mkdir -p models/kokoro/voices"
  echo "     # Download kokoro.onnx from:"
  echo "     # https://github.com/thewh1teagle/kokoro-onnx/releases"
  echo "     # → place in models/kokoro/"
  echo "     # Download voices/ folder → place in models/kokoro/voices/"
  echo ""
  echo "   TTS generation will fail until this is resolved."
fi

# ── Check asset directories ────────────────────────────────────────────
mkdir -p "$SCRIPT_DIR/assets/video_db/pexels"
mkdir -p "$SCRIPT_DIR/assets/video_db/veo"
mkdir -p "$SCRIPT_DIR/assets/video_db/manual"
mkdir -p "$SCRIPT_DIR/assets/output"
echo "✅  Asset directories ready"

# ── Check ffmpeg ───────────────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
  echo ""
  echo "❌  ffmpeg not found. Required for video rendering. Install:"
  echo "      brew install ffmpeg"
  echo "    or: sudo apt-get install ffmpeg"
  exit 1
fi

# Check NVENC GPU acceleration
if ffmpeg -encoders 2>/dev/null | grep -q h264_nvenc; then
  echo "✅  ffmpeg + NVENC (GPU rendering enabled)"
else
  echo "✅  ffmpeg ready (CPU rendering — h264_nvenc not available, will use libx264)"
fi

# ── Kill stale pipeline processes ─────────────────────────────────────
PIPELINE_PID="$LOGS_DIR/pipeline_celery.pid"
if [ -f "$PIPELINE_PID" ]; then
  OLD_PID=$(cat "$PIPELINE_PID")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "⚠️   Stopping previous pipeline Celery worker (pid $OLD_PID)..."
    kill "$OLD_PID" && sleep 1
  fi
  rm -f "$PIPELINE_PID"
fi

# ── Start pipeline Celery worker ───────────────────────────────────────
# Note: The console Celery worker (console/start.sh) handles scrape_q, script_q,
#       render_q, upload_q. This worker handles pipeline-specific heavy tasks
#       (actual TTS, video composition, rendering) with higher concurrency limits.
echo "🔄  Starting pipeline Celery worker..."
celery -A console.backend.celery_app worker \
  -Q render_q \
  --concurrency=2 \
  --loglevel=info \
  --detach \
  --logfile="$LOGS_DIR/pipeline_celery.log" \
  --pidfile="$PIPELINE_PID"
echo "✅  Pipeline worker started (render_q, concurrency=2)"

# ── Start Celery beat (cron scheduler) if not already running ─────────
BEAT_PID="$SCRIPT_DIR/console/logs/celery_beat.pid"
if ! ([ -f "$BEAT_PID" ] && kill -0 "$(cat $BEAT_PID)" 2>/dev/null); then
  BEAT_LOG="$LOGS_DIR/celery_beat.log"
  celery -A console.backend.celery_app beat \
    --loglevel=info \
    --detach \
    --logfile="$BEAT_LOG" \
    --pidfile="$BEAT_PID"
  echo "✅  Celery beat started (cron: daily pipeline at 02:00, feedback at 06:00)"
else
  echo "✅  Celery beat already running"
fi

# ── Pipeline ready ─────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Core Pipeline running"
echo ""
echo "  LLM Mode    → $LLM_MODE"
echo "  ChromaDB    → $CHROMA_DIR"
echo "  Assets      → $SCRIPT_DIR/assets/"
echo ""
echo "  Manual runs:"
echo "    python3 batch_runner.py --run-now          # full daily pipeline"
echo "    python3 -m scraper.main                    # scraper only"
echo "    python3 -m rag.script_writer --topic '...' # script generation"
echo ""
echo "  Logs:"
echo "    Pipeline worker  → logs/pipeline_celery.log"
echo "    Celery beat      → logs/celery_beat.log"
echo "    Redis            → logs/redis.log"
echo ""
echo "  Cron schedule (Celery beat):"
echo "    01:00  Scrape TikTok trends"
echo "    02:00  Daily pipeline (generate + produce + upload)"
echo "    06:00  Feedback tracker (fetch metrics)"
echo "    07:00  Reindex top performers → ChromaDB"
echo "    */30m  OAuth token refresh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
