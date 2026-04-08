from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from console.backend.auth import get_current_user, require_editor_or_admin
from console.backend.database import get_db
from console.backend.schemas.common import PaginatedResponse
from console.backend.schemas.script import (
    ScriptListItem,
    ScriptDetail,
    ScriptUpdate,
    ScriptGenerateRequest,
)
from console.backend.services.script_service import ScriptService

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("", response_model=PaginatedResponse[ScriptListItem])
def list_scripts(
    status: str | None = None,
    niche: str | None = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ScriptService(db).list_scripts(status=status, niche=niche, page=page, per_page=per_page)


@router.post("/generate", response_model=ScriptDetail, status_code=201)
def generate_script(
    body: ScriptGenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).generate_script(
            topic=body.topic,
            niche=body.niche,
            template=body.template,
            source_video_ids=body.source_video_ids,
            user_id=user.id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{script_id}", response_model=ScriptDetail)
def get_script(
    script_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).get_script(script_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{script_id}", response_model=ScriptDetail)
def update_script(
    script_id: int,
    body: ScriptUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).update_script(
            script_id=script_id,
            script_json=body.script_json,
            editor_notes=body.editor_notes,
            user_id=user.id,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{script_id}/approve", response_model=ScriptDetail)
def approve_script(
    script_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).approve_script(script_id, user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{script_id}/reject", response_model=ScriptDetail)
def reject_script(
    script_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).reject_script(script_id, user.id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{script_id}/regenerate", response_model=ScriptDetail)
def regenerate_script(
    script_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).regenerate_script(script_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{script_id}/scenes/{scene_index}/regenerate", response_model=ScriptDetail)
def regenerate_scene(
    script_id: int,
    scene_index: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ScriptService(db).regenerate_scene(script_id, scene_index)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
