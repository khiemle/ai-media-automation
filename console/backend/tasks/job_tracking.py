import logging
from datetime import datetime, timezone

from console.backend.models.pipeline_job import PipelineJob

logger = logging.getLogger(__name__)


def ensure_job(
    db,
    *,
    task_id: str | None,
    job_type: str,
    script_id: int | None = None,
    details: dict | None = None,
) -> PipelineJob:
    job = None
    if task_id:
        job = (
            db.query(PipelineJob)
            .filter(PipelineJob.celery_task_id == task_id)
            .first()
        )

    if not job:
        query = db.query(PipelineJob).filter(PipelineJob.job_type == job_type)
        if script_id is not None:
            query = query.filter(PipelineJob.script_id == script_id)
        job = (
            query.filter(PipelineJob.status.in_(("queued", "running")))
            .order_by(PipelineJob.created_at.desc())
            .first()
        )

    if not job:
        job = PipelineJob(
            job_type=job_type,
            status="queued",
            script_id=script_id,
            celery_task_id=task_id,
            details=details or None,
        )
        db.add(job)
        db.flush()
        return job

    if task_id and not job.celery_task_id:
        job.celery_task_id = task_id
    if script_id is not None and job.script_id is None:
        job.script_id = script_id
    if details:
        current_details = job.details or {}
        current_details.update(details)
        job.details = current_details
    db.flush()
    return job


def mark_job_progress(
    db,
    *,
    task_id: str | None,
    job_type: str,
    script_id: int | None = None,
    progress: int,
    details: dict | None = None,
) -> PipelineJob:
    job = ensure_job(
        db,
        task_id=task_id,
        job_type=job_type,
        script_id=script_id,
        details=details,
    )
    job.status = "running"
    job.progress = max(0, min(100, progress))
    job.error = None
    if not job.started_at:
        job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(
    db,
    *,
    task_id: str | None,
    job_type: str,
    script_id: int | None = None,
    details: dict | None = None,
) -> PipelineJob:
    job = ensure_job(
        db,
        task_id=task_id,
        job_type=job_type,
        script_id=script_id,
        details=details,
    )
    job.status = "completed"
    job.progress = 100
    job.error = None
    if not job.started_at:
        job.started_at = datetime.now(timezone.utc)
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(
    db,
    *,
    task_id: str | None,
    job_type: str,
    script_id: int | None = None,
    error: str,
    details: dict | None = None,
) -> PipelineJob | None:
    try:
        job = ensure_job(
            db,
            task_id=task_id,
            job_type=job_type,
            script_id=script_id,
            details=details,
        )
        job.status = "failed"
        job.error = error[:2000]
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        logger.exception("Failed to mark pipeline job as failed")
        db.rollback()
        return None