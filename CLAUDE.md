# AI Media Management Console — Claude Code Context

> This file is read automatically by Claude Code on every session.
> It gives full project context so development can continue without re-explanation.

---

## What This Project Is

A **web-based Management Console** layered on top of an existing AI media automation pipeline (`ai_media_company/`). The core pipeline already scrapes TikTok trends, generates scripts via LLM, produces videos, and uploads them automatically. This console adds a human control layer — editors can curate content, review scripts, edit scenes, manage upload channels, and monitor the pipeline in real time.

**Stack:** FastAPI (Python 3.11+) backend · React 18 + Vite + Tailwind CSS frontend · PostgreSQL (shared with core pipeline) · Celery + Redis task queue

**Team:** 1 engineer + 1 business user  
**Target:** 4-week build (Sprint 1 complete as of April 2026)

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
│   └── scraper_sources.yaml           ← Scraper source registry (read/written by ScraperService)
│
├── scraper/                           ← EXISTING core pipeline (do not modify)
├── rag/                               ← EXISTING core pipeline (do not modify)
├── pipeline/                          ← EXISTING core pipeline (do not modify)
├── uploader/                          ← EXISTING core pipeline (do not modify)
├── feedback/                          ← EXISTING core pipeline (do not modify)
├── database/                          ← EXISTING — models.py has ViralVideo, GeneratedScript, etc.
└── batch_runner.py                    ← EXISTING — runs unchanged alongside the console
```

---

## Core Rules (Always Follow)

1. **Never modify the core pipeline.** The console imports from `scraper/`, `rag/`, `pipeline/`, `uploader/`, `feedback/`, `database/` — but never changes them. The pipeline still runs in full-auto mode via `batch_runner.py`.

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
