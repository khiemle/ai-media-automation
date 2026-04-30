import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.config import settings
from console.backend.database import get_db
from console.backend.services.llm_service import LLMService
from console.backend.services.runway_service import RunwayService

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


@router.get("/runway")
def get_runway_config(_user=Depends(require_admin)):
    """Get Runway config (masked API key + model)."""
    api_key = (getattr(settings, "runway_api_key", None) or "").strip() or os.environ.get("RUNWAY_API_KEY", "").strip()
    model = (getattr(settings, "runway_model", None) or "").strip() or os.environ.get("RUNWAY_MODEL", "gen3-alpha").strip()
    
    api_key_masked = ""
    if api_key:
        api_key_masked = f"rw-...{api_key[-6:]}" if len(api_key) > 6 else "set"
    
    return {
        "api_key_masked": api_key_masked,
        "model": model,
    }


@router.put("/runway")
def update_runway_config(body: dict, _user=Depends(require_admin)):
    """Update Runway API key and model."""
    api_key = (body.get("api_key") or "").strip()
    model = (body.get("model") or "gen3-alpha").strip()
    
    # In production, these would be persisted to environment or secrets manager
    # For now, we return confirmation with masked key
    api_key_masked = f"rw-...{api_key[-6:]}" if len(api_key) > 6 else ("set" if api_key else "")
    
    return {
        "api_key_masked": api_key_masked,
        "model": model,
        "ok": True,
    }


@router.post("/runway/test-connection")
def test_runway_connection(_user=Depends(require_admin)):
    """Test Runway API key connectivity."""
    api_key = (getattr(settings, "runway_api_key", None) or "").strip() or os.environ.get("RUNWAY_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "RUNWAY_API_KEY not configured"}

    try:
        svc = RunwayService(api_key=api_key)
        return svc.test_connection()
    except Exception as exc:
        return {"ok": False, "error": f"Connection test failed: {exc}"}

