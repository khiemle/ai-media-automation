# console/backend/routers/youtube_videos.py
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.youtube_video_service import YoutubeVideoService

router = APIRouter(prefix="/youtube-videos", tags=["youtube-videos"])


# ── Request schemas ───────────────────────────────────────────────────────────


class YoutubeVideoCreate(BaseModel):
    title: str
    template_id: int
    theme: str | None = None
    music_track_id: int | None = None
    sfx_overrides: dict | None = None
    visual_asset_id: int | None = None
    target_duration_h: float | None = None
    output_quality: str = "1080p"
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] | None = None


class YoutubeVideoUpdate(BaseModel):
    title: str | None = None
    theme: str | None = None
    music_track_id: int | None = None
    sfx_overrides: dict | None = None
    visual_asset_id: int | None = None
    target_duration_h: float | None = None
    output_quality: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] | None = None


class StatusUpdate(BaseModel):
    status: str


# ── Templates ────────────────────────────────────────────────────────────────


@router.get("/templates")
def list_templates(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return YoutubeVideoService(db).list_templates()


@router.get("/templates/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).get_template(template_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Videos ───────────────────────────────────────────────────────────────────


@router.get("")
def list_videos(
    status: str | None = None,
    template_id: int | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return YoutubeVideoService(db).list_videos(status=status, template_id=template_id)


@router.post("", status_code=201)
def create_video(
    body: YoutubeVideoCreate,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).create_video(body.model_dump(), user_id=user.id)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{video_id}")
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).get_video(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{video_id}")
def update_video(
    video_id: int,
    body: YoutubeVideoUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).update_video(
            video_id,
            {k: v for k, v in body.model_dump().items() if v is not None},
            user_id=user.id,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{video_id}/status")
def update_status(
    video_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).update_status(video_id, body.status, user_id=user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        YoutubeVideoService(db).delete_video(video_id, user_id=user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{video_id}/render")
def start_render(
    video_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    """Queue a YouTube video for rendering via Celery."""
    svc = YoutubeVideoService(db)
    try:
        video = svc.get_video(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if video["status"] not in ("draft", "queued"):
        raise HTTPException(status_code=400, detail=f"Cannot render video in status '{video['status']}'")

    svc.update_status(video_id, "queued", user_id=user.id)

    from console.backend.tasks.youtube_render_task import render_youtube_video_task
    from console.backend.models.youtube_video import YoutubeVideo

    task = render_youtube_video_task.delay(video_id)
    db.query(YoutubeVideo).filter(YoutubeVideo.id == video_id).update({"celery_task_id": task.id})
    db.commit()

    return {"task_id": task.id, "status": "queued"}


@router.get("/{video_id}/stream")
def stream_video(video_id: int, db: Session = Depends(get_db)):
    """Stream the rendered output file. No auth — same pattern as music/sfx streams."""
    from console.backend.models.youtube_video import YoutubeVideo

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not video.output_path:
        raise HTTPException(status_code=404, detail="Video has no rendered output yet")
    path = Path(video.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Render file not found on disk")
    return FileResponse(str(path), media_type="video/mp4")

