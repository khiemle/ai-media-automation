# Consolidate env files — Design Spec

**Date:** 2026-04-26
**Status:** Approved

---

## Problem

Two runtime env files exist side-by-side:

- `.env` — loaded by the console (`config.py`, `start.sh`)
- `pipeline.env` — loaded by 4 pipeline Python files and `pipeline_start.sh`

They share ~20 duplicate keys (same API keys and DB URLs in both). `pipeline.env.example` is already marked deprecated. `pipeline_start.sh` is no longer used — everything runs through `start.sh`.

---

## Goal

Single `.env` at the project root is the only runtime configuration file. No duplication, no confusion about which file controls which setting.

---

## Changes

### 1. Update 4 Python files — swap `pipeline.env` → `.env`

Each file calls `load_dotenv(_root / "pipeline.env", override=False)`. Change the path to `.env` in:

- `database/connection.py`
- `pipeline/renderer.py`
- `pipeline/veo_client.py`
- `pipeline/asset_db.py`

The `override=False` flag is correct to keep — the console already loads `.env` via `config.py`, so pipeline files won't clobber existing values.

### 2. Restore pipeline-only vars to `.env` and `.env.example`

The following vars were prematurely removed from `.env` (they ARE used by pipeline code, just read from `pipeline.env`). Restore them with values from the current `pipeline.env`:

| Section | Vars |
|---|---|
| Pipeline settings | `IMAGEN_MODEL`, `TTS_VOICE`, `TTS_SPEED`, `RENDER_CONCURRENCY`, `WEBHOOK_URL` |
| TikTok scraper | `TIKTOK_SCRAPER_ENGINE`, `TIKTOK_BROWSER_HEADLESS`, `TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY`, `TIKTOK_SELENIUM_FALLBACK`, `TIKTOK_BROWSER_TIMEOUT_MS`, `TIKTOK_BROWSER_SCROLL_COUNT`, `TIKTOK_BROWSER_SCROLL_DELAY_MS`, `TIKTOK_BROWSER_CHANNEL`, `TIKTOK_CHROME_BINARY` |
| Apify | `APIFY_TIKTOK_ACTOR_ID` |

### 3. Delete deprecated files

- `pipeline.env` — runtime file, delete after merging vars into `.env`
- `pipeline.env.example` — already marked deprecated, delete
- `pipeline_start.sh` — no longer used, delete

### 4. Update `.gitignore`

Remove `pipeline.env` entry if present (file is being deleted).

---

## What does NOT change

- `start.sh` — already loads `.env`, no changes needed
- Console backend (`config.py`, `celery_app.py`) — already reads from `.env`
- No DB migrations, no API changes, no frontend changes
- No new abstractions or indirection layers

---

## Verification

After changes:

```bash
# Backend still starts
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/auth/me
# → 403 (expected — not logged in)

# Pipeline imports resolve without error
python3 -c "from pipeline.renderer import render_final; print('ok')"
python3 -c "from pipeline.veo_client import VeoClient; print('ok')"
python3 -c "from pipeline.asset_db import AssetDB; print('ok')"
python3 -c "from database.connection import get_session; print('ok')"
```
