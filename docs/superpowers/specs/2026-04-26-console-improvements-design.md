# Console Improvements — Design Spec
**Date:** 2026-04-26  
**Status:** Approved

---

## Overview

Seven improvements to the AI Media Automation Management Console:

1. Remove obsolete Videos feature and ChromaDB references from Scraper
2. Remove TikTok/YouTube scraper sources and their backend code
3. Add new Niches tab (first nav item) with full CRUD
4. Add new Composer page for free-form script generation
5. Enrich Production page scene cards and script header with more detail
6. Add live log streaming per job in Pipeline tab
7. Simplify LLM tab to Gemini-only with dynamic model selection

---

## Section 1 — Removals & Cleanup

### 1a. Scraper Page — Remove Videos

- Remove the `Videos` content tab, its panel, filters, selection state, `selectAll/deselectAll`, `handleIndex`, and all ChromaDB-related UI.
- Remove stat boxes: `Videos`, `Indexed (ChromaDB)`, `Avg ER`.
- Keep: `Articles` count stat, `Active Sources` stat.
- The Scraper page becomes articles-only — no content tabs, just the articles list directly under the header.
- Remove `scraperApi.getVideos()` and `scraperApi.indexVideos()` from `client.js`.
- Remove `GET /api/scraper/videos` endpoint and its service method from `scraper_service.py`. Leave the `ViralVideo` DB model intact — it is part of the shared pipeline schema.

### 1b. Manage Scraper Sources — Remove TikTok & YouTube

**`config/scraper_sources.yaml`** — delete entries:
- `tiktok_research`
- `tiktok_playwright`
- `tiktok_apify`
- `youtube_trending`

Keep: `news_vnexpress`, `news_tinhte`, `news_cnn`.

**`scraper/`** — delete files:
- `tiktok_research_api.py`
- `tiktok_playwright.py`
- `tiktok_selenium.py`
- `tiktok_browser_common.py`
- `apify_scraper.py`

Keep: `base_scraper.py`, `vnexpress_scraper.py`, `tinhte_scraper.py`, `cnn_scraper.py`, `trend_analyzer.py`, `main.py`.

The Source Manager modal in `ScraperPage` keeps its current layout — fewer rows because the YAML now only has news sources.

### 1c. LLM Service — Remove Multi-Mode Routing

- `MODES` dict removed from `llm_service.py`; replaced with `PROVIDER_REGISTRY` (see Section 6).
- `set_mode()` removed; replaced with `set_model(provider, model_name)`.
- `rag/llm_router.py` already Gemini-only — no changes needed.

---

## Section 2 — Niches Tab

### Navigation

- New tab `niches` inserted as the **first** item in `ALL_TABS` in `App.jsx`.
- Roles: `['admin', 'editor']`.
- Icon: tag/label SVG.
- New page: `console/frontend/src/pages/NichesPage.jsx`.

### Database

New table `niches`:

| Column | Type | Notes |
|---|---|---
| `id` | serial PK | |
| `name` | varchar(100) | unique, not null |
| `created_at` | timestamptz | default now() |

Alembic migration: `console/backend/alembic/versions/005_niches.py`

Seeded with: `lifestyle`, `fitness`, `finance`, `beauty`, `food`, `tech`, `education`.

### Backend

**Service:** `console/backend/services/niche_service.py`
- `list_niches() → list[Niche]` — all niches sorted by name.
- `create_niche(name) → Niche` — validates uniqueness, audit logged.
- `delete_niche(id) → None` — validates no active scripts use this niche, audit logged.
- `get_or_create(name) → Niche` — used by Composer/Generate modal for inline creation.

**Router:** `console/backend/routers/niches.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/niches` | editor+ | returns `[{id, name, script_count}]` |
| `POST` | `/api/niches` | admin | body `{name}` |
| `DELETE` | `/api/niches/{id}` | admin | 409 if niche in use |

**`client.js`:** Add `nichesApi` with `list()`, `create(name)`, `remove(id)`.

### NichesPage UI

- Page header: "Niches" + "Add Niche" button (admin only, hidden for editor role).
- Stats row: total niche count, most-used niche (by script count).
- List/table of niches: niche name, script count, delete button (admin only; disabled + tooltip if `script_count > 0`).
- "Add Niche" opens a small modal: text input + Save. Client-side validation: non-empty, no leading/trailing whitespace, no duplicates (checked against loaded list).

### Niche Combobox (shared component)

Replace all `<Select>` niche dropdowns with a new `NicheCombobox` component:
- Shows a dropdown of existing niches from `GET /api/niches`.
- Accepts free-text input.
- If typed value doesn't match any existing niche, shows "+ Add '[value]'" option at the bottom of the dropdown.
- On selecting the add option, calls `nichesApi.create(name)` (or `get_or_create` backend call), then selects the new niche.
- Used in: Generate Script modal (Scraper), Composer page.
- The hardcoded `NICHES` array in `ScraperPage.jsx` is deleted.

---

## Section 3 — Composer Page

### Navigation

- New tab `composer` added to `ALL_TABS` after `Niches`.
- Roles: `['admin', 'editor']`.
- Icon: pencil/edit SVG.
- New page: `console/frontend/src/pages/ComposerPage.jsx`.

### UI Layout

Single-column form card:

| Field | Control | Notes |
|---|---|---|
| Content / Idea | `<Textarea>` 10 rows | placeholder: "Paste a full article, write a topic sentence, or describe a general idea…" |
| Expand idea first | Checkbox | when checked, triggers a two-step flow |
| Niche | `NicheCombobox` | fetched from `/api/niches` |
| Template | `<Select>` | existing `TEMPLATES` list |
| Language | `<Select>` | Vietnamese / English |

**Single-step flow (expand unchecked):**
- "Generate Script" button calls `POST /api/scripts/generate` with `raw_content`, `expand_first: false`.
- Topic auto-derived from first 120 chars of input.
- Toast on success: "Script queued — check the Scripts tab."

**Two-step flow (expand checked):**
1. "Expand & Preview" button calls `POST /api/scripts/expand` (inline, not queued). Shows spinner "Expanding…"
2. Result card appears: "Expanded Outline" — editable `<Textarea>` pre-filled with Gemini's expansion.
3. "Generate Script from Outline" button calls `POST /api/scripts/generate` with the (possibly edited) outline as `raw_content`, `expand_first: false`.

### Backend Changes

**`POST /api/scripts/generate` schema extension** (`schemas/script.py`):
```
raw_content: str | None = None
```
Note: `expand_first` is resolved entirely on the frontend. By the time `generate` is called, the content is always final — the Celery task does not need this flag.

**New endpoint:** `POST /api/scripts/expand`
- Body: `{content: str}`
- Response: `{expanded_outline: str}`
- Runs inline (not Celery) — single Gemini call with a prompt like: "Expand this idea into a detailed video script outline with hook, key points, and call to action: {content}"
- No DB write.

**`script_service.py` / `script_tasks.py`:**
- If `raw_content` is present and `source_article_id` is None, prompt builder uses `raw_content` directly as the content source.
- `expand_first` is resolved on the frontend before the task is queued — the Celery task always receives the final content in `raw_content`; no `expand_first` flag is sent to the backend generate endpoint.

---

## Section 4 — Production Page: Richer Scene Detail

### Script Header Card — additions

- **Render status badge** — latest pipeline job status for this script (`rendering`, `render_done`, `render_failed`). Queried from `/api/pipeline/jobs?script_id={id}&job_type=render&per_page=1`.
- **Output file path** — monospace, truncated, shown if render complete.
- **Hook text** — `script_json.video.hook` field if present.

### Scene Card Header Row — additions

- **Asset indicator dot** — green if `scene.asset_id` set, grey otherwise.
- **TTS indicator dot** — green if `scene.tts_audio_url` set, grey otherwise.
- Provides at-a-glance readiness without expanding each card.

### Scene Card Expanded — Left Column (Visual)

- Replace empty placeholder with `<img src={scene.asset_thumbnail_url} />` if available; falls back to "Asset #N" text link.
- **Asset source badge**: `DB` / `Pexels` / `Veo` from `scene.asset_source`.
- **Clip duration label**: `{scene.asset_duration}s clip`.
- Keep existing Replace + Veo Gen buttons.
- Add **Pexels Search** button (opens AssetBrowser with Pexels tab active).

### Scene Card Expanded — Right Column (Audio)

- Add **TTS audio player**: `<audio controls src={scene.tts_audio_url} />` if `tts_audio_url` exists; "No audio yet" placeholder if not.
- Keep Narration textarea, Text overlay input, Regenerate TTS button.

### Sidebar — readiness indicator

- Below each script entry in the sidebar: `{ready}/{total} scenes ready` in `text-[#5a5a70] font-mono text-[10px]`.
- A scene is "ready" if it has both `asset_id` and `tts_audio_url` set.

---

## Section 5 — Pipeline Tab: Live Logs per Job

### Backend

**Redis log storage** (in `pipeline_service.py`):
- Shared helper: `emit_log(job_id, level, msg)` — pushes `{ts, level, msg}` JSON to `pipeline:job:{id}:logs` Redis list, then `LTRIM` to last 200 entries. If Redis is unavailable, fails silently (logs to Python logger only) so task execution is never blocked.
- All Celery task wrappers call `emit_log` at key steps.

**WebSocket broadcaster** (`ws/pipeline_ws.py`):
- Existing every-2s `pipeline_update` message extended with `job_logs: {job_id: [log_line, ...]}`.
- Only includes logs for jobs currently in `running` state (avoids message bloat).

**New endpoint:** `GET /api/pipeline/jobs/{id}/logs`
- Reads full log list from Redis for completed/failed jobs.
- Returns `{job_id, logs: [{ts, level, msg}]}`.

### Frontend — `PipelinePage.jsx`

**`JobRow` expanded section:**
- New **log panel** below existing metadata fields (same style as Scraper's live log panel: `bg-[#0d0d0f]`, monospace `text-xs`, colour-coded by level, timestamp prefix, auto-scroll).
- Running jobs: log lines fed from `pipeline_update` WS message, filtered by `job.id`. Auto-scroll on new lines via `useEffect` + `logBoxRef`.
- Completed/failed jobs: "View Logs" button triggers `GET /api/pipeline/jobs/{id}/logs` once on click; renders static log panel.

**`handleWsMessage`:**
- Extended to merge `job_logs` map into local job state: `setJobs(prev => prev.map(j => job_logs[j.id] ? {...j, live_logs: job_logs[j.id]} : j))`.

---

## Section 6 — LLM Tab: Gemini-Only with Dynamic Model Selection

### Backend — `llm_service.py`

Replace `MODES` with `PROVIDER_REGISTRY`:

```python
PROVIDER_REGISTRY = {
    "gemini": {
        "label": "Google Gemini",
        "description": "Cloud LLM via Google AI Studio API.",
        "fetch_models_method": "_fetch_gemini_models",
    },
    # Extensibility: add "ollama", "openai", etc. here
}
```

**Methods:**
- `get_status() → dict` — returns `{provider, model, providers_metadata, gemini: {available, models[], api_key_set}, timestamp}`.
- `set_model(provider, model_name) → dict` — validates provider in registry, writes `LLM_PROVIDER` + `LLM_MODEL` to env, returns updated status.
- `_fetch_gemini_models() → list[str]` — calls `google.generativeai.list_models()`, filters to `generateContent`-capable models, returns name list sorted alphabetically.
- `get_quota() → dict` — returns Gemini rate-limiter usage from `rag/rate_limiter.py`.

**Router — `llm.py`:**
- `GET /api/llm/status` — unchanged path, new response shape.
- `PUT /api/llm/model` — replaces `PUT /api/llm/mode`. Body: `{provider: str, model: str}`.
- `GET /api/llm/quota` — unchanged.

### Frontend — `LLMPage.jsx`

Remove `ModeCard` and `ProviderCard` components. New three-card layout:

**Card 1 — Active Model**
- Provider name ("Google Gemini") + availability dot (green/red).
- API key status: "Set ✓" (green) or "Not set ✗" (red).
- Model `<Select>` dropdown populated from `status.gemini.models`. On change → `PUT /api/llm/model`. Loading spinner during save.
- Current model shown as monospace note below dropdown.

**Card 2 — Usage / Quota**
- RPD used / RPD limit, RPM used / RPM limit from `GET /api/llm/quota`.
- "Refresh" button.

**Card 3 — Future Providers** *(muted/informational)*
- Single muted text: "Additional providers can be configured in `pipeline.env`."

---

## File Change Summary

### New files
| File | Purpose |
|---|---|
| `console/frontend/src/pages/NichesPage.jsx` | Niches management UI |
| `console/frontend/src/pages/ComposerPage.jsx` | Composer UI |
| `console/frontend/src/components/NicheCombobox.jsx` | Shared niche combobox |
| `console/backend/routers/niches.py` | Niches API router |
| `console/backend/services/niche_service.py` | Niches CRUD service |
| `console/backend/alembic/versions/005_niches.py` | DB migration |
| `docs/superpowers/specs/2026-04-26-console-improvements-design.md` | This spec |

### Modified files
| File | Change |
|---|---|
| `console/frontend/src/App.jsx` | Add Niches + Composer tabs |
| `console/frontend/src/api/client.js` | Add `nichesApi`; remove `getVideos`, `indexVideos` |
| `console/frontend/src/pages/ScraperPage.jsx` | Remove Videos tab + ChromaDB UI |
| `console/frontend/src/pages/ComposerPage.jsx` | New |
| `console/frontend/src/pages/ProductionPage.jsx` | Richer scene cards + header |
| `console/frontend/src/pages/PipelinePage.jsx` | Live log panel per job |
| `console/frontend/src/pages/LLMPage.jsx` | Gemini-only redesign |
| `console/backend/main.py` | Register niches router |
| `console/backend/routers/llm.py` | Replace mode endpoint with model endpoint |
| `console/backend/services/llm_service.py` | Replace MODES with PROVIDER_REGISTRY |
| `console/backend/services/pipeline_service.py` | Add `emit_log`, Redis log storage |
| `console/backend/ws/pipeline_ws.py` | Include job_logs in WS broadcast |
| `console/backend/schemas/script.py` | Add `raw_content`, `expand_first` fields |
| `console/backend/services/script_service.py` | Handle `raw_content` source in generation |
| `console/backend/routers/scripts.py` | Add `/expand` endpoint |
| `config/scraper_sources.yaml` | Remove TikTok + YouTube entries |
| `rag/llm_router.py` | No changes needed (already Gemini-only) |

### Deleted files
| File | Reason |
|---|---|
| `scraper/tiktok_research_api.py` | TikTok source removed |
| `scraper/tiktok_playwright.py` | TikTok source removed |
| `scraper/tiktok_selenium.py` | TikTok source removed |
| `scraper/tiktok_browser_common.py` | TikTok source removed |
| `scraper/apify_scraper.py` | TikTok/Apify source removed |
