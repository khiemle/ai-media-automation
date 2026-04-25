# AI Media Management Console — Architecture Design

> **Version:** 1.0 | **Date:** April 2026
> **Related:** `01_product_spec.md`, `03_implementation_plan.md`, `04_ai_task_guide.md`

---

## 1. High-Level Architecture

The Management Console is a thin control layer that wraps the existing AI Media Automation core pipeline. It does NOT replace any pipeline module — it provides a web interface for human operators to observe, intervene, and configure.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MANAGEMENT CONSOLE                           │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │               React SPA (Vite + Tailwind)                │  │
│   │                                                          │  │
│   │  Scraper │ Scripts │ Production │ Videos │ Pipeline       │  │
│   │  LLM Router │ Performance │ System Health                │  │
│   │                                                          │  │
│   │  State: React useState + useReducer                      │  │
│   │  HTTP:  fetch → /api/*                                   │  │
│   │  Live:  WebSocket → /ws/pipeline                         │  │
│   └────────────────────────┬─────────────────────────────────┘  │
│                            │ HTTP / WS                          │
│   ┌────────────────────────▼─────────────────────────────────┐  │
│   │               FastAPI Backend (:8080)                     │  │
│   │                                                          │  │
│   │  Routers:  scraper │ scripts │ production │ uploads      │  │
│   │            pipeline │ llm │ performance │ system          │  │
│   │            credentials │ channels │ auth                  │  │
│   │                                                          │  │
│   │  Services: Business logic → calls core pipeline modules  │  │
│   │  Auth:     JWT (admin / editor roles)                    │  │
│   │  ORM:      SQLAlchemy 2.0 (shared DB with core)         │  │
│   │  Queue:    Celery tasks for heavy operations             │  │
│   └────────────────────────┬─────────────────────────────────┘  │
│                            │                                    │
└────────────────────────────┼────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────────┐
        │                    │                        │
        ▼                    ▼                        ▼
 ┌─────────────┐  ┌───────────────────┐  ┌──────────────────┐
 │ PostgreSQL  │  │ Core Pipeline     │  │ External APIs    │
 │ (:5432)     │  │ Modules           │  │                  │
 │             │  │                   │  │ TikTok Research  │
 │ Shared DB   │  │ scraper/          │  │ Pexels           │
 │ + new tables│  │ rag/              │  │ Google Veo       │
 │             │  │ pipeline/         │  │ Gemini 2.5 Flash │
 └─────────────┘  │ uploader/         │  │ ElevenLabs TTS   │
                  │ feedback/         │  │ YouTube Data v3  │
                  │                   │  │ TikTok Content   │
                  └─────────┬─────────┘  └──────────────────┘
                            │
                   ┌────────▼────────┐
                   │ Celery + Redis  │
 ┌─────────────┐   │ (:6379)         │
 │ File System │   │                 │
 │ /assets/    │   │ Queues:         │
 │ video_db/   │   │  scrape_q       │
 │ music/      │   │  script_q       │
 │ outputs/    │   │  render_q       │
 └─────────────┘   │  upload_q       │
                   └─────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Why This Choice |
|-------|-----------|-----------------|
| Frontend | React 18 + Vite | Lightweight, fast HMR, same JSX prototype already built |
| Styling | Tailwind CSS | Utility-first, dark theme from prototype maps directly |
| HTTP Client | fetch + SWR | Built-in fetch, SWR for caching/revalidation |
| Real-time | WebSocket (native) | Pipeline job updates without polling |
| Backend | FastAPI (Python 3.11) | Same language as core pipeline — direct module imports |
| ORM | SQLAlchemy 2.0 | Already used by core system's `database/models.py` |
| Task Queue | Celery + Redis | Async for scraping, LLM generation, rendering, uploading |
| Auth | JWT + bcrypt | Simple role-based, 2 roles only |
| Database | PostgreSQL 16 | Already running — extend with 6 new tables |
| File Server | FastAPI StaticFiles | Serve asset thumbnails and audio previews |
| Encryption | Fernet (cryptography) | Encrypt OAuth secrets at rest |
| LLM | Gemini 2.5 Flash only | Ollama/local model removed — Gemini handles all script generation |
| TTS | ElevenLabs (VI) + Kokoro (EN) | TTS Router selects engine by script language; auto mode default |

---

## 3. System Integration Diagram

### 3.1 Console ↔ Core Pipeline Integration

```
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI SERVICE LAYER                            │
│                                                                        │
│  ScraperService ─────── calls ──▶ scraper/tiktok_research_api.py      │
│       │                           scraper/trend_analyzer.py            │
│       │                           (via subprocess.run or Celery)       │
│       │                                                                │
│  ScriptService ──────── calls ──▶ rag/script_writer.py                │
│       │                           rag/llm_router.py                    │
│       │                           (via direct Python import)           │
│       │                                                                │
│  ProductionService ──── calls ──▶ pipeline/tts_engine.py              │
│       │                           pipeline/asset_resolver.py           │
│       │                           pipeline/asset_db.py                 │
│       │                           pipeline/overlay_builder.py          │
│       │                           pipeline/veo_prompt_builder.py       │
│       │                           (via Celery tasks)                   │
│       │                                                                │
│  PipelineService ────── calls ──▶ pipeline/composer.py                │
│       │                           pipeline/caption_gen.py              │
│       │                           pipeline/renderer.py                 │
│       │                           batch_runner.py                      │
│       │                           (via Celery tasks)                   │
│       │                                                                │
│  UploadService ──────── calls ──▶ uploader/youtube_uploader.py        │
│       │                           uploader/tiktok_uploader.py          │
│       │                           uploader/scheduler.py                │
│       │                           (via Celery tasks)                   │
│       │                                                                │
│  PerformanceService ─── reads ──▶ feedback/tracker.py results         │
│       │                           feedback/scorer.py results           │
│       │                           (via direct DB queries)              │
│       │                                                                │
│  SystemService ──────── reads ──▶ psutil (CPU/RAM/Disk)               │
│       │                           nvidia-smi (GPU)                     │
│       │                           pg_isready (PostgreSQL)              │
│       │                           (via subprocess)                     │
│       │                                                                │
│  LLMService ─────────── calls ──▶ rag/llm_router.py config           │
│       │                           rag/rate_limiter.py status           │
│       │                           (via direct import + config file)    │
│       │                                                                │
│  CredentialService ──── manages ─▶ platform_credentials table         │
│  ChannelService ─────── manages ─▶ channels table                     │
│                                    template_channel_defaults table     │
│                                    upload_targets table                │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Calling Patterns

The backend uses three patterns to call core pipeline modules:

**Pattern A — Direct Python Import** (for fast, lightweight operations)
```python
# Used by: ScriptService, LLMService, PerformanceService
from rag.script_writer import generate_script
from rag.llm_router import LLMRouter

result = generate_script(topic="5 thói quen", niche="lifestyle", template="tiktok_viral")
```

**Pattern B — Celery Task** (for operations > 5 seconds)
```python
# Used by: ProductionService, PipelineService, UploadService, ScraperService
@celery_app.task(queue="render_q")
def render_video_task(script_id: str):
    from pipeline.composer import compose_video
    from pipeline.renderer import render_final
    compose_video(script_id)
    render_final(script_id)

# API endpoint dispatches the task
task = render_video_task.delay(script_id)
return {"task_id": task.id, "status": "queued"}
```

**Pattern C — Subprocess** (for isolated processes or non-Python tools)
```python
# Used by: SystemService (nvidia-smi, ffprobe), ScraperService (optional)
import subprocess
result = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader"],
                        capture_output=True, text=True, timeout=5)
gpu_usage = int(result.stdout.strip().replace(" %", ""))
```

---

## 4. Data Flow: Editor Workflow

### 4.1 Scrape → Curate → Generate Script

```
Editor opens Scraper tab
    │
    ├─▶ GET /api/scraper/videos?niche=lifestyle&region=VN&sort=engagement_rate
    │     └─▶ SELECT * FROM viral_videos WHERE niche='lifestyle' AND region='VN'
    │           ORDER BY engagement_rate DESC LIMIT 50
    │
    ├─▶ Editor selects 5 high-ER videos (checkbox multi-select)
    │
    └─▶ POST /api/scripts/generate
           body: { topic: "5 thói quen buổi sáng", niche: "lifestyle",
                   template: "tiktok_viral", source_video_ids: [id1, id2, id3, id4, id5] }
           │
           └─▶ ScriptService:
                 ├─ Fetch selected videos from viral_videos (for article content)
                 ├─ Build prompt (topic + niche + template + language + article)
                 ├─ GeminiRouter → generate script JSON (incl. pexels_keywords per scene)
                 ├─ script_validator.py → validate + auto-fix
                 └─ INSERT INTO generated_scripts (status='draft', script_json=...)
```

### 4.2 Edit → Approve Script

```
Editor opens Scripts tab → clicks Edit on a draft script
    │
    ├─▶ GET /api/scripts/{id}
    │     └─▶ Returns full script_json with all scenes
    │
    ├─▶ Editor modifies:
    │     - Scene #1 narration text
    │     - Scene #3 visual_hint ("person waking up" → "coffee morning routine")
    │     - Adds scene #8 (new CTA scene)
    │     - Changes music mood from "uplifting" to "calm_focus"
    │
    ├─▶ PUT /api/scripts/{id}
    │     body: { script_json: {updated...}, editor_notes: "Changed hook approach" }
    │     └─▶ UPDATE generated_scripts SET script_json=..., status='pending_review'
    │
    └─▶ PATCH /api/scripts/{id}/approve
          └─▶ UPDATE generated_scripts SET status='approved', approved_at=NOW()
```

### 4.3 Production Editing → Render

```
Editor opens Production tab → selects approved script
    │
    ├─▶ Clicks scene #3 on the visual timeline → expands editor
    │
    ├─▶ Clicks "Replace from Asset DB" → opens Asset Browser modal
    │     └─▶ GET /api/production/assets?keywords=coffee,morning&niche=lifestyle&min_duration=5
    │           └─▶ SELECT * FROM video_assets
    │                WHERE keywords @> '{coffee,morning}' AND duration_s >= 5
    │                ORDER BY quality_score DESC LIMIT 20
    │
    ├─▶ Editor clicks a clip → replaces scene #3 asset
    │     └─▶ PUT /api/production/scripts/{id}/scenes/3/asset
    │           body: { asset_id: 42 }
    │
    ├─▶ Editor edits scene #3 narration → clicks "Regenerate TTS"
    │     └─▶ POST /api/production/scripts/{id}/scenes/3/tts
    │           └─▶ Celery task → pipeline/tts_router.py
    │                 language=vietnamese → ElevenLabs API → audio_3.wav
    │                 language=english    → Kokoro ONNX   → audio_3.wav
    │
    └─▶ Editor clicks "Start Production"
          └─▶ POST /api/pipeline/jobs
                body: { script_id: "abc123" }
                └─▶ Celery task chain:
                      1. Per-scene parallel: TTS + Asset Resolve + Overlay
                      2. Scene Composer (MoviePy) → raw_video.mp4
                      3. Caption Gen (Whisper) → subtitles.srt
                      4. Final Renderer (ffmpeg NVENC) → video_final.mp4
                      5. Quality Validation
                      6. Status → 'ready' in upload queue
```

### 4.4 Upload with Multi-Channel Targeting

```
Video completes rendering → appears in Videos tab
    │
    ├─▶ Template "tiktok_viral" → auto-assigns default channels:
    │     [HealthHub (TikTok), FitnessPro (TikTok)]
    │     └─▶ SELECT channel_id FROM template_channel_defaults
    │           WHERE template='tiktok_viral'
    │     └─▶ INSERT INTO upload_targets (video_id, channel_id, status='pending')
    │
    ├─▶ Editor clicks "Target" button → opens ChannelPicker dropdown
    │     - Sees all active channels with checkboxes
    │     - Adds "MainChannel (YouTube)" to targets
    │     └─▶ PUT /api/uploads/{id}/targets
    │           body: { channel_ids: ["ch_1", "ch_4", "ch_5"] }
    │
    └─▶ Editor clicks Upload ▶
          └─▶ POST /api/uploads/{id}/upload
                └─▶ For each target channel:
                      │
                      ├─ ch_1 (YouTube / MainChannel):
                      │   └─ Celery task → uploader/youtube_uploader.py
                      │       credentials: decrypt from platform_credentials (YouTube)
                      │       metadata: title, description, tags, category=22, privacy=public
                      │
                      ├─ ch_4 (TikTok / HealthHub):
                      │   └─ Celery task → uploader/tiktok_uploader.py
                      │       credentials: decrypt from platform_credentials (TikTok)
                      │       metadata: caption, hashtags, comments=enabled
                      │
                      └─ ch_5 (TikTok / FitnessPro):
                          └─ Celery task → uploader/tiktok_uploader.py
                              (same TikTok credentials, different account)
```

---

## 5. Database Schema Extensions

### 5.1 New Tables (6 total)

```sql
-- 1. Console users
CREATE TABLE console_users (
    id              SERIAL PRIMARY KEY,
    username        TEXT UNIQUE NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'editor')),
    created_at      TIMESTAMP DEFAULT NOW(),
    last_login      TIMESTAMP
);

-- 2. Platform OAuth credentials
CREATE TABLE platform_credentials (
    id              SERIAL PRIMARY KEY,
    platform        TEXT NOT NULL,              -- 'youtube' | 'tiktok' | 'instagram'
    name            TEXT NOT NULL,
    auth_type       TEXT DEFAULT 'oauth2',
    status          TEXT DEFAULT 'disconnected', -- connected | expired | disconnected
    -- OAuth app config
    client_id       TEXT,
    client_secret   TEXT,                       -- encrypted (Fernet)
    redirect_uri    TEXT,
    scopes          TEXT[],
    auth_endpoint   TEXT,
    token_endpoint  TEXT,
    -- Active tokens
    access_token    TEXT,                       -- encrypted (Fernet)
    refresh_token   TEXT,                       -- encrypted (Fernet)
    token_expires_at TIMESTAMP,
    last_refreshed  TIMESTAMP,
    -- Quotas
    quota_label     TEXT,
    quota_total     INT,
    quota_used      INT DEFAULT 0,
    quota_reset_at  TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- 3. Channels
CREATE TABLE channels (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    platform        TEXT NOT NULL,
    credential_id   INT REFERENCES platform_credentials(id),
    account_email   TEXT,
    category        TEXT,
    default_language TEXT DEFAULT 'vi',
    monetized       BOOLEAN DEFAULT FALSE,
    status          TEXT DEFAULT 'active',      -- active | paused
    subscriber_count INT DEFAULT 0,
    video_count     INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 4. Template → default channels
CREATE TABLE template_channel_defaults (
    template        TEXT NOT NULL,
    channel_id      INT REFERENCES channels(id),
    PRIMARY KEY (template, channel_id)
);

-- 5. Video → target channels (many-to-many)
CREATE TABLE upload_targets (
    video_id        TEXT NOT NULL,
    channel_id      INT REFERENCES channels(id),
    status          TEXT DEFAULT 'pending',     -- pending | uploading | published | failed
    uploaded_at     TIMESTAMP,
    platform_id     TEXT,                       -- YouTube/TikTok post ID after upload
    PRIMARY KEY (video_id, channel_id)
);

-- 6. Audit log
CREATE TABLE audit_log (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES console_users(id),
    action          TEXT NOT NULL,
    target_type     TEXT,
    target_id       TEXT,
    details         JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 5.2 Existing Table Extensions

```sql
ALTER TABLE generated_scripts ADD COLUMN status TEXT DEFAULT 'draft'
    CHECK (status IN ('draft','pending_review','approved','rejected','editing','producing','completed'));
ALTER TABLE generated_scripts ADD COLUMN editor_notes TEXT;
ALTER TABLE generated_scripts ADD COLUMN edited_by INT REFERENCES console_users(id);
ALTER TABLE generated_scripts ADD COLUMN approved_at TIMESTAMP;
```

---

## 6. Folder Structure

```
ai_media_company/
│
├── console/                          # ★ Management Console (NEW)
│   ├── backend/
│   │   ├── main.py                   # FastAPI app, CORS, router registration
│   │   ├── auth.py                   # JWT auth, roles
│   │   ├── config.py                 # Console config (pydantic-settings)
│   │   ├── celery_app.py             # Celery instance + task registration
│   │   ├── routers/                  # 11 route groups
│   │   │   ├── auth.py               # /api/auth/*
│   │   │   ├── scraper.py            # /api/scraper/*
│   │   │   ├── scripts.py            # /api/scripts/*
│   │   │   ├── production.py         # /api/production/*
│   │   │   ├── uploads.py            # /api/uploads/*
│   │   │   ├── pipeline.py           # /api/pipeline/*
│   │   │   ├── llm.py                # /api/llm/*
│   │   │   ├── performance.py        # /api/performance/*
│   │   │   ├── system.py             # /api/system/*
│   │   │   ├── credentials.py        # /api/credentials/*
│   │   │   └── channels.py           # /api/channels/*
│   │   ├── services/                 # 11 service classes
│   │   ├── models/                   # SQLAlchemy (console-only tables)
│   │   ├── schemas/                  # Pydantic request/response
│   │   └── ws/
│   │       └── pipeline_ws.py        # WebSocket for live job updates
│   │
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── App.jsx               # Layout + tab routing
│   │   │   ├── api/                  # API client per module
│   │   │   ├── components/           # Shared UI (Card, Badge, Modal, etc.)
│   │   │   ├── pages/                # 8 page components
│   │   │   ├── hooks/                # useWebSocket, useApi, useAuth
│   │   │   └── utils/
│   │   ├── vite.config.js
│   │   └── package.json
│   │
│   ├── docker-compose.console.yml
│   └── start.sh                      # Startup script
│
├── config/                           # (existing — unchanged)
├── scraper/                          # (existing — unchanged)
├── database/                         # (existing — models extended)
├── rag/                              # (existing — unchanged)
├── pipeline/                         # (existing — unchanged)
├── uploader/                         # (existing — unchanged)
├── feedback/                         # (existing — unchanged)
└── batch_runner.py                   # (existing — unchanged)
```

---

## 7. API Endpoint Summary

```
AUTH (3)
  POST   /api/auth/login
  POST   /api/auth/register
  GET    /api/auth/me

SCRAPER (5)
  GET    /api/scraper/sources
  PATCH  /api/scraper/sources/{id}/status
  POST   /api/scraper/run
  GET    /api/scraper/videos
  POST   /api/scraper/videos/index

SCRIPTS (7)
  GET    /api/scripts
  POST   /api/scripts/generate
  GET    /api/scripts/{id}
  PUT    /api/scripts/{id}
  PATCH  /api/scripts/{id}/approve
  PATCH  /api/scripts/{id}/reject
  POST   /api/scripts/{id}/regenerate

PRODUCTION (5)
  GET    /api/production/assets
  POST   /api/production/assets/search
  PUT    /api/production/scripts/{id}/scenes/{n}/asset
  POST   /api/production/scripts/{id}/scenes/{n}/tts
  POST   /api/production/scripts/{id}/render

UPLOADS (4)
  GET    /api/uploads
  DELETE /api/uploads/{id}
  PUT    /api/uploads/{id}/targets
  POST   /api/uploads/{id}/upload

CREDENTIALS (5)
  GET    /api/credentials
  PUT    /api/credentials/{id}
  POST   /api/credentials/{id}/refresh
  POST   /api/credentials/{id}/test
  GET    /api/credentials/{id}/oauth-url

CHANNELS (6)
  GET    /api/channels
  POST   /api/channels
  PUT    /api/channels/{id}
  DELETE /api/channels/{id}
  GET    /api/channels/defaults/{template}
  PUT    /api/channels/defaults/{template}

PIPELINE (5 + 1 WS)
  GET    /api/pipeline/jobs
  POST   /api/pipeline/jobs
  PATCH  /api/pipeline/jobs/{id}/retry
  PATCH  /api/pipeline/jobs/{id}/cancel
  PUT    /api/pipeline/config
  WS     /ws/pipeline

LLM (3)
  GET    /api/llm/status
  PUT    /api/llm/mode
  GET    /api/llm/quota

PERFORMANCE (3)
  GET    /api/performance/daily
  GET    /api/performance/niches
  GET    /api/performance/top-videos

SYSTEM (3)
  GET    /api/system/health
  GET    /api/system/cron
  GET    /api/system/errors

TOTAL: 49 endpoints + 1 WebSocket
```

---

## 8. Security Considerations

- **All OAuth secrets encrypted at rest** using Fernet symmetric encryption. Key stored in `.env`, never in database.
- **JWT tokens** expire after 24 hours. Refresh requires re-login.
- **Role-based access:** Editors cannot modify system config, credentials, or LLM settings. Only admins can.
- **Audit trail:** Every write operation logged with user ID, action type, and timestamp.
- **CORS** restricted to the frontend origin in production.
- **No plaintext secrets** in API responses — tokens are always masked unless the user explicitly clicks "Show".

---

*Architecture Design v1.0 — April 2026*
