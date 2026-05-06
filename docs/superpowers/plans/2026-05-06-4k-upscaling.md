# 4K Upscaling via Topaz API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an on-demand "Upscale to 4K" button to the Assets page that uses the Topaz API to produce a 2× upscaled `video_final_4k.mp4` stored as a new VideoAsset record, with async Celery polling and status reflected in the UI without client-side polling loops.

**Architecture:** A `TopazClient` in `pipeline/topaz_client.py` wraps the 5-step Topaz API flow (create → accept → upload → complete → poll). A Celery task in `upscale_tasks.py` orchestrates the flow using `self.retry(countdown=10)` to free the worker between polls (mirrors `runway_task.py`). Three new columns on `VideoAsset` (`upscale_task_id`, `topaz_request_id`, `upscale_status`) carry status through DB so the UI auto-resumes on page load.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (mapped_column), Alembic, Celery (render_q), `requests`, React 18 + Vite

---

## File Map

| Action | File |
|--------|------|
| Create | `pipeline/topaz_client.py` |
| Create | `console/backend/tasks/upscale_tasks.py` |
| Create | `console/backend/alembic/versions/019_video_asset_topaz_upscale.py` |
| Modify | `console/backend/models/video_asset.py` |
| Modify | `console/backend/celery_app.py` |
| Modify | `console/backend/routers/production.py` |
| Modify | `console/backend/routers/llm.py` |
| Modify | `console/frontend/src/pages/LLMPage.jsx` |
| Modify | `console/frontend/src/pages/VideoAssetsPage.jsx` |
| Modify | `console/frontend/src/api/client.js` |

---

## Task 1: Database migration — add 4 columns to video_assets

**Files:**
- Create: `console/backend/alembic/versions/019_video_asset_topaz_upscale.py`

- [ ] **Step 1: Create the migration file**

```python
# console/backend/alembic/versions/019_video_asset_topaz_upscale.py
"""add topaz upscale columns to video_assets

Revision ID: 019
Revises: 018
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("video_assets", sa.Column("upscale_task_id", sa.String(100), nullable=True))
    op.add_column("video_assets", sa.Column("topaz_request_id", sa.String(100), nullable=True))
    op.add_column("video_assets", sa.Column("upscale_status", sa.String(20), nullable=True))
    op.add_column("video_assets", sa.Column("original_asset_id", sa.Integer, nullable=True))


def downgrade():
    op.drop_column("video_assets", "original_asset_id")
    op.drop_column("video_assets", "upscale_status")
    op.drop_column("video_assets", "topaz_request_id")
    op.drop_column("video_assets", "upscale_task_id")
```

- [ ] **Step 2: Run the migration**

```bash
cd console/backend
alembic upgrade head
```

Expected output ends with: `Running upgrade 018 -> 019, add topaz upscale columns to video_assets`

- [ ] **Step 3: Verify columns exist**

```bash
psql $DATABASE_URL -c "\d video_assets" | grep -E "upscale|topaz|original_asset"
```

Expected: 4 new nullable columns listed.

- [ ] **Step 4: Commit**

```bash
git add console/backend/alembic/versions/019_video_asset_topaz_upscale.py
git commit -m "feat: migration 019 — add topaz upscale columns to video_assets"
```

---

## Task 2: VideoAsset model — add 4 mapped columns

**Files:**
- Modify: `console/backend/models/video_asset.py`

- [ ] **Step 1: Add the 4 columns after `runway_invocation_id`**

In `console/backend/models/video_asset.py`, the current last field before `created_at` is:

```python
    runway_invocation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

Add these 4 lines immediately after it (before `created_at`):

```python
    upscale_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    topaz_request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    upscale_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    original_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 2: Verify import — `Integer` is already imported**

Check line 3 of the file — it already imports `Integer`. No new imports needed.

- [ ] **Step 3: Quick sanity check**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "from console.backend.models.video_asset import VideoAsset; print([c.key for c in VideoAsset.__table__.columns])"
```

Expected: list includes `upscale_task_id`, `topaz_request_id`, `upscale_status`, `original_asset_id`.

- [ ] **Step 4: Commit**

```bash
git add console/backend/models/video_asset.py
git commit -m "feat: add topaz upscale fields to VideoAsset model"
```

---

## Task 3: TopazClient — pipeline/topaz_client.py

**Files:**
- Create: `pipeline/topaz_client.py`
- Create: `tests/test_topaz_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_topaz_client.py
import json
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from pipeline.topaz_client import TopazClient


@pytest.fixture
def client():
    return TopazClient(api_key="test-key-abc")


def test_create_job_returns_request_id(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"requestId": "req-123"}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.post", return_value=mock_resp) as mock_post:
        request_id = client.create_job(width=1080, height=1920, fps=30, duration=60.0, size=50_000_000)

    assert request_id == "req-123"
    call_kwargs = mock_post.call_args
    payload = json.loads(call_kwargs.kwargs.get("data") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["data"])
    assert payload["filters"][0]["output_width"] == 2160
    assert payload["filters"][0]["output_height"] == 3840


def test_accept_job_returns_upload_url(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"urls": ["https://upload.example.com/part1"]}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.patch", return_value=mock_resp):
        url = client.accept_job("req-123")

    assert url == "https://upload.example.com/part1"


def test_upload_file_returns_etag(client, tmp_path):
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"fake video data")

    mock_resp = MagicMock()
    mock_resp.headers = {"ETag": '"abc123"'}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.put", return_value=mock_resp):
        etag = client.upload_file("https://upload.example.com/part1", test_file)

    assert etag == '"abc123"'


def test_get_status_returns_dict(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "complete", "download": {"url": "https://dl.example.com/out.mp4"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.get", return_value=mock_resp):
        result = client.get_status("req-123")

    assert result["status"] == "complete"
    assert result["download"]["url"] == "https://dl.example.com/out.mp4"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -m pytest tests/test_topaz_client.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'pipeline.topaz_client'`

- [ ] **Step 3: Create TopazClient**

```python
# pipeline/topaz_client.py
import json
import subprocess
from pathlib import Path

import requests


class TopazClient:
    BASE = "https://api.topazlabs.com"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def _headers(self) -> dict:
        return {"X-API-Key": self._api_key, "accept": "application/json"}

    def create_job(self, width: int, height: int, fps: int, duration: float, size: int) -> str:
        """Create a Topaz upscale job. Returns request_id."""
        payload = {
            "source": {
                "container": "mp4",
                "size": size,
                "duration": duration,
                "frameRate": fps,
                "frameCount": 0,
                "resolution": {"width": width, "height": height},
            },
            "filters": [{
                "model": "ast-2",
                "creativity": 0.6,
                "prompt": "cinematic, detailed, natural texture",
                "sharp": 0.5,
                "realism": 0.5,
                "input_frame_rate": fps,
                "input_width": width,
                "input_height": height,
                "output_width": width * 2,
                "output_height": height * 2,
            }],
            "output": {
                "resolution": {"width": width * 2, "height": height * 2},
                "frameRate": fps,
                "audioCodec": "AAC",
                "audioTransfer": "Copy",
                "videoEncoder": "H265",
                "dynamicCompressionLevel": "High",
                "container": "mp4",
            },
        }
        resp = requests.post(
            f"{self.BASE}/video/",
            headers={**self._headers(), "content-type": "application/json"},
            data=json.dumps(payload),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["requestId"]

    def accept_job(self, request_id: str) -> str:
        """Accept the job and get the upload URL."""
        resp = requests.patch(f"{self.BASE}/video/{request_id}/accept", headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()["urls"][0]

    def upload_file(self, upload_url: str, file_path: Path) -> str:
        """Upload the source file. Returns ETag."""
        with open(file_path, "rb") as f:
            resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=300)
        resp.raise_for_status()
        return resp.headers["ETag"]

    def complete_upload(self, request_id: str, etag: str) -> None:
        """Signal upload is complete."""
        resp = requests.patch(
            f"{self.BASE}/video/{request_id}/complete-upload",
            headers={**self._headers(), "content-type": "application/json"},
            json={"uploadResults": [{"partNum": 1, "eTag": etag}]},
            timeout=30,
        )
        resp.raise_for_status()

    def get_status(self, request_id: str) -> dict:
        """Poll job status. Returns dict with 'status' and optional 'download.url'."""
        resp = requests.get(f"{self.BASE}/video/{request_id}/status", headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def download_result(self, download_url: str, dest_path: Path) -> None:
        """Stream-download the result to dest_path."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(download_url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

    def test_connection(self) -> dict:
        """Verify API key by making a lightweight request. 401 = invalid key."""
        try:
            resp = requests.get(f"{self.BASE}/video/", headers=self._headers(), timeout=10)
            if resp.status_code == 401:
                return {"connected": False, "message": "Invalid API key"}
            return {"connected": True, "message": "Connected to Topaz API"}
        except requests.RequestException as exc:
            return {"connected": False, "message": str(exc)}


def probe_video_metadata(file_path: Path) -> dict:
    """Extract width, height, fps, duration, size via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(file_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps_str = video_stream.get("r_frame_rate", "30/1")
    num, den = map(int, fps_str.split("/"))
    fps = round(num / den)
    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "fps": fps,
        "duration": float(data["format"].get("duration", 0)),
        "size": int(data["format"].get("size", 0)),
    }
```

- [ ] **Step 4: Run tests again**

```bash
python3 -m pytest tests/test_topaz_client.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/topaz_client.py tests/test_topaz_client.py
git commit -m "feat: TopazClient for 4K upscaling API"
```

---

## Task 4: Register upscale_tasks with Celery

**Files:**
- Modify: `console/backend/celery_app.py`

- [ ] **Step 1: Add to `include` list**

In `console/backend/celery_app.py`, the `include` list currently ends with `"console.backend.tasks.runway_task"`. Add one more entry:

```python
        "console.backend.tasks.upscale_tasks",
```

- [ ] **Step 2: Add to `task_routes`**

In the same file, `task_routes` currently ends with `"tasks.animate_workflow": {"queue": "render_q"}`. Add:

```python
        "console.backend.tasks.upscale_tasks.*": {"queue": "render_q"},
```

- [ ] **Step 3: Verify Celery sees the new module**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "from console.backend.celery_app import celery_app; print('OK')"
```

Expected: `OK` (no import errors — the tasks file doesn't exist yet but the module reference is fine at import time since the task is discovered lazily).

- [ ] **Step 4: Commit**

```bash
git add console/backend/celery_app.py
git commit -m "feat: register upscale_tasks in Celery app"
```

---

## Task 5: Upscale Celery task — upscale_tasks.py

**Files:**
- Create: `console/backend/tasks/upscale_tasks.py`

- [ ] **Step 1: Create the task file**

```python
# console/backend/tasks/upscale_tasks.py
import logging
import os
from pathlib import Path

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 10
MAX_RETRIES = 60  # 60 × 10s = 10 minutes max


def _get_api_key() -> str:
    from config import api_config as _api_config
    cfg = _api_config.get_config()
    return (cfg.get("topaz", {}).get("api_key") or "").strip() or os.environ.get("TOPAZ_API_KEY", "").strip()


def _mark(asset_id: int, **kwargs):
    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset
    db = SessionLocal()
    try:
        row = db.get(VideoAsset, asset_id)
        if row:
            for k, v in kwargs.items():
                setattr(row, k, v)
            db.commit()
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="console.backend.tasks.upscale_tasks.upscale_to_4k_task",
    max_retries=MAX_RETRIES,
    queue="render_q",
)
def upscale_to_4k_task(self, asset_id: int):
    """
    First invocation: upload to Topaz, set topaz_request_id, then self.retry to poll.
    Subsequent retries: poll status, on complete download + create 4K VideoAsset.
    """
    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset

    db = SessionLocal()
    try:
        asset = db.get(VideoAsset, asset_id)
        if not asset:
            logger.error(f"[upscale] Asset {asset_id} not found")
            return

        api_key = _get_api_key()
        if not api_key:
            _mark(asset_id, upscale_status="failed")
            logger.error(f"[upscale] TOPAZ_API_KEY not configured")
            return

        from pipeline.topaz_client import TopazClient, probe_video_metadata

        client = TopazClient(api_key=api_key)
        source_path = Path(asset.file_path)

        if not source_path.exists():
            _mark(asset_id, upscale_status="failed")
            logger.error(f"[upscale] Source file missing: {source_path}")
            return

        # ── First invocation: upload phase ──────────────────────────────────
        if not asset.topaz_request_id:
            try:
                meta = probe_video_metadata(source_path)
                request_id = client.create_job(**meta)
                upload_url = client.accept_job(request_id)
                etag = client.upload_file(upload_url, source_path)
                client.complete_upload(request_id, etag)
                _mark(asset_id, topaz_request_id=request_id, upscale_status="processing")
                logger.info(f"[upscale] Asset {asset_id} uploaded → request_id={request_id}")
            except Exception as exc:
                logger.exception(f"[upscale] Upload failed for asset {asset_id}: {exc}")
                _mark(asset_id, upscale_status="failed")
                return
            raise self.retry(countdown=POLL_INTERVAL_S)

        # ── Subsequent retries: polling phase ────────────────────────────────
        request_id = asset.topaz_request_id
    finally:
        db.close()

    try:
        status_data = client.get_status(request_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=POLL_INTERVAL_S)

    status = status_data.get("status", "")

    if status in ("pending", "processing", "uploading", "queued"):
        raise self.retry(countdown=POLL_INTERVAL_S)

    if status == "complete" and status_data.get("download", {}).get("url"):
        download_url = status_data["download"]["url"]
        dest_path = source_path.parent / "video_final_4k.mp4"

        try:
            client.download_result(download_url, dest_path)
        except Exception as exc:
            raise self.retry(exc=exc, countdown=POLL_INTERVAL_S)

        # Create 4K VideoAsset record
        db2 = SessionLocal()
        try:
            from datetime import datetime, timezone
            w = asset.resolution.split("x")[0] if asset.resolution else "2160"
            h = asset.resolution.split("x")[1] if asset.resolution and "x" in asset.resolution else "3840"
            new_asset = VideoAsset(
                file_path=str(dest_path),
                source="topaz_upscale",
                resolution=f"{int(w) * 2}x{int(h) * 2}",
                duration_s=asset.duration_s,
                fps=asset.fps if hasattr(asset, "fps") else 30,
                keywords=asset.keywords,
                niche=asset.niche,
                description=asset.description,
                original_asset_id=asset_id,
                upscale_status=None,
            )
            db2.add(new_asset)
            db2.flush()
            _id = new_asset.id
            db2.commit()
            _mark(asset_id, upscale_status="ready")
            logger.info(f"[upscale] Asset {asset_id} → 4K asset {_id} at {dest_path}")
            return {"status": "ready", "asset_4k_id": _id, "file_path": str(dest_path)}
        finally:
            db2.close()

    # Topaz reported failure
    _mark(asset_id, upscale_status="failed")
    logger.error(f"[upscale] Topaz job failed for asset {asset_id}: {status_data}")
    return {"status": "failed"}
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "from console.backend.tasks.upscale_tasks import upscale_to_4k_task; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add console/backend/tasks/upscale_tasks.py
git commit -m "feat: upscale_to_4k_task Celery task with Topaz polling"
```

---

## Task 6: Production router — POST /production/assets/{asset_id}/upscale

**Files:**
- Modify: `console/backend/routers/production.py`

- [ ] **Step 1: Add the endpoint**

Find the `POST /assets/{asset_id}/animate` endpoint in `console/backend/routers/production.py` (search for `animate`). Add the following endpoint directly after it:

```python
@router.post("/assets/{asset_id}/upscale")
def upscale_asset_to_4k(asset_id: int, db: Session = Depends(get_db), _user=Depends(require_editor_or_admin)):
    """Dispatch 4K upscale for a VideoAsset via Topaz API."""
    from console.backend.models.video_asset import VideoAsset

    asset = db.get(VideoAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.upscale_status in ("pending", "processing"):
        raise HTTPException(status_code=409, detail="Upscale already in progress")

    from console.backend.tasks.upscale_tasks import upscale_to_4k_task
    task = upscale_to_4k_task.delay(asset_id)

    asset.upscale_task_id = task.id
    asset.upscale_status = "pending"
    db.commit()

    return {"task_id": task.id}
```

- [ ] **Step 2: Check that `Session`, `get_db`, `require_editor_or_admin`, `HTTPException` are already imported at the top of production.py**

```bash
grep -n "^from\|^import" /Volumes/SSD/Workspace/ai-media-automation/console/backend/routers/production.py | head -20
```

If any of `Session`, `get_db`, `require_editor_or_admin`, `HTTPException` are missing, add their imports.

- [ ] **Step 3: Test the endpoint with curl (requires backend running)**

```bash
curl -s -X POST http://localhost:8080/api/production/assets/1/upscale \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: `{"task_id": "<celery-uuid>"}` or `409` if already in progress.

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/production.py
git commit -m "feat: POST /production/assets/{id}/upscale endpoint"
```

---

## Task 7: LLM router — Topaz API key management

**Files:**
- Modify: `console/backend/routers/llm.py`

- [ ] **Step 1: Add 3 Topaz endpoints after the existing Runway endpoints**

Find the `test_runway_connection` function (the last Runway endpoint) in `console/backend/routers/llm.py`. Add the following block directly after it:

```python
@router.get("/topaz")
def get_topaz_config(_user=Depends(require_admin)):
    """Get Topaz config (masked API key)."""
    from config import api_config
    cfg = api_config.get_config()
    api_key = (cfg.get("topaz", {}).get("api_key") or "").strip() or os.environ.get("TOPAZ_API_KEY", "").strip()
    api_key_masked = f"key_...{api_key[-6:]}" if len(api_key) > 6 else ("set" if api_key else "")
    return {"api_key_masked": api_key_masked}


@router.put("/topaz")
def update_topaz_config(body: dict, _user=Depends(require_admin)):
    """Persist Topaz API key to config/api_keys.json."""
    from config import api_config
    api_key = (body.get("api_key") or "").strip()
    cfg = api_config.get_config()
    cfg["topaz"] = {"api_key": api_key}
    api_config.save_config(cfg)
    api_key_masked = f"key_...{api_key[-6:]}" if len(api_key) > 6 else ("set" if api_key else "")
    return {"api_key_masked": api_key_masked, "ok": True}


@router.post("/topaz/test-connection")
def test_topaz_connection(_user=Depends(require_admin)):
    """Test Topaz API key connectivity."""
    from config import api_config
    cfg = api_config.get_config()
    api_key = (cfg.get("topaz", {}).get("api_key") or "").strip() or os.environ.get("TOPAZ_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "TOPAZ_API_KEY not configured"}
    from pipeline.topaz_client import TopazClient
    result = TopazClient(api_key=api_key).test_connection()
    return {"ok": result["connected"], "error": result.get("message") if not result["connected"] else None}
```

- [ ] **Step 2: Restart the backend and verify endpoints appear in Swagger**

```bash
open http://localhost:8080/docs
```

Confirm `GET /api/llm/topaz`, `PUT /api/llm/topaz`, `POST /api/llm/topaz/test-connection` appear.

- [ ] **Step 3: Commit**

```bash
git add console/backend/routers/llm.py
git commit -m "feat: Topaz API key management endpoints in LLM router"
```

---

## Task 8: Frontend — client.js API helpers

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Add upscale call alongside animateWithRunway**

Find the `animateWithRunway` line in `console/frontend/src/api/client.js`:

```js
  animateWithRunway: (id, body) =>
    fetchApi(`/api/production/assets/${id}/animate`, { method: 'POST', body: JSON.stringify(body) }),
```

Add directly after it:

```js
  upscaleTo4k: (id) =>
    fetchApi(`/api/production/assets/${id}/upscale`, { method: 'POST' }),
```

- [ ] **Step 2: Add Topaz LLM API calls**

Find the section in `client.js` where Runway LLM calls are defined (search for `llm/runway`). Add alongside them:

```js
export const topazApi = {
  getConfig: () => fetchApi('/api/llm/topaz'),
  saveConfig: (api_key) => fetchApi('/api/llm/topaz', { method: 'PUT', body: JSON.stringify({ api_key }) }),
  testConnection: () => fetchApi('/api/llm/topaz/test-connection', { method: 'POST' }),
};
```

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add upscaleTo4k and topazApi helpers to client.js"
```

---

## Task 9: LLM Page frontend — Topaz section

**Files:**
- Modify: `console/frontend/src/pages/LLMPage.jsx`

- [ ] **Step 1: Add Topaz state variables**

In `LLMPage.jsx`, find where Runway state is declared (search for `runwayKey`). Add the following Topaz state right after it:

```jsx
const [topazKey, setTopazKey] = useState('');
const [topazMasked, setTopazMasked] = useState('');
const [topazSaving, setTopazSaving] = useState(false);
const [topazTesting, setTopazTesting] = useState(false);
const [topazTestResult, setTopazTestResult] = useState(null);
```

- [ ] **Step 2: Add Topaz fetch in useEffect**

In the same `useEffect` that fetches Runway config (search for `api/llm/runway`), add a parallel fetch for Topaz:

```jsx
topazApi.getConfig().then(d => setTopazMasked(d.api_key_masked || '')).catch(() => {});
```

(Import `topazApi` from `'../api/client'` at the top of the file alongside existing imports.)

- [ ] **Step 3: Add save and test handlers**

Find the Runway save/test handler functions (search for `handleRunwaySave` or similar). Add after them:

```jsx
const handleTopazSave = async () => {
  setTopazSaving(true);
  try {
    const d = await topazApi.saveConfig(topazKey);
    setTopazMasked(d.api_key_masked || '');
    setTopazKey('');
    showToast('Topaz API key saved', 'success');
  } catch {
    showToast('Failed to save Topaz key', 'error');
  } finally {
    setTopazSaving(false);
  }
};

const handleTopazTest = async () => {
  setTopazTesting(true);
  setTopazTestResult(null);
  try {
    const d = await topazApi.testConnection();
    setTopazTestResult(d.ok ? 'Connected' : d.error || 'Failed');
  } catch {
    setTopazTestResult('Connection error');
  } finally {
    setTopazTesting(false);
  }
};
```

- [ ] **Step 4: Add Topaz UI section**

Find the Runway JSX section in LLMPage.jsx (the card/section that has the Runway heading and `KeyInput`). Add an identical Topaz section directly after it. Use the Runway section's exact structure but replace every "Runway" reference with "Topaz":

```jsx
{/* Topaz Video AI */}
<div className="bg-[#1c1c22] rounded-lg p-5 border border-[#2a2a32]">
  <div className="flex items-center gap-2 mb-4">
    <span className="text-[#e8e8f0] font-medium">Topaz Video AI</span>
    {topazMasked && (
      <span className="text-xs text-[#34d399] bg-[#34d399]/10 px-2 py-0.5 rounded">
        {topazMasked}
      </span>
    )}
  </div>
  <div className="flex gap-2">
    <KeyInput
      value={topazKey}
      onChange={e => setTopazKey(e.target.value)}
      placeholder="Paste Topaz API key…"
      className="flex-1"
    />
    <button
      onClick={handleTopazSave}
      disabled={topazSaving || !topazKey}
      className="px-4 py-2 bg-[#7c6af7] text-white rounded text-sm disabled:opacity-40"
    >
      {topazSaving ? 'Saving…' : 'Save'}
    </button>
    <button
      onClick={handleTopazTest}
      disabled={topazTesting}
      className="px-4 py-2 bg-[#2a2a32] text-[#e8e8f0] rounded text-sm disabled:opacity-40"
    >
      {topazTesting ? 'Testing…' : 'Test Connection'}
    </button>
  </div>
  {topazTestResult && (
    <p className={`mt-2 text-sm ${topazTestResult === 'Connected' ? 'text-[#34d399]' : 'text-[#f87171]'}`}>
      {topazTestResult}
    </p>
  )}
</div>
```

- [ ] **Step 5: Verify in browser**

With the dev server running (`npm run dev` in `console/frontend`), navigate to the LLM tab. Confirm the "Topaz Video AI" section appears with a key input, Save button, and Test Connection button. Test Connection should return a success or auth-error message.

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/LLMPage.jsx
git commit -m "feat: add Topaz API key management to LLM page"
```

---

## Task 10: VideoAssetsPage frontend — upscale button and states

**Files:**
- Modify: `console/frontend/src/pages/VideoAssetsPage.jsx`

- [ ] **Step 1: Add upscale handler**

In `VideoAssetsPage.jsx`, find the `handleAnimate` function (or the animate click handler). Add a parallel `handleUpscale` function after it:

```jsx
const handleUpscale = async (asset) => {
  try {
    await assetsApi.upscaleTo4k(asset.id);
    showToast('4K upscale queued', 'success');
    refetch();  // refresh asset list to show pending status
  } catch (err) {
    const msg = err?.detail || 'Failed to start upscale';
    showToast(msg, 'error');
  }
};
```

- [ ] **Step 2: Add a helper to determine if an asset is already 4K**

Add this pure function near the top of the component (after imports):

```js
function isAlready4K(resolution) {
  if (!resolution) return false;
  const parts = resolution.split('x').map(Number);
  return parts.some(d => d >= 3840);
}
```

- [ ] **Step 3: Add upscale UI to each asset card**

In the asset card render (where the Runway "Animate" button is rendered), add the following upscale status block immediately after the animate button:

```jsx
{/* 4K upscale */}
{!isAlready4K(asset.resolution) && (
  <div className="mt-2">
    {(!asset.upscale_status || asset.upscale_status === 'failed') && (
      <button
        onClick={() => handleUpscale(asset)}
        className="w-full px-3 py-1.5 text-xs bg-[#2a2a32] hover:bg-[#7c6af7]/20 text-[#9090a8] hover:text-[#7c6af7] rounded border border-[#2a2a32] hover:border-[#7c6af7]/40 transition-colors"
      >
        {asset.upscale_status === 'failed' ? '⚠ Retry 4K Upscale' : '↑ Upscale to 4K'}
      </button>
    )}
    {(asset.upscale_status === 'pending') && (
      <div className="flex items-center gap-1.5 text-xs text-[#fbbf24]">
        <span className="animate-spin">⟳</span> Queued…
      </div>
    )}
    {(asset.upscale_status === 'processing') && (
      <div className="flex items-center gap-1.5 text-xs text-[#4a9eff]">
        <span className="animate-spin">⟳</span> Upscaling…
      </div>
    )}
    {asset.upscale_status === 'ready' && (
      <span className="inline-flex items-center gap-1 text-xs text-[#34d399] bg-[#34d399]/10 px-2 py-0.5 rounded">
        ✓ 4K Ready
      </span>
    )}
  </div>
)}
```

- [ ] **Step 4: Verify in browser**

Navigate to the Assets page (`/assets`). Confirm:
- Non-4K assets show the "↑ Upscale to 4K" button
- Assets with `upscale_status=pending` show spinner + "Queued…"
- Assets with `upscale_status=processing` show spinner + "Upscaling…"
- Assets with `upscale_status=ready` show "✓ 4K Ready" badge
- Assets already at 4K resolution show no upscale UI
- Clicking the button dispatches the task and immediately shows the pending spinner (after refetch)

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/VideoAssetsPage.jsx
git commit -m "feat: upscale-to-4K button and status states on Assets page"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - ✅ Topaz API key in LLM tab (Tasks 7, 8, 9)
  - ✅ POST /upscale endpoint (Task 6)
  - ✅ Celery task with self.retry (Task 5)
  - ✅ DB migration + model (Tasks 1, 2)
  - ✅ Celery registered (Task 4)
  - ✅ TopazClient with all methods (Task 3)
  - ✅ UI button + states (Task 10)
  - ✅ Separate 4K VideoAsset created on completion (Task 5)
  - ✅ upscale_task_id + topaz_request_id + upscale_status (Tasks 1, 2, 5)
  - ✅ No client-side polling (status read from DB on mount)
  - ✅ Error cases: missing file, missing API key, Topaz failure (Task 5)

- [x] **Type consistency:** `upscale_status`, `topaz_request_id`, `upscale_task_id`, `original_asset_id` are consistently named across migration (Task 1), model (Task 2), task (Task 5), and endpoint (Task 6).

- [x] **No placeholders:** All steps include concrete code.
