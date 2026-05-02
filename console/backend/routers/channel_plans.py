"""Channel Plans router — CRUD + Gemini AI endpoints."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.channel_plan_service import (
    ChannelPlanService,
    ChannelPlanAIService,
)

router = APIRouter(prefix="/channel-plans", tags=["channel-plans"])


class UpdatePlanBody(BaseModel):
    md_content: str
    channel_id: int | None = None


class AIThemeBody(BaseModel):
    theme: str
    context: str = ""


class AIQuestionBody(BaseModel):
    question: str


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("")
def list_plans(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ChannelPlanService(db).list_plans()


@router.post("/import")
def import_plan(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are accepted")
    _MAX_MD_SIZE = 1 * 1024 * 1024  # 1 MB
    try:
        raw = file.file.read(_MAX_MD_SIZE + 1)
        if len(raw) > _MAX_MD_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds 1 MB limit")
        content = raw.decode("utf-8")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    try:
        return ChannelPlanService(db).import_plan(content, file.filename)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="A plan with this slug already exists")


@router.get("/{plan_id}")
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ChannelPlanService(db).get_plan(plan_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{plan_id}")
def update_plan(
    plan_id: int,
    body: UpdatePlanBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        kwargs = {"md_content": body.md_content}
        if "channel_id" in body.model_fields_set:
            kwargs["channel_id"] = body.channel_id
        return ChannelPlanService(db).update_plan(plan_id, **kwargs)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    try:
        ChannelPlanService(db).delete_plan(plan_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── AI endpoints ──────────────────────────────────────────────────────────────

def _get_md(plan_id: int, db: Session) -> str:
    try:
        return ChannelPlanService(db).get_plan(plan_id)["md_content"]
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{plan_id}/ai/seo")
def ai_seo(
    plan_id: int,
    body: AIThemeBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    md = _get_md(plan_id, db)
    try:
        return ChannelPlanAIService().generate_seo(md, body.theme, body.context)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI generation failed: {e}")


@router.post("/{plan_id}/ai/prompts")
def ai_prompts(
    plan_id: int,
    body: AIThemeBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    md = _get_md(plan_id, db)
    try:
        return ChannelPlanAIService().generate_prompts(md, body.theme, body.context)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI generation failed: {e}")


@router.post("/{plan_id}/ai/ask")
def ai_ask(
    plan_id: int,
    body: AIQuestionBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    md = _get_md(plan_id, db)
    try:
        return ChannelPlanAIService().ask_question(md, body.question)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI generation failed: {e}")


@router.post("/{plan_id}/ai/autofill")
def ai_autofill(
    plan_id: int,
    body: AIThemeBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    md = _get_md(plan_id, db)
    try:
        return ChannelPlanAIService().autofill(md, body.theme, body.context)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI generation failed: {e}")
