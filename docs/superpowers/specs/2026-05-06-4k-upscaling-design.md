# 4K Upscaling via Topaz API — Design Spec

**Date:** 2026-05-06  
**Status:** Approved

---

## Overview

Add a "Upscale to 4K" feature to the Assets page (`/assets`). Any VideoAsset that is not already 3840×2160 shows an upscale button. The Topaz Video AI API (model `ast-2`) performs the upscaling asynchronously via a Celery task. The 4K result is saved as a separate VideoAsset. The Topaz API key is managed in the LLM tab alongside Runway.

---

## Architecture & Data Flow

```
[/assets page]
  └─ "Upscale to 4K" button (visible when asset resolution ≠ 3840×2160 and upscale_status is null/failed)
        │
        ▼
POST /api/assets/{asset_id}/upscale
  └─ writes upscale_status=pending, upscale_task_id on source asset
  └─ dispatches upscale_to_4k_task.delay(asset_id) → returns { task_id }
        │
        ▼
Celery task on render_q — upscale_tasks.py
  First invocation:
    1. Load VideoAsset, read file_path
    2. ffprobe for size/duration/fps/resolution
    3. POST /video/ → create Topaz job
    4. PATCH /video/{request_id}/accept → get upload URL
    5. PUT upload URL with file bytes → capture ETag
    6. PATCH /video/{request_id}/complete-upload
    7. Write topaz_request_id + upscale_status=processing to VideoAsset
    8. self.retry(countdown=10)

  Subsequent retries (polling):
    1. Read topaz_request_id from VideoAsset
    2. GET /video/{request_id}/status
    3. If processing → self.retry(countdown=10)
    4. If complete:
       a. Download result to {original_dir}/video_final_4k.mp4
       b. INSERT new VideoAsset (resolution=3840×2160, source=topaz_upscale,
          original_asset_id={asset_id})
       c. Set upscale_status=ready on source asset
    5. If failed → set upscale_status=failed on source asset
```

---

## Database Changes

**`video_assets` table — 3 new nullable columns:**

| Column | Type | Description |
|--------|------|-------------|
| `upscale_task_id` | String | Celery task_id, set on dispatch |
| `topaz_request_id` | String | Topaz job request_id, set after upload |
| `upscale_status` | String | `null \| pending \| processing \| ready \| failed` |
| `original_asset_id` | Integer FK | On 4K asset, points back to source asset |

New Alembic migration required.

---

## Files

### New files

| File | Purpose |
|------|---------|
| `pipeline/topaz_client.py` | `TopazClient` class — wraps all Topaz API steps |
| `console/backend/tasks/upscale_tasks.py` | `upscale_to_4k_task(asset_id)` Celery task |

### Modified files

| File | Change |
|------|--------|
| `config/api_keys.json` | Add `topaz_api_key` field |
| `console/backend/config.py` | Add `topaz_api_key: str = ""` setting |
| `console/backend/routers/llm.py` | Add `GET/PUT /llm/topaz` + `POST /llm/topaz/test-connection` |
| `console/frontend/src/pages/LLMPage.jsx` | Add Topaz section (KeyInput + Save + Test, mirrors Runway section) |
| `database/models.py` | Add 4 columns to `VideoAsset` |
| `console/backend/routers/production.py` | Add `POST /assets/{asset_id}/upscale` |
| `console/backend/alembic/versions/` | New migration for VideoAsset columns |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | Upscale button, status badge, spinner |

---

## API Endpoints

### LLM tab — Topaz key management (mirrors Runway)

```
GET  /api/llm/topaz
     → { api_key: "key_...abc123" }  (masked, last 6 chars visible)

PUT  /api/llm/topaz
     body: { api_key: str }
     → { success: bool }
     Persists to config/api_keys.json

POST /api/llm/topaz/test-connection
     → { connected: bool, message: str }
     Makes a lightweight Topaz API call to verify key validity
```

### Assets — upscale trigger & status

```
POST /api/assets/{asset_id}/upscale
     → { task_id: str }
     Sets upscale_status=pending, upscale_task_id on source asset
     Dispatches upscale_to_4k_task

GET  /api/assets  (existing)
     Already returns upscale_status, upscale_task_id, topaz_request_id
     No new status endpoint needed — UI reads from asset list
```

---

## `pipeline/topaz_client.py`

```python
class TopazClient:
    BASE = "https://api.topazlabs.com"

    def __init__(self, api_key: str): ...

    def create_job(self, width, height, fps, duration, size) -> str:
        # POST /video/ with ast-2 filter, 3840×2160 output
        # Returns request_id

    def accept_job(self, request_id: str) -> str:
        # PATCH /video/{request_id}/accept
        # Returns upload URL

    def upload_file(self, upload_url: str, file_path: Path) -> str:
        # PUT file bytes to presigned URL
        # Returns ETag

    def complete_upload(self, request_id: str, etag: str) -> None:
        # PATCH /video/{request_id}/complete-upload

    def get_status(self, request_id: str) -> dict:
        # GET /video/{request_id}/status
        # Returns { status: str, download: { url: str } | None }

    def download_result(self, download_url: str, dest_path: Path) -> None:
        # Stream download to dest_path
```

**Topaz job parameters (fixed):**
- Model: `ast-2`
- Output: 3840×2160, H265, AAC Copy, High compression
- Source metadata (width, height, fps, duration, size): read dynamically via ffprobe from the source file

---

## `console/backend/tasks/upscale_tasks.py`

```python
@celery_app.task(bind=True, max_retries=60, queue="render_q")
def upscale_to_4k_task(self, asset_id: int):
    # On first call (topaz_request_id is None):
    #   - ffprobe source file
    #   - create + upload via TopazClient
    #   - persist topaz_request_id, upscale_status=processing
    #   - self.retry(countdown=10)
    #
    # On retry (topaz_request_id exists):
    #   - poll TopazClient.get_status()
    #   - if processing: self.retry(countdown=10)
    #   - if complete: download, create 4K VideoAsset, upscale_status=ready
    #   - if failed: upscale_status=failed
```

Max retries = 60 × 10s = 10 minutes max polling time.

---

## Frontend — VideoAssetsPage

**Asset card upscale states:**

| `upscale_status` | UI |
|-----------------|-----|
| `null` + not 4K | "Upscale to 4K" button |
| `pending` | Spinner + "Queued…" |
| `processing` | Spinner + "Upscaling…" |
| `ready` | "4K ✓" badge (links to 4K asset) |
| `failed` | Error icon + "Retry" button |
| asset is already 4K | No button shown |

**Resume on page load:** Asset list fetch returns current `upscale_status` from DB — spinner shown automatically for in-progress jobs without any client-side polling loop (mirrors Runway animate pattern).

---

## LLM Tab — Topaz Section

Mirrors the existing Runway section in `LLMPage.jsx`:
- Section header: "Topaz Video AI"
- Password input with show/hide toggle (`KeyInput` component)
- "Save" button → `PUT /api/llm/topaz`
- "Test Connection" button → `POST /api/llm/topaz/test-connection`
- Success/error toast feedback

---

## Error Handling

- Missing API key: upscale endpoint returns 400 with "Topaz API key not configured"
- Upload failure: task sets `upscale_status=failed`, logs error
- Topaz job failure: task sets `upscale_status=failed`, stores error message
- Source file missing: task sets `upscale_status=failed` immediately, no retry

---

## Out of Scope

- Upscaling during the render pipeline (this is a post-render, on-demand action)
- Batch upscaling of multiple assets at once
- Configurable Topaz model or output parameters (fixed to `ast-2`, 3840×2160)
