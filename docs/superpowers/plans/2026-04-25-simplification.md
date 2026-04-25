# Simplification & Stabilisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the two startup scripts into one, merge two `.env` files into one at project root, remove Ollama + ChromaDB, fix black-screen B-roll via `pexels_keywords` in scene JSON, and add ElevenLabs TTS for Vietnamese audio.

**Architecture:** Seven sequential tasks. Env consolidation first (Task 1) — everything else reads from the same place. LLM + ChromaDB simplification next (Tasks 2–3). New startup script after the codebase is stable (Task 4). Asset fix and TTS in Tasks 5–7, wiring TTS router into the composer last.

**Tech Stack:** FastAPI, Celery, SQLAlchemy, google-genai (Gemini 2.5 Flash), ElevenLabs REST API, Kokoro ONNX, MoviePy, Pexels API, soundfile, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `.env.example` | Create | Single merged env template at project root |
| `start.sh` | Create | Unified startup script replacing console/start.sh + pipeline_start.sh |
| `console/start.sh` | Modify | Add deprecation notice |
| `pipeline_start.sh` | Modify | Add deprecation notice |
| `console/backend/config.py` | Modify | Load from project root `.env` only |
| `console/backend/alembic/env.py` | Modify | Load from project root `.env` only |
| `rag/llm_router.py` | Rewrite | GeminiRouter only — Ollama removed |
| `rag/rate_limiter.py` | Modify | Remove Ollama limiter, keep Gemini limiter, update dotenv path |
| `rag/script_writer.py` | Modify | Remove ChromaDB retrieval calls + fallback script |
| `rag/prompt_builder.py` | Modify | Remove RAG params, add pexels_keywords instruction to prompt |
| `rag/script_validator.py` | Modify | Add `pexels_keywords` optional field to scene schema; add `language` to meta |
| `pipeline/asset_resolver.py` | Modify | Use pexels_keywords from scene; niche/type fallback map; update dotenv path |
| `pipeline/pexels_client.py` | Modify | Update dotenv path |
| `pipeline/tts_router.py` | Create | Dispatch to ElevenLabs (VI) or Kokoro (EN) based on language |
| `pipeline/elevenlabs_tts.py` | Create | ElevenLabs REST client → PCM → WAV |
| `pipeline/tts_engine.py` | Modify | Remove `_normalize_text()` Vietnamese logic (moves to elevenlabs_tts.py) |
| `pipeline/composer.py` | Modify | Call `tts_router.generate_tts()` instead of `tts_engine.generate_tts()` |
| `console/backend/tasks/production_tasks.py` | Modify | Call `tts_router.generate_tts()` instead of `tts_engine.generate_tts()` |
| `batch_runner.py` | Modify | Update dotenv path |
| `requirements.pipeline.txt` | Modify | Remove chromadb, sentence-transformers |
| `vector_db/` | Delete | Unused without ChromaDB |
| `database/setup_chromadb.py` | Delete | No longer needed |
| `feedback/reindexer.py` | Delete | No longer needed |
| `tests/test_llm_router.py` | Create | GeminiRouter tests |
| `tests/test_asset_resolver_keywords.py` | Create | Pexels keyword selection tests |
| `tests/test_tts_router.py` | Create | TTS router dispatch tests |

---

## Task 1: Consolidate `.env` files

**Files:**
- Create: `.env.example`
- Modify: `console/backend/config.py`
- Modify: `console/backend/alembic/env.py`
- Modify: `rag/llm_router.py` (dotenv path only — full rewrite in Task 2)
- Modify: `rag/rate_limiter.py` (dotenv path only — Ollama removal in Task 2)
- Modify: `pipeline/asset_resolver.py` (dotenv path only)
- Modify: `pipeline/pexels_client.py` (dotenv path only)
- Modify: `batch_runner.py`

- [ ] **Step 1: Create `.env.example` at project root**

```bash
cat > /path/to/ai-media-automation/.env.example << 'EOF'
# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media
REDIS_URL=redis://localhost:6379/0

# ── Console ───────────────────────────────────────────────────────────────────
JWT_SECRET=change-me-generate-a-random-string
FERNET_KEY=                # python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CONSOLE_PORT=8080
FRONTEND_ORIGIN=http://localhost:5173

# ── LLM — Gemini only ─────────────────────────────────────────────────────────
GEMINI_API_KEY=            # https://aistudio.google.com/app/apikey
GEMINI_MODEL=gemini-2.5-flash
GEMINI_RPD=1500
GEMINI_RPM=15

# ── TTS ───────────────────────────────────────────────────────────────────────
TTS_ENGINE=auto            # auto | kokoro | elevenlabs
ELEVENLABS_API_KEY=        # https://elevenlabs.io/app/settings/api-keys
ELEVENLABS_VOICE_ID_VI=    # Vietnamese voice ID from ElevenLabs dashboard
ELEVENLABS_VOICE_ID_EN=    # English voice ID (optional fallback)
MODELS_PATH=./models       # Path to Kokoro ONNX model directory

# ── Assets ────────────────────────────────────────────────────────────────────
PEXELS_API_KEY=            # https://www.pexels.com/api/
ASSET_RESOLVER_MODE=db_then_pexels
ASSET_DB_PATH=./assets/video_db
OUTPUT_PATH=./assets/output
MUSIC_PATH=./assets/music

# ── TikTok (future) ───────────────────────────────────────────────────────────
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
EOF
```

- [ ] **Step 2: Update `console/backend/config.py`**

Replace the two `load_dotenv` calls and `model_config` env_file to use project root:

```python
# At the top of config.py, replace:
#   load_dotenv(PROJECT_ROOT / "pipeline.env", override=False)
#   load_dotenv(CONSOLE_ROOT / ".env", override=True)
# With:
load_dotenv(PROJECT_ROOT / ".env", override=False)
```

And update the `SettingsConfigDict`:
```python
model_config = SettingsConfigDict(
    env_file=PROJECT_ROOT / ".env",   # was: CONSOLE_ROOT / ".env"
    env_file_encoding="utf-8",
    extra="ignore",
)
```

- [ ] **Step 3: Update `console/backend/alembic/env.py`**

Find the existing `load_dotenv` line and replace it:

```python
# Replace (currently loads from console/.env — three parents up from alembic/env.py):
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# With (project root — four parents up):
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")
```

- [ ] **Step 4: Update `load_dotenv` paths in pipeline files**

In each of the following files, find the two-line `load_dotenv` block and replace with a single call to the project root:

**`rag/llm_router.py`** (the `_root` is already defined as `Path(__file__).parent.parent`):
```python
# Replace:
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)
# With:
load_dotenv(_root / ".env", override=False)
```

**`rag/rate_limiter.py`** (same `_root` pattern):
```python
# Replace:
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)
# With:
load_dotenv(_root / ".env", override=False)
```

**`pipeline/asset_resolver.py`** (`_root = Path(__file__).parent.parent`):
```python
# Replace:
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)
# With:
load_dotenv(_root / ".env", override=False)
```

**`pipeline/pexels_client.py`** (same pattern):
```python
# Replace:
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)
# With:
load_dotenv(_root / ".env", override=False)
```

**`batch_runner.py`**:
```python
# Replace:
load_dotenv(Path(__file__).parent / "pipeline.env", override=False)
load_dotenv(Path(__file__).parent / "console" / ".env", override=False)
# With:
load_dotenv(Path(__file__).parent / ".env", override=False)
```

- [ ] **Step 5: Create your local `.env` from the example**

```bash
cp .env.example .env
# Then edit .env and fill in real values for:
# DATABASE_URL, REDIS_URL, JWT_SECRET, FERNET_KEY,
# GEMINI_API_KEY, PEXELS_API_KEY, ELEVENLABS_API_KEY,
# ELEVENLABS_VOICE_ID_VI
```

- [ ] **Step 6: Verify the backend starts with the new env path**

```bash
cd /path/to/ai-media-automation
uvicorn console.backend.main:app --port 8080 --reload
# Expected: starts without errors, no "pipeline.env not found" warnings
```

- [ ] **Step 7: Commit**

```bash
git add .env.example console/backend/config.py console/backend/alembic/env.py \
    rag/llm_router.py rag/rate_limiter.py pipeline/asset_resolver.py \
    pipeline/pexels_client.py batch_runner.py
git commit -m "chore: consolidate env files — single .env at project root"
```

---

## Task 2: Simplify LLM Router to Gemini-only

**Files:**
- Rewrite: `rag/llm_router.py`
- Modify: `rag/rate_limiter.py` (remove Ollama limiter class and `get_ollama_limiter`)
- Create: `tests/test_llm_router.py`

- [ ] **Step 1: Create `tests/` directory and write failing tests**

```bash
mkdir -p tests
touch tests/__init__.py
```

Create `tests/test_llm_router.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def test_gemini_router_returns_dict_on_success():
    mock_response = MagicMock()
    mock_response.text = '{"meta": {"topic": "test"}, "scenes": []}'

    with patch("rag.llm_router.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        from rag.llm_router import GeminiRouter
        router = GeminiRouter()
        result = router.generate("test prompt", expect_json=True)

    assert isinstance(result, dict)
    assert result["meta"]["topic"] == "test"


def test_gemini_router_raises_on_api_error():
    with patch("rag.llm_router.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API error")

        from rag.llm_router import GeminiRouter
        router = GeminiRouter()

        with pytest.raises(RuntimeError, match="Gemini"):
            router.generate("test prompt")


def test_gemini_router_returns_string_when_not_json():
    mock_response = MagicMock()
    mock_response.text = "plain text response"

    with patch("rag.llm_router.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        from rag.llm_router import GeminiRouter
        router = GeminiRouter()
        result = router.generate("test prompt", expect_json=False)

    assert result == "plain text response"


def test_get_router_returns_singleton():
    from rag.llm_router import get_router
    r1 = get_router()
    r2 = get_router()
    assert r1 is r2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /path/to/ai-media-automation
python -m pytest tests/test_llm_router.py -v
# Expected: ImportError or AttributeError — GeminiRouter doesn't exist yet
```

- [ ] **Step 3: Rewrite `rag/llm_router.py`**

```python
"""
LLM Router — Gemini 2.5 Flash only.
Raises RuntimeError on any failure — no silent fallback.
"""
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env", override=False)

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")


class GeminiRouter:
    """Generates text via Gemini. Raises RuntimeError on any failure."""

    def __init__(self):
        from rag.rate_limiter import get_gemini_limiter
        self._limiter = get_gemini_limiter()

    def generate(self, prompt: str, template: str | None = None, expect_json: bool = True) -> dict | str:
        """
        Call Gemini and return parsed dict (expect_json=True) or raw string.
        Raises RuntimeError if Gemini is unavailable or returns an error.
        """
        if not GEMINI_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")

        client = genai.Client(api_key=GEMINI_KEY)
        logger.info(f"[GeminiRouter] model={GEMINI_MODEL} template={template}")

        for attempt in range(3):
            try:
                self._limiter.wait_if_needed()
                config = genai_types.GenerateContentConfig(temperature=0.8)
                if expect_json:
                    config = genai_types.GenerateContentConfig(
                        temperature=0.8,
                        response_mime_type="application/json",
                    )
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=config,
                )
                raw = response.text
                if expect_json:
                    return self._parse_json(raw)
                return raw
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"[GeminiRouter] Attempt {attempt + 1} failed: {e}, retrying")
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Gemini failed after 3 attempts: {e}") from e
        return {}  # unreachable

    def status(self) -> dict:
        return {
            "model":           GEMINI_MODEL,
            "gemini_key_set":  bool(GEMINI_KEY),
            "gemini_usage":    self._limiter.usage(),
        }

    def _parse_json(self, raw: str) -> dict | str:
        if not raw:
            return {}
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[GeminiRouter] Failed to parse JSON response, returning raw string")
            return raw


# Singleton — reuse across the process lifetime
_router: GeminiRouter | None = None


def get_router() -> GeminiRouter:
    global _router
    if _router is None:
        _router = GeminiRouter()
    return _router


# Backwards compatibility alias
LLMRouter = GeminiRouter
```

- [ ] **Step 4: Remove `get_ollama_limiter` from `rag/rate_limiter.py`**

Find and delete the `OllamaRateLimiter` class and `get_ollama_limiter` function. Keep everything else (the `_Counter` class, `GeminiRateLimiter`, and `get_gemini_limiter`). Also remove `get_ollama_limiter` from any `__all__` list if present.

- [ ] **Step 5: Run tests — expect pass**

```bash
python -m pytest tests/test_llm_router.py -v
# Expected: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add rag/llm_router.py rag/rate_limiter.py tests/test_llm_router.py tests/__init__.py
git commit -m "refactor: simplify LLM router to Gemini-only, remove Ollama"
```

---

## Task 3: Remove ChromaDB + simplify script pipeline

**Files:**
- Modify: `rag/script_writer.py`
- Modify: `rag/prompt_builder.py`
- Modify: `requirements.pipeline.txt`
- Delete: `vector_db/` (entire directory)
- Delete: `database/setup_chromadb.py`
- Delete: `feedback/reindexer.py`

- [ ] **Step 1: Simplify `rag/script_writer.py`**

Replace the body of `generate_script()` — remove the three retrieval calls and `_fallback_script`. The function becomes:

```python
def generate_script(
    topic: str,
    niche: str = "lifestyle",
    template: str = "tiktok_viral",
    language: str = "vietnamese",
    article_content: str | None = None,
    context_videos=None,
    video_ids: list[int] | None = None,
) -> dict:
    """
    Generate a script via Gemini. Raises RuntimeError if Gemini fails.
    """
    from rag.llm_router import get_router
    from rag.prompt_builder import build_prompt
    from rag.script_validator import validate, fix_and_normalize

    extra_hooks: list[str] = []
    if context_videos:
        extra_hooks = [v.hook_text for v in context_videos if getattr(v, "hook_text", None)]

    prompt = build_prompt(
        topic=topic,
        niche=niche,
        template=template,
        language=language,
        article_content=article_content,
        extra_hooks=extra_hooks,
    )

    router = get_router()
    last_error: str = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = router.generate(prompt, template=template, expect_json=True)

            if not isinstance(result, dict):
                last_error = f"LLM returned {type(result).__name__}, expected dict"
                logger.warning(f"[ScriptWriter] Attempt {attempt}: {last_error}")
                continue

            result.setdefault("meta", {})
            result["meta"].setdefault("topic", topic)
            result["meta"].setdefault("niche", niche)
            result["meta"].setdefault("template", template)
            result["meta"].setdefault("language", language)

            valid, errors = validate(result)
            if valid:
                logger.info(f"[ScriptWriter] Valid script on attempt {attempt}")
                return fix_and_normalize(result, topic, niche, template)

            last_error = "; ".join(errors[:3])
            logger.warning(f"[ScriptWriter] Attempt {attempt} validation failed: {errors[:3]}")
            prompt += f"\n\nPREVIOUS ATTEMPT ERRORS (fix these):\n" + "\n".join(f"- {e}" for e in errors[:5])

        except RuntimeError:
            raise  # Gemini hard failure — propagate immediately
        except Exception as e:
            last_error = str(e)
            logger.error(f"[ScriptWriter] Attempt {attempt} exception: {e}")

    raise RuntimeError(f"Script generation failed after {MAX_RETRIES} attempts. Last error: {last_error}")
```

Also delete `_fallback_script()` from the file entirely. Keep `regenerate_scene()` as-is.

- [ ] **Step 2: Simplify `rag/prompt_builder.py`**

Update the `build_prompt()` signature — remove `viral_scripts`, `top_hooks`, `patterns` and add `extra_hooks`:

```python
def build_prompt(
    topic: str,
    niche: str,
    template: str,
    language: str = "vietnamese",
    article_content: str | None = None,
    extra_hooks: list[str] | None = None,
) -> str:
```

Remove any sections of the prompt that inject `viral_scripts`, `top_hooks`, or `patterns` context. Keep `article_content` injection and all template-specific instructions.

Add the `pexels_keywords` instruction to the scene JSON schema in the prompt. Locate `SCRIPT_JSON_SCHEMA` in `prompt_builder.py` and add the field:

```python
SCRIPT_JSON_SCHEMA = """
{
  ...
  "scenes": [
    {
      "scene_number": 1,
      "type": "string (hook|body|transition|cta)",
      "narration": "string (narration text for TTS, in the script language)",
      "visual_hint": "string (English — describe the video clip to find)",
      "pexels_keywords": ["string", "string"],
      "text_overlay": "string (short text shown on screen, optional)",
      "overlay_style": "string (big_white_center|bottom_caption|top_title|highlight_box|minimal)",
      "duration": "number (seconds)",
      "transition": "string (cut|fade|crossfade)"
    }
  ]
}"""
```

Add this instruction in the prompt body after the JSON schema:

```
For each scene, generate "pexels_keywords": a list of 2-3 short English search terms
suitable for Pexels stock footage. These must be in English even when narration is Vietnamese.
Example: ["woman coffee morning", "cozy kitchen"] for a scene about morning routines.
```

- [ ] **Step 3: Delete ChromaDB-related files**

```bash
rm -rf vector_db/
rm database/setup_chromadb.py
rm feedback/reindexer.py
rm -rf chroma_db/
```

- [ ] **Step 4: Update `requirements.pipeline.txt`**

Remove these lines:
```
chromadb==0.5.3
sentence-transformers==3.0.1
```

- [ ] **Step 5: Verify script generation still imports cleanly**

```bash
python3 -c "from rag.script_writer import generate_script; print('OK')"
# Expected: OK  (no ImportError about vector_db or chromadb)
```

- [ ] **Step 6: Commit**

```bash
git add rag/script_writer.py rag/prompt_builder.py requirements.pipeline.txt
git rm -r vector_db/ database/setup_chromadb.py feedback/reindexer.py
git commit -m "refactor: remove ChromaDB + RAG retrieval, simplify script generation"
```

---

## Task 4: Write unified `./start.sh`

**Files:**
- Create: `start.sh`
- Modify: `console/start.sh` (add deprecation notice)
- Modify: `pipeline_start.sh` (add deprecation notice)

- [ ] **Step 1: Create `start.sh` at project root**

```bash
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
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x start.sh
```

- [ ] **Step 3: Add deprecation notice to `console/start.sh`**

Add at the very top of `console/start.sh` after `#!/bin/bash`:

```bash
echo "⚠️  console/start.sh is deprecated. Use ./start.sh from the project root instead."
exit 1
```

- [ ] **Step 4: Add deprecation notice to `pipeline_start.sh`**

Add at the very top of `pipeline_start.sh` after `#!/bin/bash`:

```bash
echo "⚠️  pipeline_start.sh is deprecated. Use ./start.sh from the project root instead."
exit 1
```

- [ ] **Step 5: Test the unified script (dry run — stop before Celery)**

```bash
# Comment out Celery/uvicorn steps temporarily and run:
./start.sh
# Expected: passes env load, PostgreSQL, migrations, Redis, ffmpeg checks
# then prints the startup summary
```

- [ ] **Step 6: Commit**

```bash
git add start.sh console/start.sh pipeline_start.sh
git commit -m "feat: unified start.sh replaces two separate startup scripts"
```

---

## Task 5: Fix Pexels B-roll — `pexels_keywords` + niche fallback

**Files:**
- Modify: `rag/script_validator.py`
- Modify: `pipeline/asset_resolver.py`
- Create: `tests/test_asset_resolver_keywords.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_asset_resolver_keywords.py`:

```python
import pytest
from pipeline.asset_resolver import _get_pexels_keywords


def test_uses_pexels_keywords_when_present():
    scene = {
        "type": "hook",
        "visual_hint": "người phụ nữ uống cà phê",
        "pexels_keywords": ["woman coffee morning", "cozy home"],
    }
    keywords = _get_pexels_keywords(scene, {"niche": "lifestyle"})
    assert keywords == ["woman coffee morning", "cozy home"]


def test_falls_back_to_niche_when_no_pexels_keywords():
    scene = {"type": "body", "visual_hint": "cảnh đẹp thiên nhiên"}
    keywords = _get_pexels_keywords(scene, {"niche": "lifestyle"})
    assert len(keywords) >= 1
    assert any(k in ["lifestyle", "people", "daily life"] for k in keywords)


def test_falls_back_to_niche_when_pexels_keywords_empty():
    scene = {"type": "cta", "pexels_keywords": [], "visual_hint": "vẫy tay"}
    keywords = _get_pexels_keywords(scene, {"niche": "fitness"})
    assert len(keywords) >= 1
    assert any(k in ["fitness", "workout", "exercise"] for k in keywords)


def test_scene_type_contributes_to_fallback():
    scene = {"type": "cta", "visual_hint": ""}
    keywords = _get_pexels_keywords(scene, {"niche": "unknown_niche"})
    assert "smiling" in keywords or "thumbs up" in keywords


def test_returns_at_most_three_keywords():
    scene = {
        "type": "body",
        "pexels_keywords": ["a", "b", "c", "d", "e"],
    }
    keywords = _get_pexels_keywords(scene, {"niche": "lifestyle"})
    assert len(keywords) <= 3
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_asset_resolver_keywords.py -v
# Expected: ImportError — _get_pexels_keywords doesn't exist yet
```

- [ ] **Step 3: Add `_get_pexels_keywords` to `pipeline/asset_resolver.py`**

Add after the existing imports and constants:

```python
NICHE_KEYWORDS = {
    "lifestyle":  ["lifestyle", "people", "daily life"],
    "cooking":    ["cooking", "food", "kitchen"],
    "fitness":    ["fitness", "workout", "exercise"],
    "finance":    ["business", "money", "office"],
    "tech":       ["technology", "computer", "digital"],
    "health":     ["health", "wellness", "doctor"],
    "food":       ["food", "restaurant", "eating"],
    "news":       ["city", "people walking", "urban"],
}

SCENE_TYPE_KEYWORDS = {
    "hook":       ["attention", "people"],
    "cta":        ["thumbs up", "smiling"],
    "transition": ["background", "nature"],
    "body":       ["lifestyle", "people"],
    "proof":      ["success", "results"],
    "outro":      ["waving", "smiling"],
}


def _get_pexels_keywords(scene: dict, meta: dict) -> list[str]:
    """Return up to 3 English Pexels search keywords for a scene."""
    pexels_kw = scene.get("pexels_keywords") or []
    if pexels_kw:
        return list(pexels_kw)[:3]

    niche = meta.get("niche", "lifestyle")
    scene_type = scene.get("type", "body")

    fallback = NICHE_KEYWORDS.get(niche, ["lifestyle", "people"])
    type_kw = SCENE_TYPE_KEYWORDS.get(scene_type, [])

    combined = (type_kw + fallback)[:3]
    return combined if combined else ["lifestyle", "people"]
```

- [ ] **Step 4: Update `_try_pexels()` in `pipeline/asset_resolver.py` to use `_get_pexels_keywords`**

Find `_try_pexels()` and update the call site in `resolve()`:

```python
# In resolve(), replace:
result = _try_pexels(keywords, niche, duration, scene_id)

# With:
pexels_keywords = _get_pexels_keywords(scene, meta)
result = _try_pexels(pexels_keywords, niche, duration, scene_id)
```

- [ ] **Step 5: Add `pexels_keywords` to `rag/script_validator.py`**

In `script_validator.py`, find the scene validation loop and add:

```python
# After checking REQUIRED_SCENE_KEYS, add:
pexels_kw = scene.get("pexels_keywords")
if pexels_kw is not None and not isinstance(pexels_kw, list):
    errors.append(f"scenes[{i}].pexels_keywords must be a list, got {type(pexels_kw).__name__}")
```

- [ ] **Step 6: Run tests — expect pass**

```bash
python -m pytest tests/test_asset_resolver_keywords.py -v
# Expected: 5 passed
```

- [ ] **Step 7: Commit**

```bash
git add pipeline/asset_resolver.py rag/script_validator.py \
    tests/test_asset_resolver_keywords.py
git commit -m "fix: use pexels_keywords from scene JSON for B-roll lookup, add niche fallback"
```

---

## Task 6: ElevenLabs TTS + TTS Router

**Files:**
- Create: `pipeline/elevenlabs_tts.py`
- Create: `pipeline/tts_router.py`
- Modify: `rag/script_validator.py` (add `language` to meta schema)
- Create: `tests/test_tts_router.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tts_router.py`:

```python
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_auto_vietnamese_calls_elevenlabs(tmp_path):
    out = tmp_path / "out.wav"
    with patch.dict(os.environ, {"TTS_ENGINE": "auto", "ELEVENLABS_API_KEY": "test-key",
                                  "ELEVENLABS_VOICE_ID_VI": "vi-voice-id"}):
        with patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
            mock_el.return_value = out
            from pipeline.tts_router import generate_tts
            result = generate_tts("Xin chào", "vi-voice-id", 1.0, "vietnamese", str(out))
        mock_el.assert_called_once()


def test_auto_english_calls_kokoro(tmp_path):
    out = tmp_path / "out.wav"
    with patch.dict(os.environ, {"TTS_ENGINE": "auto"}):
        with patch("pipeline.tts_router._kokoro_generate") as mock_kokoro:
            mock_kokoro.return_value = out
            from pipeline import tts_router
            import importlib; importlib.reload(tts_router)
            result = tts_router.generate_tts("Hello", "af_heart", 1.0, "english", str(out))
        mock_kokoro.assert_called_once()


def test_force_elevenlabs_mode(tmp_path):
    out = tmp_path / "out.wav"
    with patch.dict(os.environ, {"TTS_ENGINE": "elevenlabs", "ELEVENLABS_API_KEY": "key",
                                  "ELEVENLABS_VOICE_ID_VI": "vi-id"}):
        with patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
            mock_el.return_value = out
            from pipeline import tts_router
            import importlib; importlib.reload(tts_router)
            tts_router.generate_tts("Xin chào", "vi-id", 1.0, "vietnamese", str(out))
        mock_el.assert_called_once()


def test_missing_elevenlabs_key_raises():
    with patch.dict(os.environ, {"TTS_ENGINE": "elevenlabs", "ELEVENLABS_API_KEY": ""}):
        from pipeline import tts_router
        import importlib; importlib.reload(tts_router)
        with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
            tts_router.generate_tts("text", "voice", 1.0, "vietnamese", "/tmp/out.wav")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_tts_router.py -v
# Expected: ImportError — pipeline.tts_router doesn't exist yet
```

- [ ] **Step 3: Create `pipeline/elevenlabs_tts.py`**

```python
"""
ElevenLabs TTS client — for Vietnamese (and other non-English) narration.
Requests PCM output directly, writes as WAV via soundfile.
"""
import logging
import os
import re
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY     = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID_VI = os.environ.get("ELEVENLABS_VOICE_ID_VI", "")
ELEVENLABS_VOICE_ID_EN = os.environ.get("ELEVENLABS_VOICE_ID_EN", "")
ELEVENLABS_MODEL       = "eleven_multilingual_v2"
SAMPLE_RATE            = 44100  # pcm_44100 output


def _normalize_text(text: str) -> str:
    """Expand Vietnamese abbreviations for natural TTS pronunciation."""
    replacements = {
        "TP.HCM":  "Thành phố Hồ Chí Minh",
        "TP.HN":   "Thành phố Hà Nội",
        "&":       " và ",
        "%":       " phần trăm",
        "VND":     " đồng",
        "USD":     " đô la Mỹ",
        "k":       " nghìn",
        "tr":      " triệu",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def generate_tts_elevenlabs(
    text:       str,
    voice_id:   str,
    speed:      float,
    output_path: str,
) -> Path:
    """
    Generate WAV audio from text using ElevenLabs.
    Raises RuntimeError on any failure.
    """
    api_key = ELEVENLABS_API_KEY
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set in .env")

    text = _normalize_text(text)
    if not text:
        raise RuntimeError("TTS text is empty after normalization")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "output_format": "pcm_44100",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": min(max(speed, 0.7), 1.3),
        },
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"ElevenLabs API error {e.response.status_code}: {e.response.text}") from e
    except Exception as e:
        raise RuntimeError(f"ElevenLabs request failed: {e}") from e

    # PCM_44100 = signed 16-bit little-endian, mono
    pcm_bytes = response.content
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), samples, SAMPLE_RATE)

    logger.info(f"[ElevenLabs] Generated {output_path} ({len(samples)/SAMPLE_RATE:.1f}s)")
    return output_path
```

- [ ] **Step 4: Create `pipeline/tts_router.py`**

```python
"""
TTS Router — dispatches to ElevenLabs (Vietnamese) or Kokoro (English).
Engine selection via TTS_ENGINE env var: auto | kokoro | elevenlabs
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

TTS_ENGINE             = os.environ.get("TTS_ENGINE", "auto")
ELEVENLABS_VOICE_ID_VI = os.environ.get("ELEVENLABS_VOICE_ID_VI", "")
ELEVENLABS_VOICE_ID_EN = os.environ.get("ELEVENLABS_VOICE_ID_EN", "")
ELEVENLABS_API_KEY     = os.environ.get("ELEVENLABS_API_KEY", "")


def generate_tts(
    text:        str,
    voice_id:    str,
    speed:       float,
    language:    str,
    output_path: str,
) -> Path:
    """
    Generate TTS audio and write to output_path (WAV).
    Engine selection:
      auto      — vietnamese → ElevenLabs, english → Kokoro
      kokoro    — always Kokoro
      elevenlabs — always ElevenLabs
    Raises RuntimeError on failure.
    """
    engine = TTS_ENGINE
    use_elevenlabs = (
        engine == "elevenlabs"
        or (engine == "auto" and language == "vietnamese")
    )

    if use_elevenlabs:
        if not ELEVENLABS_API_KEY:
            raise RuntimeError("ELEVENLABS_API_KEY is not set in .env")
        voice = voice_id or ELEVENLABS_VOICE_ID_VI or ELEVENLABS_VOICE_ID_EN
        if not voice:
            raise RuntimeError("No ElevenLabs voice ID configured. Set ELEVENLABS_VOICE_ID_VI in .env")

        from pipeline.elevenlabs_tts import generate_tts_elevenlabs
        return generate_tts_elevenlabs(text, voice, speed, output_path)

    return _kokoro_generate(text, voice_id, speed, output_path)


def _kokoro_generate(text: str, voice_id: str, speed: float, output_path: str) -> Path:
    from pipeline.tts_engine import generate_tts as kokoro_tts
    return kokoro_tts(text=text, voice=voice_id, speed=speed, output_path=output_path)
```

- [ ] **Step 5: Add `language` validation to `rag/script_validator.py`**

In `fix_and_normalize()`, ensure `language` is set in meta. Find where meta fields are defaulted and add:

```python
meta.setdefault("language", "vietnamese")
```

- [ ] **Step 6: Run tests — expect pass**

```bash
python -m pytest tests/test_tts_router.py -v
# Expected: 4 passed
```

- [ ] **Step 7: Commit**

```bash
git add pipeline/elevenlabs_tts.py pipeline/tts_router.py \
    rag/script_validator.py tests/test_tts_router.py
git commit -m "feat: add ElevenLabs TTS for Vietnamese, TTS router dispatches by language"
```

---

## Task 7: Wire TTS router into composer and production tasks

**Files:**
- Modify: `pipeline/composer.py`
- Modify: `console/backend/tasks/production_tasks.py`
- Modify: `pipeline/tts_engine.py` (remove Vietnamese `_normalize_text` replacements)

- [ ] **Step 1: Update `pipeline/composer.py`**

In `_process_scene()`, find the TTS call and replace the import:

```python
# Replace:
from pipeline.tts_engine import generate_tts
generate_tts(
    text=scene.get("narration", ""),
    voice=meta.get("voice", "af_heart"),
    speed=float(meta.get("voice_speed", 1.1)),
    output_path=str(audio_path),
)

# With:
from pipeline.tts_router import generate_tts
generate_tts(
    text=scene.get("narration", ""),
    voice_id=meta.get("voice", "af_heart"),
    speed=float(meta.get("voice_speed", 1.1)),
    language=meta.get("language", "vietnamese"),
    output_path=str(audio_path),
)
```

- [ ] **Step 2: Update `console/backend/tasks/production_tasks.py`**

In `regenerate_tts_task()`, find the TTS call (lines 35–40) and replace:

```python
# Replace:
from pipeline.tts_engine import generate_tts
audio_path = generate_tts(
    text=scene.get("narration", ""),
    voice=voice_cfg.get("voice", "af_heart"),
    speed=voice_cfg.get("voice_speed", 1.0),
)

# With:
from pipeline.tts_router import generate_tts
meta = script.script_json.get("meta", {})
audio_path = generate_tts(
    text=scene.get("narration", ""),
    voice_id=voice_cfg.get("voice", "af_heart"),
    speed=float(voice_cfg.get("voice_speed", 1.0)),
    language=meta.get("language", "vietnamese"),
    output_path=str(audio_path),
)
```

Note: `audio_path` is defined earlier in the task as `out_dir / f"audio_{scene_index}.wav"`. Make sure it's defined before this call. If not already present, add:

```python
from pathlib import Path
import tempfile
audio_path = Path(tempfile.mktemp(suffix=".wav"))
```

- [ ] **Step 3: Clean up `pipeline/tts_engine.py`**

Remove the Vietnamese abbreviation replacements from `_normalize_text()` — they now live in `elevenlabs_tts.py`. Keep only generic whitespace normalization:

```python
def _normalize_text(text: str) -> str:
    """Normalize text for Kokoro TTS (English)."""
    import re
    return re.sub(r"\s+", " ", text).strip()
```

- [ ] **Step 4: Smoke test end-to-end TTS routing**

```bash
python3 - <<'EOF'
import os
os.environ["TTS_ENGINE"] = "auto"
os.environ["ELEVENLABS_API_KEY"] = os.environ.get("ELEVENLABS_API_KEY", "")
from pipeline.tts_router import generate_tts
# English → should use Kokoro
result = generate_tts("Hello world.", "af_heart", 1.0, "english", "/tmp/test_en.wav")
print(f"English TTS: {result}")
EOF
# Expected: /tmp/test_en.wav (Kokoro output)
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/ -v
# Expected: all tests pass
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/composer.py pipeline/tts_engine.py \
    console/backend/tasks/production_tasks.py
git commit -m "feat: wire TTS router into composer and production tasks"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Section 1 (Unified start script) → Task 4
- [x] Section 2 (Single .env) → Task 1
- [x] Section 3 (Gemini-only + ChromaDB removal) → Tasks 2–3
- [x] Section 4 (Pexels keyword fix) → Task 5
- [x] Section 5 (Multi-language TTS) → Tasks 6–7
- [x] `batch_runner.py` dotenv update → Task 1 Step 4
- [x] `daily_pipeline.py` — note: does not call `load_dotenv` directly; it is always invoked by `batch_runner.py` which already loads the env. No change needed.
- [x] `pexels_client.py` dotenv update → Task 1 Step 4
- [x] `production_tasks.py` TTS call → Task 7 Step 2
- [x] `pexels_keywords` optional field in validator → Task 5 Step 5
- [x] `language` field in meta schema → Task 6 Step 5
- [x] Duplicate render_q Celery worker removed → Task 4 (new start.sh starts only one worker)

**All tasks have real code — no placeholders.**

**Type consistency:**
- `generate_tts()` in `tts_router.py` uses `voice_id`, `speed`, `language`, `output_path` — same signature used in Task 7 Steps 1 and 2. ✓
- `_get_pexels_keywords(scene, meta)` defined in Task 5 Step 3, called in Task 5 Step 4. ✓
- `generate_tts_elevenlabs(text, voice_id, speed, output_path)` defined in Task 6 Step 3, called via `tts_router.py` in Task 6 Step 4. ✓
- `get_router()` returns `GeminiRouter` in Task 2 — used in `script_writer.py` (Task 3) which calls `router.generate(prompt, template=..., expect_json=True)`. ✓
