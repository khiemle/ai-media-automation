"""Production router — asset browsing, scene editing, TTS/Veo/render."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from console.backend.auth import get_current_user, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.production_service import ProductionService

router = APIRouter(prefix="/production", tags=["production"])


# ── Request schemas ───────────────────────────────────────────────────────────

class ReplaceAssetBody(BaseModel):
    asset_id: int


class UpdateAssetBody(BaseModel):
    description: str | None = None
    keywords: list[str] | None = None
    niche: list[str] | None = None
    quality_score: float | None = Field(None, ge=0.0, le=100.0)


# ── Assets ────────────────────────────────────────────────────────────────────

@router.get("/assets")
def search_assets(
    keywords: str | None = Query(None, description="Comma-separated keywords"),
    niche: str | None = Query(None),
    source: str | None = Query(None),
    min_duration: float | None = Query(None),
    asset_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    kw_list = [k.strip() for k in keywords.split(",")] if keywords else None
    niche_list = [niche] if niche else None
    svc = ProductionService(db)
    return svc.search_assets(
        keywords=kw_list,
        niche=niche_list,
        source=source,
        min_duration=min_duration,
        asset_type=asset_type,
        page=page,
        per_page=per_page,
    )


@router.get("/assets/{asset_id}")
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ProductionService(db).get_asset(asset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/assets/{asset_id}/stream")
def stream_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    try:
        path = ProductionService(db).stream_asset_path(asset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(path), media_type="video/mp4")


@router.put("/assets/{asset_id}")
def update_asset(
    asset_id: int,
    body: UpdateAssetBody,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return ProductionService(db).update_asset(
            asset_id,
            user_id=user.id,
            description=body.description,
            keywords=body.keywords,
            niche=body.niche,
            quality_score=body.quality_score,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        ProductionService(db).delete_asset(asset_id, user_id=user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


_ASSET_UPLOAD_ALLOWED = {'.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.webm'}
_MAX_ASSET_BYTES = 500 * 1024 * 1024  # 500 MB
_ASSET_SOURCES = {'manual', 'midjourney', 'runway', 'pexels', 'veo', 'stock'}


@router.post("/assets/upload", status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    source: str = Form(default='manual'),
    description: str = Form(default=''),
    keywords: str = Form(default=''),
    asset_type: str = Form(default=''),
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    ext = Path(file.filename or '').suffix.lower()
    if ext not in _ASSET_UPLOAD_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    if source not in _ASSET_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    content = await file.read(_MAX_ASSET_BYTES + 1)
    if len(content) > _MAX_ASSET_BYTES:
        raise HTTPException(status_code=413, detail='File too large (max 500 MB)')

    kw_list = [k.strip() for k in keywords.split(',') if k.strip()] if keywords else []
    try:
        return ProductionService(db).import_asset(
            file_bytes=content,
            filename=file.filename or 'asset',
            source=source,
            description=description or None,
            keywords=kw_list or None,
            asset_type=asset_type or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Script viewer ─────────────────────────────────────────────────────────────

@router.get("/scripts/{script_id}")
def get_production_script(
    script_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ProductionService(db).get_script(script_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Scene editing ─────────────────────────────────────────────────────────────

@router.put("/scripts/{script_id}/scenes/{scene_index}/asset")
def replace_scene_asset(
    script_id: int,
    scene_index: int,
    body: ReplaceAssetBody,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return ProductionService(db).replace_scene_asset(
            script_id, scene_index, body.asset_id, user.id
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scripts/{script_id}/scenes/{scene_index}/tts")
def regenerate_scene_tts(
    script_id: int,
    scene_index: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    svc = ProductionService(db)
    task_id = svc.regenerate_scene_tts(script_id, scene_index)
    return {"task_id": task_id}


@router.post("/scripts/{script_id}/scenes/{scene_index}/veo")
def generate_scene_veo(
    script_id: int,
    scene_index: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    svc = ProductionService(db)
    try:
        task_id = svc.generate_scene_veo(script_id, scene_index)
        return {"task_id": task_id}
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))


# ── Start production ──────────────────────────────────────────────────────────

@router.post("/scripts/{script_id}/render")
def start_production(
    script_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        task_id = ProductionService(db).start_production(script_id, user.id)
        return {"task_id": task_id, "script_id": script_id}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Animate still image with Runway ───────────────────────────────────────────

class AnimateBody(BaseModel):
    prompt: str
    motion_intensity: int = 2
    duration: int = 5


@router.post("/assets/{asset_id}/animate")
def animate_asset_endpoint(
    asset_id: int,
    body: AnimateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    import os
    from console.backend.models.video_asset import VideoAsset
    from console.backend.tasks.runway_task import animate_asset_task
    from console.backend.services.runway_service import RunwayService

    asset = db.get(VideoAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.asset_type != "still_image":
        raise HTTPException(status_code=400, detail="Only still images can be animated")

    api_key = os.environ.get("RUNWAY_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="RUNWAY_API_KEY not configured")

    model = os.environ.get("RUNWAY_MODEL", "gen3-alpha")
    svc = RunwayService(api_key=api_key, model=model)

    public_url = os.environ.get("PUBLIC_API_URL", "http://localhost:8080")
    image_url = f"{public_url}/api/production/assets/{asset_id}/stream"
    runway_task_id = svc.submit_image_to_video(image_url, body.prompt, body.duration, body.motion_intensity)

    child = VideoAsset(
        file_path="",
        source="runway",
        asset_type="video_clip",
        parent_asset_id=asset_id,
        generation_prompt=body.prompt,
        runway_status="pending",
        description=f"Runway animation of asset {asset_id}",
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    output_filename = f"runway_{child.id}.mp4"
    task = animate_asset_task.delay(child.id, runway_task_id, output_filename)

    return {"asset_id": child.id, "task_id": task.id, "runway_task_id": runway_task_id}
