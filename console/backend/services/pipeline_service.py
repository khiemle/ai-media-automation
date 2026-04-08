"""PipelineService — job management and Celery task orchestration."""
import math
import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from console.backend.models.pipeline_job import PipelineJob
from console.backend.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)

JOB_TYPES = ("scrape", "generate", "tts", "render", "upload", "batch")
STATUSES   = ("queued", "running", "completed", "failed", "cancelled")


class PipelineService:
    def __init__(self, db: Session):
        self.db = db

    # ── List / Get ────────────────────────────────────────────────────────────

    def list_jobs(
        self,
        status: str | None = None,
        job_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse:
        q = self.db.query(PipelineJob)
        if status:
            q = q.filter(PipelineJob.status == status)
        if job_type:
            q = q.filter(PipelineJob.job_type == job_type)

        total = q.count()
        rows = q.order_by(PipelineJob.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

        return PaginatedResponse(
            items=[self._to_dict(j) for j in rows],
            total=total,
            page=page,
            pages=math.ceil(total / per_page) if per_page else 1,
            per_page=per_page,
        )

    def get_job(self, job_id: int) -> dict:
        job = self.db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
        if not job:
            raise KeyError(f"Job {job_id} not found")
        return self._to_dict(job)

    # ── Create ────────────────────────────────────────────────────────────────

    def create_job(self, job_type: str, script_id: int | None = None) -> dict:
        if job_type not in JOB_TYPES:
            raise ValueError(f"job_type must be one of {JOB_TYPES}")

        job = PipelineJob(
            job_type=job_type,
            status="queued",
            script_id=script_id,
        )
        self.db.add(job)
        self.db.flush()

        # Dispatch appropriate Celery task
        task_id = self._dispatch(job_type, script_id)
        if task_id:
            job.celery_task_id = task_id
            job.started_at = datetime.now(timezone.utc)

        self.db.commit()
        logger.info(f"Created pipeline job {job.id} ({job_type}), task={task_id}")
        return self._to_dict(job)

    def _dispatch(self, job_type: str, script_id: int | None) -> str | None:
        try:
            if job_type == "scrape":
                from console.backend.tasks.scraper_tasks import run_scrape_task
                result = run_scrape_task.delay("all")
                return result.id
            elif job_type in ("generate",):
                from console.backend.tasks.script_tasks import generate_script_task
                result = generate_script_task.delay(script_id)
                return result.id
            elif job_type in ("tts", "render"):
                from console.backend.tasks.production_tasks import render_video_task
                result = render_video_task.delay(script_id)
                return result.id
            elif job_type == "upload":
                from console.backend.tasks.upload_tasks import upload_to_channel_task
                result = upload_to_channel_task.delay(script_id)
                return result.id
        except Exception as e:
            logger.warning(f"Could not dispatch task for {job_type}: {e}")
        return None

    # ── Retry / Cancel ────────────────────────────────────────────────────────

    def retry_job(self, job_id: int) -> dict:
        job = self.db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
        if not job:
            raise KeyError(f"Job {job_id} not found")
        if job.status not in ("failed", "cancelled"):
            raise ValueError(f"Can only retry failed or cancelled jobs, got '{job.status}'")

        job.status = "queued"
        job.error = None
        job.progress = 0
        job.completed_at = None
        self.db.flush()

        task_id = self._dispatch(job.job_type, job.script_id)
        if task_id:
            job.celery_task_id = task_id
            job.started_at = datetime.now(timezone.utc)

        self.db.commit()
        return self._to_dict(job)

    def cancel_job(self, job_id: int) -> dict:
        job = self.db.query(PipelineJob).filter(PipelineJob.id == job_id).first()
        if not job:
            raise KeyError(f"Job {job_id} not found")

        if job.celery_task_id:
            try:
                from console.backend.celery_app import celery_app
                celery_app.control.revoke(job.celery_task_id, terminate=True)
            except Exception as e:
                logger.warning(f"Could not revoke Celery task {job.celery_task_id}: {e}")

        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        return self._to_dict(job)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        rows = (
            self.db.query(PipelineJob.status, func.count(PipelineJob.id))
            .group_by(PipelineJob.status)
            .all()
        )
        counts = {r[0]: r[1] for r in rows}
        return {
            "queued":    counts.get("queued", 0),
            "running":   counts.get("running", 0),
            "completed": counts.get("completed", 0),
            "failed":    counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "total":     sum(counts.values()),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _to_dict(self, job: PipelineJob) -> dict:
        return {
            "id":             job.id,
            "job_type":       job.job_type,
            "status":         job.status,
            "script_id":      job.script_id,
            "celery_task_id": job.celery_task_id,
            "progress":       job.progress,
            "details":        job.details,
            "error":          job.error,
            "started_at":     job.started_at.isoformat() if job.started_at else None,
            "completed_at":   job.completed_at.isoformat() if job.completed_at else None,
            "created_at":     job.created_at.isoformat() if job.created_at else None,
        }
