# AI Media Management Console — AI Implementation Task Guide

> **Purpose:** Ready-to-paste task prompts for AI coding assistants (Claude Code, Cursor, Copilot, etc.)
> **Usage:** Copy a task block, paste it as a prompt, and the AI has full context to implement independently.
> **Related:** `01_product_spec.md`, `02_architecture_design.md`, `03_implementation_plan.md`

---

## General Rules for All Tasks

When implementing any task, follow these rules:

1. **Import existing modules directly.** The FastAPI backend runs in the same Python environment as the core pipeline. Import like: `from rag.script_writer import generate_script`.

2. **Use Celery for anything > 5 seconds.** Scraping, LLM generation, TTS, Veo, rendering, uploading — all go through Celery. Return the task ID immediately and let the frontend poll or use WebSocket.

3. **Never duplicate data.** The console reads from the same PostgreSQL tables the pipeline writes to. New tables are only for console-specific data (credentials, channels, user accounts).

4. **Encrypt secrets.** Platform credentials (client secrets, OAuth tokens) must be encrypted at rest using Fernet symmetric encryption. The encryption key lives in the `.env` file, never in the database.

5. **Audit everything.** Every write operation by an editor should create an `audit_log` entry: who did what, to which resource, at what time.

6. **Preserve auto mode.** The `batch_runner.py` and `daily_pipeline.py` still work unchanged. The console adds an alternative path where humans can intervene.

---

## Sprint 1 Tasks

### B-001: FastAPI Project Scaffolding

```
TASK: Create the FastAPI backend scaffolding for the AI Media Management Console.

CONTEXT:
- This is a new console added to an existing Python 3.11 project at the root directory
- Core pipeline modules exist at: scraper/, rag/, pipeline/, uploader/, feedback/, database/
- PostgreSQL is already running on :5432
- The console backend lives in console/backend/

CREATE THESE FILES:

1. console/backend/main.py
   - FastAPI app with title "AI Media Console API"
   - CORS middleware allowing localhost:5173 (Vite dev) and localhost:3000
   - Include all routers from console/backend/routers/ (don't fail if routers don't exist yet)
   - Mount /api prefix
   - Support /ws prefix for WebSocket endpoints
   - Lifespan event that logs "Console API started" and "Console API stopped"
   - GET /api/health → {"status": "ok", "timestamp": "..."}

2. console/backend/config.py
   - Settings class using pydantic-settings, reads from .env:
     DATABASE_URL (str, default "postgresql://localhost:5432/ai_media")
     REDIS_URL (str, default "redis://localhost:6379/0")
     JWT_SECRET (str, required)
     JWT_ALGORITHM (str, default "HS256")
     JWT_EXPIRE_MINUTES (int, default 1440)
     FERNET_KEY (str, required — for encrypting OAuth secrets)
     CORE_PIPELINE_PATH (str, default ".." — path to root project for imports)
   - Add CORE_PIPELINE_PATH to sys.path so we can import core modules

3. console/backend/__init__.py (empty)
4. console/backend/routers/__init__.py (empty)
5. console/backend/services/__init__.py (empty)
6. console/backend/models/__init__.py (empty)
7. console/backend/schemas/__init__.py (empty)

DEPENDENCIES: fastapi, uvicorn, pydantic-settings, python-dotenv
```

---

### B-002: JWT Auth Module

```
TASK: Create JWT authentication with role-based access control.

CONTEXT:
- Console backend at console/backend/
- PostgreSQL table console_users: (id SERIAL PK, username TEXT UNIQUE, email TEXT UNIQUE,
  password_hash TEXT, role TEXT CHECK ('admin','editor'), created_at TIMESTAMP, last_login TIMESTAMP)
- Two roles: admin (full access) and editor (no system/credentials access)

CREATE THESE FILES:

1. console/backend/auth.py
   Functions:
   - hash_password(password: str) → str (bcrypt)
   - verify_password(plain: str, hashed: str) → bool
   - create_access_token(user_id: int, role: str) → str (JWT with exp)
   - decode_token(token: str) → dict (raises HTTPException 401 if invalid/expired)
   - get_current_user: FastAPI Depends that extracts user from Authorization Bearer header
   - require_admin: FastAPI Depends that checks role == 'admin'
   - require_editor_or_admin: FastAPI Depends that checks role in ('admin', 'editor')

2. console/backend/routers/auth.py
   Endpoints:
   - POST /api/auth/login
     Body: {username, password}
     Returns: {access_token, token_type: "bearer", user: {id, username, email, role}}
     Updates last_login timestamp
   - POST /api/auth/register (requires admin role)
     Body: {username, email, password, role}
     Returns: {user: {id, username, email, role}}
   - GET /api/auth/me (requires any authenticated user)
     Returns: {id, username, email, role}

DEPENDENCIES: python-jose[cryptography], passlib[bcrypt]
```

---

### B-005: Scraper Service

```
TASK: Create the ScraperService that manages scraper sources and queries scraped video data.

CONTEXT:
- Existing viral_videos table: id TEXT PK, platform TEXT, region TEXT, niche TEXT,
  play_count BIGINT, engagement_rate FLOAT, script_text TEXT, hook_text TEXT,
  cta_text TEXT, is_indexed BOOLEAN, scraped_at TIMESTAMP
- Existing scraper modules:
  scraper/tiktok_research_api.py (primary)
  scraper/tiktok_playwright.py (backup)
  scraper/apify_scraper.py (backup)
  scraper/trend_analyzer.py
- Scraper source configs stored in config/scraper_sources.yaml (create this file too)
- ChromaDB indexer at vector_db/indexer.py (has function index_videos(video_ids))

CREATE:

1. config/scraper_sources.yaml
   ```yaml
   sources:
     - id: tiktok_research
       name: "TikTok Research API"
       type: tiktok
       module: scraper.tiktok_research_api
       function: scrape
       status: active
     - id: tiktok_playwright
       name: "TikTok Playwright"
       type: tiktok
       module: scraper.tiktok_playwright
       function: scrape
       status: standby
     - id: tiktok_apify
       name: "TikTok Apify"
       type: tiktok
       module: scraper.apify_scraper
       function: scrape
       status: standby
     - id: youtube_trending
       name: "YouTube Trending"
       type: youtube
       module: null
       function: null
       status: planned
     - id: news_vnexpress
       name: "VnExpress News"
       type: news
       module: null
       function: null
       status: planned
   ```

2. console/backend/services/scraper_service.py
   class ScraperService:
     def __init__(self, db: Session):
       self.db = db

     def list_sources() → list[dict]
       Read from config/scraper_sources.yaml, return all sources

     def update_source_status(source_id: str, status: str) → dict
       Update status in YAML file (active/standby/planned)

     def trigger_scrape(source_id: str) → str (Celery task ID)
       Look up source config, dispatch Celery task that calls the source's module.function
       Return task ID immediately

     def list_videos(
       source: str | None,
       niche: str | None,
       region: str | None,
       sort_by: str = "play_count",  # play_count | engagement_rate | likes
       sort_dir: str = "desc",
       page: int = 1,
       per_page: int = 50
     ) → {items: list, total: int, page: int, pages: int}
       Build SQLAlchemy query with optional WHERE clauses + ORDER BY + LIMIT/OFFSET

     def index_to_chromadb(video_ids: list[str]) → int
       Call vector_db/indexer.py for each video, return count indexed
       Update is_indexed=True on each video

3. console/backend/routers/scraper.py
   - GET  /api/scraper/sources → list_sources()
   - PATCH /api/scraper/sources/{id}/status → body: {status} → update_source_status()
   - POST /api/scraper/run → body: {source_id} → trigger_scrape()
   - GET  /api/scraper/videos?source=X&niche=X&region=X&sort_by=X&page=1&per_page=50
   - POST /api/scraper/videos/index → body: {video_ids: [...]} → index_to_chromadb()
```

---

### B-007: Script Service

```
TASK: Create the ScriptService for managing LLM-generated scripts with editorial workflow.

CONTEXT:
- Table generated_scripts: topic TEXT, niche TEXT, template TEXT, script_json JSONB,
  upload_ids JSONB, performance_48h JSONB, performance_score FLOAT, is_successful BOOLEAN
  ADDED: status TEXT, editor_notes TEXT, edited_by INT, approved_at TIMESTAMP

- script_json schema:
  {
    meta: {topic, niche, region, template},
    video: {title, description, hashtags[], total_duration, music_mood, music_track, voice, voice_speed},
    scenes: [{id, type, duration, narration, text_overlay, overlay_style, visual_hint,
              transition_out, music_volume}],
    cta: {text, start_time, duration},
    affiliate: {product, link, mention_at}
  }

- Script generation module: rag/script_writer.py
  Function: generate_script(topic: str, niche: str, template: str) → dict (script_json)

- Status workflow: draft → pending_review → approved → producing → completed
                   draft ← rejected (from pending_review)
                   editing (when editor modifies an approved script)

CREATE console/backend/services/script_service.py:

class ScriptService:
    def __init__(self, db: Session):

    def list_scripts(
        status: str | None,
        niche: str | None,
        page: int = 1,
        per_page: int = 20
    ) → paginated list of scripts (without full script_json, just meta + status)

    def get_script(script_id: int) → full script with script_json parsed

    def update_script(script_id: int, script_json: dict, editor_notes: str | None, user_id: int) → updated
        - Validate script_json has required keys (meta, video, scenes)
        - Validate each scene has required fields
        - Update status to 'editing' if it was 'approved'
        - Recalculate video.total_duration from sum of scene durations
        - Set edited_by = user_id

    def approve_script(script_id: int, user_id: int) → updated
        - Only works if status is 'pending_review' or 'editing'
        - Set status='approved', approved_at=now()
        - Log to audit_log

    def reject_script(script_id: int, user_id: int) → updated
        - Set status='draft'
        - Log to audit_log

    def generate_script(
        topic: str, niche: str, template: str,
        source_video_ids: list[str] | None,
        user_id: int
    ) → new script record
        - If source_video_ids provided, fetch those videos from viral_videos
          and pass them as context to the RAG pipeline
        - Call rag/script_writer.py generate_script()
        - Store result in generated_scripts with status='draft'
        - Return the new script

    def regenerate_script(script_id: int) → updated
        - Read existing topic/niche/template from the script
        - Call generate_script() with same params
        - Overwrite script_json, set status='draft'

    def regenerate_scene(script_id: int, scene_index: int) → updated
        - Get the existing script
        - Call LLM (via llm_router) to regenerate ONLY that scene's narration + visual_hint
        - Update just that scene in script_json
        - Keep all other scenes and editor edits intact

CREATE console/backend/routers/scripts.py:
    GET    /api/scripts?status=X&niche=X&page=1&per_page=20
    POST   /api/scripts/generate  body: {topic, niche, template, source_video_ids?}
    GET    /api/scripts/{id}
    PUT    /api/scripts/{id}      body: {script_json, editor_notes?}
    PATCH  /api/scripts/{id}/approve
    PATCH  /api/scripts/{id}/reject
    POST   /api/scripts/{id}/regenerate
    POST   /api/scripts/{id}/scenes/{n}/regenerate
```

---

### B-010: Production Service

```
TASK: Create the ProductionService for scene-level video editing.

CONTEXT:
- video_assets table: id SERIAL PK, file_path TEXT, source TEXT ('pexels'|'veo'|'manual'),
  keywords TEXT[], niche TEXT[], duration_s FLOAT, resolution TEXT, quality_score FLOAT,
  usage_count INT
- Pipeline modules:
  pipeline/tts_engine.py — generate_tts(text, voice, speed) → wav_path
  pipeline/asset_resolver.py — resolve_asset(visual_hint, niche, duration) → clip_path
  pipeline/asset_db.py — search(keywords, niche, min_duration) → Asset | None
  pipeline/veo_prompt_builder.py — build_veo_prompt(scene, meta) → prompt_str
  pipeline/overlay_builder.py — build_overlay(text, style) → png_path
  pipeline/composer.py — compose(script_json) → raw_video_path
  pipeline/renderer.py — render(raw_path) → final_path

CREATE console/backend/services/production_service.py:

class ProductionService:
    def search_assets(
        keywords: list[str] | None,
        niche: str | None,
        source: str | None,
        min_duration: float | None,
        page: int = 1,
        per_page: int = 20
    ) → paginated asset list with thumbnail URLs

    def replace_scene_asset(script_id: int, scene_index: int, asset_id: int) → updated script
        - Fetch asset from video_assets
        - Update scene's visual_hint with asset's keywords
        - Store asset_id reference in scene
        - Increment asset's usage_count
        - Set script status to 'editing'

    def regenerate_scene_tts(script_id: int, scene_index: int) → Celery task ID
        - Get scene narration text + voice config from script
        - Dispatch Celery task that calls tts_engine.py
        - Task stores the wav and updates scene state

    def generate_scene_veo(script_id: int, scene_index: int) → Celery task ID
        - Build Veo prompt from scene + meta
        - Dispatch Celery task that calls Veo API
        - Task stores clip in video_assets (write-back) and links to scene

    def start_production(script_id: int) → Celery task ID
        - Validate script status is 'approved' or 'editing'
        - Set status to 'producing'
        - Dispatch Celery task chain:
          1. Per-scene parallel: TTS + Asset Resolve + Overlay
          2. Compose (MoviePy)
          3. Caption Gen (Whisper)
          4. Render (ffmpeg NVENC)
          5. Quality Validation
          6. Set status to 'completed', create upload_schedule entry
```

---

### B-019: Upload Service

```
TASK: Create the UploadService for managing production videos, multi-channel targeting, and upload dispatching.

CONTEXT:
- New tables: channels, upload_targets, template_channel_defaults, platform_credentials
- Uploader modules:
  uploader/youtube_uploader.py — upload_to_youtube(video_path, metadata, credentials) → youtube_id
  uploader/tiktok_uploader.py — upload_to_tiktok(video_path, metadata, credentials) → tiktok_id
- Template default channel mapping:
  tiktok_viral → [ch_4, ch_5]    (TikTok channels)
  tiktok_30s → [ch_4]
  youtube_clean → [ch_1, ch_2]   (YouTube channels)
  shorts_hook → [ch_1, ch_3]

CREATE console/backend/services/upload_service.py:

class UploadService:
    def list_videos(
        platform: str | None,   # filter by target channel platform
        status: str | None,
        page: int = 1,
        per_page: int = 20
    ) → paginated list
        - Join generated_scripts with upload_targets and channels
        - Each video includes: id, title, template, niche, status, target_channels[],
          scheduled_at, views, duration

    def delete_video(video_id: str) → None
        - Delete from upload_targets
        - Soft-delete or mark as deleted in generated_scripts

    def get_default_channels(template: str) → list[int]
        - Query template_channel_defaults WHERE template=X

    def set_target_channels(video_id: str, channel_ids: list[int]) → updated
        - Delete existing upload_targets for this video
        - Insert new rows for each channel_id with status='pending'
        - If channel_ids is empty, auto-apply template defaults

    def trigger_upload(video_id: str) → list[str] (Celery task IDs)
        - For each upload_target WHERE video_id=X AND status='pending':
          - Look up channel → credential
          - Decrypt OAuth tokens using Fernet
          - Dispatch Celery task:
            If channel.platform == 'youtube': call youtube_uploader.py
            If channel.platform == 'tiktok': call tiktok_uploader.py
          - Set upload_target status='uploading'
        - Return list of task IDs

    def upload_all_ready() → int (count dispatched)
        - Find all videos where script status='completed' and has upload_targets with status='pending'
        - Call trigger_upload for each
        - Return count
```

---

### F-005: Scraper Page

```
TASK: Create the Scraper page for the React frontend.

CONTEXT:
- React 18 + Tailwind CSS dark theme
- API base URL: /api (proxied by Vite dev server)
- Shared components available in components/: Card, Badge, Button (variants: default, primary,
  danger, success, ghost, accent), Modal, Select, Input, StatBox, Tabs
- API client available: api/client.js with fetchApi(url, options) that injects JWT

ENDPOINTS USED:
  GET  /api/scraper/sources
  GET  /api/scraper/videos?source=X&niche=X&region=X&sort_by=X&page=1&per_page=50
  POST /api/scraper/run {source_id}
  POST /api/scraper/videos/index {video_ids: [...]}
  POST /api/scripts/generate {topic, niche, template, source_video_ids}

CREATE pages/ScraperPage.jsx:

SECTION 1 — Stats Row:
  5 StatBox components in a flex row:
  - Total Scraped (from API total count)
  - Indexed (count where is_indexed=true)
  - Selected (local state: selectedIds.size)
  - Avg ER (computed from fetched data)
  - Active Sources (count where status='active')

SECTION 2 — Source Manager Card:
  - Title: "Scraper Sources" with actions: [Manage Sources] [Run Scrape Now]
  - Body: flex row of source badges (icon + name + status indicator)
  - Manage Sources button opens Modal with:
    - Per source: icon, name, type, status dropdown (active/standby/planned), Run button if active
    - Footer: "Add Custom Source (coming soon)" disabled button

SECTION 3 — Scraped Videos Card:
  - Title: "Scraped Videos" with filter dropdowns in actions area:
    Source (All Sources + active/standby sources), Niche (7 options), Region (5 options),
    Sort (Views ↓, ER ↓, Likes ↓)
  - Action bar below title: Select All checkbox | "N selected" text | Generate Script button | Index button
  - Scrollable table (max-height 440px):
    Columns: checkbox(32px) | hook text + author + tags(1fr) | views(90px) | ER%(80px) | niche badge(70px) | region(80px) | indexed(60px)
    Row click toggles selection, selected rows get blue-tinted background
  - Generate Script button (disabled if 0 selected) opens Topic Creation Modal

SECTION 4 — Topic Creation Modal:
  - Title: "Create Script from N Videos"
  - Selected videos preview: up to 6 tags showing truncated hook text
  - Inputs: Topic text input, Niche dropdown, Template dropdown
  - Buttons: Cancel | Generate Script with LLM (calls POST /api/scripts/generate)
  - On success: clear selection, close modal, show toast "Script generated → Scripts tab"

STATE:
  - selectedIds: Set<string>
  - sourceFilter, nicheFilter, regionFilter, sortBy: strings
  - videos: from API (with SWR or useEffect)
  - sources: from API
  - topicModal: boolean
  - newTopic, newNiche, newTemplate: strings
  - sourceManagerModal: boolean
```

---

### F-015: ChannelPicker Component

```
TASK: Create a reusable ChannelPicker component for multi-channel selection.

CONTEXT:
- Used in the Videos sub-tab of the Uploads page
- Each production video can target multiple channels
- Only shown for videos NOT in 'uploading' or 'published' status
- Channels fetched from GET /api/channels

PROPS:
  channels: Channel[]        — all available channels
  platformAuths: Platform[]  — platform configs (for icon/color)
  selected: string[]         — currently selected channel IDs
  onChange: (ids: string[]) → void
  notify: (msg: string) → void

BEHAVIOR:
  - Renders a small ghost button: [edit icon] "Target"
  - On click: opens a dropdown positioned below the button
  - Dropdown contents:
    - Header: "Select Target Channels" (uppercase, small, gray)
    - List of active channels, each with:
      - Checkbox (blue filled if selected, gray border if not)
      - Platform icon (colored)
      - Channel name (bold)
      - Platform name + subscriber count (small gray)
    - Click a channel row → toggle selection
  - Footer: three small buttons in a row:
    - "All" → select all active channels
    - "None" → deselect all
    - "Done" → close dropdown, show toast "N channels targeted"
  - Click outside dropdown → close (useRef + useEffect with mousedown listener)

IMPORTANT:
  - Position: absolute, z-index: 100 so it floats above the table
  - Min-width: 220px
  - Dark theme: bg matches Card background, border matches theme
  - Transition on hover for each channel row
```

---

## Sprint 2–4 Tasks

The remaining tasks follow the same pattern. For each, provide:
- The exact table schemas and existing module paths
- The function signatures the service should implement
- The API endpoints the router should expose
- The UI layout and state management for frontend pages

Key tasks to prompt individually:

| Task | Summary |
|------|---------|
| B-012 | PipelineService — job management, Celery integration with batch_runner.py |
| B-013 | Pipeline WebSocket — broadcast job status changes to connected clients |
| B-015 | CredentialService — Fernet encryption, OAuth URL builder, token refresh |
| B-021 | OAuth callback — exchange auth code for tokens, store encrypted |
| B-022 | Token auto-refresh — Celery beat task, check expiry, refresh proactively |
| F-008 | ProductionPage — timeline visualization, scene card expand/collapse |
| F-010 | AssetBrowser — thumbnail grid, search, click-to-replace |
| F-012 | useWebSocket hook — auto-reconnect, message parsing, state dispatch |
| F-016 | Auth credentials UI — expandable cards, secret fields, OAuth flow |
| F-023 | Login page — JWT storage, role-based visibility |
| D-001 | Docker setup — multi-stage builds, compose with Redis |

For any of these, ask the AI to implement by providing:
1. This document as context
2. The architecture doc (02_architecture_design.md) for system-level understanding
3. The specific task description from the implementation plan (03_implementation_plan.md)

---

*AI Task Guide v1.0 — April 2026*
