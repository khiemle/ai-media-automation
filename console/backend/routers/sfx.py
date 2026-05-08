import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.api_config import get_config
from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.sfx_service import SfxService

try:
    from elevenlabs import ElevenLabs
except ImportError:
    ElevenLabs = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sfx", tags=["sfx"])

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}
MEDIA_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
ELEVENLABS_TEXT_MAX = 450  # ElevenLabs sound-generation hard limit


class GenerateBody(BaseModel):
    text: str
    loop: bool = False
    duration_seconds: float | None = Field(default=None, ge=0.5, le=22.0)
    title: str = ""


@router.get("")
def list_sfx(
    sound_type: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return SfxService(db).list_sfx(sound_type=sound_type, search=search)


@router.get("/sound-types")
def list_sound_types(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return SfxService(db).list_sound_types()


@router.post("/generate", status_code=201)
def generate_sfx_elevenlabs(
    body: GenerateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Generate a sound effect via ElevenLabs text-to-sound-effects and save it to the SFX library."""
    if ElevenLabs is None:
        raise HTTPException(status_code=503, detail="elevenlabs package is not installed")

    try:
        key = get_config().get("elevenlabs", {}).get("api_key", "")
    except Exception:
        key = ""
    if not key:
        raise HTTPException(status_code=503, detail="ElevenLabs API key is not configured")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > ELEVENLABS_TEXT_MAX:
        logger.warning(
            "SFX generate: text truncated from %d to %d chars (loop=%s)",
            len(text), ELEVENLABS_TEXT_MAX, body.loop,
        )
        text = text[:ELEVENLABS_TEXT_MAX]

    try:
        client = ElevenLabs(api_key=key)
        kwargs: dict = {"text": text}
        if body.loop:
            kwargs["loop"] = True
        if body.duration_seconds is not None:
            kwargs["duration_seconds"] = body.duration_seconds
        audio_bytes = b"".join(client.text_to_sound_effects.convert(**kwargs))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {e}")

    title = body.title.strip() or text[:60]
    return SfxService(db).import_sfx(
        title=title,
        sound_type=None,
        source="elevenlabs",
        file_bytes=audio_bytes,
        filename="sfx.mp3",
        is_loopable=body.loop,
    )


@router.post("/import", status_code=201)
async def import_sfx(
    file: UploadFile = File(...),
    title: str = Form(...),
    sound_type: str = Form(...),
    source: str = Form(default="import"),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
    return SfxService(db).import_sfx(
        title=title,
        sound_type=sound_type,
        source=source,
        file_bytes=content,
        filename=file.filename or "sfx.wav",
    )


@router.delete("/{sfx_id}", status_code=204)
def delete_sfx(
    sfx_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        SfxService(db).delete_sfx(sfx_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{sfx_id}/stream")
def stream_sfx(sfx_id: int, db: Session = Depends(get_db)):
    """Stream SFX audio — no auth required so browser <audio> tags can load it directly."""
    from console.backend.models.sfx_asset import SfxAsset
    row = db.get(SfxAsset, sfx_id)
    if not row:
        raise HTTPException(status_code=404, detail="SFX not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    ext = path.suffix.lower()
    media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(str(path), media_type=media_type)
