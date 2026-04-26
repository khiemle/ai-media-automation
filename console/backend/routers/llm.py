from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.services.llm_service import LLMService

router = APIRouter(prefix="/llm", tags=["llm"])


class SetModelBody(BaseModel):
    provider: str
    model: str


@router.get("/status")
def get_status(_user=Depends(require_editor_or_admin)):
    return LLMService().get_status()


@router.put("/model")
def set_model(body: SetModelBody, _user=Depends(require_admin)):
    try:
        return LLMService().set_model(body.provider, body.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quota")
def get_quota(_user=Depends(require_editor_or_admin)):
    return LLMService().get_quota()

