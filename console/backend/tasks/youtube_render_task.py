"""Celery task: orchestrate full YouTube long-form video rendering."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from console.backend.celery_app import celery_app

# Import models at module load so SQLAlchemy resolves the YoutubeVideo →
# VideoTemplate FK before any task flushes a YoutubeVideo update.
# Without this, ANY task that does db.commit() on a YoutubeVideo would hit
# NoReferencedTableError because video_templates isn't in the metadata yet.
from console.backend.models.youtube_video import YoutubeVideo  # noqa: F401
from console.backend.models.video_template import VideoTemplate  # noqa: F401

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(
    os.environ.get("RENDER_OUTPUT_PATH")
    or os.environ.get("OUTPUT_PATH")
    or "./assets/output"
)


def _update_chunk_status(db, youtube_video_id: int, chunk_idx: int, patch: dict) -> None:
    """Atomically merge `patch` into render_parts[chunk_idx] using Postgres jsonb_set.
    Avoids read-modify-write races with parallel chunk tasks on the same video."""
    import json
    from sqlalchemy import text as _sql
    db.execute(
        _sql("""
            UPDATE youtube_videos
            SET render_parts = jsonb_set(
                COALESCE(render_parts, '[]'::jsonb),
                ARRAY[CAST(:idx_str AS text)],
                COALESCE(render_parts->CAST(:idx_int AS int), '{}'::jsonb) || CAST(:patch AS jsonb),
                true
            )
            WHERE id = :video_id
        """),
        {"idx_str": str(chunk_idx), "idx_int": chunk_idx,
         "patch": json.dumps(patch), "video_id": youtube_video_id},
    )
    db.commit()


def _publish_youtube_render_event(youtube_video_id: int, payload: dict | None = None) -> None:
    """Publish a render event to the per-video Redis channel for WS clients.
    The payload itself is a hint; the WS handler will re-snapshot via DB anyway."""
    try:
        from console.backend.services.pipeline_service import _get_redis
        import json
        _get_redis().publish(
            f"render:youtube:{youtube_video_id}",
            json.dumps(payload or {"type": "tick"}),
        )
    except Exception:
        pass  # best-effort; never fail a render because pubsub is down


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_video",
    queue="render_q",
    max_retries=2,
    default_retry_delay=60,
)
def render_youtube_video_task(self, youtube_video_id: int):
    """Render a long-form landscape YouTube video."""
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_template import VideoTemplate  # noqa: F401 — registers FK target
    from pipeline.youtube_ffmpeg import render_landscape

    db = SessionLocal()
    video = None
    render_completed = False
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            logger.error("YoutubeVideo %s not found", youtube_video_id)
            return {"status": "failed", "reason": "video not found"}

        if video.status not in {"draft", "queued"}:
            logger.warning(
                "YoutubeVideo %s is already %s; skipping render",
                youtube_video_id, video.status,
            )
            return {"status": "skipped", "reason": f"already {video.status}"}

        video.status = "rendering"
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"youtube_{youtube_video_id}_v{int(time.time())}.mp4"

        render_landscape(video, output_path, db)
        render_completed = True

        video.status = "done"
        video.output_path = str(output_path)
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        logger.info("YoutubeVideo %s rendered to %s", youtube_video_id, output_path)
        return {"status": "done", "output_path": str(output_path)}

    except Exception as exc:
        logger.exception("YoutubeVideo %s render failed: %s", youtube_video_id, exc)
        if video is not None and not render_completed:
            try:
                video.status = "failed"
                db.commit()
                _publish_youtube_render_event(youtube_video_id)
            except Exception as db_exc:
                db.rollback()
                logger.error(
                    "Failed to persist 'failed' status for YoutubeVideo %s: %s",
                    youtube_video_id, db_exc,
                )
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_audio_preview",
    queue="render_q",
    max_retries=1,
    default_retry_delay=60,
)
def render_youtube_audio_preview_task(self, youtube_video_id: int):
    """Render audio-only preview (first 2 min) for ASMR/soundscape videos."""
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_audio_only import render_audio_preview

    db = SessionLocal()
    video = None
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            return {"status": "failed", "reason": "video not found"}

        # Auto-seed sfx_seed if missing
        if video.sfx_seed is None:
            import random
            video.sfx_seed = random.randint(1, 2**31 - 1)

        video.status = "audio_preview_rendering"
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_dir = OUTPUT_DIR / f"youtube_{youtube_video_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "audio_preview.wav"

        full_dur = int((video.target_duration_h or 3.0) * 3600)
        end_s = min(120.0, full_dur)

        render_audio_preview(video, out_path, db, start_s=0.0, end_s=end_s)

        video.audio_preview_path = str(out_path)
        video.status = "audio_preview_ready"
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        logger.info("YoutubeVideo %s audio preview ready: %s", youtube_video_id, out_path)
        return {"status": "ready", "path": str(out_path)}
    except Exception as exc:
        logger.exception("YoutubeVideo %s audio preview failed: %s", youtube_video_id, exc)
        if video is not None:
            try:
                video.status = "queued"  # roll back to queued so editor can retry
                db.commit()
                _publish_youtube_render_event(youtube_video_id)
            except Exception:
                db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_video_preview",
    queue="render_q",
    max_retries=1,
    default_retry_delay=60,
)
def render_youtube_video_preview_task(self, youtube_video_id: int):
    """Render first 2 min of full video (with audio) as preview."""
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import render_landscape

    db = SessionLocal()
    video = None
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            return {"status": "failed", "reason": "video not found"}

        video.status = "video_preview_rendering"
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_dir = OUTPUT_DIR / f"youtube_{youtube_video_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "video_preview.mp4"

        full_dur = int((video.target_duration_h or 3.0) * 3600)
        end_s = min(120.0, full_dur)

        render_landscape(video, out_path, db, start_s=0.0, end_s=end_s)

        video.video_preview_path = str(out_path)
        video.status = "video_preview_ready"
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        logger.info("YoutubeVideo %s video preview ready: %s", youtube_video_id, out_path)
        return {"status": "ready", "path": str(out_path)}
    except Exception as exc:
        logger.exception("YoutubeVideo %s video preview failed: %s", youtube_video_id, exc)
        if video is not None:
            try:
                video.status = "audio_preview_ready"  # back one gate
                db.commit()
                _publish_youtube_render_event(youtube_video_id)
            except Exception:
                db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_chunk",
    queue="render_q",
    max_retries=2,
    default_retry_delay=60,
)
def render_youtube_chunk_task(self, youtube_video_id: int, chunk_idx: int, start_s: float, end_s: float):
    """Render a single chunk of a YouTube video.

    All chunks MUST use identical encoder settings (codec, fps, resolution,
    audio sample rate) so the final concat with -c copy works. The youtube_ffmpeg
    render_landscape function enforces this via fixed encoder params keyed off
    the FULL video duration (not chunk duration) — see the preset selection in
    render_landscape.
    """
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import render_landscape
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            return {"status": "failed", "reason": "video not found"}

        # Mark chunk running
        _update_chunk_status(db, youtube_video_id, chunk_idx, {
            "idx": chunk_idx, "start_s": start_s, "end_s": end_s,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        _publish_youtube_render_event(youtube_video_id)

        # Per-chunk subdirectory so parallel chunks don't collide on temp files
        chunk_dir = OUTPUT_DIR / f"youtube_{youtube_video_id}" / f"chunk_{chunk_idx}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_path = chunk_dir / "chunk.mp4"

        render_landscape(video, chunk_path, db, start_s=start_s, end_s=end_s)

        # Mark completed (atomic)
        _update_chunk_status(db, youtube_video_id, chunk_idx, {
            "status": "completed",
            "file_path": str(chunk_path),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        _publish_youtube_render_event(youtube_video_id)

        logger.info("YoutubeVideo %s chunk %s done: %s", youtube_video_id, chunk_idx, chunk_path)
        return {"chunk_idx": chunk_idx, "path": str(chunk_path)}
    except Exception as exc:
        logger.exception("YoutubeVideo %s chunk %s failed: %s", youtube_video_id, chunk_idx, exc)
        try:
            _update_chunk_status(db, youtube_video_id, chunk_idx, {
                "status": "failed",
                "error": str(exc)[:500],
            })
            _publish_youtube_render_event(youtube_video_id)
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="tasks.concat_youtube_chunks",
    queue="render_q",
)
def concat_youtube_chunks_task(self, _chunk_results, youtube_video_id: int):
    """Concatenate all rendered chunks into the final video.

    Receives the chord header's results as the first arg (we don't use them
    individually — we re-read render_parts from the DB to handle resume cases).
    """
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.concat import concat_parts

    db = SessionLocal()
    video = None
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            return {"status": "failed", "reason": "video not found"}

        parts = sorted(video.render_parts or [], key=lambda p: p["idx"])
        missing = [p for p in parts if p.get("status") != "completed" or not p.get("file_path")]
        if missing:
            raise RuntimeError(f"Cannot concat: {len(missing)} chunks not completed")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_dir = OUTPUT_DIR / f"youtube_{youtube_video_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        final_path = out_dir / f"final_v{int(time.time())}.mp4"

        concat_parts([p["file_path"] for p in parts], final_path)

        video.output_path = str(final_path)
        video.status = "done"
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        logger.info("YoutubeVideo %s concat done: %s", youtube_video_id, final_path)
        return {"status": "done", "output_path": str(final_path)}
    except Exception as exc:
        logger.exception("YoutubeVideo %s concat failed: %s", youtube_video_id, exc)
        if video is not None:
            try:
                video.status = "video_preview_ready"  # back to last gate
                db.commit()
                _publish_youtube_render_event(youtube_video_id)
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_chunked_orchestrator",
    queue="render_q",
)
def render_youtube_chunked_orchestrator_task(self, youtube_video_id: int):
    """Plan chunks, persist render_parts, and dispatch a chord(group(chunks), concat)."""
    import math
    import random
    from celery import chord, group
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    video = None
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            return {"status": "failed", "reason": "video not found"}

        if video.sfx_seed is None:
            video.sfx_seed = random.randint(1, 2**31 - 1)

        full_dur = int((video.target_duration_h or 3.0) * 3600)
        n_chunks = max(1, math.ceil(full_dur / 300))
        chunk_size = math.ceil(full_dur / n_chunks)

        # Build / replace render_parts. Preserve completed entries (resume case).
        existing = {p["idx"]: p for p in (video.render_parts or [])}
        new_parts = []
        for i in range(n_chunks):
            start = i * chunk_size
            end = min(full_dur, start + chunk_size)
            prev = existing.get(i, {})
            if prev.get("status") == "completed" and prev.get("file_path"):
                new_parts.append(prev)
            else:
                new_parts.append({
                    "idx": i, "start_s": start, "end_s": end, "status": "pending",
                    "file_path": None, "started_at": None, "completed_at": None,
                })
        video.render_parts = new_parts
        flag_modified(video, "render_parts")
        video.status = "rendering"
        db.commit()
        _publish_youtube_render_event(youtube_video_id)

        logger.info("YoutubeVideo %s planned %s chunks of ~%ss each", youtube_video_id, n_chunks, chunk_size)

        pending = [p for p in new_parts if p["status"] != "completed"]
        if not pending:
            concat_youtube_chunks_task.delay([], youtube_video_id)
            return {"status": "all-completed", "n_chunks": n_chunks}

        sigs = [
            render_youtube_chunk_task.s(youtube_video_id, p["idx"], p["start_s"], p["end_s"])
            for p in pending
        ]
        chord(group(sigs))(concat_youtube_chunks_task.s(youtube_video_id))
        return {"status": "dispatched", "n_chunks": n_chunks, "pending": len(pending)}
    except Exception as exc:
        logger.exception("YoutubeVideo %s chunked orchestrator failed: %s", youtube_video_id, exc)
        if video is not None:
            try:
                video.status = "video_preview_ready"
                db.commit()
                _publish_youtube_render_event(youtube_video_id)
            except Exception:
                db.rollback()
        raise
    finally:
        db.close()
