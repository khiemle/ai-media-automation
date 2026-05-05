# console/backend/routers/youtube_videos.py
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
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
    music_track_ids: list[int] | None = None
    sfx_overrides: dict | None = None
    sfx_pool: list[dict] | None = None
    sfx_density_seconds: int | None = None
    black_from_seconds: int | None = None
    skip_previews: bool | None = None
    visual_asset_id: int | None = None
    target_duration_h: float | None = None
    output_quality: str = "1080p"
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] | None = None
    parent_youtube_video_id: int | None = None
    visual_asset_ids:        list[int] | None = None
    visual_clip_durations_s: list[float] | None = None
    visual_loop_mode:        Literal["concat_loop", "per_clip"] | None = None


class YoutubeVideoUpdate(BaseModel):
    title: str | None = None
    theme: str | None = None
    music_track_id: int | None = None
    music_track_ids: list[int] | None = None
    sfx_overrides: dict | None = None
    sfx_pool: list[dict] | None = None
    sfx_density_seconds: int | None = None
    black_from_seconds: int | None = None
    skip_previews: bool | None = None
    visual_asset_id: int | None = None
    target_duration_h: float | None = None
    output_quality: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] | None = None
    visual_asset_ids:        list[int] | None = None
    visual_clip_durations_s: list[float] | None = None
    visual_loop_mode:        Literal["concat_loop", "per_clip"] | None = None


class StatusUpdate(BaseModel):
    status: str


class ThumbnailGenerateRequest(BaseModel):
    text: str | None = None


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
        # Only forward fields the caller actually provided (preserves explicit None)
        provided = {k: getattr(body, k) for k in body.model_fields_set}
        return YoutubeVideoService(db).update_video(video_id, provided, user_id=user.id)
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

    try:
        task_id = svc.dispatch_render(video_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {"task_id": task_id, "status": "queued"}


@router.get("/{video_id}/stream")
def stream_video(video_id: int, request: Request, db: Session = Depends(get_db)):
    """Stream the rendered output file with Range request support for seeking."""
    from console.backend.models.youtube_video import YoutubeVideo

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not video.output_path:
        raise HTTPException(status_code=404, detail="Video has no rendered output yet")
    path = Path(video.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Render file not found on disk")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        range_val = range_header.replace("bytes=", "")
        parts = range_val.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iterfile():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    data = f.read(min(65536, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iterfile(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    return FileResponse(
        str(path),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
    )


class UploadBody(BaseModel):
    channel_id: int


@router.post("/{video_id}/upload", status_code=202)
def start_upload(
    video_id: int,
    body: UploadBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    svc = YoutubeVideoService(db)
    try:
        return svc.queue_upload(video_id, channel_id=body.channel_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


# ── ASMR / Soundscape render lifecycle ────────────────────────────────────────


def _dispatch(svc_method, video_id: int, user_id: int):
    try:
        return svc_method(video_id, user_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{video_id}/render/audio-preview")
def render_audio_preview(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    task_id = _dispatch(YoutubeVideoService(db).start_audio_preview, video_id, user.id)
    return {"task_id": task_id, "video_id": video_id}


@router.post("/{video_id}/render/audio-preview/approve")
def approve_audio_preview(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    return _dispatch(YoutubeVideoService(db).approve_audio_preview, video_id, user.id)


@router.post("/{video_id}/render/audio-preview/reject")
def reject_audio_preview(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    return _dispatch(YoutubeVideoService(db).reject_audio_preview, video_id, user.id)


@router.post("/{video_id}/render/video-preview")
def render_video_preview(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    task_id = _dispatch(YoutubeVideoService(db).start_video_preview, video_id, user.id)
    return {"task_id": task_id, "video_id": video_id}


@router.post("/{video_id}/render/video-preview/approve")
def approve_video_preview(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    return _dispatch(YoutubeVideoService(db).approve_video_preview, video_id, user.id)


@router.post("/{video_id}/render/video-preview/reject")
def reject_video_preview(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    return _dispatch(YoutubeVideoService(db).reject_video_preview, video_id, user.id)


@router.post("/{video_id}/render/final")
def render_final_chunked(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    task_id = _dispatch(YoutubeVideoService(db).start_chunked_render, video_id, user.id)
    return {"task_id": task_id, "video_id": video_id}


@router.post("/{video_id}/render/cancel")
def cancel_render(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    return _dispatch(YoutubeVideoService(db).cancel_chunked_render, video_id, user.id)


@router.post("/{video_id}/render/resume")
def resume_render(
    video_id: int, db: Session = Depends(get_db), user=Depends(require_editor_or_admin),
):
    task_id = _dispatch(YoutubeVideoService(db).resume_chunked_render, video_id, user.id)
    return {"task_id": task_id, "video_id": video_id}


@router.get("/{video_id}/render/state")
def get_render_state(
    video_id: int, db: Session = Depends(get_db), _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).get_render_state(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Preview file serving (no auth — browsers can't send Bearer to media element loads) ──


@router.get("/{video_id}/preview/audio")
def get_audio_preview_file(video_id: int, db: Session = Depends(get_db)):
    """Serve the audio preview WAV. No auth — gated by knowing video_id, matching stream_video precedent."""
    from console.backend.models.youtube_video import YoutubeVideo
    video = db.get(YoutubeVideo, video_id)
    if not video or not video.audio_preview_path:
        raise HTTPException(status_code=404, detail="No audio preview")
    if not Path(video.audio_preview_path).is_file():
        raise HTTPException(status_code=404, detail="Audio preview file not found on disk")
    return FileResponse(video.audio_preview_path, media_type="audio/wav")


@router.get("/{video_id}/preview/video")
def get_video_preview_file(video_id: int, db: Session = Depends(get_db)):
    """Serve the video preview MP4. No auth — gated by knowing video_id, matching stream_video precedent."""
    from console.backend.models.youtube_video import YoutubeVideo
    video = db.get(YoutubeVideo, video_id)
    if not video or not video.video_preview_path:
        raise HTTPException(status_code=404, detail="No video preview")
    if not Path(video.video_preview_path).is_file():
        raise HTTPException(status_code=404, detail="Video preview file not found on disk")
    return FileResponse(video.video_preview_path, media_type="video/mp4")


# ── Thumbnail endpoints ───────────────────────────────────────────────────────


@router.post("/{video_id}/thumbnail-image", status_code=201)
async def upload_thumbnail_image(
    video_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    """Upload a Midjourney source image; saves as VideoAsset(source='midjourney')."""
    from console.backend.models.audit_log import AuditLog
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_asset import VideoAsset

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"YoutubeVideo {video_id} not found")
    if video.status == "published":
        raise HTTPException(status_code=400, detail="Cannot update thumbnail of a published video")

    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

    filename = image.filename or "thumbnail.jpg"
    ext = Path(filename).suffix.lower() or ".jpg"
    if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise HTTPException(status_code=400, detail="Unsupported image type. Use jpg, png, or webp.")
    save_dir = Path("assets/thumbnails/source").resolve()
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"yt_{video_id}_{int(time.time())}{ext}"
    save_path.write_bytes(content)

    asset = VideoAsset(
        file_path=str(save_path),
        source="midjourney",
        asset_type="still_image",
        description=f"Thumbnail source for YouTube video {video_id}",
    )
    try:
        db.add(asset)
        db.flush()
        video.thumbnail_asset_id = asset.id
        db.commit()
        db.refresh(asset)
        db.add(AuditLog(
            user_id=user.id,
            action="upload_thumbnail_image",
            target_type="youtube_video",
            target_id=str(video_id),
            details={"asset_id": asset.id, "filename": filename},
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save thumbnail asset")

    return {"asset_id": asset.id, "source_url": f"/api/youtube-videos/{video_id}/thumbnail-source"}


@router.post("/{video_id}/thumbnail-generate")
def generate_thumbnail_endpoint(
    video_id: int,
    body: ThumbnailGenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    """Generate (or regenerate) the thumbnail PNG from the uploaded source image."""
    from console.backend.models.audit_log import AuditLog
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_asset import VideoAsset
    from pipeline.youtube_thumbnail import generate_thumbnail

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"YoutubeVideo {video_id} not found")
    if not video.thumbnail_asset_id:
        raise HTTPException(status_code=400, detail="No thumbnail image uploaded yet")

    text = body.text
    if text and len(text.strip().split()) > 5:
        raise HTTPException(status_code=400, detail="Thumbnail text must be 5 words or fewer")

    asset = db.get(VideoAsset, video.thumbnail_asset_id)
    if not asset:
        raise HTTPException(status_code=400, detail="Thumbnail source asset not found")

    output_path = Path(f"assets/thumbnails/generated/yt_{video_id}.png").resolve()
    try:
        generate_thumbnail(source_path=asset.file_path, output_path=output_path, text=text or None)
    except Exception as exc:
        video.thumbnail_path = None
        db.commit()
        raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {exc}")

    video.thumbnail_path = str(output_path)
    video.thumbnail_text = text or None
    db.commit()
    db.add(AuditLog(
        user_id=user.id,
        action="generate_thumbnail",
        target_type="youtube_video",
        target_id=str(video_id),
        details={"text": text or None},
    ))
    db.commit()

    return {"thumbnail_url": f"/api/youtube-videos/{video_id}/thumbnail"}


@router.get("/{video_id}/thumbnail")
def get_thumbnail(video_id: int, db: Session = Depends(get_db)):
    """Serve the generated thumbnail PNG."""
    from console.backend.models.youtube_video import YoutubeVideo

    video = db.get(YoutubeVideo, video_id)
    if not video or not video.thumbnail_path:
        raise HTTPException(status_code=404, detail="No thumbnail available")
    p = Path(video.thumbnail_path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail file not found on disk")
    return FileResponse(str(p), media_type="image/png")


@router.get("/{video_id}/thumbnail-source")
def get_thumbnail_source(video_id: int, db: Session = Depends(get_db)):
    """Serve the original Midjourney source image."""
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_asset import VideoAsset

    video = db.get(YoutubeVideo, video_id)
    if not video or not video.thumbnail_asset_id:
        raise HTTPException(status_code=404, detail="No thumbnail source available")
    asset = db.get(VideoAsset, video.thumbnail_asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Thumbnail source asset not found")
    p = Path(asset.file_path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail source file not found on disk")
    ext = p.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "image/jpeg")
    return FileResponse(str(p), media_type=media_type)

