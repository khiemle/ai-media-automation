"""Celery task: poll Runway workflow invocation every 30s, timeout 10min."""
import os
import time
from pathlib import Path

import requests

from console.backend.celery_app import celery_app

RUNWAY_OUTPUT_DIR = Path(os.environ.get("ASSETS_PATH", "/app/assets/video_db")) / "runway"
POLL_INTERVAL_S = 30
TIMEOUT_S = 600  # 10 minutes


@celery_app.task(bind=True, name="tasks.animate_workflow")
def animate_workflow_task(
    self,
    asset_id: int,
    invocation_id: str,
    output_filename: str,
):
    """Poll Runway workflow invocation until SUCCEEDED/FAILED/timeout, then save video."""
    api_key = os.environ.get("RUNWAY_API_KEY", "").strip()

    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset
    from console.backend.services.runway_service import RunwayService

    svc = RunwayService(api_key=api_key)
    deadline = time.time() + TIMEOUT_S

    while time.time() < deadline:
        try:
            result = svc.poll_workflow_invocation(invocation_id)
        except requests.RequestException as exc:
            raise self.retry(exc=exc, countdown=30)

        status = result["status"]

        if status == "SUCCEEDED" and result["output_url"]:
            RUNWAY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            dest = RUNWAY_OUTPUT_DIR / output_filename
            try:
                video_resp = requests.get(result["output_url"], timeout=120)
                video_resp.raise_for_status()
            except requests.RequestException as exc:
                raise self.retry(exc=exc, countdown=30)
            dest.write_bytes(video_resp.content)

            db = SessionLocal()
            try:
                row = db.get(VideoAsset, asset_id)
                if row:
                    row.file_path = str(dest)
                    row.runway_status = "ready"
                    row.asset_type = "video_clip"
                    db.commit()
            finally:
                db.close()
            return {"status": "ready", "file_path": str(dest)}

        if status == "FAILED":
            db = SessionLocal()
            try:
                row = db.get(VideoAsset, asset_id)
                if row:
                    row.runway_status = "failed"
                    db.commit()
            finally:
                db.close()
            return {"status": "failed"}

        time.sleep(POLL_INTERVAL_S)

    # Timeout — mark as failed
    db = SessionLocal()
    try:
        row = db.get(VideoAsset, asset_id)
        if row:
            row.runway_status = "failed"
            db.commit()
    finally:
        db.close()
    return {"status": "failed", "reason": "timeout"}
