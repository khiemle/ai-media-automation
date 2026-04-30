"""Celery task: poll Runway animation job every 30s, timeout 10min."""
import os
import time
from pathlib import Path

import requests
import requests as _requests

from console.backend.celery_app import celery_app

RUNWAY_OUTPUT_DIR = Path(os.environ.get("ASSETS_PATH", "./assets")) / "runway"
POLL_INTERVAL_S = 30
TIMEOUT_S = 600  # 10 minutes


@celery_app.task(bind=True, name="tasks.animate_asset")
def animate_asset_task(
    self,
    asset_id: int,
    runway_task_id: str,
    output_filename: str,
):
    """Poll Runway until succeeded/failed/timeout, then save video and update asset."""
    api_key = os.environ.get("RUNWAY_API_KEY", "").strip()
    model = os.environ.get("RUNWAY_MODEL", "gen3-alpha")

    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset
    from console.backend.services.runway_service import RunwayService

    svc = RunwayService(api_key=api_key, model=model)
    deadline = time.time() + TIMEOUT_S

    while time.time() < deadline:
        try:
            result = svc.poll_task(runway_task_id)
        except _requests.RequestException as exc:
            raise self.retry(exc=exc, countdown=30)
        status = result["status"]

        if status == "succeeded" and result["output_url"]:
            RUNWAY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            dest = RUNWAY_OUTPUT_DIR / output_filename
            video_resp = requests.get(result["output_url"], timeout=120)
            video_resp.raise_for_status()
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

        if status == "failed":
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

    # Timeout
    db = SessionLocal()
    try:
        row = db.get(VideoAsset, asset_id)
        if row:
            row.runway_status = "failed"
            db.commit()
    finally:
        db.close()
    return {"status": "failed", "reason": "timeout"}
