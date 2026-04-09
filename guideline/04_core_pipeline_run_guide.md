# Core Pipeline — Detailed Run Guide

> **Purpose:** Understand and operate every layer of the core pipeline.
> **Covers:** architecture flow · starting services · running each layer individually · cron schedule · logs · monitoring · tuning

---

## Pipeline Architecture

The pipeline runs in 7 layers executed in order every day:

```
┌──────────────────────────────────────────────────────┐
│  01:00  Layer 1 — Scraper                            │
│         TikTok Research API + Playwright + Apify      │
│         → viral_videos table + ChromaDB hooks         │
├──────────────────────────────────────────────────────┤
│  01:30  Layer 2 — Trend Analyzer                     │
│         extracts patterns from viral_videos           │
│         → viral_patterns table + ChromaDB patterns    │
├──────────────────────────────────────────────────────┤
│  02:00  Layer 3 — Script Generator (RAG + LLM)       │
│         ChromaDB retrieval → prompt → Qwen/Gemini     │
│         → generated_scripts table (status: approved)  │
├──────────────────────────────────────────────────────┤
│  02:xx  Layer 4 — Production (per script)            │
│         TTS (Kokoro) + Asset Resolver + Composer      │
│         → raw_video.mp4 per scene                     │
├──────────────────────────────────────────────────────┤
│  02:xx  Layer 5 — Renderer                           │
│         ffmpeg NVENC/libx264 + subtitle burn-in       │
│         → video_final.mp4                             │
├──────────────────────────────────────────────────────┤
│  02:xx  Layer 6 — Uploader                           │
│         YouTube Data API v3 + TikTok Content API      │
│         → upload_targets table (status: scheduled)    │
├──────────────────────────────────────────────────────┤
│  06:00  Layer 7 — Feedback Loop                      │
│         fetch metrics → score (0–100) → reindex       │
│         → ChromaDB updated with top performers        │
└──────────────────────────────────────────────────────┘
```

All layers are orchestrated by `batch_runner.py` → `daily_pipeline.py`.  
Heavy tasks (render, upload) run through Celery on `render_q` / `upload_q`.

---

## Prerequisites Checklist

Before starting, verify each service is running:

```bash
# PostgreSQL
pg_isready                              # should print "accepting connections"

# Redis
redis-cli ping                          # should print "PONG"

# Ollama (if LLM_MODE=local or auto)
curl -s http://localhost:11434/api/tags # should return JSON with models list

# ffmpeg
ffmpeg -version                         # should print version info
```

If anything is missing, see `guideline/02_core_pipeline_setup.md`.

---

## Starting the Pipeline

### Standard start

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

./pipeline_start.sh
```

What this does on every start:
1. Loads `pipeline.env`
2. Verifies PostgreSQL, Redis, Ollama, Gemini keys, ChromaDB, ffmpeg
3. Runs `alembic upgrade head` (migrations are idempotent)
4. Creates asset directories if missing
5. Starts a Celery worker on `render_q` (concurrency=2)
6. Starts Celery beat for cron scheduling (if not already running)

Output summary at the end shows all active settings and log paths.

---

## Running Each Layer Manually

Use these commands during development, testing, or after a partial failure.

---

### Layer 1 — Scraper

Scrapes TikTok for viral videos matching configured niches and hashtags.

```bash
# Run all enabled scrapers
python3 -m scraper.main

# Or from Python
python3 -c "
from scraper.main import run_scrape
result = run_scrape()
print(f\"Sources run: {result['sources_run']}\")
print(f\"Videos inserted: {result['videos_inserted']}\")
print(f\"Errors: {result['errors']}\")
"
```

Sources are configured in `config/scraper_sources.yaml`.  
Toggle a source active/standby without code changes:
```bash
# Edit the yaml directly
nano config/scraper_sources.yaml

# Or via the console Scraper tab → toggle source status
```

**Scrapers available:**

| Source ID | Module | Requires |
|-----------|--------|---------|
| `tiktok_research` | `scraper.tiktok_research_api` | `TIKTOK_CLIENT_KEY` + `TIKTOK_CLIENT_SECRET` |
| `tiktok_playwright` | `scraper.tiktok_playwright` | Playwright + Chromium installed; optionally falls back to Selenium + Chrome/Chromium |
| `apify` | `scraper.apify_scraper` | `APIFY_API_TOKEN` |

After scraping, trend analysis and ChromaDB indexing run automatically.

For the browser-based TikTok scraper, runtime behavior is controlled from `pipeline.env`:
```bash
TIKTOK_SCRAPER_ENGINE=auto
TIKTOK_BROWSER_HEADLESS=true
TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY=true
TIKTOK_SELENIUM_FALLBACK=true
```

Recommended usage:
- Keep `TIKTOK_SCRAPER_ENGINE=auto` for Playwright first, Selenium fallback.
- Set `TIKTOK_BROWSER_HEADLESS=false` to open a real browser tab/window while debugging local scraping.
- If Playwright is unstable on your machine, set `TIKTOK_SCRAPER_ENGINE=selenium` temporarily.

---

### Layer 2 — Trend Analyzer

Extracts hook templates, scene types, CTA phrases, and hashtag clusters from scraped videos.

```bash
python3 -c "
from scraper.trend_analyzer import analyze
analyze()
print('Trend analysis complete — viral_patterns table updated')
"
```

Results are stored in `viral_patterns` and also indexed into ChromaDB `viral_patterns` collection.

---

### Layer 3 — Script Generator

Generates a full video script JSON using RAG (ChromaDB retrieval) + LLM.

```bash
# Generate a single script (prints result)
python3 -c "
from rag.script_writer import generate_script
import json

script = generate_script(
    topic='5 thói quen buổi sáng giúp bạn thành công',
    niche='lifestyle',
    template='tiktok_viral',
)
print(json.dumps(script, ensure_ascii=False, indent=2))
"
```

**Available templates:**

| Template | Duration | Style |
|----------|----------|-------|
| `tiktok_viral` | 30–60s | Hook → proof → CTA, fast cuts |
| `tiktok_30s` | 25–35s | Condensed hook → single insight → CTA |
| `youtube_clean` | 45–75s | Intro → structured body → outro |
| `shorts_hook` | 15–30s | Pure hook + one actionable tip |

**LLM routing** (set `LLM_MODE` in `pipeline.env`):

| Mode | Behavior |
|------|----------|
| `local` | Qwen2.5 via Ollama — free, offline, ~15s/script on 3B |
| `gemini` | Gemini 2.5 Flash — best quality, requires API key |
| `auto` | Gemini if quota available, Ollama fallback |
| `hybrid` | hook + CTA scenes → Gemini, body scenes → local |

**Regenerate a single scene:**
```bash
python3 -c "
from rag.script_writer import regenerate_scene
import json

# Replace this with a real script dict loaded from DB or file.
script = {
  'meta': {'template': 'tiktok_viral'},
  'scenes': [
    {
      'narration': 'Mở đầu ngắn gọn',
      'visual_hint': 'person talking to camera',
      'text_overlay': 'Mở đầu',
      'overlay_style': 'minimal',
    },
    {
      'narration': 'Nội dung chính',
      'visual_hint': 'illustration of daily routine',
      'text_overlay': '',
      'overlay_style': 'minimal',
    },
  ],
}
updated = regenerate_scene(script, scene_index=1)
print(json.dumps(updated['scenes'][1], ensure_ascii=False, indent=2))
"
```

---

### Layer 4 — Production (TTS + Assets + Composition)

Takes an approved script from the DB and produces `raw_video.mp4`.

```bash
# Compose video for a script by its DB id
python3 -c "
from pipeline.composer import compose_video
raw_path = compose_video(script_id=1)
print('Raw video:', raw_path)
"
```

**What compose_video does per scene (in parallel threads):**
1. **TTS** — Kokoro ONNX generates 44.1kHz WAV from narration text
2. **Asset resolver** — finds/downloads video clip (3-tier):
   - Tier 1: search `video_assets` DB by keyword overlap
   - Tier 2: Pexels API portrait video (if DB miss)
   - Tier 3: Google Veo generation (if Pexels miss, requires `GEMINI_MEDIA_API_KEY`)
3. **Overlay builder** — renders text overlay PNG (Pillow)
4. **Scene assembly** — MoviePy stacks clip + overlay + audio

**Test TTS alone:**
```bash
python3 -c "
from pipeline.tts_engine import generate_tts
wav = generate_tts('Xin chào, đây là bài kiểm tra tiếng Việt', voice='af_heart', speed=1.1)
print('WAV output:', wav)
"
```

**Test asset resolver alone:**
```bash
python3 -c "
from pipeline.asset_resolver import resolve
scene = {'type': 'body', 'visual_hint': 'person jogging morning sunlight', 'duration': 8}
meta  = {'niche': 'fitness', 'template': 'tiktok_viral'}
path  = resolve(scene, meta)
print('Asset:', path)
"
```

**Kokoro TTS model setup** (required for TTS to work):
```bash
mkdir -p models/kokoro/voices

# Download kokoro-v1.1-zh.onnx (~82 MB) from:
# https://github.com/thewh1teagle/kokoro-onnx/releases

# Verify after download:
python3 -c "
from kokoro_onnx import Kokoro
k = Kokoro('models/kokoro/kokoro.onnx', 'models/kokoro/voices/voices-v1.1-zh.bin')
print('Kokoro OK — voices:', list(k.get_voices())[:5])
"
```

---

### Layer 5 — Renderer

Burns subtitles, mixes background music, and encodes the final MP4.

```bash
python3 -c "
from pipeline.renderer import render_final
final_path = render_final(
  raw_video_path='assets/output/script_1/raw_video.mp4',
    srt_path='assets/output/script_1/audio_merged.srt',  # optional
)
print('Final video:', final_path)
"
```

**Generate captions (Whisper → SRT) separately:**
```bash
python3 -c "
from pipeline.caption_gen import generate_captions
srt = generate_captions('assets/output/script_1/audio_merged.wav')
print('SRT:', srt)
"
```

**Renderer uses GPU if available:**
- With NVIDIA GPU: `h264_nvenc` (fast, hardware)
- Without GPU: `libx264` (slower, software — automatic fallback)

Check GPU availability:
```bash
ffmpeg -encoders 2>/dev/null | grep nvenc
```

**Quality validator** — run after rendering to check output:
```bash
python3 -c "
from pipeline.quality_validator import validate
valid, report = validate('assets/output/script_1/video_final.mp4')
print('Valid:', valid)
print('Report:', report)
"
```

Checks: duration (15–80s), h264 codec, 1080×1920 resolution, audio track, file size (1–500 MB).

---

### Layer 6 — Uploader

Schedules and uploads finished videos to YouTube and TikTok.

```bash
# Schedule an upload (creates upload_targets row, queues Celery task)
python3 -c "
from uploader.scheduler import schedule_upload
schedule_upload(
    script_id=1,
    channel_ids=[1, 2],    # from channels table
    niche='lifestyle',
)
print('Upload scheduled')
"
```

**Upload directly (bypasses scheduler):**
```bash
# YouTube
python3 -c "
from uploader.youtube_uploader import upload_to_youtube
credentials = {
  'client_id': 'your-client-id',
  'client_secret': 'your-client-secret',
  'access_token': 'your-access-token',
  'refresh_token': 'your-refresh-token',
}
metadata = {
  'title': 'Test upload',
  'description': 'Uploaded from the core pipeline guide',
  'hashtags': ['test'],
  'niche': 'lifestyle',
}
video_id = upload_to_youtube('assets/output/script_1/video_final.mp4', metadata, credentials)
print('YouTube video ID:', video_id)
"
```

OAuth tokens are stored encrypted in `platform_credentials` table.  
Manage credentials via the console **Uploads** tab.

---

### Layer 7 — Feedback Loop

Fetches real metrics from platforms, scores scripts, and reindexes top performers.

```bash
# Fetch metrics for all uploaded videos
python3 -c "
from feedback.tracker import fetch_all
metrics = fetch_all()
print(f'Fetched metrics for {len(metrics)} videos')
for m in metrics[:3]:
    print(f'  {m.platform_id}: {m.views} views, ER {m.engagement_rate:.1%}')
"

# Score all scripts (updates quality_score column)
python3 -c "
from feedback.scorer import score_all
scores = score_all()
print(f'Scored {len(scores)} scripts')
"

# Reindex top performers into ChromaDB (score >= 70)
python3 -c "
from feedback.reindexer import reindex_top_performers
result = reindex_top_performers()
print(f'Indexed {result[\"indexed\"]} top scripts, removed {result[\"removed\"]} low quality')
"
```

**Quality score formula (0–100):**
```
score = 0.4 × views_norm + 0.3 × engagement_rate + 0.2 × shares_norm + 0.1 × comments_norm
```
- `>= 70` → reindexed into ChromaDB as high-quality example
- `< 40`  → removed from ChromaDB, marked low quality

---

## Full Daily Pipeline

### Dry run (safe — no API calls, no renders, no uploads)

```bash
python3 batch_runner.py --run-now --dry-run
```

Logs what would happen without doing it. Use to verify config before real runs.

### Run with specific topics

```bash
python3 batch_runner.py --run-now --topics \
  "5 thói quen buổi sáng giúp bạn thành công" \
  "Bí quyết tiết kiệm 10 triệu mỗi tháng" \
  "Bài tập giảm cân hiệu quả tại nhà"
```

### Scrape only (no script generation)

```bash
python3 batch_runner.py --scrape-only
```

### Full auto run (auto-selects topics from trending videos)

```bash
python3 batch_runner.py --run-now
```

### Run daily_pipeline directly (more control)

```bash
python3 daily_pipeline.py --dry-run
# or
python3 -c "
from daily_pipeline import run_daily
summary = run_daily(topics=['5 thói quen sống khỏe'], dry_run=False)
print(summary)
"
```

---

## Cron Schedule (Automatic)

Celery beat (started by `./pipeline_start.sh`) runs these automatically:

| Time (Vietnam, UTC+7) | Task | Function |
|-----------------------|------|---------|
| 01:00 daily | Scrape TikTok trends | `run_scrape_task` |
| 02:00 daily | Full pipeline: generate + produce + upload | `batch_runner.py` |
| 06:00 daily | Fetch performance metrics | `feedback.tracker.fetch_all` |
| 07:00 daily | Reindex top performers → ChromaDB | `feedback.reindexer.reindex_top_performers` |
| Every 30 min | Refresh expiring OAuth tokens | `tasks.token_refresh` |

Check beat is running:
```bash
test -f logs/celery_beat.pid && xargs kill -0 < logs/celery_beat.pid && echo "Running" || echo "Not running"
```

---

## Logs

| Log file | Contents |
|----------|---------|
| `logs/pipeline.log` | `batch_runner.py` daily run output |
| `logs/pipeline_celery.log` | Celery render worker (TTS, compose, render) |
| `logs/celery_beat.log` | Cron scheduler (beat) |
| `logs/redis.log` | Redis (if started by pipeline_start.sh) |
| `console/logs/celery_worker.log` | Console Celery worker (scrape, scripts, uploads) |

**Tail live logs:**
```bash
tail -f logs/pipeline.log
tail -f logs/pipeline_celery.log
```

**Filter for errors only:**
```bash
grep "ERROR\|FAILED\|Exception" logs/pipeline.log | tail -20
```

---

## Asset Resolver Modes

Set `ASSET_RESOLVER_MODE` in `pipeline.env`:

| Mode | Behavior | Cost |
|------|----------|------|
| `db_only` | Only cached DB assets — never fetches external | Free |
| `db_then_pexels` | DB → Pexels fallback | Free (Pexels API) |
| `db_then_veo` | DB → Veo generation fallback | ~$0.40/clip |
| `db_then_hybrid` | DB → Pexels for body, Veo for hook/CTA | Mixed |

**Hybrid routing** (default):
```
hook scene   → Veo (cinematic, high impact)
cta scene    → Veo (polished)
body scene   → Pexels (fast, free)
transition   → Pexels (fast, free)
```

---

## Pipeline Config Tuning

Edit `config/pipeline_config.yaml` — no code changes needed:

```yaml
pipeline:
  daily_video_target: 10    # videos per day
  niches:
    - health
    - fitness
    - lifestyle
    - finance

scraper:
  min_play_count: 10000     # ignore videos below this view count
  max_videos_per_source: 100

llm:
  mode: auto                # local | gemini | auto | hybrid
  ollama_model: qwen2.5:3b  # switch to 7b for better quality

assets:
  db_min_score: 0.72        # lower → more DB cache hits, lower quality match
  veo_model: veo-3.1-lite-generate-preview

production:
  render_workers: 2         # increase if you have more GPU memory
  music_volume: 0.08        # 0.0 = no music, 0.1 = quiet background

feedback:
  reindex_threshold: 70     # score >= this → ChromaDB high-quality
  low_quality_threshold: 40 # score < this → removed from ChromaDB
```

---

## Troubleshooting

| Problem | Diagnosis | Fix |
|---------|-----------|-----|
| `Ollama up: False` | Ollama not running | `ollama serve` in a separate terminal |
| `Gemini key: False` | Key missing from env | Check `GEMINI_API_KEY` in `pipeline.env` |
| Scraper returns 0 videos | No credentials or source disabled | Check `TIKTOK_CLIENT_KEY` / `APIFY_API_TOKEN`; verify source status in `scraper_sources.yaml` |
| `[TTS] Failed to load Kokoro` | ONNX model not found | Download `kokoro.onnx` to `models/kokoro/` |
| `[Asset] No asset found` | DB empty + Pexels key missing | Set `PEXELS_API_KEY` in `pipeline.env` |
| Render fails — `h264_nvenc` error | NVENC not available | Normal on Mac/CPU — renderer auto-falls back to `libx264` |
| `quality check failed` in logs | Video didn't pass validator | Check `logs/pipeline.log` for specific check that failed (duration/resolution/codec) |
| Celery task stuck in PENDING | Worker not running | Run `./pipeline_start.sh` again |
| ChromaDB errors after reinstall | Embedding function mismatch | `rm -rf ./chroma_db && python3 database/setup_chromadb.py` |
| `export: '#': not a valid identifier` | Old `pipeline_start.sh` with `xargs` | Pull latest `pipeline_start.sh` — fixed with safe line reader |
| Scripts use fallback template | LLM failed all 3 retries | Check Ollama is running and model is pulled; check Gemini quota |

---

## Quick Health Check

Run this after starting to verify all layers are functional:

```bash
python3 -c "
from rag.llm_router import LLMRouter
from database.connection import get_session
from database.models import ViralVideo, GeneratedScript
import chromadb

# LLM
r = LLMRouter()
print('Ollama:    ', r.is_ollama_available())
print('Gemini key:', r.status()[\"gemini_key_set\"])

# DB
db = get_session()
print('Videos:    ', db.query(ViralVideo).count(), 'in DB')
print('Scripts:   ', db.query(GeneratedScript).count(), 'in DB')
db.close()

# ChromaDB
c = chromadb.PersistentClient('./chroma_db')
for col in c.list_collections():
    print(f'ChromaDB [{col.name}]: {col.count()} vectors')
"
```

---

*Guide version: April 2026 — AI Media Automation Project*
