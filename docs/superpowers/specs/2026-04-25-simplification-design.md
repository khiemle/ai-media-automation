# Simplification & Stabilisation Design

**Date:** 2026-04-25
**Status:** Approved — ready for implementation

---

## Problem Statement

The system is hard to run and maintain:
- Two startup scripts (`console/start.sh` + `pipeline_start.sh`) must run in separate terminals
- Two `.env` files (`console/.env` + `pipeline.env`) with overlapping keys — changes in one don't reflect in the other
- Ollama/local LLM dependency adds setup friction; Gemini alone is sufficient
- ChromaDB + sentence-transformers adds ~500 MB of dependencies and a one-time init step, but collections are empty in practice (TikTok sources are `planned`, feedback loop never ran)
- Video scenes render as black screens because Pexels keyword extraction fails on Vietnamese `visual_hint` text
- Kokoro TTS is English-only; Vietnamese narration produces broken audio

---

## Scope

Option B: targeted fixes + env consolidation. Five sections.

---

## Section 1 — Unified Startup Script

Replace `console/start.sh` and `pipeline_start.sh` with a single `./start.sh` at the project root.

**Startup sequence:**
1. Load single `.env` from project root
2. Validate required vars: `DATABASE_URL`, `GEMINI_API_KEY`, `FERNET_KEY`, `PEXELS_API_KEY`
3. Check PostgreSQL running → verify DB exists
4. Run Alembic migrations (`cd console/backend && alembic upgrade head`)
5. Start Redis if not running
6. Check ffmpeg present
7. Initialize ChromaDB — **removed** (see Section 3)
8. Kill stale Celery/uvicorn processes
9. Start **one** Celery worker on all queues (`scrape_q,script_q,render_q,upload_q`) + Celery beat
10. Start FastAPI backend (uvicorn, background)
11. Print instructions for frontend: `cd console/frontend && npm run dev`

**Removed:** The duplicate `render_q` Celery worker that `pipeline_start.sh` was launching alongside the console worker — this caused duplicate task processing on the render queue.

**Old scripts:** Kept as files but marked deprecated with a note pointing to `./start.sh`.

---

## Section 2 — Single `.env` File

Merge `console/.env` and `pipeline.env` into a single `.env` at project root.

**Canonical key set:**
```
# Database
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media
REDIS_URL=redis://localhost:6379/0

# Console
JWT_SECRET=...
FERNET_KEY=...
CONSOLE_PORT=8080

# LLM — Gemini only
LLM_MODE=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash

# Assets
PEXELS_API_KEY=...
ASSET_RESOLVER_MODE=db_then_pexels
OUTPUT_PATH=./assets/output
MUSIC_PATH=./assets/music
MODELS_PATH=./models

# TTS
TTS_ENGINE=auto
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID_VI=...
ELEVENLABS_VOICE_ID_EN=...

# TikTok (future)
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
```

**Files requiring `load_dotenv` path update** (all point to project root `.env`):
- `rag/llm_router.py`
- `pipeline/asset_resolver.py`
- `console/backend/config.py`
- `console/backend/alembic/env.py`
- `batch_runner.py`
- `daily_pipeline.py`

`console/.env` and `pipeline.env` are deleted. `console/.env.example` and `pipeline.env.example` are replaced by a single `.env.example` at project root.

---

## Section 3 — Gemini-Only + ChromaDB Removal

### LLM Router

`rag/llm_router.py` is simplified to a `GeminiRouter`:
- Remove `_call_ollama()`, `_ollama_limiter`, `is_ollama_available()`, hybrid/local/auto mode logic
- `LLM_MODE` env var removed
- `generate()` calls Gemini directly; on any failure raises `RuntimeError` — no fallback, no silent degradation

### Script Writer

`rag/script_writer.py`:
- Drop the three ChromaDB retrieval calls (`retrieve_similar_scripts`, `retrieve_top_hooks`, `retrieve_patterns`)
- Drop `_fallback_script()` — if Gemini fails, the Celery task fails and is logged
- `generate_script()` flow: build prompt → call Gemini → validate JSON → return

### Prompt Builder

`rag/prompt_builder.py`:
- Remove `viral_scripts`, `top_hooks`, `patterns` parameters
- Prompt inputs: topic + niche + template + language + article content (news rewrite mode)

### Deleted Entirely

| Path | Reason |
|------|--------|
| `vector_db/` | ChromaDB indexer + retriever — unused without ChromaDB |
| `database/setup_chromadb.py` | One-time init — no longer needed |
| `feedback/reindexer.py` | Re-indexed into ChromaDB — no longer needed |
| `chroma_db/` | Data directory |

**Dependencies removed from `requirements.pipeline.txt`:**
- `chromadb`
- `sentence-transformers`

**`feedback/tracker.py` and `feedback/scorer.py` are kept** — metric fetching and quality scoring are useful for analytics independent of ChromaDB.

---

## Section 4 — Pexels Keyword Fix

### Root Cause

`_extract_keywords()` in `pipeline/asset_resolver.py` uses `\b[a-zA-Z]{3,}\b` (ASCII only). Vietnamese `visual_hint` text produces an empty list → Pexels gets a blank query → returns nothing → scene falls through to black `ColorClip`.

Additionally, the prompt schema already instructs Gemini to write `visual_hint` in English, but Gemini sometimes generates it in Vietnamese.

### Fix — Part 1: `pexels_keywords` field in scene JSON

Scene schema gets a new optional field `pexels_keywords: list[str]` — 2–4 short English Pexels search terms generated by Gemini alongside the Vietnamese narration.

Example scene:
```json
{
  "narration": "Buổi sáng bắt đầu với một tách cà phê...",
  "visual_hint": "woman drinking coffee at home in the morning",
  "pexels_keywords": ["woman coffee morning", "cozy home"],
  "duration": 5
}
```

Asset resolver reads `pexels_keywords` directly. No extraction needed.

**Files changed:**
- `rag/prompt_builder.py` — add instruction to generate `pexels_keywords` per scene
- `rag/script_validator.py` — add `pexels_keywords` as optional `list[str]` field in scene schema
- `pipeline/asset_resolver.py` — read `pexels_keywords` first in `_try_pexels()`

### Fix — Part 2: Niche/type fallback

When `pexels_keywords` is absent or empty (old scripts, validator edge cases), fall back to a niche/scene-type keyword map:

```python
NICHE_KEYWORDS = {
    "lifestyle":  ["lifestyle", "people", "daily life"],
    "cooking":    ["cooking", "food", "kitchen"],
    "fitness":    ["fitness", "workout", "exercise"],
    "finance":    ["business", "money", "office"],
    "tech":       ["technology", "computer", "digital"],
    "news":       ["city", "people walking", "urban"],
}
SCENE_TYPE_KEYWORDS = {
    "hook":       ["attention", "people"],
    "cta":        ["thumbs up", "smiling"],
    "transition": ["background", "nature"],
}
```

Pexels receives at most 3 keywords (most specific first).

---

## Section 5 — Multi-Language TTS

### Problem

Kokoro ONNX supports only `en-us` and `cmn` (Mandarin). Vietnamese narration runs through Kokoro but produces broken output. The system needs a Vietnamese-capable TTS engine.

### TTS Router (`pipeline/tts_router.py`)

Single public function replacing all direct `generate_tts()` calls:

```python
def generate_tts(text: str, voice_id: str, speed: float, language: str, output_path: str) -> Path
```

Engine selection via `TTS_ENGINE` env var:
- `auto` — `vietnamese` → ElevenLabs, `english` → Kokoro
- `kokoro` — force Kokoro
- `elevenlabs` — force ElevenLabs

### ElevenLabs TTS (`pipeline/elevenlabs_tts.py`)

- POST `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` with `output_format=pcm_44100` → raw PCM bytes written directly to WAV using `soundfile` (same approach as Kokoro, no format conversion needed)
- Voice selected by language: `ELEVENLABS_VOICE_ID_VI` or `ELEVENLABS_VOICE_ID_EN`
- Vietnamese abbreviation normalisation (`_normalize_text()`) moves here from `tts_engine.py`
- On failure: raises `RuntimeError` — no silent fallback

### Script JSON Schema Change

`meta` gains a `language` field:
```json
"meta": { "language": "vietnamese" }
```

Populated from the scraper source's `language` field in `scraper_sources.yaml`. TTS router reads `meta.language` to pick the engine.

### `pipeline/composer.py`

Replace direct `from pipeline.tts_engine import generate_tts` call with `from pipeline.tts_router import generate_tts`.

### `pipeline/tts_engine.py`

Kept as-is (Kokoro, English). `_normalize_text()` Vietnamese logic migrates to `elevenlabs_tts.py`.

---

## Files Changed Summary

| File | Change |
|------|--------|
| `start.sh` | New — unified startup script |
| `console/start.sh` | Deprecated |
| `pipeline_start.sh` | Deprecated |
| `.env` | New — merged from `console/.env` + `pipeline.env` |
| `.env.example` | New — replaces two example files |
| `console/.env` | Deleted |
| `pipeline.env` | Deleted |
| `rag/llm_router.py` | Simplified to GeminiRouter, Ollama removed |
| `rag/script_writer.py` | ChromaDB retrieval removed, fallback removed |
| `rag/prompt_builder.py` | RAG params removed, pexels_keywords instruction added |
| `rag/script_validator.py` | pexels_keywords added to scene schema |
| `pipeline/asset_resolver.py` | Read pexels_keywords, niche fallback map |
| `pipeline/tts_router.py` | New — dispatches Kokoro or ElevenLabs by language |
| `pipeline/elevenlabs_tts.py` | New — ElevenLabs REST client |
| `pipeline/composer.py` | Use tts_router instead of tts_engine directly |
| `console/backend/config.py` | Update dotenv path |
| `console/backend/alembic/env.py` | Update dotenv path |
| `batch_runner.py` | Update dotenv path |
| `daily_pipeline.py` | Update dotenv path |
| `vector_db/` | Deleted |
| `database/setup_chromadb.py` | Deleted |
| `feedback/reindexer.py` | Deleted |
| `requirements.pipeline.txt` | Remove chromadb, sentence-transformers |
