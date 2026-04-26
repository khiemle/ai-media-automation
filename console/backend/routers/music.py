"""Music library API — CRUD, generation, import, streaming."""
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.celery_app import celery_app
from console.backend.database import get_db
from console.backend.services.music_service import MusicService

router = APIRouter(prefix="/music", tags=["music"])

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class GenerateBody(BaseModel):
    idea: str
    niches: list[str] = []
    moods: list[str] = []
    genres: list[str] = []
    provider: str = "suno"         # suno | lyria-clip | lyria-pro
    is_vocal: bool = False
    title: str = ""
    expand_only: bool = False      # True = return expanded prompt only, no generation


class UpdateBody(BaseModel):
    title: str | None = None
    niches: list[str] | None = None
    moods: list[str] | None = None
    genres: list[str] | None = None
    is_vocal: bool | None = None
    is_favorite: bool | None = None
    volume: float | None = None
    quality_score: int | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_tracks(
    niche: str | None = None,
    mood: str | None = None,
    genre: str | None = None,
    is_vocal: bool | None = None,
    status: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return MusicService(db).list_tracks(niche=niche, mood=mood, genre=genre,
                                        is_vocal=is_vocal, status=status, search=search)


@router.post("/generate", status_code=201)
def generate_or_expand(
    body: GenerateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    svc = MusicService(db)

    # Always expand prompt first
    expanded = svc.expand_prompt_with_gemini(
        idea=body.idea,
        niches=body.niches,
        moods=body.moods,
        genres=body.genres,
        is_vocal=body.is_vocal,
    )

    if body.expand_only:
        return expanded

    title = body.title or body.idea[:60]
    track = svc.create_pending(
        title=title,
        niches=body.niches,
        moods=body.moods,
        genres=body.genres,
        is_vocal=body.is_vocal,
        volume=0.15,
        provider=body.provider,
        prompt=expanded["expanded_prompt"],
        negative_tags=expanded.get("negative_tags", ""),
    )
    track_id = track["id"]

    if body.provider == "suno":
        from console.backend.tasks.music_tasks import generate_suno_music_task
        celery_task = generate_suno_music_task.delay(track_id)
    else:
        from console.backend.tasks.music_tasks import generate_lyria_music_task
        celery_task = generate_lyria_music_task.delay(track_id)

    return {"task_id": celery_task.id, "track_id": track_id, "track": track}


@router.post("/upload", status_code=201)
async def upload_track(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {ALLOWED_AUDIO_EXTENSIONS}")

    try:
        meta = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    file_bytes = await file.read()
    svc = MusicService(db)
    track = svc.import_track(
        file_bytes=file_bytes,
        extension=ext,
        title=meta.get("title", file.filename or "Untitled"),
        niches=meta.get("niches", []),
        moods=meta.get("moods", []),
        genres=meta.get("genres", []),
        is_vocal=meta.get("is_vocal", False),
        volume=float(meta.get("volume", 0.15)),
        quality_score=int(meta.get("quality_score", 80)),
    )
    return track


@router.get("/tasks/{task_id}")
def get_task_status(
    task_id: str,
    _user=Depends(require_editor_or_admin),
):
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "state":   result.state,
        "info":    result.info if isinstance(result.info, dict) else {},
    }


@router.get("/{track_id}")
def get_track(
    track_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return MusicService(db).get_track(track_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{track_id}/stream")
def stream_track(
    track_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        track = MusicService(db).get_track(track_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Track not found")

    path = Path(track["file_path"] or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    media_type = "audio/mpeg" if path.suffix in (".mp3", ".m4a") else "audio/wav"
    return FileResponse(str(path), media_type=media_type)


@router.put("/{track_id}")
def update_track(
    track_id: int,
    body: UpdateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    data = body.model_dump(exclude_none=True)
    try:
        return MusicService(db).update_track(track_id, data)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{track_id}", status_code=204)
def delete_track(
    track_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        MusicService(db).delete_track(track_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
