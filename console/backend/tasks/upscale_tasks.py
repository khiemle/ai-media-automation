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
    First invocation: upload source to Topaz, persist topaz_request_id, then self.retry to poll.
    Subsequent retries: poll status; on complete download result and create 4K VideoAsset record.
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
            logger.error("[upscale] TOPAZ_API_KEY not configured")
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
        # Keep reference to asset fields needed after db.close()
        asset_file_path = asset.file_path
        asset_resolution = asset.resolution
        asset_duration_s = asset.duration_s
        asset_keywords = asset.keywords
        asset_niche = asset.niche
        asset_description = asset.description
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
        source_path = Path(asset_file_path)
        dest_path = source_path.parent / "video_final_4k.mp4"

        try:
            client.download_result(download_url, dest_path)
        except Exception as exc:
            raise self.retry(exc=exc, countdown=POLL_INTERVAL_S)

        db2 = SessionLocal()
        try:
            from datetime import datetime, timezone
            parts = asset_resolution.split("x") if asset_resolution and "x" in asset_resolution else ["1080", "1920"]
            new_w = int(parts[0]) * 2
            new_h = int(parts[1]) * 2
            new_asset = VideoAsset(
                file_path=str(dest_path),
                source="topaz_upscale",
                resolution=f"{new_w}x{new_h}",
                duration_s=asset_duration_s,
                keywords=asset_keywords,
                niche=asset_niche,
                description=asset_description,
                original_asset_id=asset_id,
            )
            db2.add(new_asset)
            db2.flush()
            new_id = new_asset.id
            db2.commit()
            _mark(asset_id, upscale_status="ready")
            logger.info(f"[upscale] Asset {asset_id} → 4K asset {new_id} at {dest_path}")
            return {"status": "ready", "asset_4k_id": new_id, "file_path": str(dest_path)}
        finally:
            db2.close()

    # Topaz reported failure or unrecognised status
    _mark(asset_id, upscale_status="failed")
    logger.error(f"[upscale] Topaz job failed for asset {asset_id}: status={status}")
    return {"status": "failed"}
