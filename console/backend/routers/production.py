"""Production router — asset browsing, scene editing, TTS/Veo/render."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
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
