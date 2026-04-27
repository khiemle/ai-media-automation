from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.llm_service import LLMService

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/voices")
def get_voices(_user=Depends(require_editor_or_admin)):
    return LLMService().get_voices()


@router.get("/status")
def get_status(_user=Depends(require_editor_or_admin)):
    return LLMService().get_status()


@router.get("/quota")
def get_quota(db: Session = Depends(get_db), _user=Depends(require_editor_or_admin)):
    return LLMService().get_quota(db=db)


@router.get("/config")
def get_config_masked(_user=Depends(require_admin)):
    return LLMService().get_config_masked()


@router.get("/config/raw")
def get_config_raw(_user=Depends(require_admin)):
    return LLMService().get_config_raw()


@router.put("/config")
def save_config(body: dict, _user=Depends(require_admin)):
    try:
        LLMService().save_config(body)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

