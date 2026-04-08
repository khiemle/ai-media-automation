"""Uploads router — production video list, target management, upload dispatch."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


class SetTargetsBody(BaseModel):
    channel_ids: list[int]


@router.get("/videos")
def list_videos(
    platform: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return UploadService(db).list_videos(platform=platform, status=status, page=page, per_page=per_page)


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    UploadService(db).delete_video(video_id)


@router.put("/videos/{video_id}/targets")
def set_targets(
    video_id: str,
    body: SetTargetsBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return UploadService(db).set_target_channels(video_id, body.channel_ids)


@router.post("/videos/{video_id}/upload")
def trigger_upload(
    video_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    task_ids = UploadService(db).trigger_upload(video_id)
    return {"task_ids": task_ids, "queued": len(task_ids)}


@router.post("/upload-all")
def upload_all_ready(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    count = UploadService(db).upload_all_ready()
    return {"queued": count}
