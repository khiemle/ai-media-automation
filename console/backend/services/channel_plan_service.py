"""ChannelPlanService — CRUD + metadata extraction for channel plan documents.
ChannelPlanAIService — Gemini-powered AI features (SEO, prompts, Q&A, autofill).
"""
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from console.backend.models.channel_plan import ChannelPlan

logger = logging.getLogger(__name__)

try:
    from google import genai
except ImportError:
    genai = None


def extract_metadata(md_content: str, filename: str) -> dict:
    """Parse key metadata fields from a channel plan MD document."""
    h1_match = re.search(
        r'^#\s+Channel Launch Plan\s+[—–-]+\s+(.+)$', md_content, re.MULTILINE
    )
    if h1_match:
        name = h1_match.group(1).strip()
    else:
        name_fallback = filename
        if name_fallback.startswith("Channel_Launch_Plan_"):
            name_fallback = name_fallback[len("Channel_Launch_Plan_"):]
        if name_fallback.endswith(".md"):
            name_fallback = name_fallback[:-3]
        name = name_fallback

    slug = filename
    if slug.startswith("Channel_Launch_Plan_"):
        slug = slug[len("Channel_Launch_Plan_"):]
    if slug.endswith(".md"):
        slug = slug[:-3]
    slug = slug.lower()

    focus_m = re.search(r'\|\s*\*\*Focus\*\*\s*\|\s*([^|]+?)\s*\|', md_content)
    freq_m  = re.search(r'\|\s*\*\*Upload frequency\*\*\s*\|\s*([^|]+?)\s*\|', md_content)
    rpm_m   = re.search(r'\|\s*\*\*RPM\s+ước\s+tính\*\*\s*\|\s*([^|]+?)\s*\|', md_content)

    return {
        "name":             name,
        "slug":             slug,
        "focus":            focus_m.group(1).strip() if focus_m else None,
        "upload_frequency": freq_m.group(1).strip()  if freq_m  else None,
        "rpm_estimate":     rpm_m.group(1).strip()   if rpm_m   else None,
    }


_SENTINEL = object()


class ChannelPlanService:
    def __init__(self, db: Session):
        self.db = db

    def list_plans(self) -> list[dict]:
        plans = self.db.query(ChannelPlan).order_by(ChannelPlan.name).all()
        return [self._list_dict(p) for p in plans]

    def get_plan(self, plan_id: int) -> dict:
        plan = self._or_404(plan_id)
        return self._detail_dict(plan)

    def import_plan(self, md_content: str, filename: str) -> dict:
        meta = extract_metadata(md_content, filename)
        plan = ChannelPlan(
            name=meta["name"],
            slug=meta["slug"],
            focus=meta["focus"],
            upload_frequency=meta["upload_frequency"],
            rpm_estimate=meta["rpm_estimate"],
            md_content=md_content,
            md_filename=filename,
        )
        self.db.add(plan)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise
        self.db.refresh(plan)
        logger.info("Imported channel plan %s (slug=%s)", plan.id, plan.slug)
        return self._detail_dict(plan)

    def update_plan(self, plan_id: int, md_content: str, channel_id: int | None = _SENTINEL) -> dict:
        plan = self._or_404(plan_id)
        meta = extract_metadata(md_content, plan.md_filename or "")
        # slug is derived from filename and intentionally not updated here
        plan.name             = meta["name"]
        plan.focus            = meta["focus"]
        plan.upload_frequency = meta["upload_frequency"]
        plan.rpm_estimate     = meta["rpm_estimate"]
        plan.md_content       = md_content
        plan.updated_at       = datetime.now(timezone.utc)
        if channel_id is not _SENTINEL:
            plan.channel_id = channel_id
        self.db.commit()
        self.db.refresh(plan)
        return self._detail_dict(plan)

    def delete_plan(self, plan_id: int) -> None:
        plan = self._or_404(plan_id)
        self.db.delete(plan)
        self.db.commit()
        logger.info("Deleted channel plan %s", plan_id)

    def _or_404(self, plan_id: int) -> ChannelPlan:
        plan = self.db.query(ChannelPlan).filter(ChannelPlan.id == plan_id).first()
        if not plan:
            raise KeyError(f"ChannelPlan {plan_id} not found")
        return plan

    def _list_dict(self, p: ChannelPlan) -> dict:
        return {
            "id":               p.id,
            "name":             p.name,
            "slug":             p.slug,
            "focus":            p.focus,
            "upload_frequency": p.upload_frequency,
            "rpm_estimate":     p.rpm_estimate,
            "md_filename":      p.md_filename,
            "channel_id":       p.channel_id,
            "created_at":       p.created_at.isoformat() if p.created_at else None,
            "updated_at":       p.updated_at.isoformat() if p.updated_at else None,
        }

    def _detail_dict(self, p: ChannelPlan) -> dict:
        d = self._list_dict(p)
        d["md_content"] = p.md_content
        return d


class ChannelPlanAIService:
    """Gemini-powered AI features for a channel plan."""

    _SEO_INSTRUCTION = """\
Given the video theme "{theme}"{ctx}, generate YouTube metadata following \
the patterns in this channel plan.
Return ONLY valid JSON with no prose or markdown fences:
{{
  "title": "YouTube title (max 70 characters, use the title formula from Section 6.1)",
  "description": "YouTube description (max 300 characters, based on Section 6.2 template)",
  "tags": "tag1, tag2, tag3, tag4, tag5, tag6, tag7, tag8, tag9, tag10"
}}"""

    _PROMPTS_INSTRUCTION = """\
Given the video theme "{theme}"{ctx}, generate AI tool prompts following \
the exact formats defined in Section 5 of this channel plan.
Return ONLY valid JSON with no prose or markdown fences:
{{
  "suno": "Suno AI music prompt",
  "midjourney": "Midjourney visual prompt including --ar and --v flags",
  "runway": "Runway Gen-4 animation prompt including motion intensity and camera settings",
  "thumbnail": "YouTube thumbnail prompt (1280x720) derived from the midjourney prompt above, \
following the thumbnail guidelines in Section 7"
}}"""

    _ASK_INSTRUCTION = 'Answer this question about the channel: "{question}"'

    _AUTOFILL_INSTRUCTION = """\
Given the video theme "{theme}"{ctx}, fill in all YouTube video creation fields \
following the templates in Sections 5 and 6 of this channel plan.
Return ONLY valid JSON with no prose or markdown fences:
{{
  "title": "YouTube title (max 70 characters)",
  "description": "YouTube description (max 300 characters)",
  "tags": "tag1, tag2, ...",
  "suno_prompt": "Suno AI music prompt for this theme",
  "runway_prompt": "Runway Gen-4 animation prompt for this theme",
  "target_duration_h": 8
}}
target_duration_h must be a plain number matching the channel's recommended video duration."""

    def generate_seo(self, md_content: str, theme: str, context: str = "") -> dict:
        ctx = f' and context "{context}"' if context else ""
        instruction = self._SEO_INSTRUCTION.format(theme=theme, ctx=ctx)
        return self._call_gemini(md_content, instruction, expect_json=True)

    def generate_prompts(self, md_content: str, theme: str, context: str = "") -> dict:
        ctx = f' and context "{context}"' if context else ""
        instruction = self._PROMPTS_INSTRUCTION.format(theme=theme, ctx=ctx)
        return self._call_gemini(md_content, instruction, expect_json=True)

    def ask_question(self, md_content: str, question: str) -> dict:
        instruction = self._ASK_INSTRUCTION.format(question=question)
        answer = self._call_gemini(md_content, instruction, expect_json=False)
        return {"answer": answer}

    def autofill(self, md_content: str, theme: str, context: str = "") -> dict:
        ctx = f' and context "{context}"' if context else ""
        instruction = self._AUTOFILL_INSTRUCTION.format(theme=theme, ctx=ctx)
        return self._call_gemini(md_content, instruction, expect_json=True)

    def _call_gemini(self, md_content: str, instruction: str, expect_json: bool) -> dict | str:
        from config.api_config import get_config
        cfg = get_config()
        api_key = cfg.get("gemini", {}).get("script", {}).get("api_key", "")
        if not api_key:
            raise RuntimeError("Gemini API key not configured in LLM settings")
        if genai is None:
            raise RuntimeError("google-genai not installed")

        model = cfg.get("gemini", {}).get("script", {}).get("model", "gemini-2.5-flash")
        prompt = (
            "You are an expert YouTube content strategist.\n"
            "Below is the full channel launch plan for this channel:\n\n"
            "---\n"
            f"{md_content}\n"
            "---\n\n"
            f"{instruction}"
        )

        client = genai.Client(api_key=api_key)
        if expect_json:
            config = genai.types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            )
        else:
            config = genai.types.GenerateContentConfig(temperature=0.7)

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        raw = response.text

        if expect_json:
            text = raw.strip()
            if text.startswith("```"):
                text = re.sub(r'^```[a-z]*\n?', '', text)
                text = re.sub(r'\n?```$', '', text.strip())
            return json.loads(text)
        return raw
