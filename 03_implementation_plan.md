# AI Media Management Console — Implementation Plan

> **Version:** 1.0 | **Date:** April 2026
> **Duration:** 4 weeks (1 engineer, ~40h/week)
> **Total Estimated Hours:** ~172h

---

## 1. Timeline Overview

```
Week 1 ─── Foundation + Scraper + Script Editor
Week 2 ─── Production Editor + Pipeline Monitor
Week 3 ─── Upload Manager + Auth Credentials + Channels
Week 4 ─── Performance + System Health + Polish + Deploy
```

---

## 2. Prerequisites (Day 0 — before Sprint 1)

| Task | Est. | Notes |
|------|------|-------|
| Install Redis | 15m | `apt install redis-server` or Docker |
| Create `console/` directory structure | 15m | Backend + frontend skeleton |
| Initialize FastAPI project | 30m | `pip install fastapi uvicorn celery redis sqlalchemy` |
| Initialize Vite + React project | 30m | `npm create vite@latest frontend -- --template react` |
| Install Tailwind CSS | 15m | `npm install tailwindcss` |
| Run Alembic migration for new tables | 30m | 6 new tables + 4 column additions |
| Create `.env` with all required vars | 15m | DATABASE_URL, REDIS_URL, JWT_SECRET |
| **Total** | **~2.5h** | |

---

## 3. Sprint 1 — Week 1: Foundation + Scraper + Script Editor

### Backend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| B-001 | FastAPI scaffolding: main.py, CORS, router registration, health check, lifespan events | 3h | — | `console/backend/main.py`, `config.py` |
| B-002 | JWT auth module: login, register, role middleware, password hashing | 2h | B-001 | `auth.py`, `routers/auth.py` |
| B-003 | Database migration: 6 new tables + generated_scripts extensions via Alembic | 2h | B-001 | `models/*.py`, migration files |
| B-004 | Pydantic schemas: ScrapedVideo, ScriptCreate, ScriptUpdate, ScriptResponse, PaginatedResponse | 2h | B-003 | `schemas/*.py` |
| B-005 | ScraperService: list sources (from YAML config), toggle status, trigger scrape (subprocess), list videos (filtered + paginated query), index to ChromaDB | 4h | B-003, B-004 | `services/scraper_service.py` |
| B-006 | Scraper router: GET sources, PATCH status, POST run, GET videos, POST index | 2h | B-005 | `routers/scraper.py` |
| B-007 | ScriptService: CRUD, status transitions, generate (calls script_writer.py), regenerate, scene-level update | 6h | B-003, B-004 | `services/script_service.py` |
| B-008 | Script router: GET list, POST generate, GET/PUT detail, PATCH approve/reject, POST regenerate | 2h | B-007 | `routers/scripts.py` |
| B-009 | Celery setup: Redis connection, app instance, task definitions for scrape + generate | 3h | B-001 | `celery_app.py`, `tasks/*.py` |

### Frontend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| F-001 | Vite + React project: Tailwind config, dark theme CSS vars, IBM Plex Mono font, base layout | 2h | — | `frontend/src/`, `tailwind.config.js` |
| F-002 | Shared UI components: Card, Badge, Button (5 variants), Modal, Select, Input, ProgressBar, Tabs, StatBox, BarChart, Sparkline | 4h | F-001 | `components/*.jsx` |
| F-003 | API client: fetch wrapper with JWT header injection, error handling, base URL config | 2h | F-001 | `api/client.js` |
| F-004 | App shell: header bar, tab navigation (8 tabs with icons + counts), content area routing | 2h | F-002 | `App.jsx` |
| F-005 | ScraperPage: stats row, source cards, source manager modal, video table (filters/sort/multi-select), topic creation modal | 6h | F-002, F-003, B-006 | `pages/ScraperPage.jsx` |
| F-006 | ScriptsPage: script list with status filters, status badges, approve/reject/regen action buttons | 4h | F-002, F-003, B-008 | `pages/ScriptsPage.jsx` |
| F-007 | Script Editor modal: meta fields (topic/niche/template/region), video metadata (title/desc/hashtags/voice/speed/mood), scene list with inline editing (narration/visual_hint/overlay/duration/type/transition), reorder/add/remove, CTA + affiliate sections | 6h | F-006 | Inside `ScriptsPage.jsx` |

### Sprint 1 Total: ~45h

---

## 4. Sprint 2 — Week 2: Production Editor + Pipeline Monitor

### Backend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| B-010 | ProductionService: asset DB search (keyword/niche/duration), scene asset replacement (update script_json), TTS regeneration (Celery task → tts_engine.py), Veo generation (Celery task) | 6h | B-009 | `services/production_service.py` |
| B-011 | Production router: GET assets, POST search, PUT scene asset, POST scene TTS, POST scene Veo, POST render | 2h | B-010 | `routers/production.py` |
| B-012 | PipelineService: list jobs from DB/memory, create job (Celery task chain), retry failed, cancel active, update worker config | 4h | B-009 | `services/pipeline_service.py` |
| B-013 | Pipeline router + WebSocket: GET jobs, POST create, PATCH retry/cancel, PUT config. WebSocket handler that broadcasts job status changes every 2s | 3h | B-012 | `routers/pipeline.py`, `ws/pipeline_ws.py` |
| B-014 | Asset thumbnail generator: for each clip in video_assets, extract frame 0 as 160×284 JPEG via ffmpeg. Run as a migration/batch script | 2h | B-010 | `scripts/gen_thumbnails.py` |

### Frontend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| F-008 | ProductionPage: approved scripts sidebar (tabs for each script), visual timeline bar (proportional widths per scene), scene card list with expand/collapse | 5h | F-002, B-011 | `pages/ProductionPage.jsx` |
| F-009 | Scene editor panel: two-column layout. Left: visual asset preview, Replace/Veo/Pexels buttons, visual hint input. Right: audio status, TTS regen/upload buttons, narration textarea, overlay text + style selector | 5h | F-008 | Inside `ProductionPage.jsx` |
| F-010 | Asset Browser modal: search input, source/niche filter dropdowns, thumbnail grid (4 columns), click-to-select, metadata overlay on each card | 4h | F-009, B-014 | `components/AssetBrowser.jsx` |
| F-011 | PipelinePage: stats row (active/queued/completed/failed), batch controls (start/pause, worker count selects, overnight queue, cancel all), job list (grid rows with status/progress bar/LLM/duration), expand for details, retry/cancel buttons | 5h | F-002, B-013 | `pages/PipelinePage.jsx` |
| F-012 | WebSocket hook: `useWebSocket('/ws/pipeline')` with auto-reconnect, message parsing, job state update dispatch | 2h | F-011 | `hooks/useWebSocket.js` |

### Sprint 2 Total: ~38h

---

## 5. Sprint 3 — Week 3: Upload Manager + Auth + Channels

### Backend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| B-015 | CredentialService: CRUD for platform_credentials, Fernet encrypt/decrypt for secrets, OAuth URL builder, token refresh logic (call platform token endpoint), connection test (lightweight API call) | 5h | B-003 | `services/credential_service.py` |
| B-016 | Credential router: GET list, PUT update, POST refresh, POST test, GET oauth-url | 2h | B-015 | `routers/credentials.py` |
| B-017 | ChannelService: CRUD for channels, template→channel default mapping (CRUD for template_channel_defaults), link channel to credential | 3h | B-003, B-015 | `services/channel_service.py` |
| B-018 | Channel router: GET list, POST create, PUT update, DELETE, GET/PUT defaults per template | 2h | B-017 | `routers/channels.py` |
| B-019 | UploadService: list videos (join scripts + upload_targets), delete video, set target channels (with template default fallback), trigger upload per channel (Celery task), bulk upload all ready | 5h | B-017, B-009 | `services/upload_service.py` |
| B-020 | Upload router: GET list, DELETE, PUT targets, POST upload, POST upload-all | 2h | B-019 | `routers/uploads.py` |
| B-021 | OAuth callback handler: GET /api/credentials/{platform}/callback — receives auth code, exchanges for tokens, stores encrypted | 3h | B-015 | Inside `routers/credentials.py` |
| B-022 | Token auto-refresh: Celery beat periodic task (every 30min) checks platform_credentials for tokens expiring within 1 hour and refreshes them | 2h | B-015, B-009 | `tasks/token_refresh.py` |

### Frontend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| F-013 | UploadsPage shell: platform overview cards (3 cards with icon, connection status, token TTL, quota bar, published/scheduled counts), sub-tabs (Videos / Auth & Credentials / Channels) | 3h | F-002, B-020 | `pages/UploadsPage.jsx` |
| F-014 | Videos sub-tab: production videos table with columns (title/template, status, niche, target channels as tags, schedule, views, actions). Header row. Delete button per row. Empty state | 5h | F-013, B-020 | Inside `UploadsPage.jsx` |
| F-015 | ChannelPicker component: inline dropdown with checkboxes per active channel (platform icon + name + subs), All/None/Done footer. Click-outside-to-close via useRef. Shown on non-uploaded/non-published items | 3h | F-014, B-018 | `components/ChannelPicker.jsx` |
| F-016 | Auth & Credentials sub-tab: per-platform expandable cards. Collapsed: token status bar (4 metric boxes: expires, last refresh, auth type, quota). Expanded: OAuth credentials (secret fields with show/hide/copy), redirect URI, scopes tags, active tokens (masked), API endpoints, action buttons (OAuth flow, refresh, test, disconnect, save) | 6h | F-013, B-016 | Inside `UploadsPage.jsx` |
| F-017 | Channels sub-tab: channel list (platform icon + name + status + monetized badge + subs/videos counts), edit/pause/play buttons. Channel edit modal (name, platform, email, category, language, status, monetization, platform connection link) | 4h | F-013, B-018 | Inside `UploadsPage.jsx` |
| F-018 | Default upload settings: 3-column card grid (YouTube/TikTok/Instagram) showing per-platform defaults (privacy, category, language, comments, etc.) | 2h | F-017 | Inside `UploadsPage.jsx` |
| F-019 | .env reference card: formatted code block with all env vars, Export/Import/Validate buttons | 1h | F-016 | Inside `UploadsPage.jsx` |

### Sprint 3 Total: ~48h

---

## 6. Sprint 4 — Week 4: Performance + System + Polish + Deploy

### Backend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| B-023 | PerformanceService: daily aggregates (GROUP BY date, last N days), niche breakdown, top videos by performance_score | 3h | B-003 | `services/performance_service.py` |
| B-024 | Performance router: GET daily, GET niches, GET top-videos | 1h | B-023 | `routers/performance.py` |
| B-025 | SystemService: psutil for CPU/RAM/disk, nvidia-smi subprocess for GPU, service health checks (pg_isready, curl Ollama :11434, ffmpeg -version), parse crontab for schedule, read error log files | 4h | — | `services/system_service.py` |
| B-026 | System router: GET health, GET cron, GET errors | 1h | B-025 | `routers/system.py` |
| B-027 | LLMService: read/write LLM_STRATEGY from config.py, Gemini quota (read rate_limiter state), Ollama health (curl :11434/api/tags) | 2h | — | `services/llm_service.py` |
| B-028 | LLM router: GET status, PUT mode, GET quota | 1h | B-027 | `routers/llm.py` |
| B-029 | Audit logging middleware: FastAPI middleware that intercepts all POST/PUT/PATCH/DELETE requests and writes to audit_log table | 2h | B-002 | `middleware/audit.py` |

### Frontend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| F-020 | PerformancePage: stat boxes with sparklines, bar charts (daily output, views, revenue), feedback scoring cards (formula, >70 reindexed, <40 low-perf), niche breakdown grid | 5h | F-002, B-024 | `pages/PerformancePage.jsx` |
| F-021 | SystemPage: resource gauges (CPU/GPU/RAM/disk with color thresholds), service status grid (8 services with green/yellow/red dots), cron schedule table, error log list (time + level + message + source) | 4h | F-002, B-026 | `pages/SystemPage.jsx` |
| F-022 | LLMPage: mode selector cards (4 modes with cost + description), quota monitors (per-model progress bars), hybrid routing config cards, rate limiter status | 4h | F-002, B-028 | `pages/LLMPage.jsx` |
| F-023 | Login page: centered form with username/password, JWT storage in memory (not localStorage), redirect to main app, role-based tab visibility (editors can't see System/LLM/Credentials) | 3h | F-003, B-002 | `pages/LoginPage.jsx` |
| F-024 | Responsive polish: test all 8 pages at 1024px and 1440px, fix horizontal overflow, scrollable tables, touch-friendly button targets, loading states | 3h | All F-* | All pages |
| F-025 | Error handling: loading skeleton placeholders, empty state messages ("No approved scripts yet"), API error toasts, retry affordances on failed fetches | 2h | All F-* | All pages |

### DevOps Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| D-001 | Docker: Dockerfile for FastAPI (python:3.11-slim), Dockerfile for frontend (node:20 build → nginx:alpine serve), docker-compose.console.yml (api + frontend + redis) | 3h | All B-*, F-* | `Dockerfile.*`, `docker-compose.console.yml` |
| D-002 | Nginx config: reverse proxy /api → FastAPI :8080, / → React static files, /ws → WebSocket upgrade | 1h | D-001 | `nginx.conf` |
| D-003 | Environment config: `.env.example` with all required vars, secrets management docs, production vs development flag | 1h | D-001 | `.env.example`, docs |
| D-004 | Startup script: `console/start.sh` — run Alembic migrations, start Redis, start Celery workers (4 queues), start FastAPI with uvicorn, serve React build | 1h | D-001 | `start.sh` |

### Sprint 4 Total: ~41h

---

## 7. Summary

| Sprint | Week | Focus | Hours |
|--------|------|-------|-------|
| 1 | 1 | Foundation + Scraper + Script Editor | ~45h |
| 2 | 2 | Production Editor + Pipeline Monitor | ~38h |
| 3 | 3 | Upload Manager + Auth + Channels | ~48h |
| 4 | 4 | Performance + System + Polish + Deploy | ~41h |
| **Total** | **4 weeks** | **All modules** | **~172h** |

### Task Count

| Category | Count |
|----------|-------|
| Backend tasks (B-*) | 29 |
| Frontend tasks (F-*) | 25 |
| DevOps tasks (D-*) | 4 |
| **Total tasks** | **58** |

### Dependency Chain (Critical Path)

```
B-001 → B-002 → B-003 → B-004 → B-005/B-007 → B-009 → B-010/B-012/B-015/B-019
  │                                                          │
  └─ F-001 → F-002 → F-003 → F-004 ─────────────────────────┘
                                      → F-005 (Scraper)
                                      → F-006/F-007 (Scripts)
                                      → F-008/F-009/F-010 (Production)
                                      → F-011/F-012 (Pipeline)
                                      → F-013–F-019 (Uploads)
                                      → F-020–F-022 (Perf/System/LLM)
                                      → F-023–F-025 (Polish)
```

---

*Implementation Plan v1.0 — April 2026*
