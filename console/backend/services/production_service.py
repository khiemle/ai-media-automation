"""ProductionService — asset search, scene editing, TTS/Veo regen, start production."""
import math
import logging
import mimetypes
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from console.backend.models.video_asset import VideoAsset
from console.backend.models.pipeline_job import PipelineJob
from console.backend.schemas.common import PaginatedResponse
from console.backend.utils.file_naming import make_unique_path

logger = logging.getLogger(__name__)

_ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
_ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm'}
_ALLOWED_ASSET_EXTENSIONS = _ALLOWED_IMAGE_EXTENSIONS | _ALLOWED_VIDEO_EXTENSIONS
_DEFAULT_ASSETS_DIR = Path(os.path.abspath(
    os.environ.get('ASSETS_PATH', './assets/video_db/manual')
))


def generate_video_thumbnail(video_path: str) -> str | None:
    """Extract a JPEG thumbnail from a video at the 1-second mark using ffmpeg.

    Args:
        video_path: Path to the video file.

    Returns:
        Path to the generated thumbnail file (same directory, suffix _thumb.jpg),
        or None if ffmpeg fails or is not available.
    """
    p = Path(video_path)
    thumb_path = p.parent / f"{p.stem}_thumb.jpg"
    try:
        result = subprocess.run(
            ["ffmpeg", "-ss", "1", "-i", str(p), "-frames:v", "1", "-q:v", "2", str(thumb_path), "-y"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and thumb_path.is_file():
            return str(thumb_path)
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


class ProductionService:
    def __init__(self, db: Session):
        self.db = db

    def _audit(self, user_id: int, action: str, target_type: str, target_id: str, details: dict = None) -> None:
        from console.backend.models.audit_log import AuditLog
        self.db.add(AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        ))
        # Commit happens in the calling method

    # ── Assets ────────────────────────────────────────────────────────────────

    def search_assets(
        self,
        keywords: list[str] | None = None,
        niche: list[str] | None = None,
        source: str | None = None,
        min_duration: float | None = None,
        asset_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse:
        query = self.db.query(VideoAsset)

        if keywords:
            # Match if asset.keywords overlaps with the provided keywords (PostgreSQL && operator)
            query = query.filter(VideoAsset.keywords.overlap(keywords))

        if niche:
            query = query.filter(VideoAsset.niche.overlap(niche))

        if source:
            query = query.filter(VideoAsset.source == source)

        if min_duration is not None:
            query = query.filter(VideoAsset.duration_s >= min_duration)

        if asset_type:
            query = query.filter(VideoAsset.asset_type == asset_type)

        total = query.count()
        rows = (
            query.order_by(VideoAsset.quality_score.desc(), VideoAsset.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        items = [self._asset_to_dict(a) for a in rows]
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            pages=math.ceil(total / per_page) if per_page else 1,
            per_page=per_page,
        )

    def get_asset(self, asset_id: int) -> dict:
        asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            raise KeyError(f"Asset {asset_id} not found")
        return self._asset_to_dict(asset)

    def _asset_to_dict(self, asset: VideoAsset) -> dict:
        return {
            "id": asset.id,
            "file_path": asset.file_path,
            "thumbnail_url": asset.thumbnail_path,
            "source": asset.source,
            "asset_type": asset.asset_type,
            "runway_status": asset.runway_status,
            "runway_invocation_id": asset.runway_invocation_id,
            "upscale_status": asset.upscale_status,
            "upscale_task_id": asset.upscale_task_id,
            "topaz_request_id": asset.topaz_request_id,
            "original_asset_id": asset.original_asset_id,
            "description": asset.description,
            "keywords": asset.keywords or [],
            "niche": asset.niche or [],
            "duration_s": asset.duration_s,
            "resolution": asset.resolution,
            "quality_score": asset.quality_score,
            "usage_count": asset.usage_count,
            "generation_prompt": asset.generation_prompt,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
        }

    def update_asset(
        self,
        asset_id: int,
        user_id: int,
        description: str | None = None,
        keywords: list[str] | None = None,
        niche: list[str] | None = None,
        quality_score: float | None = None,
    ) -> dict:
        asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            raise KeyError(f"Asset {asset_id} not found")
        if description is not None:
            asset.description = description
        if keywords is not None:
            asset.keywords = keywords
        if niche is not None:
            asset.niche = niche
        if quality_score is not None:
            asset.quality_score = quality_score
        self._audit(user_id, "update", "video_asset", str(asset_id))
        self.db.commit()
        self.db.refresh(asset)
        return self._asset_to_dict(asset)

    def delete_asset(self, asset_id: int, user_id: int) -> None:
        asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            raise KeyError(f"Asset {asset_id} not found")
        self.db.delete(asset)
        self._audit(user_id, "delete", "video_asset", str(asset_id))
        self.db.commit()

    def import_asset(
        self,
        file_bytes: bytes,
        filename: str,
        source: str,
        description: str | None,
        keywords: list[str] | None,
        asset_type: str | None = None,
        generation_prompt: str | None = None,
        assets_dir: Path | None = None,
        user_id: int | None = None,
        title: str | None = None,
    ) -> dict:
        ext = Path(filename).suffix.lower()
        if ext not in _ALLOWED_ASSET_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

        if not asset_type:
            asset_type = 'still_image' if ext in _ALLOWED_IMAGE_EXTENSIONS else 'video_clip'
        save_dir = Path(assets_dir) if assets_dir else _DEFAULT_ASSETS_DIR
        save_dir.mkdir(parents=True, exist_ok=True)

        row = VideoAsset(
            file_path='',
            source=source,
            asset_type=asset_type,
            description=description,
            keywords=keywords or [],
            generation_prompt=generation_prompt or None,
        )
        self.db.add(row)
        self.db.flush()

        label = title or description or Path(filename).stem
        dest = make_unique_path(label, ext, save_dir)
        dest.write_bytes(file_bytes)
        row.file_path = str(dest)

        # Set thumbnail_path based on asset type
        if asset_type == 'still_image':
            row.thumbnail_path = str(dest)
        elif asset_type == 'video_clip':
            row.thumbnail_path = generate_video_thumbnail(str(dest))

        if user_id is not None:
            self._audit(user_id, "import", "video_asset", str(row.id))
        self.db.commit()
        self.db.refresh(row)
        return self._asset_to_dict(row)

    def stream_asset_path(self, asset_id: int) -> str:
        asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            raise KeyError(f"Asset {asset_id} not found")
        if not asset.file_path:
            raise ValueError(f"Asset {asset_id} has no file path")
        return asset.file_path

    def get_thumbnail_path(self, asset_id: int, generate: bool) -> tuple[str, str] | None:
        asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            return None

        # Serve existing thumbnail
        if asset.thumbnail_path and Path(asset.thumbnail_path).is_file():
            media_type, _ = mimetypes.guess_type(asset.thumbnail_path)
            return (asset.thumbnail_path, media_type or "image/jpeg")

        if not generate:
            return None

        # Lazy generation for videos
        if asset.asset_type == 'video_clip':
            if not Path(asset.file_path).is_file():
                return None
            thumb_path = generate_video_thumbnail(asset.file_path)
            if thumb_path is None:
                return None
            if asset.thumbnail_path != thumb_path:
                asset.thumbnail_path = thumb_path
                self.db.commit()
            return (thumb_path, "image/jpeg")

        # Still images serve themselves
        if asset.asset_type == 'still_image':
            if not Path(asset.file_path).is_file():
                return None
            if asset.thumbnail_path != asset.file_path:
                asset.thumbnail_path = asset.file_path
                self.db.commit()
            media_type, _ = mimetypes.guess_type(asset.file_path)
            return (asset.file_path, media_type or "image/jpeg")

        return None

    # ── Scene editing ─────────────────────────────────────────────────────────

    def replace_scene_asset(
        self,
        script_id: int,
        scene_index: int,
        asset_id: int,
        db_user_id: int,
    ) -> dict:
        # 1. Fetch asset
        asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            raise KeyError(f"Asset {asset_id} not found")

        # 2. Fetch script via raw SQL (core pipeline table)
        row = self.db.execute(
            text("SELECT id, script_json, status FROM generated_scripts WHERE id = :id"),
            {"id": script_id},
        ).fetchone()
        if not row:
            raise KeyError(f"Script {script_id} not found")

        # 3. Parse script_json
        script_json = row.script_json if isinstance(row.script_json, dict) else {}
        scenes = script_json.get("scenes", [])

        if scene_index < 0 or scene_index >= len(scenes):
            raise ValueError(
                f"Scene index {scene_index} out of range (script has {len(scenes)} scenes)"
            )

        scene = scenes[scene_index]
        scene["asset_id"] = asset_id
        if asset.keywords:
            scene["visual_hint"] = " ".join(asset.keywords[:3])
        scenes[scene_index] = scene

        # 4. Increment usage_count
        asset.usage_count = (asset.usage_count or 0) + 1

        # 5. Update script
        import json as _json

        new_status = row.status
        if row.status == "approved":
            new_status = "editing"

        updated_script_json = _json.dumps(dict(script_json, scenes=scenes))

        self.db.execute(
            text(
                "UPDATE generated_scripts SET script_json = :sj::jsonb, status = :st, edited_by = :uid "
                "WHERE id = :id"
            ),
            {
                "sj": updated_script_json,
                "st": new_status,
                "uid": db_user_id,
                "id": script_id,
            },
        )

        self.db.commit()

        logger.info(f"Replaced asset for script {script_id} scene {scene_index} → asset {asset_id}")
        return scene

    def regenerate_scene_tts(self, script_id: int, scene_index: int) -> str:
        """Dispatch TTS regen Celery task, return task_id."""
        from console.backend.tasks.production_tasks import regenerate_tts_task

        result = regenerate_tts_task.delay(script_id, scene_index)
        return result.id

    def generate_scene_veo(self, script_id: int, scene_index: int) -> str:
        """Veo scene generation is not wired yet for the console."""
        raise NotImplementedError("Scene-level Veo generation is not integrated yet")

    def start_production(self, script_id: int, user_id: int) -> str:
        """Validate script status, set to 'producing', create a job, dispatch render task."""
        # 1. Load script
        row = self.db.execute(
            text("SELECT id, status, video_format FROM generated_scripts WHERE id = :id"),
            {"id": script_id},
        ).fetchone()
        if not row:
            raise KeyError(f"Script {script_id} not found")

        # 2. Validate status
        if row.status not in ("approved", "editing"):
            raise ValueError(
                f"Script must be 'approved' or 'editing' to start production, got '{row.status}'"
            )

        # 3. Set status to 'producing'
        self.db.execute(
            text("UPDATE generated_scripts SET status = 'producing' WHERE id = :id"),
            {"id": script_id},
        )

        # 4. Create pipeline_job row with video_format from script
        job = PipelineJob(
            job_type="render",
            status="queued",
            script_id=script_id,
            video_format=row.video_format or "short",  # Propagate format from script
        )
        self.db.add(job)
        self.db.flush()  # get job.id before dispatch

        # 5. Dispatch render task
        from console.backend.tasks.production_tasks import render_video_task

        result = render_video_task.delay(script_id)

        # 6. Update job with celery_task_id
        job.celery_task_id = result.id
        job.started_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"Production started: script {script_id}, task {result.id}, job {job.id}")
        return result.id

    # ── Script reader ─────────────────────────────────────────────────────────

    def get_script(self, script_id: int) -> dict:
        """Return the full script_json plus metadata from generated_scripts."""
        row = self.db.execute(
            text(
                "SELECT id, topic, niche, template, status, script_json, editor_notes, "
                "approved_at, created_at FROM generated_scripts WHERE id = :id"
            ),
            {"id": script_id},
        ).fetchone()
        if not row:
            raise KeyError(f"Script {script_id} not found")

        return {
            "id": row.id,
            "topic": row.topic if hasattr(row, "topic") else None,
            "niche": row.niche if hasattr(row, "niche") else None,
            "template": row.template if hasattr(row, "template") else None,
            "status": row.status if hasattr(row, "status") else None,
            "editor_notes": row.editor_notes if hasattr(row, "editor_notes") else None,
            "approved_at": row.approved_at.isoformat() if hasattr(row, "approved_at") and row.approved_at else None,
            "created_at": row.created_at.isoformat() if hasattr(row, "created_at") and row.created_at else None,
            "script_json": row.script_json if isinstance(row.script_json, dict) else {},
        }
