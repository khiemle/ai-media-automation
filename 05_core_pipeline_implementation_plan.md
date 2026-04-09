# AI Media Automation — Core Pipeline Implementation Plan

> **Version:** 1.0 | **Date:** April 2026
> **Phase:** Post-Console — building the core automation pipeline
> **Duration:** 4 weeks (1 engineer, ~35h/week)
> **Total Estimated Hours:** ~140h

---

## Context

The Management Console (all 8 tabs) is complete and provides the human control layer. The next phase builds the **core pipeline** — the 6-layer automation engine that the console manages. All console Celery tasks are currently stubs; all pipeline imports are wrapped in `try/except ImportError`. This plan replaces those stubs with real implementations.

### Pipeline layers (build order — bottom-up)

```
Layer 1 — database/       Models + ChromaDB setup
Layer 2 — scraper/        TikTok data collection
Layer 3 — vector_db/      ChromaDB indexer + retriever
Layer 4 — rag/            LLM router + RAG script generation
Layer 5 — pipeline/       TTS + asset resolution + compose + render
Layer 6 — uploader/       YouTube + TikTok distribution
Layer 7 — feedback/       Metrics tracking + reindexing
Layer 8 — batch_runner    Cron orchestration
```

### Integration points with console

The console's Celery tasks call these exact function signatures:
- `scraper.main.run_scrape(source_ids)` → dispatched from `tasks/scraper_tasks.py`
- `rag.script_writer.write_script(topic, niche, template, video_ids)` → `tasks/script_tasks.py`
- `pipeline.tts_engine.generate_tts(text, voice, speed)` → `tasks/production_tasks.py`
- `pipeline.composer.compose_video(script_id)` → `tasks/production_tasks.py`
- `uploader.youtube_uploader.upload(video_path, metadata, credentials)` → `tasks/upload_tasks.py`

---

## 1. Timeline Overview

```
Week 1 — database + scraper + vector_db
Week 2 — rag (LLM router + script generation)
Week 3 — pipeline (production: TTS + assets + compose + render)
Week 4 — uploader + feedback + batch_runner + integration testing
```

---

## 2. Prerequisites (Day 0)

| Task | Est. | Notes |
|------|------|-------|
| Install Ollama + pull Qwen2.5 7B | 30m | `ollama pull qwen2.5:7b` |
| Install ChromaDB | 15m | `pip install chromadb` |
| Install Kokoro ONNX + model file | 45m | `kokoro.onnx` → `models/kokoro/` |
| Install Whisper | 15m | `pip install openai-whisper` |
| Install MoviePy 2.x + ffmpeg | 30m | `pip install moviepy`, `brew install ffmpeg` |
| Install Pillow, opencv-python | 10m | `pip install pillow opencv-python` |
| Verify NVENC support | 15m | `ffmpeg -encoders \| grep nvenc` |
| Create asset directories | 10m | `/assets/video_db/{pexels,veo,manual}/`, `/assets/output/` |
| Add new deps to `console/requirements.txt` | 15m | chromadb, kokoro, whisper, moviepy, pillow |
| **Total** | **~3h** | |

---

## 3. Sprint 1 — Week 1: Database + Scraper + Vector DB

### Backend Tasks

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-001 | `database/models.py` — SQLAlchemy models: ViralVideo, GeneratedScript, VideoAsset, ViralPattern (all columns matching architecture spec, sharing the PostgreSQL instance with console) | 4h | — | `database/models.py` |
| P-002 | `database/connection.py` — SQLAlchemy engine + SessionLocal factory, reads `DATABASE_URL` from `.env` | 1h | P-001 | `database/connection.py` |
| P-003 | `database/setup_chromadb.py` — initialize ChromaDB client, create 3 collections: `viral_scripts`, `viral_hooks`, `viral_patterns`. Include vietnamese-sbert embedding function config | 2h | — | `database/setup_chromadb.py` |
| P-004 | `scraper/base_scraper.py` — abstract adapter interface: `scrape(config: dict) → list[ScrapedVideo]`. `ScrapedVideo` dataclass with all fields from viral_videos table | 1h | P-001 | `scraper/base_scraper.py` |
| P-005 | `scraper/tiktok_research_api.py` — TikTok Research API adapter. Auth with app credentials, paginated video list, extract: author, play_count, like_count, share_count, comment_count, hook (first 3s caption), region, niche tags | 5h | P-004 | `scraper/tiktok_research_api.py` |
| P-006 | `scraper/tiktok_playwright.py` — Playwright headless browser fallback. Navigate TikTok trending pages, extract same fields. Stealth mode (randomize UA, delays). Rate limit: 1 req/2s | 6h | P-004 | `scraper/tiktok_playwright.py` |
| P-007 | `scraper/apify_scraper.py` — Apify Actor adapter (TikTok Scraper actor). Configure run input, poll for results, map to ScrapedVideo format | 3h | P-004 | `scraper/apify_scraper.py` |
| P-008 | `scraper/trend_analyzer.py` — analyze scraped videos, extract viral patterns per niche/region: top hooks (first 5 words), scene types, CTA phrases, hashtag clusters. Write to `viral_patterns` table | 4h | P-001 | `scraper/trend_analyzer.py` |
| P-009 | `scraper/main.py` — `run_scrape(source_ids: list[str])` orchestrator: load enabled sources from config, run each adapter, deduplicate by video_id, bulk insert to `viral_videos`, call trend_analyzer, return count | 2h | P-005, P-006, P-007, P-008 | `scraper/main.py` |
| P-010 | `vector_db/indexer.py` — `index_videos(video_ids)`: embed hook text via vietnamese-sbert, upsert to ChromaDB `viral_hooks` collection. `index_script(script_id)`: embed full script text → `viral_scripts`. `index_patterns(niche)` → `viral_patterns` | 4h | P-003 | `vector_db/indexer.py` |
| P-011 | `vector_db/retriever.py` — `retrieve_similar_scripts(topic, niche, k=5)` → list of script JSON strings. `retrieve_top_hooks(niche, k=10)` → hook strings. `retrieve_patterns(niche)` → pattern dict. All using ChromaDB `.query()` with metadata filters | 3h | P-010 | `vector_db/retriever.py` |

### Console integration (once P-009 exists)

Update `console/backend/tasks/scraper_tasks.py` to remove `try/except ImportError` guard:

```python
from scraper.main import run_scrape
```

### Sprint 1 Total: ~35h

---

## 4. Sprint 2 — Week 2: RAG + Script Generation

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-012 | `rag/rate_limiter.py` — per-model token bucket: `GeminiRateLimiter` (RPD=1500, RPM=15 free; 2M RPD paid), `OllamaRateLimiter` (local, unlimited). Thread-safe counters with Redis fallback for multi-worker | 3h | — | `rag/rate_limiter.py` |
| P-013 | `rag/llm_router.py` — 4 modes: `local` (Ollama only), `gemini` (Gemini only), `auto` (Gemini if quota available else Ollama), `hybrid` (per-template routing). `generate(prompt, mode, template) → str`. Wraps google-generativeai + httpx to Ollama `/api/generate` | 5h | P-012 | `rag/llm_router.py` |
| P-014 | `rag/prompt_builder.py` — `build_prompt(topic, niche, template, viral_scripts, top_hooks, patterns) → str`. Template-specific prompt variants: `tiktok_viral`, `tiktok_30s`, `youtube_clean`, `shorts_hook`. Includes few-shot examples + output schema instructions | 4h | P-011 | `rag/prompt_builder.py` |
| P-015 | `rag/script_validator.py` — validate LLM output: parse JSON, check required keys (topic, niche, template, scenes[]), validate each scene has narration/visual_hint/duration/type, check total duration 55–65s, return `(valid: bool, errors: list[str])` | 2h | — | `rag/script_validator.py` |
| P-016 | `rag/script_writer.py` — `write_script(topic, niche, template, video_ids) → dict`. Full flow: retrieve context → build prompt → route to LLM → validate → retry up to 3× on validation failure → return script dict. Also: `regenerate_scene(script_dict, scene_index) → dict` | 5h | P-013, P-014, P-015 | `rag/script_writer.py` |
| P-017 | Wire `rag/` into console: update `console/backend/tasks/script_tasks.py` to call `rag.script_writer.write_script()`. Update `console/backend/services/script_service.py` to remove mock LLM response | 2h | P-016 | Modified console tasks |
| P-018 | LLM mode config: add `LLM_MODE`, `GEMINI_API_KEY`, `OLLAMA_URL` to `console/.env.example` and `console/backend/config.py`. LLM Page in console now reads real mode from config | 1h | P-013 | Modified config.py, .env.example |
| P-019 | ChromaDB integration: update `console/backend/tasks/scraper_tasks.py` to call `vector_db.indexer.index_videos()` after scrape completes. Update `POST /api/scraper/videos/index` to call real indexer | 2h | P-010 | Modified scraper_tasks.py |

### Sprint 2 Total: ~24h

---

## 5. Sprint 3 — Week 3: Production Pipeline

### TTS + Assets

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-020 | `pipeline/tts_engine.py` — `generate_tts(text, voice="af_heart", speed=1.1) → wav_path`. Load Kokoro ONNX model from `models/kokoro/`. Text normalize (expand numbers, punctuation). Inference → resample to 44.1kHz mono. Pad/speed-adjust to match target duration. Write `audio_N.wav`. Fallback: silent track on error | 6h | — | `pipeline/tts_engine.py` |
| P-021 | `pipeline/asset_db.py` — `search_asset_db(keywords, niche, min_duration, aspect_ratio, min_score=0.72) → Asset|None`. Keyword overlap scoring query (see architecture spec). `write_to_asset_db(file_path, source, keywords, niche, ...) → int`. Uses shared DB session | 4h | P-001 | `pipeline/asset_db.py` |
| P-022 | `pipeline/pexels_client.py` — `search_and_download(keywords, niche, min_duration, scene_id) → clip_path`. Build query from keywords. `GET /videos/search?orientation=portrait`. Select best result. Download stream. Trim to duration. Resize+crop to 1080×1920 via ffmpeg. Write to asset DB | 4h | P-021 | `pipeline/pexels_client.py` |
| P-023 | `pipeline/veo_prompt_builder.py` — `build_veo_prompt(scene, meta) → str`. Assemble cinematic prompt with topic + visual_hint + narration[:120] + niche style directive. `VEO_STYLE_DIRECTIVES` per niche (finance/health/lifestyle/fitness/food) | 2h | — | `pipeline/veo_prompt_builder.py` |
| P-024 | `pipeline/veo_client.py` — `VeoBackend.generate_segment(prompt, scene_id, seg_idx) → clip_path`. Submit via `genai.Client().models.generate_videos()`, poll every 5s (timeout 180s), download, write each 8s segment to Asset DB. `generate_for_scene(prompt, scene) → clip_path`: calls n segments, concatenates, trims, resize+crop | 6h | P-021, P-023 | `pipeline/veo_client.py` |
| P-025 | `pipeline/asset_resolver.py` — `resolve_asset(scene, meta, mode="db_then_hybrid") → clip_path`. Main 3-tier resolver: Tier 1 Asset DB → Tier 2A Pexels or Tier 2B Veo based on mode + hybrid_rules. All assets write-back to DB | 4h | P-021, P-022, P-024 | `pipeline/asset_resolver.py` |

### Compose + Render

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-026 | `pipeline/overlay_builder.py` — `build_overlay(scene) → png_path`. 5 built-in overlay styles (gradient bar, minimal center, banner top, split lower-third, none). Pillow: load background frame, draw text with IBM Plex Sans/Mono, alpha composite. Write `overlay_N.png` | 3h | — | `pipeline/overlay_builder.py` |
| P-027 | `pipeline/caption_gen.py` — `generate_captions(audio_path) → srt_path`. Load Whisper base model. Transcribe audio. Write SRT with proper timestamps. Handle Vietnamese text | 2h | — | `pipeline/caption_gen.py` |
| P-028 | `pipeline/composer.py` — `compose_video(script_id) → raw_video_path`. Load script from DB. For each scene: run TTS + asset resolver + overlay builder in parallel threads (ThreadPoolExecutor). Once all scenes ready: MoviePy concatenate clips, layer overlays, mix narration audio + background music (0.08 vol), add transitions. Output `raw_video.mp4` | 8h | P-020, P-025, P-026 | `pipeline/composer.py` |
| P-029 | `pipeline/renderer.py` — `render_final(raw_video_path, srt_path) → final_path`. ffmpeg command: `h264_nvenc` encoder, 1080×1920, 30fps, CRF 23, AAC 192k, burn subtitles via `subtitles=` filter, merge audio. CPU fallback: `libx264` if NVENC unavailable. Output `video_final.mp4` | 4h | P-027 | `pipeline/renderer.py` |
| P-030 | `pipeline/quality_validator.py` — `validate_video(path) → (valid: bool, report: dict)`. ffprobe: check duration within ±5s of target, codec is h264, resolution is 1080×1920, audio track present, file size 30–500MB | 2h | P-029 | `pipeline/quality_validator.py` |
| P-031 | Wire production pipeline into console: update `console/backend/tasks/production_tasks.py` — `regenerate_tts_task` calls real `tts_engine.generate_tts()`, `render_video_task` calls real `composer.compose_video()` + `renderer.render_final()`. Remove stub returns | 3h | P-028, P-029 | Modified production_tasks.py |

### Sprint 3 Total: ~48h

---

## 6. Sprint 4 — Week 4: Uploader + Feedback + Batch Runner + Integration

### Uploader

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-032 | `uploader/youtube_uploader.py` — `upload(video_path, metadata, credentials) → video_id`. Build YouTube Data API v3 client with credentials from DB (Fernet-decrypted). `MediaFileUpload` with resumable upload. Set title/description/tags/category/privacy. Return YouTube video ID | 5h | — | `uploader/youtube_uploader.py` |
| P-033 | `uploader/tiktok_uploader.py` — `upload(video_path, metadata, credentials) → post_id`. TikTok Content Posting API v2. File-based upload with OAuth token. Set caption, hashtags, privacy, duet/stitch settings | 5h | — | `uploader/tiktok_uploader.py` |
| P-034 | `uploader/scheduler.py` — `get_optimal_time(platform, niche) → datetime`. Peak hours per platform (YouTube: 8am-10am, 5pm-8pm; TikTok: 7am-9am, 7pm-9pm). `schedule_upload(video_id, channels) → list[UploadTarget]` — creates upload_targets rows with scheduled_at | 2h | — | `uploader/scheduler.py` |
| P-035 | Wire uploads into console: update `console/backend/tasks/upload_tasks.py` — `upload_to_channel_task` calls real `youtube_uploader.upload()` or `tiktok_uploader.upload()` based on channel platform. Decrypt credentials via `credential_service.decrypt()` | 2h | P-032, P-033 | Modified upload_tasks.py |

### Feedback Loop

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-036 | `feedback/tracker.py` — `fetch_metrics(video_id, platform) → Metrics`. YouTube: `videos.list()` API for `statistics`. TikTok: `video/query/` API. Store to `viral_videos` or new `video_performance` table: views, likes, comments, shares, ER | 4h | — | `feedback/tracker.py` |
| P-037 | `feedback/scorer.py` — `compute_score(metrics) → float`. Formula: `0.4×(views/max_views) + 0.3×ER + 0.2×(shares/max_shares) + 0.1×(comments/max_comments)`, normalized 0–100. Mark videos with score ≥ 70 as `high_quality`, < 40 as `low_quality` | 2h | P-036 | `feedback/scorer.py` |
| P-038 | `feedback/reindexer.py` — `reindex_top_performers()`. Query `high_quality` scored scripts. Embed script JSON → ChromaDB `viral_scripts` collection with quality_score metadata. Remove `low_quality` entries | 2h | P-037 | `feedback/reindexer.py` |

### Batch Runner + Config

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-039 | `config/pipeline_config.yaml` — all configurable settings: scraper sources, LLM mode, asset resolver mode, TTS config, Veo config, upload schedule, feedback thresholds, cron schedule | 2h | — | `config/pipeline_config.yaml` |
| P-040 | `daily_pipeline.py` — `run_daily(topics: list[str] = None)`. Full orchestration: 1) scrape (if enabled), 2) analyze trends, 3) generate scripts for each topic/niche, 4) compose + render each script, 5) upload to configured channels, 6) report. Uses Celery task chains for async execution | 4h | All pipeline tasks | `daily_pipeline.py` |
| P-041 | `batch_runner.py` — main entry point for cron. Loads `pipeline_config.yaml`, reads enabled niches + topics from DB, calls `daily_pipeline.run_daily()`. Sends summary report (log file). Schedule: `0 2 * * *` (2am daily) | 2h | P-040 | `batch_runner.py` |
| P-042 | Alembic migration: add `viral_patterns` table (niche, region, hook_templates[], scene_types[], cta_phrases[], hashtag_clusters[], created_at). Also add `quality_score`, `platform_video_id` columns to `generated_scripts` | 2h | P-001 | `console/backend/alembic/versions/003_pipeline_tables.py` |
| P-043 | Update `console/requirements.txt` with all new deps: `chromadb`, `kokoro-onnx`, `openai-whisper`, `moviepy`, `pillow`, `opencv-python`, `playwright`, `apify-client`, `google-generativeai`, `pexels-python` | 30m | — | Updated `requirements.txt` |

### Integration Testing

| ID | Task | Est. | Depends | Deliverable |
|----|------|------|---------|-------------|
| P-044 | End-to-end smoke test: 1) trigger scrape → verify viral_videos populated, 2) generate script → verify script.json in DB, 3) run production → verify video_final.mp4 created, 4) upload → verify video_id returned | 4h | All above | Manual verification |
| P-045 | Console integration test: verify all 8 console tabs work with real pipeline data (no stub data, no ImportError warnings in logs) | 3h | P-044 | Manual verification |
| P-046 | Update `CLAUDE.md` — mark console complete, add core pipeline section with new directory structure, updated API integration points, cron schedule details | 1h | — | Updated `CLAUDE.md` |

### Sprint 4 Total: ~38h

---

## 7. Directory Structure After Implementation

```
ai-media-automation/
│
├── database/
│   ├── models.py                    ← ViralVideo, GeneratedScript, VideoAsset, ViralPattern
│   ├── connection.py                ← SQLAlchemy engine (shared with console)
│   └── setup_chromadb.py            ← Initialize 3 ChromaDB collections
│
├── scraper/
│   ├── base_scraper.py              ← Abstract adapter interface
│   ├── tiktok_research_api.py       ← TikTok Research API adapter
│   ├── tiktok_playwright.py         ← Playwright headless scraper
│   ├── apify_scraper.py             ← Apify cloud scraper
│   ├── trend_analyzer.py            ← Viral pattern extraction
│   └── main.py                      ← run_scrape() orchestrator
│
├── vector_db/
│   ├── indexer.py                   ← Embed + upsert to ChromaDB
│   └── retriever.py                 ← Semantic search
│
├── rag/
│   ├── llm_router.py                ← local/gemini/auto/hybrid dispatch
│   ├── rate_limiter.py              ← Per-model RPD/RPM tracking
│   ├── prompt_builder.py            ← RAG-enriched prompt assembly
│   ├── script_writer.py             ← write_script() + regenerate_scene()
│   └── script_validator.py          ← JSON schema validation
│
├── pipeline/
│   ├── tts_engine.py                ← Kokoro ONNX → audio_N.wav
│   ├── asset_db.py                  ← Video Asset DB search + write-back
│   ├── asset_resolver.py            ← 3-tier resolver (DB→Pexels→Veo)
│   ├── pexels_client.py             ← Pexels API download + resize
│   ├── veo_client.py                ← Google Veo generation
│   ├── veo_prompt_builder.py        ← Cinematic prompt construction
│   ├── overlay_builder.py           ← Pillow text overlay → PNG
│   ├── caption_gen.py               ← Whisper → SRT
│   ├── composer.py                  ← MoviePy scene assembly
│   ├── renderer.py                  ← ffmpeg NVENC final encode
│   └── quality_validator.py         ← Duration/codec/resolution checks
│
├── uploader/
│   ├── youtube_uploader.py          ← YouTube Data API v3
│   ├── tiktok_uploader.py           ← TikTok Content Posting API
│   └── scheduler.py                 ← Peak-hour upload scheduling
│
├── feedback/
│   ├── tracker.py                   ← Fetch platform metrics (views/ER)
│   ├── scorer.py                    ← Quality score 0–100
│   └── reindexer.py                 ← Reindex top performers to ChromaDB
│
├── config/
│   ├── scraper_sources.yaml         ← Source registry (already exists)
│   └── pipeline_config.yaml         ← All pipeline settings (new)
│
├── daily_pipeline.py                ← Full daily run orchestrator
├── batch_runner.py                  ← Cron entry point
│
└── console/                         ← Management Console (COMPLETE)
    └── ...
```

---

## 8. Key Technical Specs

### TTS Config
```python
TTS_CONFIG = {
    "engine": "kokoro", "model": "kokoro.onnx",
    "voice": "af_heart", "speed": 1.1,
    "sample_rate": 44100, "channels": 1, "threads": 8,
}
```

### Asset Resolver Mode (recommended)
```python
"source_mode": "db_then_hybrid",
"hybrid_rules": {"hook": "veo", "cta": "veo", "body": "pexels", "transition": "pexels"},
"db_min_score": 0.72,
"veo_model": "veo-2.0-generate-001",
```

### Renderer Config
```
ffmpeg -i raw.mp4 -vf "subtitles=subs.srt" -c:v h264_nvenc -crf 23 -c:a aac -b:a 192k output.mp4
CPU fallback: -c:v libx264 (when NVENC unavailable)
```

### Cron Schedule
```
0 1 * * *   scrape (3am)
0 2 * * *   batch_runner daily pipeline
0 6 * * *   feedback tracker + scorer
0 7 * * *   reindexer (top performers → ChromaDB)
*/30 * * * * token refresh (already in Celery beat)
```

---

## 9. Environment Variables to Add

```bash
# LLM
LLM_MODE=auto           # local | gemini | auto | hybrid
OLLAMA_URL=http://localhost:11434
GEMINI_API_KEY=...

# Scraper
TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
APIFY_API_TOKEN=...

# Assets
PEXELS_API_KEY=...
ASSET_DB_PATH=/assets/video_db

# Pipeline
MODELS_PATH=./models
OUTPUT_PATH=/assets/output
```

---

## 10. Verification Checklist

- [ ] `python -c "from database.models import ViralVideo"` — no error
- [ ] `python -c "from database.setup_chromadb import setup; setup()"` — 3 collections created
- [ ] Scraper: `python -m scraper.main` → videos appear in `viral_videos` table
- [ ] RAG: `python -m rag.script_writer` with test topic → valid script.json returned
- [ ] TTS: `python -m pipeline.tts_engine` → `audio_0.wav` file created
- [ ] Asset resolver: runs with `db_only` mode → returns closest match from test data
- [ ] Composer: `python -m pipeline.composer` with test script → `raw_video.mp4` created
- [ ] Renderer: `python -m pipeline.renderer` → `video_final.mp4`, passes quality validator
- [ ] Console smoke test: all 8 tabs load with real data, no ImportError in logs
- [ ] Celery tasks: scrape_q, script_q, render_q, upload_q all process real jobs end-to-end

---

*Core Pipeline Implementation Plan v1.0 — April 2026*
*Console complete (Sprints 1–4) → Core pipeline next (this document)*
