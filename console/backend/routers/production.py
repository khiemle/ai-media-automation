"""Production router — asset browsing, scene editing, TTS/Veo/render."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import get_current_user, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.production_service import ProductionService

router = APIRouter(prefix="/production", tags=["production"])


# ── Request schemas ───────────────────────────────────────────────────────────

class ReplaceAssetBody(BaseModel):
    asset_id: int


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
    task_id = svc.generate_scene_veo(script_id, scene_index)
    return {"task_id": task_id}


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
