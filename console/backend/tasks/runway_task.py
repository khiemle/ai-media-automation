"""Celery tasks: poll Runway workflow invocation, recover stale pending assets."""
import os
from pathlib import Path

import requests

from console.backend.celery_app import celery_app

RUNWAY_OUTPUT_DIR = Path(os.environ.get("ASSETS_PATH", "/app/assets/video_db")) / "runway"
POLL_INTERVAL_S = 30
MAX_RETRIES = 20  # 20 × 30s = 10 minutes max


def _get_api_key() -> str:
    from config import api_config as _api_config
    cfg = _api_config.get_config()
    return (cfg.get("runway", {}).get("api_key") or "").strip() or os.environ.get("RUNWAY_API_KEY", "").strip()


def _mark_status(asset_id: int, status: str, file_path: str | None = None):
    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset
    db = SessionLocal()
    try:
        row = db.get(VideoAsset, asset_id)
        if row:
            row.runway_status = status
            if file_path is not None:
                row.file_path = file_path
                row.asset_type = "video_clip"
            db.commit()
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.animate_workflow", max_retries=MAX_RETRIES)
def animate_workflow_task(self, asset_id: int, invocation_id: str, output_filename: str):
    """Check Runway once; reschedule if still running. Frees the worker between polls."""
    from console.backend.services.runway_service import RunwayService

    api_key = _get_api_key()
    svc = RunwayService(api_key=api_key)

    try:
        result = svc.poll_workflow_invocation(invocation_id)
    except requests.RequestException as exc:
        raise self.retry(exc=exc, countdown=POLL_INTERVAL_S)

    status = result["status"]

    if status in ("PENDING", "RUNNING"):
        raise self.retry(countdown=POLL_INTERVAL_S)

    if status == "SUCCEEDED" and result["output_url"]:
        RUNWAY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        dest = RUNWAY_OUTPUT_DIR / output_filename
        try:
            video_resp = requests.get(result["output_url"], timeout=120)
            video_resp.raise_for_status()
        except requests.RequestException as exc:
            raise self.retry(exc=exc, countdown=POLL_INTERVAL_S)
        dest.write_bytes(video_resp.content)
        _mark_status(asset_id, "ready", file_path=str(dest))
        return {"status": "ready", "file_path": str(dest)}

    # FAILED or unrecognised status
    _mark_status(asset_id, "failed")
    return {"status": "failed"}


@celery_app.task(name="tasks.recover_pending_runway")
def recover_pending_runway():
    """Re-queue poll tasks for any VideoAsset stuck in runway_status='pending'."""
    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset
    from sqlalchemy import select

    db = SessionLocal()
    try:
        rows = db.execute(
            select(VideoAsset).where(VideoAsset.runway_status == "pending")
        ).scalars().all()
        for row in rows:
            if not row.runway_invocation_id:
                continue
            output_filename = f"runway_{row.id}.mp4"
            animate_workflow_task.apply_async(
                args=[row.id, row.runway_invocation_id, output_filename],
                countdown=5,
            )
    finally:
        db.close()
