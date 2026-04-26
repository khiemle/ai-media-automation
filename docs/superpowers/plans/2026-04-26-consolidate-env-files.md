# Consolidate env Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two-file env system (`pipeline.env` + `.env`) with a single `.env` at the project root, and delete all deprecated pipeline env artefacts.

**Architecture:** Four pipeline Python files hardcode `pipeline.env` as their dotenv source; each gets a one-line path change to `.env`. The vars that were prematurely stripped from `.env` are restored. Three deprecated files (`pipeline.env`, `pipeline.env.example`, `pipeline_start.sh`) are deleted.

**Tech Stack:** Python 3.11, python-dotenv, bash

---

## File Map

| Action | File | What changes |
|--------|------|--------------|
| Modify | `database/connection.py:3,12-20` | Load `.env` only; remove `pipeline.env` + `console/.env` fallback |
| Modify | `pipeline/renderer.py:15-16` | Load `.env` only |
| Modify | `pipeline/veo_client.py:16-17,38` | Load `.env` only; fix error message |
| Modify | `pipeline/asset_db.py:16-17` | Load `.env` only |
| Modify | `.env` | Restore 15 pipeline-only vars |
| Modify | `.env.example` | Restore same 15 vars with placeholder values |
| Modify | `.gitignore` | Remove `pipeline.env` entry |
| Delete | `pipeline.env` | Runtime file — vars merged into `.env` |
| Delete | `pipeline.env.example` | Deprecated template |
| Delete | `pipeline_start.sh` | No longer used |

---

## Task 1: Restore pipeline vars to `.env` and `.env.example`

**Files:**
- Modify: `.env`
- Modify: `.env.example`

- [ ] **Step 1.1: Restore vars in `.env`**

Open `.env` and replace the Pipeline Settings section with the full set (values from current `pipeline.env`):

```
# ── Pipeline Settings ─────────────────────────────────────────────────────────
IMAGEN_MODEL=imagen-4.0-fast-generate-001
TTS_VOICE=af_heart
TTS_SPEED=1.1
RENDER_CONCURRENCY=2
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920
VIDEO_FPS=30
FEEDBACK_REINDEX_THRESHOLD=70
FEEDBACK_LOW_QUALITY_THRESHOLD=40
WEBHOOK_URL=

# ── TikTok Scraper ────────────────────────────────────────────────────────────
TIKTOK_CLIENT_KEY=aw5gncxsx9kudlmd
TIKTOK_CLIENT_SECRET=wQw13pEBOHkOebRccAshCqCoa9XrupLF
TIKTOK_SCRAPER_ENGINE=auto
TIKTOK_BROWSER_HEADLESS=true
TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY=true
TIKTOK_SELENIUM_FALLBACK=true
TIKTOK_BROWSER_TIMEOUT_MS=30000
TIKTOK_BROWSER_SCROLL_COUNT=4
TIKTOK_BROWSER_SCROLL_DELAY_MS=1800
TIKTOK_BROWSER_CHANNEL=
TIKTOK_CHROME_BINARY=

# ── Apify (fallback scraper) ──────────────────────────────────────────────────
APIFY_API_TOKEN=<YOUR_APIFY_API_TOKEN>
APIFY_TIKTOK_ACTOR_ID=GdWCkxBtKWOsKjdch
```

- [ ] **Step 1.2: Restore same vars in `.env.example` with placeholder values**

Replace the Pipeline Settings section in `.env.example` with:

```
# ── Pipeline Settings ─────────────────────────────────────────────────────────
IMAGEN_MODEL=imagen-4.0-fast-generate-001
TTS_VOICE=af_heart
TTS_SPEED=1.1
RENDER_CONCURRENCY=2
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920
VIDEO_FPS=30
FEEDBACK_REINDEX_THRESHOLD=70
FEEDBACK_LOW_QUALITY_THRESHOLD=40
WEBHOOK_URL=

# ── TikTok Scraper ────────────────────────────────────────────────────────────
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_SCRAPER_ENGINE=auto          # auto | playwright | selenium
TIKTOK_BROWSER_HEADLESS=true
TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY=true
TIKTOK_SELENIUM_FALLBACK=true
TIKTOK_BROWSER_TIMEOUT_MS=30000
TIKTOK_BROWSER_SCROLL_COUNT=4
TIKTOK_BROWSER_SCROLL_DELAY_MS=1800
TIKTOK_BROWSER_CHANNEL=
TIKTOK_CHROME_BINARY=

# ── Apify (fallback scraper) ──────────────────────────────────────────────────
APIFY_API_TOKEN=
APIFY_TIKTOK_ACTOR_ID=GdWCkxBtKWOsKjdch
```

- [ ] **Step 1.3: Commit**

```bash
git add .env.example
git commit -m "chore: restore pipeline-only vars to .env.example"
```

(`.env` is gitignored — no need to stage it.)

---

## Task 2: Update `database/connection.py`

**Files:**
- Modify: `database/connection.py:1-21`

- [ ] **Step 2.1: Replace the dotenv loading block**

Replace lines 1–21 with:

```python
"""
Shared SQLAlchemy engine + session factory.
Reads DATABASE_URL from environment (.env at project root).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load .env from project root if not already set
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)
```

- [ ] **Step 2.2: Verify import works**

```bash
python3 -c "from database.connection import get_session; print('ok')"
```

Expected: `ok`

- [ ] **Step 2.3: Commit**

```bash
git add database/connection.py
git commit -m "chore: load .env instead of pipeline.env in database/connection.py"
```

---

## Task 3: Update `pipeline/renderer.py`

**Files:**
- Modify: `pipeline/renderer.py:15-16`

- [ ] **Step 3.1: Replace the two load_dotenv lines**

Find:
```python
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)
```

Replace with:
```python
load_dotenv(_root / ".env", override=False)
```

- [ ] **Step 3.2: Verify import works**

```bash
python3 -c "from pipeline.renderer import render_final; print('ok')"
```

Expected: `ok`

- [ ] **Step 3.3: Commit**

```bash
git add pipeline/renderer.py
git commit -m "chore: load .env instead of pipeline.env in pipeline/renderer.py"
```

---

## Task 4: Update `pipeline/veo_client.py`

**Files:**
- Modify: `pipeline/veo_client.py:16-17,38`

- [ ] **Step 4.1: Replace the two load_dotenv lines**

Find:
```python
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)
```

Replace with:
```python
load_dotenv(_root / ".env", override=False)
```

- [ ] **Step 4.2: Fix the error message on line 38**

Find:
```python
raise RuntimeError("GEMINI_MEDIA_API_KEY not set in pipeline.env")
```

Replace with:
```python
raise RuntimeError("GEMINI_MEDIA_API_KEY not set in .env")
```

- [ ] **Step 4.3: Verify import works**

```bash
python3 -c "from pipeline.veo_client import VeoClient; print('ok')"
```

Expected: `ok`

- [ ] **Step 4.4: Commit**

```bash
git add pipeline/veo_client.py
git commit -m "chore: load .env instead of pipeline.env in pipeline/veo_client.py"
```

---

## Task 5: Update `pipeline/asset_db.py`

**Files:**
- Modify: `pipeline/asset_db.py:16-17`

- [ ] **Step 5.1: Replace the two load_dotenv lines**

Find:
```python
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)
```

Replace with:
```python
load_dotenv(_root / ".env", override=False)
```

- [ ] **Step 5.2: Verify import works**

```bash
python3 -c "from pipeline.asset_db import AssetDB; print('ok')"
```

Expected: `ok`

- [ ] **Step 5.3: Commit**

```bash
git add pipeline/asset_db.py
git commit -m "chore: load .env instead of pipeline.env in pipeline/asset_db.py"
```

---

## Task 6: Delete deprecated files and clean `.gitignore`

**Files:**
- Delete: `pipeline.env`
- Delete: `pipeline.env.example`
- Delete: `pipeline_start.sh`
- Modify: `.gitignore:44`

- [ ] **Step 6.1: Delete the three deprecated files**

```bash
rm pipeline.env pipeline.env.example pipeline_start.sh
```

- [ ] **Step 6.2: Remove `pipeline.env` from `.gitignore`**

Open `.gitignore` and delete the line:
```
pipeline.env
```

- [ ] **Step 6.3: Verify no remaining references to pipeline.env**

```bash
grep -r "pipeline\.env" --include="*.py" --include="*.sh" --include="*.md" . --exclude-dir=".git" | grep -v "docs/superpowers"
```

Expected: no output.

- [ ] **Step 6.4: Commit**

```bash
git add -A
git commit -m "chore: delete pipeline.env, pipeline.env.example, pipeline_start.sh; clean .gitignore"
```

---

## Task 7: Final verification

- [ ] **Step 7.1: Confirm backend still responds**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/auth/me
```

Expected: `403`

- [ ] **Step 7.2: Confirm all four pipeline imports resolve**

```bash
python3 -c "
from database.connection import get_session
from pipeline.renderer import render_final
from pipeline.veo_client import VeoClient
from pipeline.asset_db import AssetDB
print('all ok')
"
```

Expected: `all ok`

- [ ] **Step 7.3: Confirm no pipeline.env references remain**

```bash
grep -r "pipeline\.env" . --exclude-dir=".git" --exclude-dir="docs/superpowers"
```

Expected: no output.
