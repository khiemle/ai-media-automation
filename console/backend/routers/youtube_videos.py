# console/backend/routers/youtube_videos.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.youtube_video_service import YoutubeVideoService

router = APIRouter(prefix="/youtube-videos", tags=["youtube-videos"])


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
    data: dict,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).create_video(data)
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
    data: dict,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).update_video(video_id, data)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{video_id}/status")
def update_status(
    video_id: int,
    data: dict,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).update_status(video_id, data.get("status", ""))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        YoutubeVideoService(db).delete_video(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
