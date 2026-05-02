# Channel Plans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Channel Plans — import Markdown strategy docs, store them in PostgreSQL, edit them in-app, generate SEO/prompts/Q&A/autofill via Gemini, and surface plans in the YouTube Videos creation flow.

**Architecture:** New `channel_plans` DB table stores raw MD + 5 extracted metadata fields. `ChannelPlanService` handles CRUD + metadata parsing (regex-based); `ChannelPlanAIService` calls Gemini using the same `google-genai` client pattern as `rag/llm_router.py`. New `ChannelPlansPage.jsx` and shared `AIAssistantPanel.jsx`. `YouTubeVideosPage.jsx` gets a channel plans accordion and AI Autofill in `CreationPanel`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x (Mapped columns), Alembic, `google-genai` SDK, React 18 + Vite + Tailwind CSS (design tokens from `tailwind.config.js`), pytest + `unittest.mock`, PostgreSQL

---

## File Map

### Created
| File | Purpose |
|---|---|
| `console/backend/alembic/versions/012_channel_plans.py` | Migration: creates `channel_plans` table |
| `console/backend/models/channel_plan.py` | SQLAlchemy `ChannelPlan` model |
| `console/backend/services/channel_plan_service.py` | `ChannelPlanService` (CRUD + parser) + `ChannelPlanAIService` (Gemini) |
| `console/backend/routers/channel_plans.py` | FastAPI router `/api/channel-plans` |
| `console/frontend/src/components/AIAssistantPanel.jsx` | Shared AI panel (SEO / Prompts / Q&A), used by both pages |
| `console/frontend/src/pages/ChannelPlansPage.jsx` | Channel Plans management page |
| `tests/test_channel_plan_service.py` | Unit tests (metadata parser + CRUD + Gemini AI) |

### Modified
| File | Change |
|---|---|
| `console/backend/main.py` | Register `channel_plans` router in `register_routers()` |
| `console/backend/models/__init__.py` | Export `ChannelPlan` |
| `console/frontend/src/api/client.js` | Add `channelPlansApi` |
| `console/frontend/src/App.jsx` | Add Channel Plans icon, tab entry, import, and `renderPage` case |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Channel plans accordion + CreationPanel AI Autofill |
| `tests/conftest.py` | Import `channel_plan` model so `create_all` registers the table |

---

## Task 1: Alembic migration

**Files:**
- Create: `console/backend/alembic/versions/012_channel_plans.py`

Run all commands from the **project root** (`ai-media-automation/`), NOT from `console/`.

- [ ] **Step 1: Write the migration file**

Create `console/backend/alembic/versions/012_channel_plans.py`:

```python
"""channel_plans — channel strategy document storage

Revision ID: 012
Revises: 011
Create Date: 2026-05-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_plans",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("focus", sa.Text, nullable=True),
        sa.Column("upload_frequency", sa.Text, nullable=True),
        sa.Column("rpm_estimate", sa.Text, nullable=True),
        sa.Column("md_content", sa.Text, nullable=False),
        sa.Column("md_filename", sa.Text, nullable=True),
        sa.Column(
            "channel_id",
            sa.Integer,
            sa.ForeignKey("channels.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_channel_plans_slug", "channel_plans", ["slug"])
    op.create_index("ix_channel_plans_slug", "channel_plans", ["slug"])


def downgrade() -> None:
    op.drop_table("channel_plans")
```

- [ ] **Step 2: Run the migration**

```bash
cd console/backend && alembic upgrade head && cd ../..
```

Expected: `Running upgrade 011 -> 012, channel_plans`

- [ ] **Step 3: Verify the table exists**

```bash
psql -d ai_media_automation -c "\d channel_plans"
```

Expected: table listing with columns `id`, `name`, `slug`, `focus`, `upload_frequency`, `rpm_estimate`, `md_content`, `md_filename`, `channel_id`, `created_at`, `updated_at`.

- [ ] **Step 4: Commit**

```bash
git add console/backend/alembic/versions/012_channel_plans.py
git commit -m "feat: add channel_plans migration"
```

---

## Task 2: SQLAlchemy model

**Files:**
- Create: `console/backend/models/channel_plan.py`
- Modify: `console/backend/models/__init__.py`

- [ ] **Step 1: Create the model**

Create `console/backend/models/channel_plan.py`:

```python
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class ChannelPlan(Base):
    __tablename__ = "channel_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    upload_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    rpm_estimate: Mapped[str | None] = mapped_column(Text, nullable=True)
    md_content: Mapped[str] = mapped_column(Text, nullable=False)
    md_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Export from `__init__.py`**

In `console/backend/models/__init__.py`, add after the last import and in `__all__`:

```python
from console.backend.models.channel_plan import ChannelPlan

__all__ = [
    "AuditLog",
    "Channel",
    "ChannelPlan",
    "ConsoleUser",
    "Niche",
    "PlatformCredential",
    "TemplateChannelDefault",
    "UploadTarget",
]
```

- [ ] **Step 3: Register in test conftest**

In `tests/conftest.py`, add `channel_plan` to the model import line so `Base.metadata.create_all` picks it up:

```python
from console.backend.models import sfx_asset, video_template, youtube_video, video_asset, pipeline_job, channel_plan  # noqa: ensure tables registered
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/models/channel_plan.py console/backend/models/__init__.py tests/conftest.py
git commit -m "feat: add ChannelPlan SQLAlchemy model"
```

---

## Task 3: ChannelPlanService — CRUD + metadata parser

**Files:**
- Create: `console/backend/services/channel_plan_service.py`
- Create: `tests/test_channel_plan_service.py` (CRUD + metadata tests)

- [ ] **Step 1: Write the failing tests (metadata + CRUD)**

Create `tests/test_channel_plan_service.py`:

```python
import pytest
from console.backend.services.channel_plan_service import ChannelPlanService, extract_metadata

_ASMR_MD = """\
# Channel Launch Plan — ASMR Sleep & Relax

## 1. Tổng quan kênh

| Tiêu chí | Kênh ASMR Sleep & Relax |
|---|---|
| **Focus** | Sleep, deep relaxation, stress relief |
| **Audience** | Người mất ngủ, lo âu, cần thư giãn sâu |
| **Video length** | 8–10 giờ/video |
| **Upload frequency** | 3–4 video/tuần |
| **RPM ước tính** | $10–$11 |
"""

# ── metadata extraction ──────────────────────────────────────────────────────

def test_extract_name_from_h1():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["name"] == "ASMR Sleep & Relax"

def test_extract_slug_strips_prefix():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["slug"] == "asmr"

def test_extract_slug_fallback_no_prefix():
    result = extract_metadata(_ASMR_MD, "My_Custom.md")
    assert result["slug"] == "my_custom"

def test_extract_focus():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["focus"] == "Sleep, deep relaxation, stress relief"

def test_extract_upload_frequency():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["upload_frequency"] == "3–4 video/tuần"

def test_extract_rpm_estimate():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["rpm_estimate"] == "$10–$11"

def test_extract_returns_none_for_missing_fields():
    minimal = "# Channel Launch Plan — Minimal\n"
    result = extract_metadata(minimal, "Channel_Launch_Plan_Minimal.md")
    assert result["name"] == "Minimal"
    assert result["focus"] is None
    assert result["upload_frequency"] is None
    assert result["rpm_estimate"] is None

# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_import_plan_stores_all_fields(db):
    svc = ChannelPlanService(db)
    plan = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert plan["id"] is not None
    assert plan["name"] == "ASMR Sleep & Relax"
    assert plan["slug"] == "asmr"
    assert plan["focus"] == "Sleep, deep relaxation, stress relief"
    assert plan["upload_frequency"] == "3–4 video/tuần"
    assert plan["rpm_estimate"] == "$10–$11"
    assert plan["md_filename"] == "Channel_Launch_Plan_ASMR.md"

def test_list_plans_excludes_md_content(db):
    svc = ChannelPlanService(db)
    svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    plans = svc.list_plans()
    assert len(plans) == 1
    assert "md_content" not in plans[0]
    assert plans[0]["name"] == "ASMR Sleep & Relax"

def test_get_plan_includes_md_content(db):
    svc = ChannelPlanService(db)
    created = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    retrieved = svc.get_plan(created["id"])
    assert retrieved["md_content"] == _ASMR_MD

def test_update_plan_re_parses_metadata(db):
    svc = ChannelPlanService(db)
    plan = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    new_md = "# Channel Launch Plan — Soundscapes\n\n## 1. Tổng quan kênh\n\n| **Focus** | Nature and focus |\n"
    updated = svc.update_plan(plan["id"], new_md)
    assert updated["name"] == "Soundscapes"
    assert updated["focus"] == "Nature and focus"
    assert updated["md_content"] == new_md

def test_delete_plan_removes_from_db(db):
    svc = ChannelPlanService(db)
    plan = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    svc.delete_plan(plan["id"])
    assert svc.list_plans() == []

def test_get_plan_not_found_raises_key_error(db):
    svc = ChannelPlanService(db)
    with pytest.raises(KeyError):
        svc.get_plan(99999)

def test_duplicate_slug_raises(db):
    svc = ChannelPlanService(db)
    svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    with pytest.raises(Exception):
        svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/ai-media-automation
pytest tests/test_channel_plan_service.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` — `channel_plan_service` does not exist yet.

- [ ] **Step 3: Implement `channel_plan_service.py`**

Create `console/backend/services/channel_plan_service.py`:

```python
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
    # name: from H1 heading "# Channel Launch Plan — {name}"
    h1_match = re.search(
        r'^#\s+Channel Launch Plan\s+[—–-]+\s+(.+)$', md_content, re.MULTILINE
    )
    name = h1_match.group(1).strip() if h1_match else filename

    # slug: strip known prefix + .md suffix, lowercase
    slug = filename
    if slug.startswith("Channel_Launch_Plan_"):
        slug = slug[len("Channel_Launch_Plan_"):]
    if slug.endswith(".md"):
        slug = slug[:-3]
    slug = slug.lower()

    # focus, upload_frequency, rpm_estimate: from overview markdown table
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


class ChannelPlanService:
    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────────────

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

    # ── Helpers ───────────────────────────────────────────────────────────────

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


_SENTINEL = object()  # distinguishes "not passed" from None for channel_id


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
```

**Fix: `_SENTINEL` placement.** The sentinel object must be defined before `update_plan` references it. Move `_SENTINEL = object()` above the class definition and use it as a default arg:

Replace the `update_plan` signature with:
```python
_SENTINEL = object()

class ChannelPlanService:
    ...
    def update_plan(self, plan_id: int, md_content: str, channel_id: int | None = _SENTINEL) -> dict:
```

- [ ] **Step 4: Run the tests**

```bash
pytest tests/test_channel_plan_service.py -v -k "not AI and not ai"
```

Expected: all metadata and CRUD tests pass.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/channel_plan_service.py tests/test_channel_plan_service.py
git commit -m "feat: add ChannelPlanService with CRUD and metadata parser"
```

---

## Task 4: ChannelPlanAIService — Gemini tests

**Files:**
- Modify: `tests/test_channel_plan_service.py` (add AI tests)

- [ ] **Step 1: Add AI tests to the test file**

Append to `tests/test_channel_plan_service.py`:

```python
# ── AI service ───────────────────────────────────────────────────────────────

from unittest.mock import patch, MagicMock
from console.backend.services.channel_plan_service import ChannelPlanAIService

_FAKE_CFG = {
    "gemini": {"script": {"api_key": "fake-key", "model": "gemini-2.0-flash"}}
}

def _gemini_response(text):
    m = MagicMock()
    m.text = text
    return m


def test_generate_seo_returns_parsed_dict():
    svc = ChannelPlanAIService()
    payload = '{"title": "Rain Sounds 8h", "description": "Relax with rain", "tags": "rain, sleep, asmr"}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response(payload)

    with patch("console.backend.services.channel_plan_service.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.generate_seo("# Channel Plan\n", "Heavy Rain", "")

    assert result["title"] == "Rain Sounds 8h"
    assert result["description"] == "Relax with rain"
    assert result["tags"] == "rain, sleep, asmr"


def test_generate_prompts_returns_four_keys():
    svc = ChannelPlanAIService()
    payload = '{"suno": "s", "midjourney": "mj", "runway": "r", "thumbnail": "t"}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response(payload)

    with patch("console.backend.services.channel_plan_service.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.generate_prompts("# Channel Plan\n", "Forest Stream", "")

    for key in ("suno", "midjourney", "runway", "thumbnail"):
        assert key in result


def test_ask_question_wraps_plain_text():
    svc = ChannelPlanAIService()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response("Upload 3-4 videos per week.")

    with patch("console.backend.services.channel_plan_service.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.ask_question("# Channel Plan\n", "What is the upload schedule?")

    assert result == {"answer": "Upload 3-4 videos per week."}


def test_autofill_returns_all_fields():
    svc = ChannelPlanAIService()
    payload = '{"title":"T","description":"D","tags":"t","suno_prompt":"s","runway_prompt":"r","target_duration_h":8}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response(payload)

    with patch("console.backend.services.channel_plan_service.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.autofill("# Channel Plan\n", "Heavy Rain", "")

    for key in ("title", "description", "tags", "suno_prompt", "runway_prompt", "target_duration_h"):
        assert key in result
    assert result["target_duration_h"] == 8


def test_generate_seo_raises_on_missing_api_key():
    svc = ChannelPlanAIService()
    cfg_no_key = {"gemini": {"script": {"api_key": "", "model": ""}}}

    with patch("console.backend.services.channel_plan_service.get_config", return_value=cfg_no_key):
        with pytest.raises(RuntimeError, match="API key"):
            svc.generate_seo("# Plan\n", "theme", "")
```

- [ ] **Step 2: Run the AI tests**

```bash
pytest tests/test_channel_plan_service.py -v -k "ai or AI or seo or SEO or ask or autofill or prompt"
```

Expected: all 5 AI tests pass.

- [ ] **Step 3: Run the full test file**

```bash
pytest tests/test_channel_plan_service.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_channel_plan_service.py
git commit -m "test: add ChannelPlanAIService unit tests"
```

---

## Task 5: FastAPI router + register in main.py

**Files:**
- Create: `console/backend/routers/channel_plans.py`
- Modify: `console/backend/main.py`

- [ ] **Step 1: Create the router**

Create `console/backend/routers/channel_plans.py`:

```python
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
```

- [ ] **Step 2: Register the router in main.py**

In `console/backend/main.py`, add inside `register_routers()` after the `channels` block:

```python
    try:
        from console.backend.routers import channel_plans
        app.include_router(channel_plans.router, prefix="/api")
    except ImportError:
        pass
```

- [ ] **Step 3: Smoke-test the API**

Start the server (in a separate terminal):
```bash
uvicorn console.backend.main:app --port 8080 --reload
```

Then verify the endpoints appear:
```bash
curl -s http://localhost:8080/docs | grep -o "channel-plans" | head -5
```

Expected: `channel-plans` appears in the OpenAPI docs.

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/channel_plans.py console/backend/main.py
git commit -m "feat: add channel-plans router and register in main"
```

---

## Task 6: Frontend API client

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Add `channelPlansApi` to client.js**

Append to the end of `console/frontend/src/api/client.js`:

```js
// ── Channel Plans ──────────────────────────────────────────────────────────────
export const channelPlansApi = {
  list: () => fetchApi('/api/channel-plans'),

  get: (id) => fetchApi(`/api/channel-plans/${id}`),

  import: (file) => {
    const form = new FormData()
    form.append('file', file)
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/channel-plans/import', { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },

  update: (id, mdContent, channelId = null) =>
    fetchApi(`/api/channel-plans/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ md_content: mdContent, channel_id: channelId }),
    }),

  delete: (id) => fetchApi(`/api/channel-plans/${id}`, { method: 'DELETE' }),

  aiSeo: (id, theme, context = '') =>
    fetchApi(`/api/channel-plans/${id}/ai/seo`, {
      method: 'POST',
      body: JSON.stringify({ theme, context }),
    }),

  aiPrompts: (id, theme, context = '') =>
    fetchApi(`/api/channel-plans/${id}/ai/prompts`, {
      method: 'POST',
      body: JSON.stringify({ theme, context }),
    }),

  aiAsk: (id, question) =>
    fetchApi(`/api/channel-plans/${id}/ai/ask`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

  aiAutofill: (id, theme, context = '') =>
    fetchApi(`/api/channel-plans/${id}/ai/autofill`, {
      method: 'POST',
      body: JSON.stringify({ theme, context }),
    }),
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add channelPlansApi to frontend client"
```

---

## Task 7: AIAssistantPanel shared component

**Files:**
- Create: `console/frontend/src/components/AIAssistantPanel.jsx`

This component is used in both `ChannelPlansPage` and `YouTubeVideosPage`. It accepts a `planId` prop and renders three accordion sections (SEO, Prompts, Q&A).

- [ ] **Step 1: Create the component**

Create `console/frontend/src/components/AIAssistantPanel.jsx`:

```jsx
import { useState } from 'react'
import { channelPlansApi } from '../api/client.js'
import { Button, Input } from './index.jsx'

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button
      onClick={handleCopy}
      className="text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-0.5 bg-[#16161a] rounded border border-[#2a2a32] transition-colors flex-shrink-0"
    >
      {copied ? '✓' : 'Copy'}
    </button>
  )
}

function ResultBlock({ label, text }) {
  if (!text) return null
  return (
    <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-bold text-[#5a5a70] tracking-widest uppercase">{label}</span>
        <CopyButton text={text} />
      </div>
      <p className="text-xs text-[#9090a8] leading-relaxed whitespace-pre-wrap font-mono">{text}</p>
    </div>
  )
}

function AccordionSection({ title, open, onToggle, children }) {
  return (
    <div className="border border-[#2a2a32] rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#1c1c22] hover:bg-[#222228] transition-colors text-left"
      >
        <span className="text-sm font-semibold text-[#e8e8f0]">{title}</span>
        <span className="text-[#9090a8] text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="p-4 flex flex-col gap-3 bg-[#16161a]">{children}</div>}
    </div>
  )
}

export default function AIAssistantPanel({ planId }) {
  const [openSection, setOpenSection] = useState('seo')

  // SEO state
  const [seoTheme, setSeoTheme]       = useState('')
  const [seoContext, setSeoContext]   = useState('')
  const [seoResult, setSeoResult]     = useState(null)
  const [seoLoading, setSeoLoading]   = useState(false)
  const [seoError, setSeoError]       = useState(null)

  // Prompts state
  const [pTheme, setPTheme]           = useState('')
  const [pContext, setPContext]       = useState('')
  const [pResult, setPResult]         = useState(null)
  const [pLoading, setPLoading]       = useState(false)
  const [pError, setPError]           = useState(null)

  // Q&A state
  const [question, setQuestion]       = useState('')
  const [answer, setAnswer]           = useState(null)
  const [qaLoading, setQaLoading]     = useState(false)
  const [qaError, setQaError]         = useState(null)

  const toggle = (section) => setOpenSection(s => s === section ? null : section)

  const handleSeo = async () => {
    if (!seoTheme.trim()) return
    setSeoLoading(true); setSeoError(null); setSeoResult(null)
    try {
      setSeoResult(await channelPlansApi.aiSeo(planId, seoTheme.trim(), seoContext.trim()))
    } catch (e) {
      setSeoError(e.message)
    } finally {
      setSeoLoading(false)
    }
  }

  const handlePrompts = async () => {
    if (!pTheme.trim()) return
    setPLoading(true); setPError(null); setPResult(null)
    try {
      setPResult(await channelPlansApi.aiPrompts(planId, pTheme.trim(), pContext.trim()))
    } catch (e) {
      setPError(e.message)
    } finally {
      setPLoading(false)
    }
  }

  const handleAsk = async () => {
    if (!question.trim()) return
    setQaLoading(true); setQaError(null); setAnswer(null)
    try {
      const res = await channelPlansApi.aiAsk(planId, question.trim())
      setAnswer(res.answer)
    } catch (e) {
      setQaError(e.message)
    } finally {
      setQaLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">

      {/* SEO */}
      <AccordionSection title="SEO" open={openSection === 'seo'} onToggle={() => toggle('seo')}>
        <Input
          label="Theme"
          value={seoTheme}
          onChange={e => setSeoTheme(e.target.value)}
          placeholder="e.g. Heavy Rain on Window"
          disabled={seoLoading}
        />
        <Input
          label="Context (optional)"
          value={seoContext}
          onChange={e => setSeoContext(e.target.value)}
          placeholder="Any extra context..."
          disabled={seoLoading}
        />
        <Button variant="primary" size="sm" loading={seoLoading} onClick={handleSeo} disabled={!seoTheme.trim()}>
          Generate SEO
        </Button>
        {seoError && <p className="text-xs text-[#f87171]">{seoError}</p>}
        {seoResult && (
          <div className="flex flex-col gap-2">
            <ResultBlock label="Title" text={seoResult.title} />
            <ResultBlock label="Description" text={seoResult.description} />
            <ResultBlock label="Tags" text={seoResult.tags} />
          </div>
        )}
      </AccordionSection>

      {/* Prompts */}
      <AccordionSection title="Prompts" open={openSection === 'prompts'} onToggle={() => toggle('prompts')}>
        <Input
          label="Theme"
          value={pTheme}
          onChange={e => setPTheme(e.target.value)}
          placeholder="e.g. Heavy Rain on Window"
          disabled={pLoading}
        />
        <Input
          label="Context (optional)"
          value={pContext}
          onChange={e => setPContext(e.target.value)}
          placeholder="Any extra context..."
          disabled={pLoading}
        />
        <Button variant="primary" size="sm" loading={pLoading} onClick={handlePrompts} disabled={!pTheme.trim()}>
          Generate All
        </Button>
        {pError && <p className="text-xs text-[#f87171]">{pError}</p>}
        {pResult && (
          <div className="flex flex-col gap-2">
            <ResultBlock label="Suno" text={pResult.suno} />
            <ResultBlock label="Midjourney" text={pResult.midjourney} />
            <ResultBlock label="Runway" text={pResult.runway} />
            <ResultBlock label="Thumbnail (based on Midjourney)" text={pResult.thumbnail} />
          </div>
        )}
      </AccordionSection>

      {/* Q&A */}
      <AccordionSection title="Q&A" open={openSection === 'qa'} onToggle={() => toggle('qa')}>
        <Input
          label="Question"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="e.g. What is the recommended upload schedule?"
          disabled={qaLoading}
        />
        <Button variant="primary" size="sm" loading={qaLoading} onClick={handleAsk} disabled={!question.trim()}>
          Ask
        </Button>
        {qaError && <p className="text-xs text-[#f87171]">{qaError}</p>}
        {answer && (
          <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold text-[#5a5a70] tracking-widest uppercase">Answer</span>
              <CopyButton text={answer} />
            </div>
            <p className="text-xs text-[#9090a8] leading-relaxed whitespace-pre-wrap">{answer}</p>
          </div>
        )}
      </AccordionSection>

    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/components/AIAssistantPanel.jsx
git commit -m "feat: add shared AIAssistantPanel component"
```

---

## Task 8: ChannelPlansPage

**Files:**
- Create: `console/frontend/src/pages/ChannelPlansPage.jsx`

- [ ] **Step 1: Create the page**

Create `console/frontend/src/pages/ChannelPlansPage.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { channelPlansApi } from '../api/client.js'
import { Card, Button, Badge, Input, Select, Toast, Spinner, EmptyState, Modal } from '../components/index.jsx'
import AIAssistantPanel from '../components/AIAssistantPanel.jsx'

function PlanCard({ plan, onClick }) {
  return (
    <Card className="cursor-pointer hover:border-[#7c6af7] transition-colors" onClick={onClick}>
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="text-sm font-semibold text-[#e8e8f0]">{plan.name}</div>
          {plan.channel_id && (
            <Badge status="youtube" label="linked" />
          )}
        </div>
        {plan.focus && (
          <p className="text-xs text-[#9090a8] leading-relaxed">{plan.focus}</p>
        )}
        <div className="flex flex-wrap gap-2 mt-1">
          {plan.upload_frequency && (
            <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
              {plan.upload_frequency}
            </span>
          )}
          {plan.rpm_estimate && (
            <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#34d399]">
              RPM {plan.rpm_estimate}
            </span>
          )}
        </div>
        {plan.md_filename && (
          <p className="text-[10px] text-[#5a5a70] font-mono">{plan.md_filename}</p>
        )}
      </div>
    </Card>
  )
}

function ImportModal({ onClose, onImported }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleImport = async () => {
    if (!file) { setError('Select a .md file'); return }
    setLoading(true); setError(null)
    try {
      const plan = await channelPlansApi.import(file)
      onImported(plan)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Import Channel Plan"
      width="max-w-sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleImport}>Import</Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-[#9090a8]">
          Select a Markdown file following the channel plan template format.
        </p>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Markdown file (.md)</label>
          <input
            type="file"
            accept=".md"
            onChange={e => { setFile(e.target.files?.[0] || null); setError(null) }}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        </div>
        {error && <p className="text-xs text-[#f87171]">{error}</p>}
      </div>
    </Modal>
  )
}

function DetailPanel({ plan: initialPlan, channels, onClose, onSaved }) {
  const [plan, setPlan]         = useState(initialPlan)
  const [mdContent, setMdContent] = useState(initialPlan.md_content ?? '')
  const [channelId, setChannelId] = useState(String(initialPlan.channel_id ?? ''))
  const [activeTab, setActiveTab] = useState('plan')
  const [saving, setSaving]     = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [toast, setToast]       = useState(null)

  // Load full md_content if not yet present
  useEffect(() => {
    if (!plan.md_content) {
      channelPlansApi.get(plan.id)
        .then(full => { setPlan(full); setMdContent(full.md_content) })
        .catch(() => {})
    }
  }, [plan.id])

  const handleSave = async () => {
    setSaving(true); setSaveError(null)
    try {
      const updated = await channelPlansApi.update(
        plan.id,
        mdContent,
        channelId ? parseInt(channelId, 10) : null
      )
      setPlan(updated)
      setToast({ msg: 'Saved', type: 'success' })
      setTimeout(() => setToast(null), 2000)
      onSaved(updated)
    } catch (e) {
      setSaveError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const tabs = ['plan', 'ai']

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-[560px] h-full bg-[#16161a] border-l border-[#2a2a32] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32] gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-[#e8e8f0] truncate">{plan.name}</h2>
            {plan.md_filename && (
              <p className="text-[10px] text-[#5a5a70] font-mono truncate">{plan.md_filename}</p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button variant="primary" size="sm" loading={saving} onClick={handleSave}>Save</Button>
            <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0] transition-colors">✕</button>
          </div>
        </div>

        {/* Toast */}
        {toast && (
          <div className="absolute top-16 left-0 right-0 z-10 px-6">
            <Toast message={toast.msg} type={toast.type} />
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-[#2a2a32]">
          {[['plan', 'Plan'], ['ai', 'AI Assistant']].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-5 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                activeTab === id
                  ? 'border-[#7c6af7] text-[#7c6af7]'
                  : 'border-transparent text-[#9090a8] hover:text-[#e8e8f0]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'plan' && (
            <div className="flex flex-col gap-4 p-6">
              {/* Metadata chips */}
              <div className="flex flex-wrap gap-2">
                {plan.focus && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                    {plan.focus}
                  </span>
                )}
                {plan.upload_frequency && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                    {plan.upload_frequency}
                  </span>
                )}
                {plan.rpm_estimate && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#34d399]">
                    RPM {plan.rpm_estimate}
                  </span>
                )}
              </div>

              {/* Channel link */}
              <Select
                label="Linked YouTube Channel (optional)"
                value={channelId}
                onChange={e => setChannelId(e.target.value)}
              >
                <option value="">— Not linked —</option>
                {channels.map(ch => (
                  <option key={ch.id} value={String(ch.id)}>{ch.name}</option>
                ))}
              </Select>

              {/* MD editor */}
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">Markdown content</label>
                <textarea
                  value={mdContent}
                  onChange={e => setMdContent(e.target.value)}
                  className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 text-xs text-[#e8e8f0] font-mono leading-relaxed resize-none focus:outline-none focus:border-[#7c6af7] transition-colors"
                  style={{ minHeight: '50vh' }}
                  spellCheck={false}
                />
              </div>

              {saveError && <p className="text-xs text-[#f87171]">{saveError}</p>}
            </div>
          )}
          {activeTab === 'ai' && (
            <div className="p-6">
              <AIAssistantPanel planId={plan.id} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ChannelPlansPage() {
  const [plans, setPlans]           = useState([])
  const [channels, setChannels]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [showImport, setShowImport] = useState(false)
  const [activePlan, setActivePlan] = useState(null)
  const [toast, setToast]           = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const load = async () => {
    setLoading(true)
    try {
      const [p, ch] = await Promise.all([
        channelPlansApi.list(),
        fetch('/api/channels?platform=youtube', {
          headers: { Authorization: `Bearer ${sessionStorage.getItem('console_token')}` }
        }).then(r => r.ok ? r.json() : []).catch(() => []),
      ])
      setPlans(p)
      setChannels(ch)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleImported = (plan) => {
    setShowImport(false)
    showToast(`"${plan.name}" imported`, 'success')
    load()
    // Open detail panel for the new plan
    channelPlansApi.get(plan.id).then(full => setActivePlan(full)).catch(() => {})
  }

  const handleSaved = (updated) => {
    setPlans(prev => prev.map(p => p.id === updated.id ? { ...p, ...updated } : p))
  }

  return (
    <div className="flex flex-col gap-6">
      {toast && <Toast message={toast.msg} type={toast.type} />}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Channel Plans</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">{plans.length} plans</p>
        </div>
        <Button variant="primary" onClick={() => setShowImport(true)}>+ Import Plan</Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : plans.length === 0 ? (
        <EmptyState
          title="No channel plans"
          description="Import a Markdown channel plan file to get started."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map(plan => (
            <PlanCard
              key={plan.id}
              plan={plan}
              onClick={() => channelPlansApi.get(plan.id).then(setActivePlan).catch(() => {})}
            />
          ))}
        </div>
      )}

      {/* Import modal */}
      {showImport && (
        <ImportModal onClose={() => setShowImport(false)} onImported={handleImported} />
      )}

      {/* Detail panel */}
      {activePlan && (
        <DetailPanel
          plan={activePlan}
          channels={channels}
          onClose={() => setActivePlan(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/pages/ChannelPlansPage.jsx
git commit -m "feat: add ChannelPlansPage"
```

---

## Task 9: App.jsx — Add nav tab and route

**Files:**
- Modify: `console/frontend/src/App.jsx`

- [ ] **Step 1: Add the import and icon**

At the top of `App.jsx`, add the import after the YouTubeVideosPage import line:

```js
import ChannelPlansPage from './pages/ChannelPlansPage.jsx'
```

Inside the `Icons` object (after the `YouTube` entry), add:

```js
  ChannelPlans: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
      <line x1="8" y1="13" x2="16" y2="13"/>
      <line x1="8" y1="17" x2="16" y2="17"/>
      <circle cx="10" cy="9" r="1"/>
    </svg>
  ),
```

- [ ] **Step 2: Add the tab to ALL_TABS**

In `ALL_TABS`, after the `youtube` entry and before the `pipeline` entry, add:

```js
  { id: 'channel-plans', label: 'Channel Plans', Icon: Icons.ChannelPlans, roles: ['admin', 'editor'], section: 'youtube' },
```

- [ ] **Step 3: Add the renderPage case**

In the `renderPage` switch, after the `case 'youtube':` line, add:

```js
      case 'channel-plans': return <ChannelPlansPage />
```

- [ ] **Step 4: Verify in the browser**

Start the dev server if not already running:
```bash
cd console/frontend && npm run dev
```

Navigate to `http://localhost:5173` → confirm "Channel Plans" appears in the sidebar under "YOUTUBE VIDEOS" → clicking it shows the page.

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/App.jsx
git commit -m "feat: add Channel Plans nav tab and route"
```

---

## Task 10: YouTubeVideosPage — Channel Plans accordion

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

This task modifies the page header and adds an expandable accordion listing all channel plans above the video list.

- [ ] **Step 1: Add channelPlans state and load function**

At the top of `YouTubeVideosPage` (the default export function), add new state variables after the existing `useState` declarations:

```js
const [channelPlans, setChannelPlans]     = useState([])
const [accordionOpen, setAccordionOpen]   = useState(false)
const [expandedPlanId, setExpandedPlanId] = useState(null)
```

Update the `load` function to also fetch channel plans. Replace the existing `load` function with:

```js
const load = async (signal = { cancelled: false }) => {
  setLoading(true)
  try {
    const vids = await youtubeVideosApi.list({ status: filterStatus || undefined })
    if (!signal.cancelled) setVideos(vids.items || vids)
  } catch (e) {
    if (!signal.cancelled) showToast(e.message, 'error')
  }
  try {
    const tmpl = await youtubeVideosApi.listTemplates()
    if (!signal.cancelled) setTemplates(tmpl)
  } catch (e) {
    if (!signal.cancelled) console.warn('Failed to load templates:', e)
  }
  try {
    const plans = await channelPlansApi.list()
    if (!signal.cancelled) setChannelPlans(plans)
  } catch (e) {
    if (!signal.cancelled) console.warn('Failed to load channel plans:', e)
  }
  if (!signal.cancelled) setLoading(false)
}
```

Also add the import at the top of the file:
```js
import { youtubeVideosApi, musicApi, assetsApi, sfxApi, channelPlansApi } from '../api/client.js'
```

- [ ] **Step 2: Replace header buttons with single "+ New Video"**

Find the header div that renders template buttons:

```jsx
<div className="flex gap-2">
  {templates.filter(t => t.output_format === 'landscape_long').map(t => (
    <Button key={t.slug} variant="primary" onClick={() => setActiveTemplate(t)}>
      + New {t.label}
    </Button>
  ))}
</div>
```

Replace it with:

```jsx
<div className="flex gap-2">
  <Button
    variant="primary"
    onClick={() => {
      // Pick first landscape_long template as default, or show picker
      const firstTemplate = templates.find(t => t.output_format === 'landscape_long')
      if (firstTemplate) {
        setActiveTemplate(firstTemplate)
        setActiveChannelPlan(null)
      }
    }}
  >
    + New Video
  </Button>
</div>
```

Add `activeChannelPlan` state:
```js
const [activeChannelPlan, setActiveChannelPlan] = useState(null)
```

- [ ] **Step 3: Add the Channel Plans accordion**

After the closing `</div>` of the page header section and before the Filters section, insert:

```jsx
{/* Channel Plans accordion */}
<div className="border border-[#2a2a32] rounded-xl overflow-hidden">
  <button
    onClick={() => setAccordionOpen(v => !v)}
    className="w-full flex items-center justify-between px-5 py-3 bg-[#1c1c22] hover:bg-[#222228] transition-colors"
  >
    <span className="text-sm font-semibold text-[#e8e8f0]">
      Channel Plans <span className="text-[#5a5a70] font-normal">({channelPlans.length})</span>
    </span>
    <span className="text-[#9090a8] text-xs">{accordionOpen ? '▲' : '▼'}</span>
  </button>

  {accordionOpen && (
    <div className="divide-y divide-[#2a2a32]">
      {channelPlans.length === 0 ? (
        <p className="px-5 py-4 text-xs text-[#5a5a70]">
          No channel plans yet. <a href="/channel-plans" className="text-[#7c6af7] hover:underline">Import one →</a>
        </p>
      ) : channelPlans.map(plan => (
        <div key={plan.id} className="bg-[#16161a]">
          {/* Plan row header */}
          <button
            onClick={() => setExpandedPlanId(id => id === plan.id ? null : plan.id)}
            className="w-full flex items-center gap-3 px-5 py-3 hover:bg-[#1c1c22] transition-colors text-left"
          >
            <span className="text-sm font-medium text-[#e8e8f0] flex-1">{plan.name}</span>
            {plan.focus && (
              <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8] hidden sm:inline">
                {plan.focus.split(',')[0].trim()}
              </span>
            )}
            {plan.rpm_estimate && (
              <span className="text-[10px] font-mono text-[#34d399]">{plan.rpm_estimate}</span>
            )}
            <span className="text-[#9090a8] text-xs">{expandedPlanId === plan.id ? '▲' : '▼'}</span>
          </button>

          {/* Expanded plan content */}
          {expandedPlanId === plan.id && (
            <div className="px-5 pb-5 flex flex-col gap-4">
              {/* Metadata chips */}
              <div className="flex flex-wrap gap-2">
                {plan.focus && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                    {plan.focus}
                  </span>
                )}
                {plan.upload_frequency && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#9090a8]">
                    {plan.upload_frequency}
                  </span>
                )}
                {plan.rpm_estimate && (
                  <span className="text-[10px] font-mono bg-[#1c1c22] border border-[#2a2a32] px-2 py-0.5 rounded text-[#34d399]">
                    RPM {plan.rpm_estimate}
                  </span>
                )}
              </div>

              {/* AI assistant */}
              <AIAssistantPanel planId={plan.id} />

              {/* New Video button */}
              <div className="flex justify-end">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    const firstTemplate = templates.find(t => t.output_format === 'landscape_long')
                    if (firstTemplate) {
                      setActiveTemplate(firstTemplate)
                      setActiveChannelPlan(plan)
                    }
                  }}
                >
                  + New Video for this channel
                </Button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )}
</div>
```

Add the AIAssistantPanel import at the top of the file:
```js
import AIAssistantPanel from '../components/AIAssistantPanel.jsx'
```

- [ ] **Step 4: Pass `activeChannelPlan` to CreationPanel**

Find where `CreationPanel` is rendered:
```jsx
{activeTemplate && (
  <CreationPanel
    template={activeTemplate}
    onClose={() => setActiveTemplate(null)}
    onCreated={() => { setActiveTemplate(null); load() }}
  />
)}
```

Replace with:
```jsx
{activeTemplate && (
  <CreationPanel
    template={activeTemplate}
    channelPlan={activeChannelPlan}
    onClose={() => { setActiveTemplate(null); setActiveChannelPlan(null) }}
    onCreated={() => { setActiveTemplate(null); setActiveChannelPlan(null); load() }}
  />
)}
```

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: add channel plans accordion to YouTubeVideosPage"
```

---

## Task 11: YouTubeVideosPage — CreationPanel AI Autofill

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

This task adds the AI Autofill button and channel plan display to the existing `CreationPanel` component.

- [ ] **Step 1: Update `CreationPanel` props and state**

In the `CreationPanel` function signature, add `channelPlan` param:

```js
function CreationPanel({ template, channelPlan, onClose, onCreated }) {
```

Add autofill state inside `CreationPanel`, after the existing state declarations:

```js
const [autofilling, setAutofilling] = useState(false)
const [autofillError, setAutofillError] = useState(null)
```

- [ ] **Step 2: Add autofill handler inside `CreationPanel`**

Add the handler after the existing `handleSubmit` function:

```js
const handleAutofill = async () => {
  if (!channelPlan || !form.theme) return
  setAutofilling(true)
  setAutofillError(null)
  try {
    const result = await channelPlansApi.aiAutofill(channelPlan.id, form.theme)
    setForm(f => ({
      ...f,
      seo_title:       result.title        || f.seo_title,
      seo_description: result.description  || f.seo_description,
      seo_tags:        result.tags         || f.seo_tags,
      // duration
      ...(result.target_duration_h
        ? (() => {
            const preset = DURATION_PRESETS.find(p => p.value === result.target_duration_h)
            return preset
              ? { target_duration_h: result.target_duration_h, isCustomDuration: false }
              : { customDuration: String(result.target_duration_h), isCustomDuration: true }
          })()
        : {}),
    }))
    // Update prompt reference blocks if provided
    if (result.suno_prompt && template) {
      template._autofill_suno = result.suno_prompt
    }
    if (result.runway_prompt && template) {
      template._autofill_runway = result.runway_prompt
    }
    showToast('AI autofill complete', 'success')
  } catch (e) {
    setAutofillError(e.message)
  } finally {
    setAutofilling(false)
  }
}
```

- [ ] **Step 3: Update the CreationPanel header to show channel plan + AI Autofill button**

Find the existing header inside `CreationPanel`:

```jsx
<div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32]">
  <h2 className="text-base font-semibold text-[#e8e8f0]">New {template?.label}</h2>
  <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0]">✕</button>
</div>
```

Replace with:

```jsx
<div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32]">
  <div className="flex flex-col gap-0.5 min-w-0">
    <h2 className="text-base font-semibold text-[#e8e8f0]">New {template?.label}</h2>
    {channelPlan && (
      <span className="text-xs text-[#7c6af7] font-mono">{channelPlan.name}</span>
    )}
  </div>
  <div className="flex items-center gap-2 flex-shrink-0">
    {channelPlan && (
      <Button
        variant="accent"
        size="sm"
        loading={autofilling}
        disabled={!form.theme.trim()}
        onClick={handleAutofill}
        title={form.theme.trim() ? 'AI Autofill from channel plan' : 'Enter a theme first'}
      >
        ✦ AI Autofill
      </Button>
    )}
    <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0]">✕</button>
  </div>
</div>
```

- [ ] **Step 4: Show autofill error and update prompt reference blocks**

After the existing toast element inside `CreationPanel` scroll area, add after `{toast && ...}`:

```jsx
{autofillError && (
  <div className="px-6 pt-2">
    <p className="text-xs text-[#f87171]">{autofillError}</p>
  </div>
)}
```

In the existing Suno prompt reference block, update to show autofill result if available:

```jsx
{(template?.suno_prompt_template || template?._autofill_suno) && (
  <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
    <div className="text-xs text-[#5a5a70] mb-1">
      Suno Prompt {template?._autofill_suno ? '(AI generated)' : '(reference)'}
    </div>
    <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
      {template._autofill_suno || template.suno_prompt_template}
    </p>
    <button
      onClick={() => navigator.clipboard.writeText(template._autofill_suno || template.suno_prompt_template)}
      className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
    >
      Copy
    </button>
  </div>
)}
```

Apply the same pattern for the Runway prompt reference block:

```jsx
{(template?.runway_prompt_template || template?._autofill_runway) && (
  <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
    <div className="text-xs text-[#5a5a70] mb-1">
      Runway Prompt {template?._autofill_runway ? '(AI generated)' : '(reference)'}
    </div>
    <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
      {template._autofill_runway || template.runway_prompt_template}
    </p>
    <button
      onClick={() => navigator.clipboard.writeText(template._autofill_runway || template.runway_prompt_template)}
      className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
    >
      Copy
    </button>
  </div>
)}
```

- [ ] **Step 5: Also fill seo_description in the form**

The existing `CreationPanel` form has `seo_title` and `seo_tags` inputs, but not `seo_description` — it uses a template auto-fill. Add a `seo_description` textarea field in the **① THEME & SEO** section, after the `seo_title` input:

```jsx
<div className="flex flex-col gap-1">
  <label className="text-xs text-[#9090a8] font-medium">SEO Description</label>
  <textarea
    value={form.seo_description}
    onChange={e => setForm(f => ({ ...f, seo_description: e.target.value }))}
    placeholder="YouTube description..."
    rows={4}
    className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors resize-none"
  />
</div>
```

- [ ] **Step 6: Verify the full flow in the browser**

1. Navigate to `/youtube`
2. Expand the "Channel Plans" accordion
3. Expand an ASMR plan row → confirm AI assistant panel renders
4. Click "+ New Video for this channel" → confirm slide-over opens with ASMR plan name shown in header
5. Enter a theme (e.g. "Heavy Rain on Window") → confirm "✦ AI Autofill" button becomes active
6. Click AI Autofill → confirm fields fill in (title, description, tags, duration)

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: add AI Autofill and channel plan context to CreationPanel"
```

---

## Self-Review Checklist

Run these before declaring the feature complete:

```bash
# All channel plan tests pass
pytest tests/test_channel_plan_service.py -v

# No import errors on backend startup
uvicorn console.backend.main:app --port 8080 --reload

# All endpoints appear in OpenAPI docs
curl -s http://localhost:8080/openapi.json | python3 -c "import json,sys; paths=json.load(sys.stdin)['paths']; print([p for p in paths if 'channel-plans' in p])"

# Frontend builds without errors
cd console/frontend && npm run build
```

Expected:
- All tests pass
- 9 paths with `/channel-plans` in the OpenAPI output
- Frontend build completes with no errors
