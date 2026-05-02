"""Channel Plans router — CRUD + Gemini AI endpoints."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
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
    try:
        content = file.file.read().decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
    try:
        return ChannelPlanService(db).import_plan(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))


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
        return ChannelPlanService(db).update_plan(
            plan_id, body.md_content, body.channel_id
        )
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


def _ai_error(e: Exception):
    raise HTTPException(status_code=503, detail=f"AI generation failed: {e}")


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
        _ai_error(e)


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
        _ai_error(e)


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
        _ai_error(e)


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
        _ai_error(e)
