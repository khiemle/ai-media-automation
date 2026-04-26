# AI Media Automation — Claude Code Context

> This file is read automatically by Claude Code on every session.
> It gives full project context so development can continue without re-explanation.

---

## What This Project Is

A fully automated AI media pipeline with a **web-based Management Console** as the human control layer. Editors can curate content, review scripts, edit scenes, manage upload channels, and monitor the pipeline in real time.

**Status (April 2026):**
- **Management Console** (all 8 tabs) — implemented; active integration/debugging still in progress
- **Core Pipeline** — mostly implemented end to end, with scraper currently using browser-based fallback strategy for TikTok
- **TikTok scraping** — official Research API is not production-ready yet in this repo; active path is `tiktok_playwright` with broader page-state extraction, optional headful retry, and Selenium + Chromium fallback

**Stack:** FastAPI (Python 3.11+) backend · React 18 + Vite + Tailwind CSS frontend · PostgreSQL · Celery + Redis · Ollama/Qwen2.5 (local LLM) · Gemini 2.5 Flash (cloud LLM) · Kokoro ONNX (TTS) · ChromaDB (vector search) · MoviePy + ffmpeg (video) · Playwright + Selenium/Chromium (TikTok scraping fallback)

**Team:** 1 engineer + 1 business user

---

## How to Run

```bash
# Always run from the PROJECT ROOT (ai-media-automation/), NOT from console/
cd /path/to/ai-media-automation

# Prerequisites: PostgreSQL must be running
brew services start postgresql@16   # macOS Homebrew
# or open Postgres.app

# Start everything (migrations + Redis + Celery + FastAPI)
./console/start.sh

# Frontend dev server (separate terminal)
cd console/frontend
npm install   # first time only
npm run dev   # → http://localhost:5173

# API docs
open http://localhost:8080/docs
```

**Manual migration only:**
```bash
cd console/backend
alembic upgrade head
```

### Core Pipeline

```bash
# Install pipeline dependencies
pip install -r requirements.pipeline.txt

# Browser scraping prerequisites for TikTok
playwright install chromium
# Optional local fallback for visible-browser or Selenium runs:
# install Google Chrome / Chromium on the machine

# First-time setup (ChromaDB collections)
python3 database/setup_chromadb.py

# Run migrations
cd console/backend && alembic upgrade head && cd ../..

# Start pipeline worker (render queue)
./pipeline_start.sh

# Run full daily pipeline
python3 batch_runner.py --run-now

# Dry-run (no LLM/render/upload)
python3 batch_runner.py --run-now --dry-run

# Verify LLM setup
python3 -c "
from rag.llm_router import LLMRouter
r = LLMRouter(mode='local')
print('Ollama up:', r.is_ollama_available())
print('Model:', r.status()['ollama_model'])
print('Gemini key:', r.status()['gemini_key_set'])
"
```

See `guideline/01_install_ollama.md` for Ollama setup.  
Set API keys in `pipeline.env` (copy from `pipeline.env.example`).

---

## Directory Structure

```
ai-media-automation/
│
├── CLAUDE.md                          ← YOU ARE HERE
│
├── console/                           ← Management Console (Sprint 1 complete)
│   ├── .env.example                   ← Copy to .env and fill in values
│   ├── .env                           ← DATABASE_URL, JWT_SECRET, FERNET_KEY, etc.
│   ├── requirements.txt
│   ├── start.sh                       ← One-command startup (run from project root)
│   │
│   ├── backend/
│   │   ├── main.py                    ← FastAPI app, CORS, router registration
│   │   ├── config.py                  ← Pydantic settings (reads .env)
│   │   ├── database.py                ← SQLAlchemy engine + get_db dependency
│   │   ├── auth.py                    ← JWT, bcrypt, role-based Depends
│   │   ├── celery_app.py              ← Celery instance, 4 queues, beat schedule
│   │   │
│   │   ├── alembic.ini                ← Alembic config (run alembic from console/backend/)
│   │   ├── alembic/
│   │   │   ├── env.py                 ← Adds project root to sys.path, loads .env
│   │   │   └── versions/
│   │   │       └── 001_initial_console_tables.py   ← Creates 6 tables, extends generated_scripts
│   │   │
│   │   ├── models/
│   │   │   ├── console_user.py        ← ConsoleUser (id, username, email, password_hash, role)
│   │   │   ├── credentials.py         ← PlatformCredential (OAuth config + encrypted tokens)
│   │   │   ├── channel.py             ← Channel, TemplateChannelDefault, UploadTarget
│   │   │   └── audit_log.py           ← AuditLog (every write operation)
│   │   │
│   │   ├── schemas/
│   │   │   ├── common.py              ← PaginatedResponse[T]
│   │   │   ├── scraper.py             ← ScraperSourceResponse, ScrapedVideoResponse, etc.
│   │   │   └── script.py              ← ScriptListItem, ScriptDetail, ScriptUpdate, etc.
│   │   │
│   │   ├── services/
│   │   │   ├── scraper_service.py     ← Source YAML management, video queries, ChromaDB indexing
│   │   │   └── script_service.py      ← Script CRUD, status workflow, generate/regenerate
│   │   │
│   │   ├── routers/
│   │   │   ├── auth.py                ← POST /api/auth/login|register, GET /api/auth/me
│   │   │   ├── scraper.py             ← GET|PATCH /api/scraper/sources, GET /api/scraper/videos, etc.
│   │   │   └── scripts.py             ← Full CRUD + approve/reject/regenerate
│   │   │
│   │   ├── tasks/
│   │   │   ├── scraper_tasks.py       ← run_scrape_task (queue: scrape_q)
│   │   │   ├── script_tasks.py        ← generate_script_task (queue: script_q)
│   │   │   ├── production_tasks.py    ← regenerate_tts_task, render_video_task (queue: render_q)
│   │   │   ├── upload_tasks.py        ← upload_to_channel_task (queue: upload_q)
│   │   │   └── token_refresh.py       ← refresh_expiring_tokens (Celery beat, every 30min)
│   │   │
│   │   └── ws/
│   │       └── pipeline_ws.py         ← TODO Sprint 2: WebSocket for live job updates
│   │
│   └── frontend/
│       ├── package.json
│       ├── vite.config.js             ← Dev proxy: /api → :8080, /ws → ws://:8080
│       ├── tailwind.config.js         ← Dark theme tokens (IBM Plex Mono/Sans)
│       └── src/
│           ├── main.jsx
│           ├── App.jsx                ← Sidebar nav, role-based tabs, login guard
│           ├── index.css              ← Global dark theme, scrollbars
│           ├── api/
│           │   └── client.js          ← JWT-in-memory fetch wrapper, scraperApi, scriptsApi
│           ├── hooks/
│           │   └── useApi.js          ← Simple data-fetching hook with loading/error state
│           ├── components/
│           │   └── index.jsx          ← Card, Badge, Button, Input, Textarea, Select,
│           │                             Modal, StatBox, ProgressBar, Tabs, Toast,
│           │                             Spinner, EmptyState
│           └── pages/
│               ├── LoginPage.jsx      ← JWT stored in memory (not localStorage)
│               ├── ScraperPage.jsx    ← Stats · Source manager · Video table · Topic modal
│               └── ScriptsPage.jsx    ← Status tabs · Bulk approve/reject · Script editor modal
│
├── config/
│   ├── scraper_sources.yaml           ← Scraper source registry (read/written by ScraperService)
│   └── pipeline_config.yaml           ← All pipeline runtime settings (niches, LLM, TTS, upload)
│
├── database/
│   ├── models.py                      ← ViralVideo, GeneratedScript, VideoAsset, ViralPattern
│   ├── connection.py                  ← engine + SessionLocal + get_session()
│   └── setup_chromadb.py             ← creates 3 ChromaDB collections (run once)
│
├── scraper/
│   ├── base_scraper.py               ← ScrapedVideo dataclass + BaseScraper abstract class
│   ├── tiktok_browser_common.py      ← shared TikTok browser config + parsing helpers
│   ├── tiktok_research_api.py        ← TikTok Research API adapter
│   ├── tiktok_playwright.py          ← Playwright-first TikTok scraper with headful + Selenium fallback
│   ├── tiktok_selenium.py            ← Selenium + Chromium TikTok fallback scraper
│   ├── apify_scraper.py              ← Apify cloud scraper
│   ├── trend_analyzer.py             ← extracts patterns → viral_patterns table
│   └── main.py                       ← run_scrape() orchestrator
│
├── vector_db/
│   ├── indexer.py                    ← embed + upsert into ChromaDB
│   └── retriever.py                  ← semantic search (scripts / hooks / patterns)
│
├── rag/
│   ├── llm_router.py                 ← local/gemini/auto/hybrid dispatch
│   ├── rate_limiter.py               ← RPD/RPM tracking with Redis fallback
│   ├── prompt_builder.py             ← RAG-enriched prompt assembly
│   ├── script_writer.py              ← generate_script() / regenerate_scene()
│   └── script_validator.py           ← JSON schema validation + fix_and_normalize()
│
├── pipeline/
│   ├── tts_engine.py                 ← Kokoro ONNX TTS → 44.1kHz WAV
│   ├── asset_db.py                   ← VideoAsset CRUD + keyword-match search
│   ├── asset_resolver.py             ← 3-tier: DB → Pexels → Veo
│   ├── pexels_client.py              ← Pexels portrait video download + crop
│   ├── veo_client.py                 ← Google Veo 8s segment generation
│   ├── veo_prompt_builder.py         ← per-niche Veo style directives
│   ├── overlay_builder.py            ← Pillow text overlay → PNG
│   ├── caption_gen.py                ← Whisper base → SRT subtitles
│   ├── composer.py                   ← MoviePy scene assembly → raw_video.mp4
│   ├── renderer.py                   ← ffmpeg NVENC → video_final.mp4
│   └── quality_validator.py          ← duration/codec/resolution/audio checks
│
├── uploader/
│   ├── youtube_uploader.py           ← YouTube Data API v3 resumable upload
│   ├── tiktok_uploader.py            ← TikTok Content Posting API v2
│   └── scheduler.py                  ← peak-hour scheduling + upload_targets rows
│
├── feedback/
│   ├── tracker.py                    ← fetch real metrics from YouTube/TikTok APIs
│   ├── scorer.py                     ← compute quality score 0-100
│   └── reindexer.py                  ← reindex top performers into ChromaDB
│
├── guideline/
│   └── 01_install_ollama.md          ← Ollama + Qwen2.5 setup guide
│
├── pipeline.env.example              ← template — copy to pipeline.env
├── pipeline.env                      ← GEMINI_API_KEY, GEMINI_MEDIA_API_KEY, PEXELS_API_KEY, etc.
├── requirements.pipeline.txt         ← pip deps for core pipeline
├── pipeline_start.sh                 ← starts Celery render worker + checks prerequisites
├── batch_runner.py                   ← cron entry point (--run-now / --dry-run / --scrape-only)
└── daily_pipeline.py                 ← orchestrates full daily run
```

---

## Core Rules (Always Follow)

1. **Treat current code as the source of truth.** Planning docs may lag behind the repo. Prefer the real implementation and recent runtime behavior when they disagree.

2. **Run uvicorn from the project root**, not from `console/`:
   ```bash
   cd ai-media-automation
   uvicorn console.backend.main:app --port 8080 --reload
   ```

3. **Run alembic from `console/backend/`**, not from the project root:
   ```bash
   cd console/backend
   alembic upgrade head
   alembic revision --autogenerate -m "description"
   ```

4. **Use Celery for anything > 5 seconds.** Scraping, LLM generation, TTS, rendering, uploading → all go via Celery tasks. Return `task_id` immediately.

5. **Encrypt all OAuth secrets.** Use Fernet (`cryptography` library). Key lives in `.env` as `FERNET_KEY`. Never store plaintext tokens in the DB.

6. **Audit every write.** Every POST/PUT/PATCH/DELETE by an editor must create an `AuditLog` entry via the `_audit()` helper in `script_service.py`.

7. **JWT stored in memory only.** `client.js` holds the token in a module-level variable, never `localStorage` or `sessionStorage`.

8. **Role-based access:**
   - `admin` → all 8 tabs (Scraper, Scripts, Production, Uploads, Pipeline, LLM, Performance, System)
   - `editor` → Scraper, Scripts, Production, Uploads, Pipeline, Performance only

---

## Database

Shared PostgreSQL instance with the core pipeline. The console adds 6 new tables and extends `generated_scripts`:

**New tables:** `console_users`, `platform_credentials`, `channels`, `template_channel_defaults`, `upload_targets`, `audit_log`

**Extended:** `generated_scripts` gets 4 new columns: `status`, `editor_notes`, `edited_by`, `approved_at`

**Script status workflow:**
```
draft → pending_review → approved → producing → completed
draft ← rejected        (from pending_review)
editing                 (approved script being modified — goes back to approved on save)
```

---

## API Endpoints (Sprint 1 — implemented)

```
POST   /api/auth/login
POST   /api/auth/register        (admin only)
GET    /api/auth/me

GET    /api/scraper/sources
PATCH  /api/scraper/sources/{id}/status
POST   /api/scraper/run
GET    /api/scraper/videos
POST   /api/scraper/videos/index

GET    /api/scripts
POST   /api/scripts/generate
GET    /api/scripts/{id}
PUT    /api/scripts/{id}
PATCH  /api/scripts/{id}/approve
PATCH  /api/scripts/{id}/reject
POST   /api/scripts/{id}/regenerate
POST   /api/scripts/{id}/scenes/{n}/regenerate
```

## Current Scraper Reality

- The active TikTok source is currently configured in `config/scraper_sources.yaml` and should be treated as operational config, not static documentation.
- Right now the intended temporary production path is browser scraping through `tiktok_playwright`.
- `tiktok_playwright` now tries broader page-state extraction first, can retry in visible-browser mode, and can fall back to Selenium + Chromium when Playwright returns empty results.
- TikTok Research API support remains in the repo, but should be treated as a future official path that depends on external approval and valid research credentials.
- Apify remains a fallback source only; do not assume quota is available.

### Browser Scraper Runtime Settings

Set these in `pipeline.env` when debugging TikTok scraping locally:

```bash
TIKTOK_SCRAPER_ENGINE=auto
TIKTOK_BROWSER_HEADLESS=true
TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY=true
TIKTOK_SELENIUM_FALLBACK=true
TIKTOK_BROWSER_TIMEOUT_MS=30000
TIKTOK_BROWSER_SCROLL_COUNT=4
TIKTOK_BROWSER_SCROLL_DELAY_MS=1800
TIKTOK_BROWSER_CHANNEL=
TIKTOK_CHROME_BINARY=
```

- Set `TIKTOK_BROWSER_HEADLESS=false` to force a real browser window/tab for local debugging.
- Set `TIKTOK_SCRAPER_ENGINE=selenium` if you want Selenium to be the first browser engine instead of a fallback.

---

## What's Next — Sprint 2 (Week 2)

Refer to `03_implementation_plan.md` and `04_ai_task_guide.md` for full task specs.

### Backend tasks

| ID | Task | File to create |
|----|------|----------------|
| B-010 | ProductionService — asset DB search, scene asset replacement, TTS regen, Veo gen, start_production | `services/production_service.py` |
| B-011 | Production router — GET/POST assets, PUT scene asset, POST TTS/Veo/render | `routers/production.py` |
| B-012 | PipelineService — list/create/retry/cancel jobs, worker config | `services/pipeline_service.py` |
| B-013 | Pipeline router + **WebSocket** — job status broadcast every 2s | `routers/pipeline.py`, `ws/pipeline_ws.py` |
| B-014 | Asset thumbnail generator — ffmpeg frame extraction script | `scripts/gen_thumbnails.py` |

### Frontend tasks

| ID | Task | File to create |
|----|------|----------------|
| F-008 | ProductionPage — approved scripts sidebar, visual timeline bar, scene card list | `pages/ProductionPage.jsx` |
| F-009 | Scene editor panel — asset preview, Replace/Veo/Pexels buttons, TTS regen | inside ProductionPage.jsx |
| F-010 | AssetBrowser modal — search, thumbnail grid (4 cols), click-to-select | `components/AssetBrowser.jsx` |
| F-011 | PipelinePage — stats row, batch controls, job list with progress bars | `pages/PipelinePage.jsx` |
| F-012 | useWebSocket hook — auto-reconnect, message parsing, job state dispatch | `hooks/useWebSocket.js` |

### Key integration points for Sprint 2

- `video_assets` table: `id, file_path, source, keywords[], niche[], duration_s, resolution, quality_score, usage_count`
- Pipeline modules to call via Celery:
  - `pipeline/tts_engine.py` → `generate_tts(text, voice, speed) → wav_path`
  - `pipeline/asset_resolver.py` → `resolve_asset(visual_hint, niche, duration) → clip_path`
  - `pipeline/composer.py` → `compose_video(script_id) → raw_video_path`
  - `pipeline/renderer.py` → `render_final(raw_path) → final_path`
- WebSocket endpoint: `WS /ws/pipeline` — broadcast job status changes to all connected clients

---

## Sprint 3 Preview (Week 3) — Upload Manager + Auth + Channels

- `CredentialService` — Fernet encrypt/decrypt, OAuth URL builder, token refresh, connection test
- `ChannelService` — CRUD channels, template→channel default mapping
- `UploadService` — multi-channel targeting, dispatch upload Celery tasks
- OAuth callback handler: `GET /api/credentials/{platform}/callback`
- Token auto-refresh via Celery beat (already wired in `celery_app.py`)
- Frontend: UploadsPage with Videos / Auth & Credentials / Channels sub-tabs

---

## Sprint 4 Preview (Week 4) — Performance + System + Polish + Deploy

- PerformanceService, SystemService (psutil + nvidia-smi), LLMService
- Login page polish, responsive fixes, error states, loading skeletons
- Docker: `Dockerfile.api`, `Dockerfile.frontend`, `docker-compose.console.yml`
- `start.sh` Docker variant

---

## Design Tokens (Tailwind)

All defined in `tailwind.config.js`. Key values:

| Token | Value | Use |
|-------|-------|-----|
| `bg-[#0d0d0f]` | Page background | |
| `bg-[#16161a]` | Surface / sidebar | |
| `bg-[#1c1c22]` | Card background | |
| `bg-[#2a2a32]` | Borders | |
| `text-[#e8e8f0]` | Primary text | |
| `text-[#9090a8]` | Secondary text | |
| `text-[#5a5a70]` | Muted / placeholder | |
| `#7c6af7` | Accent purple (primary actions, active nav) | |
| `#34d399` | Green (success, approved, connected) | |
| `#f87171` | Red (error, danger, rejected) | |
| `#fbbf24` | Yellow (warning, pending) | |
| `#4a9eff` | Blue (info, editing) | |

Font: IBM Plex Mono (code/numbers), IBM Plex Sans (body)

---

## Planning Documents (in this folder)

| File | Contents |
|------|----------|
| `01_product_spec.md` | Full feature specs for all 8 modules with priorities |
| `02_architecture_design.md` | System diagram, tech stack, data flows, DB schema |
| `03_implementation_plan.md` | Sprint breakdown, 58 tasks with estimates and dependencies |
| `04_ai_task_guide.md` | Ready-to-paste prompts for each task (copy → paste → implement) |
| `ai_media_console.jsx` | Original React prototype (design reference) |

---

*Last updated: April 2026 — Sprint 1 complete, Sprint 2 starting*
