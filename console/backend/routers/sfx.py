from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.sfx_service import SfxService

router = APIRouter(prefix="/sfx", tags=["sfx"])

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}
MEDIA_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


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
def stream_sfx(sfx_id: int, db: Session = Depends(get_db), _user=Depends(require_editor_or_admin)):
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
