"""UploadService — list production videos, manage targets, dispatch upload tasks."""
import math
import logging
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from console.backend.models.channel import Channel, TemplateChannelDefault, UploadTarget
from console.backend.models.pipeline_job import PipelineJob
from console.backend.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class UploadService:
    def __init__(self, db: Session):
        self.db = db

    # ── Video list ────────────────────────────────────────────────────────────

    def list_videos(
        self,
        platform: str | None = None,
        status: str | None = None,
        video_format: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse:
        """List production-ready scripts joined with their upload targets."""
        # Use raw SQL to join with core pipeline's generated_scripts
        where_clauses = ["gs.status IN ('completed', 'producing', 'approved')"]
        params: dict = {}

        if status:
            where_clauses.append("ut.status = :ut_status")
            params["ut_status"] = status
        if platform:
            where_clauses.append("ch.platform = :platform")
            params["platform"] = platform
        if video_format:
            where_clauses.append("gs.video_format = :video_format")
            params["video_format"] = video_format

        where_sql = " AND ".join(where_clauses)

        count_sql = f"""
            SELECT COUNT(DISTINCT gs.id)
            FROM generated_scripts gs
            LEFT JOIN upload_targets ut ON ut.video_id = gs.id::text
            LEFT JOIN channels ch ON ch.id = ut.channel_id
            WHERE {where_sql}
        """
        data_sql = f"""
            SELECT
                gs.id, gs.status, gs.script_json, gs.output_path, gs.video_format, gs.duration_s,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'channel_id', ut.channel_id,
                            'channel_name', ch.name,
                            'platform', ch.platform,
                            'upload_status', ut.status,
                            'uploaded_at', ut.uploaded_at,
                            'platform_id', ut.platform_id
                        )
                    ) FILTER (WHERE ut.channel_id IS NOT NULL),
                    '[]'
                ) AS targets
            FROM generated_scripts gs
            LEFT JOIN upload_targets ut ON ut.video_id = gs.id::text
            LEFT JOIN channels ch ON ch.id = ut.channel_id
            WHERE {where_sql}
            GROUP BY gs.id
            ORDER BY gs.id DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"]  = per_page
        params["offset"] = (page - 1) * per_page

        try:
            total = self.db.execute(text(count_sql), params).scalar() or 0
            rows  = self.db.execute(text(data_sql), params).fetchall()
        except Exception:
            # generated_scripts table doesn't exist yet
            return PaginatedResponse(items=[], total=0, page=page, pages=0, per_page=per_page)

        items = []
        for row in rows:
            sj = row.script_json if isinstance(row.script_json, dict) else {}
            video = sj.get("video", {})
            meta  = sj.get("meta", {})
            has_video = bool(row.output_path and os.path.isfile(row.output_path))
            items.append({
                "id":            row.id,
                "title":         video.get("title") or meta.get("topic") or f"Script #{row.id}",
                "template":      meta.get("template"),
                "niche":         meta.get("niche"),
                "status":        row.status,
                "video_format":  row.video_format or "short",
                "duration_s":    row.duration_s,
                "targets":       row.targets if isinstance(row.targets, list) else [],
                "has_video":     has_video,
            })

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            pages=math.ceil(total / per_page) if per_page else 1,
            per_page=per_page,
        )

    # ── Target management ─────────────────────────────────────────────────────

    def get_default_channels(self, template: str) -> list[int]:
        rows = self.db.query(TemplateChannelDefault).filter(
            TemplateChannelDefault.template == template
        ).all()
        return [r.channel_id for r in rows]

    def set_target_channels(self, video_id: str, channel_ids: list[int]) -> list[dict]:
        """Replace upload targets for a video. If empty, apply template defaults."""
        if not channel_ids:
            try:
                template = self.db.execute(
                    text("SELECT script_json->>'meta'->>'template' AS t FROM generated_scripts WHERE id = :id"),
                    {"id": video_id},
                ).scalar()
                if template:
                    channel_ids = self.get_default_channels(template)
            except Exception:
                pass

        # Delete all existing targets so re-upload doesn't hit a unique constraint
        self.db.query(UploadTarget).filter(
            UploadTarget.video_id == str(video_id),
        ).delete()

        for cid in channel_ids:
            self.db.add(UploadTarget(video_id=str(video_id), channel_id=cid, status="pending"))

        self.db.commit()

        # Return current targets
        targets = self.db.query(UploadTarget, Channel).join(
            Channel, UploadTarget.channel_id == Channel.id
        ).filter(UploadTarget.video_id == str(video_id)).all()

        return [
            {
                "channel_id":   ut.channel_id,
                "channel_name": ch.name,
                "platform":     ch.platform,
                "status":       ut.status,
            }
            for ut, ch in targets
        ]

    def delete_video(self, video_id: str) -> None:
        """Remove upload targets for a video (soft-delete from upload queue)."""
        self.db.query(UploadTarget).filter(
            UploadTarget.video_id == str(video_id)
        ).delete()
        self.db.commit()
        logger.info(f"Removed upload targets for video {video_id}")

    # ── Upload dispatch ───────────────────────────────────────────────────────

    def trigger_upload(self, video_id: str) -> list[str]:
        """Dispatch Celery upload tasks for all pending targets. Returns task IDs."""
        video_row = self.db.execute(
            text("SELECT id, status, output_path FROM generated_scripts WHERE id = :id"),
            {"id": video_id},
        ).fetchone()
        if not video_row:
            raise KeyError(f"Video {video_id} not found")
        if video_row.status != "completed":
            raise ValueError(f"Video {video_id} is not ready for upload (status: {video_row.status})")
        if not video_row.output_path:
            raise ValueError(f"Video {video_id} has no rendered output yet")

        targets = (
            self.db.query(UploadTarget, Channel)
            .join(Channel, UploadTarget.channel_id == Channel.id)
            .filter(
                UploadTarget.video_id == str(video_id),
                UploadTarget.status == "pending",
            )
            .all()
        )

        task_ids = []
        for ut, ch in targets:
            try:
                from console.backend.tasks.upload_tasks import upload_to_channel_task
                job = PipelineJob(
                    job_type="upload",
                    status="queued",
                    script_id=int(video_id) if str(video_id).isdigit() else None,
                    details={
                        "channel_id": ch.id,
                        "platform": ch.platform,
                        "step": "queued",
                    },
                )
                self.db.add(job)
                self.db.flush()

                result = upload_to_channel_task.delay(str(video_id), ch.id)
                job.celery_task_id = result.id
                ut.status = "uploading"
                task_ids.append(result.id)
                logger.info(f"Queued upload: video={video_id} → channel={ch.id} ({ch.platform}), task={result.id}")
            except Exception as e:
                logger.error(f"Failed to queue upload for channel {ch.id}: {e}")

        self.db.commit()
        return task_ids

    def upload_all_ready(self) -> int:
        """Trigger uploads for all completed videos with pending targets."""
        rows = self.db.execute(
            text(
                "SELECT DISTINCT ut.video_id "
                "FROM upload_targets ut "
                "JOIN generated_scripts gs ON gs.id::text = ut.video_id "
                "WHERE ut.status = 'pending' AND gs.status = 'completed' AND gs.output_path IS NOT NULL"
            )
        ).fetchall()
        count = 0
        for (video_id,) in rows:
            task_ids = self.trigger_upload(video_id)
            count += len(task_ids)
        return count

    def stream_video_path(self, video_id: str) -> str:
        row = self.db.execute(
            text("SELECT output_path FROM generated_scripts WHERE id = :id"),
            {"id": video_id},
        ).fetchone()
        if not row:
            raise KeyError(f"Video {video_id} not found")
        if not row.output_path or not os.path.isfile(row.output_path):
            raise ValueError(f"Video {video_id} has no rendered file on disk")
        return row.output_path
