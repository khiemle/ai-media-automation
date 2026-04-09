# Core Pipeline — First-Time Setup & Start Guide

> **Purpose:** Get all core pipeline components running for the first time.
> **Covers:** PostgreSQL · ChromaDB · Ollama · Kokoro TTS · Celery worker · daily pipeline test

---

## Prerequisites

- Python 3.12+
- PostgreSQL 16 running (see Step 1)
- Ollama installed with `qwen2.5:3b` pulled (see `guideline/01_install_ollama.md`)
- `ffmpeg` installed: `brew install ffmpeg`

---

## Step 1 — Start PostgreSQL

```bash
# macOS Homebrew
brew services start postgresql@16

# Or open Postgres.app and click Start
```

Verify:
```bash
psql -U postgres -c "SELECT version();"
```

---

## Step 2 — Configure environment

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

# Copy the template if pipeline.env doesn't exist yet
cp pipeline.env.example pipeline.env
```

Edit `pipeline.env` and fill in:

```bash
# Required for Gemini text generation (free tier works)
GEMINI_API_KEY=your_key_here

# Required for Veo video + Imagen photo generation (separate key)
GEMINI_MEDIA_API_KEY=your_media_key_here

# Required for stock footage fallback
PEXELS_API_KEY=your_key_here

# PostgreSQL — match your console/.env DATABASE_URL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_media

# Leave defaults for local testing
OLLAMA_MODEL=qwen2.5:3b
LLM_MODE=auto
```

Also make sure `console/.env` exists with a valid `DATABASE_URL` (the pipeline shares the same DB).

---

## Step 3 — Install pipeline dependencies

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

pip install -r requirements.pipeline.txt
```

This installs: `chromadb`, `faster-whisper`, `kokoro-onnx`, `sentence-transformers`, `moviepy`, `google-genai`, `playwright`, and all other pipeline deps.

Install Playwright browser (for TikTok scraper):
```bash
playwright install chromium
```

If you want the TikTok scraper to fall back to Selenium, make sure Chrome or Chromium is installed locally as well. On macOS, one straightforward option is:
```bash
brew install --cask google-chrome
```

The browser scraper now supports these `pipeline.env` controls:
```bash
TIKTOK_SCRAPER_ENGINE=auto
TIKTOK_BROWSER_HEADLESS=true
TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY=true
TIKTOK_SELENIUM_FALLBACK=true
```

Set `TIKTOK_BROWSER_HEADLESS=false` when you want the scraper to open a real browser window for local debugging.

---

## Step 4 — Run database migrations

```bash
cd console/backend
alembic upgrade head
cd ../..
```

Expected output: migrations 001, 002, 003 applied (creates all tables including `viral_videos`, `generated_scripts`, `video_assets`, `viral_patterns`).

---

## Step 5 — Initialize ChromaDB

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

python3 database/setup_chromadb.py
```

Expected output:
```
✅  Created collection: viral_scripts
✅  Created collection: viral_hooks
✅  Created collection: viral_patterns

ChromaDB ready at: ./chroma_db
```

> **Note:** If you see "Collection already exists" errors after reinstalling or changing Python versions, delete and recreate:
> ```bash
> rm -rf ./chroma_db
> python3 database/setup_chromadb.py
> ```

---

## Step 6 — Verify LLM setup

```bash
python3 -c "
from rag.llm_router import LLMRouter
r = LLMRouter(mode='local')
print('Ollama up:  ', r.is_ollama_available())
print('Model:      ', r.status()['ollama_model'])
print('Gemini key: ', r.status()['gemini_key_set'])
"
```

Expected:
```
Ollama up:   True
Model:       qwen2.5:3b
Gemini key:  True
```

If `Ollama up: False` → run `ollama serve` in a separate terminal.  
If `Gemini key: False` → check `GEMINI_API_KEY` is set in `pipeline.env`.

---

## Step 7 — Test script generation

```bash
python3 -c "
from rag.script_writer import generate_script
import json

script = generate_script(
    topic='5 thói quen buổi sáng giúp bạn thành công',
    niche='lifestyle',
    template='tiktok_viral',
)
print('Scenes:  ', len(script[\"scenes\"]))
print('Title:   ', script[\"video\"][\"title\"])
print('Duration:', script[\"video\"][\"total_duration\"], 's')
print(json.dumps(script[\"scenes\"][0], ensure_ascii=False, indent=2))
"
```

Expected: 5–9 scenes, Vietnamese narration, valid JSON structure.

---

## Step 8 — Start the pipeline worker

The pipeline worker handles video rendering (TTS → asset resolver → MoviePy → ffmpeg).

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

./pipeline_start.sh
```

This script:
- Checks PostgreSQL, Redis, Ollama, ffmpeg, Kokoro model
- Creates required asset directories (`assets/output`, `assets/video_db`, etc.)
- Starts a Celery worker on the `render_q` queue

Keep this terminal open while the pipeline is running.

> **Redis required for Celery:**
> ```bash
> brew install redis
> brew services start redis
> ```

---

## Step 9 — Run the full daily pipeline (test)

**Dry run (no LLM calls, no rendering, no uploads):**
```bash
python3 batch_runner.py --run-now --dry-run
```

**Full run with specific topics:**
```bash
python3 batch_runner.py --run-now --topics "5 thói quen sống khỏe" "Bí quyết tiết kiệm tiền"
```

**Full auto run (auto-selects topics from viral videos):**
```bash
python3 batch_runner.py --run-now
```

Expected summary output:
```
PIPELINE SUMMARY
  Scrape: N new videos
  Generate: N scripts
  Produce: N videos (failed: 0)
  Schedule: N uploads queued
  Duration: Xs
```

---

## Component Start Reference

| Component | Start command | Required for |
|-----------|--------------|--------------|
| PostgreSQL | `brew services start postgresql@16` | Everything |
| Redis | `brew services start redis` | Celery tasks |
| Ollama | `ollama serve` | Local LLM (script generation) |
| Console API | `./console/start.sh` | Web dashboard |
| Pipeline worker | `./pipeline_start.sh` | Video rendering |
| Frontend | `cd console/frontend && npm run dev` | Web UI |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `connection refused` on port 5432 | PostgreSQL not running — `brew services start postgresql@16` |
| `connection refused` on port 6379 | Redis not running — `brew services start redis` |
| `Ollama up: False` | Ollama not started — `ollama serve` |
| `Gemini key: False` | `GEMINI_API_KEY` missing in `pipeline.env` |
| ChromaDB embedding conflict | `rm -rf ./chroma_db && python3 database/setup_chromadb.py` |
| `alembic: command not found` | Run `pip install alembic` or activate your virtualenv |
| Kokoro model not found | Download `kokoro.onnx` to `./models/` (see `pipeline_start.sh` for instructions) |
| `ffmpeg: command not found` | `brew install ffmpeg` |
| Script generation returns fallback | Normal on first run (empty ChromaDB) — scrape some videos first to populate RAG context |

---

## LLM Mode Reference

Set in `pipeline.env`:

```bash
LLM_MODE=auto   # recommended
```

| Mode | Behavior |
|------|----------|
| `local` | Qwen2.5 only (offline, free) |
| `gemini` | Gemini 2.5 Flash only (requires `GEMINI_API_KEY`) |
| `auto` | Gemini if quota available, Ollama fallback |
| `hybrid` | hook/cta → Gemini, body scenes → local |

---

*Guide version: April 2026 — AI Media Automation Project*
