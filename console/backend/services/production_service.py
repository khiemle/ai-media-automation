"""ProductionService — asset search, scene editing, TTS/Veo regen, start production."""
import math
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from console.backend.models.video_asset import VideoAsset
from console.backend.models.pipeline_job import PipelineJob
from console.backend.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class ProductionService:
    def __init__(self, db: Session):
        self.db = db

    # ── Assets ────────────────────────────────────────────────────────────────

    def search_assets(
        self,
        keywords: list[str] | None = None,
        niche: list[str] | None = None,
        source: str | None = None,
        min_duration: float | None = None,
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
            "keywords": asset.keywords or [],
            "niche": asset.niche or [],
            "duration_s": asset.duration_s,
            "resolution": asset.resolution,
            "quality_score": asset.quality_score,
            "usage_count": asset.usage_count,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
        }

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
            text("SELECT id, status FROM generated_scripts WHERE id = :id"),
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

        # 4. Create pipeline_job row
        job = PipelineJob(
            job_type="render",
            status="queued",
            script_id=script_id,
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
