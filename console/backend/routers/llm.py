import os
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
    """Get Runway config (masked API key)."""
    from config import api_config
    cfg = api_config.get_config()
    api_key = (cfg.get("runway", {}).get("api_key") or "").strip() or os.environ.get("RUNWAY_API_KEY", "").strip()
    api_key_masked = f"key_...{api_key[-6:]}" if len(api_key) > 6 else ("set" if api_key else "")
    return {"api_key_masked": api_key_masked}


@router.put("/runway")
def update_runway_config(body: dict, _user=Depends(require_admin)):
    """Persist Runway API key to config/api_keys.json."""
    from config import api_config
    api_key = (body.get("api_key") or "").strip()
    cfg = api_config.get_config()
    cfg["runway"] = {"api_key": api_key}
    api_config.save_config(cfg)
    api_key_masked = f"key_...{api_key[-6:]}" if len(api_key) > 6 else ("set" if api_key else "")
    return {"api_key_masked": api_key_masked, "ok": True}


@router.post("/runway/test-connection")
def test_runway_connection(_user=Depends(require_admin)):
    """Test Runway API key connectivity."""
    from config import api_config
    cfg = api_config.get_config()
    api_key = (cfg.get("runway", {}).get("api_key") or "").strip() or os.environ.get("RUNWAY_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "RUNWAY_API_KEY not configured"}
    try:
        return RunwayService(api_key=api_key).test_connection()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Autofill ──────────────────────────────────────────────────────────────────

class _AutofillMeta(BaseModel):
    filename: str
    file_size_bytes: int
    mime_type: str
    duration_s: Optional[float] = None


class _AutofillRequest(BaseModel):
    modal_type: Literal["music", "sfx", "asset"]
    metadata: _AutofillMeta
    form_values: dict[str, Any] = {}


@router.post("/autofill")
def autofill(body: _AutofillRequest, _user=Depends(require_editor_or_admin)):
    from rag.llm_router import get_router
    from console.backend.services.llm_service import AutofillPromptBuilder, AutofillResponseParser
    try:
        prompt = AutofillPromptBuilder().build(
            body.modal_type, body.metadata.model_dump(), body.form_values
        )
        raw = get_router().generate(prompt, expect_json=True)
        return AutofillResponseParser().parse(body.modal_type, raw)
    except RuntimeError as exc:
        msg = str(exc)
        if "rate" in msg.lower() or "quota" in msg.lower() or "429" in msg:
            raise HTTPException(status_code=429, detail="Gemini rate limit reached")
        raise HTTPException(status_code=422, detail=f"AI suggestion failed: {msg}")

