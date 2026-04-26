"""Pipeline router — job management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class CreateJobBody(BaseModel):
    job_type: str
    script_id: int | None = None


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return PipelineService(db).get_stats()


@router.get("/jobs")
def list_jobs(
    status: str | None = Query(None),
    job_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return PipelineService(db).list_jobs(status=status, job_type=job_type, page=page, per_page=per_page)


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return PipelineService(db).get_job(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs")
def create_job(
    body: CreateJobBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return PipelineService(db).create_job(body.job_type, body.script_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/jobs/{job_id}/retry")
def retry_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return PipelineService(db).retry_job(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}/logs")
def get_job_logs(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        PipelineService(db).get_job(job_id)  # validates job exists
        logs = PipelineService(db).get_job_logs(job_id)
        return {"job_id": job_id, "logs": logs}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return PipelineService(db).cancel_job(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
