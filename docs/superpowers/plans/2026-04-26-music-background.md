# Music Background Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Music library tab to the Management Console with Suno/Lyria generation, import, and per-script background music assignment that flows through to video rendering.

**Architecture:** `MusicTrack` lives in `database/models.py` (shared with the pipeline); Celery tasks in `render_q` handle async generation; the console router/service layer handles CRUD and Gemini prompt expansion; `composer.py` uses the DB-assigned track (with looping) instead of the existing filename scan.

**Tech Stack:** FastAPI · SQLAlchemy · PostgreSQL (ARRAY columns) · Celery + Redis · Suno REST API · Google Lyria via `google-genai` SDK · React 18 + Tailwind

---

## File Map

| Action | Path |
|---|---|
| Modify | `database/models.py` |
| Create | `console/backend/alembic/versions/006_music_tracks.py` |
| Create | `pipeline/music_providers/__init__.py` |
| Create | `pipeline/music_providers/suno_provider.py` |
| Create | `pipeline/music_providers/lyria_provider.py` |
| Create | `console/backend/services/music_service.py` |
| Create | `console/backend/tasks/music_tasks.py` |
| Modify | `console/backend/celery_app.py` |
| Create | `console/backend/routers/music.py` |
| Modify | `console/backend/main.py` |
| Modify | `console/.env.example` |
| Modify | `pipeline/composer.py` |
| Modify | `console/backend/services/script_service.py` |
| Create | `tests/test_music_providers.py` |
| Create | `tests/test_music_service.py` |
| Modify | `console/frontend/src/api/client.js` |
| Create | `console/frontend/src/pages/MusicPage.jsx` |
| Modify | `console/frontend/src/App.jsx` |
| Modify | `console/frontend/src/pages/ScriptsPage.jsx` |

---

## Task 1: MusicTrack model + DB migration

**Files:**
- Modify: `database/models.py`
- Create: `console/backend/alembic/versions/006_music_tracks.py`

- [ ] **Step 1: Add MusicTrack to `database/models.py`**

Open `database/models.py`. Add after the last import and before `class ViralVideo`:

```python
class MusicTrack(Base):
    """Background music tracks — generated via Suno/Lyria or imported."""
    __tablename__ = "music_tracks"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    title             = Column(String(200), nullable=False)
    file_path         = Column(String(500))
    duration_s        = Column(Float)
    niches            = Column(ARRAY(String), default=list)
    moods             = Column(ARRAY(String), default=list)
    genres            = Column(ARRAY(String), default=list)
    is_vocal          = Column(Boolean, default=False)
    is_favorite       = Column(Boolean, default=False)
    volume            = Column(Float, default=0.15)
    usage_count       = Column(Integer, default=0)
    quality_score     = Column(Integer, default=80)
    provider          = Column(String(20))   # suno | lyria-clip | lyria-pro | import
    provider_task_id  = Column(String(200))
    generation_status = Column(String(20), default="pending")  # pending | ready | failed
    generation_prompt = Column(Text)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Add `music_track_id` to `GeneratedScript` in `database/models.py`**

In the `GeneratedScript` class, after the `language` column line, add:

```python
    # Music extension (added by migration 006)
    music_track_id    = Column(Integer, ForeignKey("music_tracks.id"), nullable=True)
```

- [ ] **Step 3: Verify the model can be imported**

```bash
cd /path/to/ai-media-automation
python -c "from database.models import MusicTrack, GeneratedScript; print('OK', MusicTrack.__tablename__)"
```

Expected output: `OK music_tracks`

- [ ] **Step 4: Write migration `006_music_tracks.py`**

Create `console/backend/alembic/versions/006_music_tracks.py`:

```python
"""Add music_tracks table and music_track_id to generated_scripts

Revision ID: 006
Revises: 005
Create Date: 2026-04-26
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "music_tracks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("file_path", sa.String(500)),
        sa.Column("duration_s", sa.Float),
        sa.Column("niches", ARRAY(sa.String), server_default="{}"),
        sa.Column("moods", ARRAY(sa.String), server_default="{}"),
        sa.Column("genres", ARRAY(sa.String), server_default="{}"),
        sa.Column("is_vocal", sa.Boolean, server_default="false"),
        sa.Column("is_favorite", sa.Boolean, server_default="false"),
        sa.Column("volume", sa.Float, server_default="0.15"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("quality_score", sa.Integer, server_default="80"),
        sa.Column("provider", sa.String(20)),
        sa.Column("provider_task_id", sa.String(200)),
        sa.Column("generation_status", sa.String(20), server_default="pending"),
        sa.Column("generation_prompt", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_music_tracks_status", "music_tracks", ["generation_status"])
    op.create_index("idx_music_tracks_provider", "music_tracks", ["provider"])

    op.add_column(
        "generated_scripts",
        sa.Column("music_track_id", sa.Integer, sa.ForeignKey("music_tracks.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_scripts", "music_track_id")
    op.drop_index("idx_music_tracks_provider", table_name="music_tracks")
    op.drop_index("idx_music_tracks_status", table_name="music_tracks")
    op.drop_table("music_tracks")
```

- [ ] **Step 5: Run the migration**

```bash
cd console/backend
alembic upgrade head
```

Expected: `Running upgrade 005 -> 006, Add music_tracks table ...`

- [ ] **Step 6: Commit**

```bash
git add database/models.py console/backend/alembic/versions/006_music_tracks.py
git commit -m "feat: add MusicTrack model and migration 006"
```

---

## Task 2: Suno provider + shared audio probe utility

**Files:**
- Create: `pipeline/music_providers/__init__.py`
- Create: `pipeline/music_providers/suno_provider.py`
- Create: `tests/test_music_providers.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_music_providers.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _fake_suno_key():
    with patch.dict("os.environ", {"SUNO_API_KEY": "test-key"}):
        yield


def test_suno_provider_generate_returns_task_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 200, "data": {"taskId": "abc-123"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.music_providers.suno_provider.requests.post", return_value=mock_resp):
        from pipeline.music_providers.suno_provider import SunoProvider
        provider = SunoProvider()
        task_id = provider.submit(
            prompt="uplifting pop track",
            style="pop, electronic",
            title="Test Track",
            instrumental=True,
        )

    assert task_id == "abc-123"


def test_suno_provider_poll_returns_audio_url_on_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "code": 200,
        "data": {
            "status": "SUCCESS",
            "sunoData": [{"audioUrl": "https://cdn.suno.ai/track.mp3"}],
        },
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.music_providers.suno_provider.requests.get", return_value=mock_resp):
        from pipeline.music_providers.suno_provider import SunoProvider
        provider = SunoProvider()
        url = provider.poll("abc-123")

    assert url == "https://cdn.suno.ai/track.mp3"


def test_suno_provider_poll_returns_none_when_pending():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 200, "data": {"status": "PENDING", "sunoData": []}}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.music_providers.suno_provider.requests.get", return_value=mock_resp):
        from pipeline.music_providers.suno_provider import SunoProvider
        provider = SunoProvider()
        url = provider.poll("abc-123")

    assert url is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /path/to/ai-media-automation
python -m pytest tests/test_music_providers.py -v
```

Expected: `ImportError` — `pipeline.music_providers.suno_provider` does not exist yet.

- [ ] **Step 3: Create `pipeline/music_providers/__init__.py`**

```python
"""Music provider utilities."""
import json
import subprocess


def probe_audio_duration(path: str) -> float:
    """Return duration in seconds using ffprobe. Returns 0.0 on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if streams:
            return float(streams[0].get("duration", 0))
    except Exception:
        pass
    return 0.0
```

- [ ] **Step 4: Create `pipeline/music_providers/suno_provider.py`**

```python
"""Suno API client — submit generation tasks and poll for results."""
import os
import requests


SUNO_BASE = "https://api.sunoapi.org/api/v1"
SUNO_MODEL = "V4_5"


class SunoProvider:
    def __init__(self):
        self._key = os.environ.get("SUNO_API_KEY", "")
        if not self._key:
            raise RuntimeError("SUNO_API_KEY is not set")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    def submit(
        self,
        prompt: str,
        style: str,
        title: str,
        instrumental: bool = True,
        negative_tags: str = "",
    ) -> str:
        """Submit a generation request. Returns Suno taskId."""
        payload = {
            "customMode": True,
            "model": SUNO_MODEL,
            "instrumental": instrumental,
            "prompt": prompt,
            "style": style,
            "title": title,
            "callBackUrl": "https://placeholder.invalid/noop",
        }
        if negative_tags:
            payload["negativeTags"] = negative_tags

        resp = requests.post(f"{SUNO_BASE}/generate", json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["taskId"]

    def poll(self, task_id: str) -> str | None:
        """
        Poll for task completion.
        Returns the first audio URL on SUCCESS, None if still pending, raises on failure.
        """
        resp = requests.get(
            f"{SUNO_BASE}/generate/record-info",
            params={"taskId": task_id},
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("status", "")
        if status == "SUCCESS":
            suno_data = data.get("sunoData", [])
            if suno_data:
                return suno_data[0].get("audioUrl")
        if status == "FAILED":
            raise RuntimeError(f"Suno generation failed for task {task_id}")
        return None  # still pending
```

- [ ] **Step 5: Run tests — expect pass**

```bash
python -m pytest tests/test_music_providers.py::test_suno_provider_generate_returns_task_id \
                 tests/test_music_providers.py::test_suno_provider_poll_returns_audio_url_on_success \
                 tests/test_music_providers.py::test_suno_provider_poll_returns_none_when_pending -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add pipeline/music_providers/__init__.py pipeline/music_providers/suno_provider.py tests/test_music_providers.py
git commit -m "feat: add Suno provider and audio probe utility"
```

---

## Task 3: Lyria provider

**Files:**
- Create: `pipeline/music_providers/lyria_provider.py`
- Modify: `tests/test_music_providers.py`

- [ ] **Step 1: Add Lyria tests to `tests/test_music_providers.py`**

Append to the file:

```python
def test_lyria_provider_generate_returns_bytes():
    import base64
    fake_audio = base64.b64encode(b"FAKE_MP3_DATA").decode()

    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.data = fake_audio

    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    mock_candidate = MagicMock()
    mock_candidate.content = mock_content

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        with patch("pipeline.music_providers.lyria_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            from pipeline.music_providers.lyria_provider import LyriaProvider
            provider = LyriaProvider()
            audio_bytes = provider.generate(
                prompt="calm ambient background",
                model="lyria-3-clip-preview",
                is_vocal=False,
            )

    assert audio_bytes == b"FAKE_MP3_DATA"
```

- [ ] **Step 2: Run new test — expect failure**

```bash
python -m pytest tests/test_music_providers.py::test_lyria_provider_generate_returns_bytes -v
```

Expected: `ImportError` — lyria_provider does not exist yet.

- [ ] **Step 3: Create `pipeline/music_providers/lyria_provider.py`**

```python
"""Lyria music generation via the Gemini API (google-genai SDK)."""
import base64
import os

try:
    from google import genai
except ImportError:
    genai = None

LYRIA_MODELS = {
    "lyria-clip": "lyria-3-clip-preview",
    "lyria-pro":  "lyria-3-pro-preview",
}


class LyriaProvider:
    def __init__(self):
        self._key = os.environ.get("GEMINI_API_KEY", "")
        if not self._key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        if genai is None:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")

    def generate(self, prompt: str, model: str, is_vocal: bool = False) -> bytes:
        """
        Generate music and return raw MP3 bytes.

        model: 'lyria-3-clip-preview' (30s) or 'lyria-3-pro-preview' (full song)
        """
        vocal_suffix = " with vocals, sung lyrics" if is_vocal else " instrumental only, no vocals, no singing"
        full_prompt = prompt.strip() + vocal_suffix

        client = genai.Client(api_key=self._key)
        config = genai.types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            response_mime_type="audio/mp3",
        )
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=config,
        )

        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    return base64.b64decode(part.inline_data.data)

        raise RuntimeError("Lyria returned no audio data")
```

- [ ] **Step 4: Run all provider tests**

```bash
python -m pytest tests/test_music_providers.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/music_providers/lyria_provider.py tests/test_music_providers.py
git commit -m "feat: add Lyria provider"
```

---

## Task 4: MusicService

**Files:**
- Create: `console/backend/services/music_service.py`
- Create: `tests/test_music_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_music_service.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def _make_track(**kwargs):
    t = MagicMock()
    t.id = kwargs.get("id", 1)
    t.title = kwargs.get("title", "Test Track")
    t.file_path = kwargs.get("file_path", "assets/music/1.mp3")
    t.duration_s = kwargs.get("duration_s", 30.0)
    t.niches = kwargs.get("niches", ["fitness"])
    t.moods = kwargs.get("moods", ["energetic"])
    t.genres = kwargs.get("genres", ["pop"])
    t.is_vocal = kwargs.get("is_vocal", False)
    t.is_favorite = kwargs.get("is_favorite", False)
    t.volume = kwargs.get("volume", 0.15)
    t.usage_count = kwargs.get("usage_count", 0)
    t.quality_score = kwargs.get("quality_score", 80)
    t.provider = kwargs.get("provider", "import")
    t.provider_task_id = kwargs.get("provider_task_id", None)
    t.generation_status = kwargs.get("generation_status", "ready")
    t.generation_prompt = kwargs.get("generation_prompt", None)
    t.created_at = None
    return t


def test_list_tracks_returns_all_when_no_filters():
    db = MagicMock()
    track = _make_track()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [track]
    db.query.return_value.order_by.return_value.all.return_value = [track]

    from console.backend.services.music_service import MusicService
    svc = MusicService(db)
    result = svc.list_tracks()

    assert len(result) == 1
    assert result[0]["title"] == "Test Track"


def test_increment_usage_updates_count():
    db = MagicMock()
    track = _make_track(usage_count=3)
    db.query.return_value.filter.return_value.first.return_value = track

    from console.backend.services.music_service import MusicService
    svc = MusicService(db)
    svc.increment_usage(1)

    assert track.usage_count == 4
    db.commit.assert_called_once()


def test_expand_prompt_calls_gemini():
    db = MagicMock()

    mock_router = MagicMock()
    mock_router.generate.return_value = '{"expanded_prompt": "An energetic pop track...", "negative_tags": "slow, sad"}'

    with patch("console.backend.services.music_service.GeminiRouter", return_value=mock_router):
        from console.backend.services.music_service import MusicService
        svc = MusicService(db)
        result = svc.expand_prompt_with_gemini(
            idea="upbeat workout music",
            niches=["fitness"],
            moods=["energetic"],
            genres=["pop"],
            is_vocal=False,
        )

    assert "expanded_prompt" in result
    assert "negative_tags" in result
```

- [ ] **Step 2: Run tests — expect failure**

```bash
python -m pytest tests/test_music_service.py -v
```

Expected: `ImportError` — music_service does not exist yet.

- [ ] **Step 3: Create `console/backend/services/music_service.py`**

```python
"""MusicService — CRUD, Gemini prompt expansion, provider dispatch, usage tracking."""
import json
import os
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

MUSIC_DIR = Path(os.environ.get("MUSIC_PATH", "./assets/music"))


def _track_to_dict(t) -> dict:
    return {
        "id":               t.id,
        "title":            t.title,
        "file_path":        t.file_path,
        "duration_s":       t.duration_s,
        "niches":           t.niches or [],
        "moods":            t.moods or [],
        "genres":           t.genres or [],
        "is_vocal":         t.is_vocal,
        "is_favorite":      t.is_favorite,
        "volume":           t.volume,
        "usage_count":      t.usage_count,
        "quality_score":    t.quality_score,
        "provider":         t.provider,
        "provider_task_id": t.provider_task_id,
        "generation_status":t.generation_status,
        "generation_prompt":t.generation_prompt,
        "created_at":       t.created_at.isoformat() if t.created_at else None,
    }


class MusicService:
    def __init__(self, db: Session):
        self.db = db

    def _model(self):
        from database.models import MusicTrack
        return MusicTrack

    # ── List ──────────────────────────────────────────────────────────────────

    def list_tracks(
        self,
        niche: str | None = None,
        mood: str | None = None,
        genre: str | None = None,
        is_vocal: bool | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        MusicTrack = self._model()
        q = self.db.query(MusicTrack)
        if niche:
            q = q.filter(MusicTrack.niches.contains([niche]))
        if mood:
            q = q.filter(MusicTrack.moods.contains([mood]))
        if genre:
            q = q.filter(MusicTrack.genres.contains([genre]))
        if is_vocal is not None:
            q = q.filter(MusicTrack.is_vocal == is_vocal)
        if status:
            q = q.filter(MusicTrack.generation_status == status)
        if search:
            q = q.filter(MusicTrack.title.ilike(f"%{search}%"))
        tracks = q.order_by(MusicTrack.created_at.desc()).all()
        return [_track_to_dict(t) for t in tracks]

    # ── Get ───────────────────────────────────────────────────────────────────

    def get_track(self, track_id: int) -> dict:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if not t:
            raise KeyError(f"Music track {track_id} not found")
        return _track_to_dict(t)

    # ── Create pending row ────────────────────────────────────────────────────

    def create_pending(
        self,
        title: str,
        niches: list[str],
        moods: list[str],
        genres: list[str],
        is_vocal: bool,
        volume: float,
        provider: str,
        prompt: str,
        negative_tags: str = "",
    ) -> dict:
        MusicTrack = self._model()
        track = MusicTrack(
            title=title,
            niches=niches,
            moods=moods,
            genres=genres,
            is_vocal=is_vocal,
            volume=volume,
            provider=provider,
            generation_status="pending",
            generation_prompt=prompt,
        )
        self.db.add(track)
        self.db.commit()
        self.db.refresh(track)
        return _track_to_dict(track)

    # ── Mark ready / failed ───────────────────────────────────────────────────

    def mark_ready(self, track_id: int, file_path: str, duration_s: float) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.file_path = file_path
            t.duration_s = duration_s
            t.generation_status = "ready"
            self.db.commit()

    def mark_failed(self, track_id: int) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.generation_status = "failed"
            self.db.commit()

    def set_provider_task_id(self, track_id: int, provider_task_id: str) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.provider_task_id = provider_task_id
            self.db.commit()

    # ── Update metadata ───────────────────────────────────────────────────────

    def update_track(self, track_id: int, data: dict) -> dict:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if not t:
            raise KeyError(f"Music track {track_id} not found")
        for field in ("title", "niches", "moods", "genres", "is_vocal", "is_favorite", "volume", "quality_score"):
            if field in data:
                setattr(t, field, data[field])
        self.db.commit()
        self.db.refresh(t)
        return _track_to_dict(t)

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_track(self, track_id: int) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if not t:
            raise KeyError(f"Music track {track_id} not found")
        if t.file_path and Path(t.file_path).exists():
            Path(t.file_path).unlink(missing_ok=True)
        self.db.delete(t)
        self.db.commit()

    # ── Usage increment ───────────────────────────────────────────────────────

    def increment_usage(self, track_id: int) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.usage_count = (t.usage_count or 0) + 1
            self.db.commit()

    # ── Gemini prompt expansion ───────────────────────────────────────────────

    def expand_prompt_with_gemini(
        self,
        idea: str,
        niches: list[str],
        moods: list[str],
        genres: list[str],
        is_vocal: bool,
    ) -> dict:
        """Call Gemini to produce a rich Suno/Lyria prompt + negative_tags."""
        from rag.llm_router import GeminiRouter

        vocal_style = "with vocals and sung lyrics" if is_vocal else "instrumental only, no vocals"
        system_prompt = f"""You are a music prompt engineer. Given a user idea and tags, produce a rich music generation prompt.

User idea: {idea}
Niches: {', '.join(niches) if niches else 'general'}
Moods: {', '.join(moods) if moods else 'neutral'}
Genres: {', '.join(genres) if genres else 'any'}
Vocal style: {vocal_style}

Return a JSON object with exactly two keys:
- "expanded_prompt": A vivid, descriptive music prompt (max 500 characters) suitable for Suno or Lyria. Include tempo, instrumentation, mood, and style details.
- "negative_tags": A short comma-separated string of styles to avoid (e.g. "aggressive, dissonant, minor key").

Respond with JSON only."""

        router = GeminiRouter()
        raw = router.generate(system_prompt, expect_json=False)
        try:
            data = json.loads(raw)
            return {
                "expanded_prompt": data.get("expanded_prompt", idea),
                "negative_tags":   data.get("negative_tags", ""),
            }
        except Exception:
            return {"expanded_prompt": idea, "negative_tags": ""}

    # ── Import (file upload) ──────────────────────────────────────────────────

    def import_track(
        self,
        file_bytes: bytes,
        extension: str,
        title: str,
        niches: list[str],
        moods: list[str],
        genres: list[str],
        is_vocal: bool,
        volume: float,
        quality_score: int,
    ) -> dict:
        MusicTrack = self._model()
        track = MusicTrack(
            title=title,
            niches=niches,
            moods=moods,
            genres=genres,
            is_vocal=is_vocal,
            volume=volume,
            quality_score=quality_score,
            provider="import",
            generation_status="ready",
        )
        self.db.add(track)
        self.db.flush()  # get track.id before writing file

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        dest = MUSIC_DIR / f"{track.id}{extension}"
        dest.write_bytes(file_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))

        track.file_path = str(dest)
        track.duration_s = duration
        self.db.commit()
        self.db.refresh(track)
        return _track_to_dict(track)

    # ── Auto-select for a niche ───────────────────────────────────────────────

    def best_track_for_niche(self, niche: str) -> int | None:
        """Return the best ready track id for a niche, or None."""
        MusicTrack = self._model()
        track = (
            self.db.query(MusicTrack)
            .filter(
                MusicTrack.generation_status == "ready",
                MusicTrack.niches.contains([niche]),
            )
            .order_by(MusicTrack.is_favorite.desc(), MusicTrack.quality_score.desc())
            .first()
        )
        return track.id if track else None
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_music_service.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/music_service.py tests/test_music_service.py
git commit -m "feat: add MusicService with CRUD, Gemini expansion, import"
```

---

## Task 5: Celery tasks + celery_app registration

**Files:**
- Create: `console/backend/tasks/music_tasks.py`
- Modify: `console/backend/celery_app.py`

- [ ] **Step 1: Create `console/backend/tasks/music_tasks.py`**

```python
"""Celery tasks for music generation — Suno (async polling) and Lyria (sync call)."""
import logging
import os
import time
from pathlib import Path

import requests

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(os.environ.get("MUSIC_PATH", "./assets/music"))
SUNO_POLL_INTERVAL = 15   # seconds between polls
SUNO_MAX_ATTEMPTS  = 20   # ~5 minutes total


@celery_app.task(bind=True, name="console.backend.tasks.music_tasks.generate_suno_music_task", queue="render_q")
def generate_suno_music_task(self, track_id: int):
    """Submit to Suno, poll until ready, download MP3, update DB."""
    from console.backend.database import SessionLocal
    from console.backend.services.music_service import MusicService
    from pipeline.music_providers.suno_provider import SunoProvider

    db = SessionLocal()
    try:
        svc = MusicService(db)
        track = svc.get_track(track_id)

        provider = SunoProvider()
        suno_task_id = provider.submit(
            prompt=track["generation_prompt"] or "",
            style=", ".join(track["genres"]) if track["genres"] else "pop",
            title=track["title"],
            instrumental=not track["is_vocal"],
        )
        svc.set_provider_task_id(track_id, suno_task_id)
        logger.info(f"[music_tasks] Suno task submitted: {suno_task_id}")

        # Poll loop
        audio_url = None
        for attempt in range(SUNO_MAX_ATTEMPTS):
            time.sleep(SUNO_POLL_INTERVAL)
            self.update_state(state="PROGRESS", meta={"attempt": attempt + 1, "suno_task_id": suno_task_id})
            try:
                audio_url = provider.poll(suno_task_id)
                if audio_url:
                    break
            except RuntimeError as e:
                logger.error(f"[music_tasks] Suno failed: {e}")
                svc.mark_failed(track_id)
                raise

        if not audio_url:
            logger.warning(f"[music_tasks] Suno timed out for track {track_id}")
            svc.mark_failed(track_id)
            return {"status": "failed", "track_id": track_id}

        # Download MP3
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        dest = MUSIC_DIR / f"{track_id}.mp3"
        resp = requests.get(audio_url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready(track_id, str(dest), duration)
        logger.info(f"[music_tasks] Suno track {track_id} ready: {dest}")
        return {"status": "ready", "track_id": track_id, "file_path": str(dest)}

    except Exception as exc:
        try:
            MusicService(db).mark_failed(track_id)
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="console.backend.tasks.music_tasks.generate_lyria_music_task", queue="render_q")
def generate_lyria_music_task(self, track_id: int):
    """Generate music via Lyria (synchronous API call), save to disk, update DB."""
    from console.backend.database import SessionLocal
    from console.backend.services.music_service import MusicService
    from pipeline.music_providers.lyria_provider import LyriaProvider, LYRIA_MODELS

    db = SessionLocal()
    try:
        svc = MusicService(db)
        track = svc.get_track(track_id)

        # provider is 'lyria-clip' or 'lyria-pro' — map to model string
        model_key = track["provider"]  # 'lyria-clip' or 'lyria-pro'
        model_name = LYRIA_MODELS.get(model_key, "lyria-3-clip-preview")

        provider = LyriaProvider()
        audio_bytes = provider.generate(
            prompt=track["generation_prompt"] or "",
            model=model_name,
            is_vocal=track["is_vocal"],
        )

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        dest = MUSIC_DIR / f"{track_id}.mp3"
        dest.write_bytes(audio_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready(track_id, str(dest), duration)
        logger.info(f"[music_tasks] Lyria track {track_id} ready: {dest} ({duration:.1f}s)")
        return {"status": "ready", "track_id": track_id, "file_path": str(dest)}

    except Exception as exc:
        try:
            MusicService(db).mark_failed(track_id)
        except Exception:
            pass
        raise
    finally:
        db.close()
```

- [ ] **Step 2: Register task module in `console/backend/celery_app.py`**

In `celery_app.py`, find the `include=[...]` list and add the music tasks entry:

```python
    include=[
        "console.backend.tasks.scraper_tasks",
        "console.backend.tasks.script_tasks",
        "console.backend.tasks.production_tasks",
        "console.backend.tasks.upload_tasks",
        "console.backend.tasks.token_refresh",
        "console.backend.tasks.music_tasks",   # ← add this line
    ],
```

Also add the task route in `task_routes`:

```python
        "console.backend.tasks.music_tasks.*": {"queue": "render_q"},
```

- [ ] **Step 3: Verify Celery can discover the tasks**

```bash
cd /path/to/ai-media-automation
python -c "
from console.backend.celery_app import celery_app
from console.backend.tasks import music_tasks
print('Suno task:', music_tasks.generate_suno_music_task.name)
print('Lyria task:', music_tasks.generate_lyria_music_task.name)
"
```

Expected:
```
Suno task: console.backend.tasks.music_tasks.generate_suno_music_task
Lyria task: console.backend.tasks.music_tasks.generate_lyria_music_task
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/tasks/music_tasks.py console/backend/celery_app.py
git commit -m "feat: add Suno and Lyria Celery tasks for music generation"
```

---

## Task 6: Music router + main.py registration + env.example

**Files:**
- Create: `console/backend/routers/music.py`
- Modify: `console/backend/main.py`
- Modify: `console/.env.example`

- [ ] **Step 1: Create `console/backend/routers/music.py`**

```python
"""Music library API — CRUD, generation, import, streaming."""
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.celery_app import celery_app
from console.backend.database import get_db
from console.backend.services.music_service import MusicService

router = APIRouter(prefix="/music", tags=["music"])

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class GenerateBody(BaseModel):
    idea: str
    niches: list[str] = []
    moods: list[str] = []
    genres: list[str] = []
    provider: str = "suno"         # suno | lyria-clip | lyria-pro
    is_vocal: bool = False
    title: str = ""
    expand_only: bool = False      # True = return expanded prompt only, no generation


class UpdateBody(BaseModel):
    title: str | None = None
    niches: list[str] | None = None
    moods: list[str] | None = None
    genres: list[str] | None = None
    is_vocal: bool | None = None
    is_favorite: bool | None = None
    volume: float | None = None
    quality_score: int | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_tracks(
    niche: str | None = None,
    mood: str | None = None,
    genre: str | None = None,
    is_vocal: bool | None = None,
    status: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return MusicService(db).list_tracks(niche=niche, mood=mood, genre=genre,
                                        is_vocal=is_vocal, status=status, search=search)


@router.post("/generate", status_code=201)
def generate_or_expand(
    body: GenerateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    svc = MusicService(db)

    # Always expand prompt first
    expanded = svc.expand_prompt_with_gemini(
        idea=body.idea,
        niches=body.niches,
        moods=body.moods,
        genres=body.genres,
        is_vocal=body.is_vocal,
    )

    if body.expand_only:
        return expanded

    title = body.title or body.idea[:60]
    track = svc.create_pending(
        title=title,
        niches=body.niches,
        moods=body.moods,
        genres=body.genres,
        is_vocal=body.is_vocal,
        volume=0.15,
        provider=body.provider,
        prompt=expanded["expanded_prompt"],
        negative_tags=expanded.get("negative_tags", ""),
    )
    track_id = track["id"]

    if body.provider == "suno":
        from console.backend.tasks.music_tasks import generate_suno_music_task
        celery_task = generate_suno_music_task.delay(track_id)
    else:
        from console.backend.tasks.music_tasks import generate_lyria_music_task
        celery_task = generate_lyria_music_task.delay(track_id)

    return {"task_id": celery_task.id, "track_id": track_id, "track": track}


@router.post("/upload", status_code=201)
async def upload_track(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {ALLOWED_AUDIO_EXTENSIONS}")

    try:
        meta = json.loads(metadata)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    file_bytes = await file.read()
    svc = MusicService(db)
    track = svc.import_track(
        file_bytes=file_bytes,
        extension=ext,
        title=meta.get("title", file.filename or "Untitled"),
        niches=meta.get("niches", []),
        moods=meta.get("moods", []),
        genres=meta.get("genres", []),
        is_vocal=meta.get("is_vocal", False),
        volume=float(meta.get("volume", 0.15)),
        quality_score=int(meta.get("quality_score", 80)),
    )
    return track


@router.get("/tasks/{task_id}")
def get_task_status(
    task_id: str,
    _user=Depends(require_editor_or_admin),
):
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "state":   result.state,
        "info":    result.info if isinstance(result.info, dict) else {},
    }


@router.get("/{track_id}")
def get_track(
    track_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return MusicService(db).get_track(track_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{track_id}/stream")
def stream_track(
    track_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        track = MusicService(db).get_track(track_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Track not found")

    path = Path(track["file_path"] or "")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    media_type = "audio/mpeg" if path.suffix in (".mp3", ".m4a") else "audio/wav"
    return FileResponse(str(path), media_type=media_type)


@router.put("/{track_id}")
def update_track(
    track_id: int,
    body: UpdateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    data = body.model_dump(exclude_none=True)
    try:
        return MusicService(db).update_track(track_id, data)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{track_id}", status_code=204)
def delete_track(
    track_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        MusicService(db).delete_track(track_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 2: Register the music router in `console/backend/main.py`**

In `main.py`, inside the `register_routers()` function, add after the `channels` try-block:

```python
    try:
        from console.backend.routers import music
        app.include_router(music.router, prefix="/api")
    except ImportError:
        pass
```

- [ ] **Step 3: Add `SUNO_API_KEY` to `console/.env.example`**

Append to `console/.env.example`:

```
# Suno API key for music generation (https://sunoapi.org)
SUNO_API_KEY=
```

- [ ] **Step 4: Smoke-test the router**

With the server running (`./console/start.sh` from project root), run:

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/music | python -m json.tool
```

Expected: `[]` (empty array — no tracks yet)

Also confirm the OpenAPI docs show the `/api/music` endpoints:
```bash
curl -s http://localhost:8080/docs | grep -c "music"
```

Expected: non-zero count.

- [ ] **Step 5: Commit**

```bash
git add console/backend/routers/music.py console/backend/main.py console/.env.example
git commit -m "feat: add music router with CRUD, generation, upload, streaming"
```

---

## Task 7: Composer integration

**Files:**
- Modify: `pipeline/composer.py`

- [ ] **Step 1: Locate the music section in `pipeline/composer.py`**

Lines 215–236 contain the `_select_music()` call and mixing logic. Lines 249–268 contain `_select_music()`. We will replace the call at line 216 with a DB lookup when `music_track_id` is set.

- [ ] **Step 2: Replace music selection logic in `compose_video()`**

In `pipeline/composer.py`, find the block that starts at line 36 where `script` is loaded from DB:

```python
    db = get_session()
    try:
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")
        script_json = script.script_json
    finally:
        db.close()
```

Replace with (adds `music_track_id` capture):

```python
    db = get_session()
    try:
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")
        script_json = script.script_json
        music_track_id = getattr(script, "music_track_id", None)
    finally:
        db.close()
```

- [ ] **Step 3: Replace `_select_music()` call in `compose_video()`**

Find lines 215–236:

```python
    # Mix background music (if available)
    music_track = _select_music(meta.get("mood", "uplifting"), meta.get("niche", "lifestyle"), final.duration)
    if music_track:
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
            music = AudioFileClip(music_track).with_volume_scaled(MUSIC_VOLUME)
```

Replace the entire music mixing block (lines 215–236) with:

```python
    # Mix background music (if available)
    _assigned_track = None
    _track_volume = MUSIC_VOLUME
    if music_track_id:
        try:
            from database.connection import get_session as _gs
            from database.models import MusicTrack
            _db2 = _gs()
            try:
                _t = _db2.query(MusicTrack).filter(MusicTrack.id == music_track_id, MusicTrack.generation_status == "ready").first()
                if _t and _t.file_path and Path(_t.file_path).exists():
                    _assigned_track = _t.file_path
                    _track_volume = float(_t.volume or MUSIC_VOLUME)
            finally:
                _db2.close()
        except Exception as _e:
            logger.warning(f"[Composer] Could not load assigned music track {music_track_id}: {_e}")

    music_track_path = _assigned_track or _select_music(meta.get("mood", "uplifting"), meta.get("niche", "lifestyle"), final.duration)
    if music_track_path:
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
            music = AudioFileClip(music_track_path).with_volume_scaled(_track_volume)
```

The rest of the looping logic (lines 221–234) remains unchanged.

After the music mixing block succeeds, increment usage count:

```python
            if final.audio:
                mixed = CompositeAudioClip([final.audio, music])
                final = final.with_audio(mixed)
            else:
                final = final.with_audio(music)

            # Increment usage count for DB-tracked tracks
            if music_track_id and _assigned_track:
                try:
                    from database.connection import get_session as _gs3
                    from database.models import MusicTrack
                    _db3 = _gs3()
                    try:
                        _mt = _db3.query(MusicTrack).filter(MusicTrack.id == music_track_id).first()
                        if _mt:
                            _mt.usage_count = (_mt.usage_count or 0) + 1
                            _db3.commit()
                    finally:
                        _db3.close()
                except Exception:
                    pass
```

- [ ] **Step 4: Verify the file still imports cleanly**

```bash
python -c "from pipeline.composer import compose_video; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pipeline/composer.py
git commit -m "feat: composer uses DB-assigned music track with per-track volume and usage tracking"
```

---

## Task 8: Script service auto-select music on draft creation

**Files:**
- Modify: `console/backend/services/script_service.py`

- [ ] **Step 1: Locate draft creation in `script_service.py`**

In `generate_script()`, find lines 210–226 where the `Script` row is created and committed:

```python
        row = Script(
            topic=topic,
            niche=niche,
            template=template,
            language=language,
            script_json=script_json,
            status="draft",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
```

- [ ] **Step 2: Add auto-select after commit**

Replace that block with:

```python
        row = Script(
            topic=topic,
            niche=niche,
            template=template,
            language=language,
            script_json=script_json,
            status="draft",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        # Auto-assign music track for the niche (best ready track, or none)
        try:
            from console.backend.services.music_service import MusicService
            track_id = MusicService(self.db).best_track_for_niche(niche or "")
            if track_id:
                row.music_track_id = track_id
                self.db.commit()
                self.db.refresh(row)
        except Exception:
            pass  # never block script creation
```

- [ ] **Step 3: Verify import works**

```bash
python -c "from console.backend.services.script_service import ScriptService; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/script_service.py
git commit -m "feat: auto-assign best music track on script draft creation"
```

---

## Task 9: Frontend — musicApi client

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Add `musicApi` to `console/frontend/src/api/client.js`**

Append after the `nichesApi` block:

```javascript
// ── Music ──────────────────────────────────────────────────────────────────────
export const musicApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== '')))
    return fetchApi(`/api/music?${q}`)
  },
  generate: (body) =>
    fetchApi('/api/music/generate', { method: 'POST', body: JSON.stringify(body) }),
  upload: (file, metadata) => {
    const form = new FormData()
    form.append('file', file)
    form.append('metadata', JSON.stringify(metadata))
    // fetchApi adds Content-Type: application/json which breaks multipart — use raw fetch
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/music/upload', { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
  get: (id) => fetchApi(`/api/music/${id}`),
  update: (id, body) =>
    fetchApi(`/api/music/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) =>
    fetchApi(`/api/music/${id}`, { method: 'DELETE' }),
  pollTask: (taskId) => fetchApi(`/api/music/tasks/${taskId}`),
  streamUrl: (id) => `/api/music/${id}/stream`,
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add musicApi client"
```

---

## Task 10: MusicPage — library table, edit modal, inline player + sidebar tab

**Files:**
- Create: `console/frontend/src/pages/MusicPage.jsx`
- Modify: `console/frontend/src/App.jsx`

- [ ] **Step 1: Create `console/frontend/src/pages/MusicPage.jsx`** (library + edit modal + player — no generate/import modals yet)

```jsx
import { useState, useRef, useEffect } from 'react'
import { musicApi, nichesApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Badge, Button, StatBox, Modal, Input, Select, Spinner, EmptyState, Toast } from '../components/index.jsx'

const MOODS   = ['uplifting', 'calm_focus', 'energetic', 'dramatic', 'neutral']
const GENRES  = ['pop', 'rock', 'electronic', 'jazz', 'classical', 'hip-hop', 'ambient', 'cinematic']

// ── Multi-select pill group ───────────────────────────────────────────────────
function MultiSelect({ label, options, value = [], onChange }) {
  const toggle = (opt) => onChange(value.includes(opt) ? value.filter(v => v !== opt) : [...value, opt])
  return (
    <div className="flex flex-col gap-1">
      {label && <label className="text-xs text-[#9090a8] font-medium">{label}</label>}
      <div className="flex flex-wrap gap-1.5">
        {options.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
              value.includes(opt)
                ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:border-[#7c6af7] hover:text-[#e8e8f0]'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Edit Track Modal ──────────────────────────────────────────────────────────
function EditModal({ track, niches, onClose, onSaved }) {
  const [form, setForm] = useState({
    title:         track.title,
    niches:        track.niches || [],
    moods:         track.moods || [],
    genres:        track.genres || [],
    is_vocal:      track.is_vocal,
    is_favorite:   track.is_favorite,
    volume:        track.volume ?? 0.15,
    quality_score: track.quality_score ?? 80,
  })
  const [saving, setSaving] = useState(false)
  const [toast,  setToast]  = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleSave = async () => {
    setSaving(true)
    try {
      await musicApi.update(track.id, form)
      onSaved()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={`Edit — ${track.title}`} width="max-w-xl"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={saving} onClick={handleSave}>Save</Button></>}
    >
      <div className="flex flex-col gap-4">
        <Input label="Title" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
        <MultiSelect label="Niches" options={niches.map(n => n.name)} value={form.niches} onChange={v => setForm(f => ({ ...f, niches: v }))} />
        <MultiSelect label="Moods"  options={MOODS}  value={form.moods}  onChange={v => setForm(f => ({ ...f, moods: v }))} />
        <MultiSelect label="Genres" options={GENRES} value={form.genres} onChange={v => setForm(f => ({ ...f, genres: v }))} />
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Volume ({(form.volume * 100).toFixed(0)}%)</label>
            <input type="range" min="0" max="1" step="0.01" value={form.volume}
              onChange={e => setForm(f => ({ ...f, volume: parseFloat(e.target.value) }))}
              className="accent-[#7c6af7]" />
          </div>
          <Input label="Quality Score (0–100)" type="number" value={form.quality_score}
            onChange={e => setForm(f => ({ ...f, quality_score: parseInt(e.target.value) || 0 }))} />
        </div>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
            <input type="checkbox" checked={form.is_vocal} onChange={e => setForm(f => ({ ...f, is_vocal: e.target.checked }))}
              className="accent-[#7c6af7]" />
            Vocal
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
            <input type="checkbox" checked={form.is_favorite} onChange={e => setForm(f => ({ ...f, is_favorite: e.target.checked }))}
              className="accent-[#7c6af7]" />
            Favorite ★
          </label>
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}

// ── Provider / Status badge colors ───────────────────────────────────────────
const PROVIDER_COLORS = {
  suno:        'bg-[#1a0e2e] text-[#7c6af7] border-[#2a1a50]',
  'lyria-clip':'bg-[#001624] text-[#4a9eff] border-[#002840]',
  'lyria-pro': 'bg-[#001e12] text-[#34d399] border-[#003020]',
  import:      'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]',
}
const STATUS_COLORS = {
  ready:   'bg-[#001e12] text-[#34d399] border-[#003020]',
  pending: 'bg-[#1e1a00] text-[#fbbf24] border-[#3a3000]',
  failed:  'bg-[#1e0a0a] text-[#f87171] border-[#3a1010]',
}

function ProviderBadge({ provider }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${PROVIDER_COLORS[provider] || PROVIDER_COLORS.import}`}>{(provider || 'import').toUpperCase()}</span>
}
function StatusBadge({ status }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${STATUS_COLORS[status] || STATUS_COLORS.pending}`}>{status}</span>
}

// ── Inline Audio Player ───────────────────────────────────────────────────────
function AudioPlayer({ track, onClose }) {
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    setPlaying(false)
    setProgress(0)
    if (audioRef.current) {
      audioRef.current.load()
      audioRef.current.play().catch(() => {})
      setPlaying(true)
    }
  }, [track?.id])

  const togglePlay = () => {
    if (!audioRef.current) return
    if (playing) { audioRef.current.pause(); setPlaying(false) }
    else { audioRef.current.play(); setPlaying(true) }
  }

  const handleTimeUpdate = () => {
    if (audioRef.current) setProgress((audioRef.current.currentTime / (audioRef.current.duration || 1)) * 100)
  }

  if (!track) return null
  return (
    <div className="fixed bottom-0 left-[200px] right-0 z-40 bg-[#16161a] border-t border-[#2a2a32] px-6 py-3 flex items-center gap-4">
      <audio ref={audioRef} src={musicApi.streamUrl(track.id)} onTimeUpdate={handleTimeUpdate} onEnded={() => setPlaying(false)} />
      <button onClick={togglePlay} className="w-8 h-8 rounded-full bg-[#7c6af7] text-white flex items-center justify-center text-sm hover:bg-[#6a58e5] transition-colors">
        {playing ? '⏸' : '▶'}
      </button>
      <div className="flex-1">
        <div className="text-sm font-medium text-[#e8e8f0] truncate">{track.title}</div>
        <div className="h-1 bg-[#2a2a32] rounded-full mt-1 overflow-hidden">
          <div className="h-full bg-[#7c6af7] rounded-full transition-all" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <span className="text-xs font-mono text-[#5a5a70]">{track.duration_s ? `${track.duration_s.toFixed(0)}s` : '—'}</span>
      <button onClick={onClose} className="text-[#9090a8] hover:text-[#f87171] transition-colors">✕</button>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function MusicPage() {
  const [filterNiche,  setFilterNiche]  = useState('')
  const [filterMood,   setFilterMood]   = useState('')
  const [filterGenre,  setFilterGenre]  = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterSearch, setFilterSearch] = useState('')
  const [editingTrack, setEditingTrack] = useState(null)
  const [playingTrack, setPlayingTrack] = useState(null)
  const [deletingId,   setDeletingId]   = useState(null)
  const [toast,        setToast]        = useState(null)
  const [pendingPolls, setPendingPolls] = useState({}) // trackId → celeryTaskId

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const { data: niches = [] } = useApi(() => nichesApi.list(), [])
  const { data: tracks = [], loading, refetch } = useApi(
    () => musicApi.list({ niche: filterNiche, mood: filterMood, genre: filterGenre, status: filterStatus, search: filterSearch }),
    [filterNiche, filterMood, filterGenre, filterStatus, filterSearch]
  )

  // Poll pending tracks every 10s
  useEffect(() => {
    const pending = tracks.filter(t => t.generation_status === 'pending' && pendingPolls[t.id])
    if (!pending.length) return
    const timer = setInterval(async () => {
      for (const t of pending) {
        try {
          const res = await musicApi.pollTask(pendingPolls[t.id])
          if (res.state === 'SUCCESS' || res.state === 'FAILURE') {
            refetch()
            setPendingPolls(p => { const n = { ...p }; delete n[t.id]; return n })
          }
        } catch { /* ignore */ }
      }
    }, 10000)
    return () => clearInterval(timer)
  }, [tracks, pendingPolls])

  const handleDelete = async (track) => {
    setDeletingId(track.id)
    try {
      await musicApi.delete(track.id)
      if (playingTrack?.id === track.id) setPlayingTrack(null)
      refetch()
      showToast(`Deleted "${track.title}"`)
    } catch (e) { showToast(e.message, 'error') }
    finally { setDeletingId(null) }
  }

  const handleFavoriteToggle = async (track) => {
    try {
      await musicApi.update(track.id, { is_favorite: !track.is_favorite })
      refetch()
    } catch (e) { showToast(e.message, 'error') }
  }

  // Stats
  const totalTracks  = tracks.length
  const sunoCount    = tracks.filter(t => t.provider === 'suno').length
  const lyriaCount   = tracks.filter(t => t.provider?.startsWith('lyria')).length
  const importCount  = tracks.filter(t => t.provider === 'import').length
  const favCount     = tracks.filter(t => t.is_favorite).length

  return (
    <div className="flex flex-col gap-5" style={{ paddingBottom: playingTrack ? 80 : 0 }}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">Music</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">Manage background music tracks for videos</p>
        </div>
        <div className="flex gap-2">
          <Button variant="default" onClick={() => {/* ImportModal - Task 12 */}}>↑ Import</Button>
          <Button variant="primary" onClick={() => {/* GenerateModal - Task 11 */}}>+ Generate</Button>
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total" value={totalTracks} />
        <StatBox label="Suno" value={sunoCount} />
        <StatBox label="Lyria" value={lyriaCount} />
        <StatBox label="Imported" value={importCount} />
        <StatBox label="Favorites" value={favCount} />
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <input value={filterSearch} onChange={e => setFilterSearch(e.target.value)} placeholder="Search title…"
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] w-48" />
        <select value={filterNiche} onChange={e => setFilterNiche(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All niches</option>
          {niches.map(n => <option key={n.id} value={n.name}>{n.name}</option>)}
        </select>
        <select value={filterMood} onChange={e => setFilterMood(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All moods</option>
          {MOODS.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={filterGenre} onChange={e => setFilterGenre(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All genres</option>
          {GENRES.map(g => <option key={g} value={g}>{g}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
          <option value="">All status</option>
          <option value="ready">Ready</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Library table */}
      <Card>
        {loading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : tracks.length === 0 ? (
          <EmptyState icon="🎵" title="No music tracks yet" description="Generate new tracks via Suno or Lyria, or import your own files." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#2a2a32] text-left">
                  {['Title', 'Provider', 'Status', 'Duration', 'Tags', 'Score', '★', 'Uses', ''].map(h => (
                    <th key={h} className="pb-2 pr-4 text-xs font-semibold text-[#9090a8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tracks.map(t => (
                  <tr key={t.id} className="border-b border-[#2a2a32] hover:bg-[#16161a] transition-colors">
                    <td className="py-2.5 pr-4">
                      <div className="font-medium text-[#e8e8f0] max-w-[180px] truncate">{t.title}</div>
                      <div className="text-xs text-[#5a5a70] font-mono">{t.is_vocal ? 'vocal' : 'instrumental'}</div>
                    </td>
                    <td className="py-2.5 pr-4"><ProviderBadge provider={t.provider} /></td>
                    <td className="py-2.5 pr-4"><StatusBadge status={t.generation_status} /></td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs whitespace-nowrap">
                      {t.duration_s ? `${t.duration_s.toFixed(0)}s` : '—'}
                    </td>
                    <td className="py-2.5 pr-4">
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {[...(t.niches || []), ...(t.genres || [])].slice(0, 4).map(tag => (
                          <span key={tag} className="text-[10px] bg-[#2a2a32] text-[#9090a8] rounded px-1.5 py-0.5">{tag}</span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">{t.quality_score}</td>
                    <td className="py-2.5 pr-4">
                      <button onClick={() => handleFavoriteToggle(t)}
                        className={`text-lg transition-colors ${t.is_favorite ? 'text-[#fbbf24]' : 'text-[#2a2a32] hover:text-[#fbbf24]'}`}>★</button>
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">{t.usage_count}</td>
                    <td className="py-2.5">
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm"
                          disabled={t.generation_status !== 'ready'}
                          onClick={() => setPlayingTrack(playingTrack?.id === t.id ? null : t)}>▶</Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditingTrack(t)}>✎</Button>
                        <Button variant="danger" size="sm" loading={deletingId === t.id} onClick={() => handleDelete(t)}>✕</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {editingTrack && (
        <EditModal track={editingTrack} niches={niches}
          onClose={() => setEditingTrack(null)} onSaved={refetch} />
      )}

      <AudioPlayer track={playingTrack} onClose={() => setPlayingTrack(null)} />
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
```

- [ ] **Step 2: Add Music tab to `console/frontend/src/App.jsx`**

Add the Music icon to the `Icons` object (after the `Niches` icon):

```jsx
  Music: () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
    </svg>
  ),
```

Add the Music tab to `ALL_TABS` after the `niches` entry:

```jsx
  { id: 'music', label: 'Music', Icon: Icons.Music, roles: ['admin', 'editor'] },
```

Add the import at the top of `App.jsx`:

```jsx
import MusicPage from './pages/MusicPage.jsx'
```

Add the case to `renderPage()`:

```jsx
      case 'music':      return <MusicPage />
```

- [ ] **Step 3: Start the dev server and verify the Music tab appears**

```bash
cd console/frontend && npm run dev
```

Open `http://localhost:5173`. Log in, confirm "Music" appears between "Niches" and "Composer" in the sidebar. Confirm the empty state shows.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/MusicPage.jsx console/frontend/src/App.jsx
git commit -m "feat: add MusicPage with library table, edit modal, inline player, and sidebar tab"
```

---

## Task 11: MusicPage — Generate modal

**Files:**
- Modify: `console/frontend/src/pages/MusicPage.jsx`

- [ ] **Step 1: Add `GenerateModal` component to `MusicPage.jsx`**

Insert the following component before the `export default function MusicPage()` line:

```jsx
// ── Generate Music Modal ──────────────────────────────────────────────────────
function GenerateModal({ niches, onClose, onGenerated, onPollTrack }) {
  const [idea,      setIdea]      = useState('')
  const [selNiches, setSelNiches] = useState([])
  const [selMoods,  setSelMoods]  = useState([])
  const [selGenres, setSelGenres] = useState([])
  const [provider,  setProvider]  = useState('suno')
  const [isVocal,   setIsVocal]   = useState(false)
  const [expanded,  setExpanded]  = useState('')
  const [expanding, setExpanding] = useState(false)
  const [generating,setGenerating]= useState(false)
  const [toast,     setToast]     = useState(null)
  const showToast = (msg, type='error') => { setToast({msg,type}); setTimeout(()=>setToast(null),3000) }

  const handleExpand = async () => {
    if (!idea.trim()) { showToast('Enter an idea first'); return }
    setExpanding(true)
    try {
      const res = await musicApi.generate({
        idea, niches: selNiches, moods: selMoods, genres: selGenres,
        provider, is_vocal: isVocal, expand_only: true,
      })
      setExpanded(res.expanded_prompt || idea)
    } catch (e) { showToast(e.message) }
    finally { setExpanding(false) }
  }

  const handleGenerate = async () => {
    if (!idea.trim() && !expanded.trim()) { showToast('Enter an idea or expand first'); return }
    setGenerating(true)
    try {
      const res = await musicApi.generate({
        idea: expanded || idea, niches: selNiches, moods: selMoods, genres: selGenres,
        provider, is_vocal: isVocal, expand_only: false,
      })
      onPollTrack(res.track_id, res.task_id)
      onGenerated()
      onClose()
    } catch (e) { showToast(e.message) }
    finally { setGenerating(false) }
  }

  return (
    <Modal open onClose={onClose} title="Generate Music" width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="default" loading={expanding} onClick={handleExpand}>✨ Expand with Gemini</Button>
          <Button variant="primary" loading={generating} onClick={handleGenerate}>Generate</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">General idea / description</label>
          <textarea
            value={expanded || idea}
            onChange={e => { expanded ? setExpanded(e.target.value) : setIdea(e.target.value) }}
            rows={3}
            placeholder="e.g. upbeat energetic workout music with punchy beats"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y"
          />
          {expanded && <p className="text-xs text-[#34d399]">✓ Expanded by Gemini — edit freely before generating</p>}
        </div>

        <MultiSelect label="Niches" options={niches.map(n => n.name)} value={selNiches} onChange={setSelNiches} />
        <MultiSelect label="Moods"  options={MOODS}  value={selMoods}  onChange={setSelMoods} />
        <MultiSelect label="Genres" options={GENRES} value={selGenres} onChange={setSelGenres} />

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Provider</label>
            <select value={provider} onChange={e => setProvider(e.target.value)}
              className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]">
              <option value="suno">Suno</option>
              <option value="lyria-clip">Lyria Clip (30s)</option>
              <option value="lyria-pro">Lyria Pro (full song)</option>
            </select>
          </div>
          <div className="flex flex-col justify-end">
            <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8] pb-1.5">
              <input type="checkbox" checked={isVocal} onChange={e => setIsVocal(e.target.checked)} className="accent-[#7c6af7]" />
              With vocals
            </label>
          </div>
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}
```

- [ ] **Step 2: Wire the Generate button and state in `MusicPage`**

In `MusicPage`, add state:
```jsx
  const [showGenerate, setShowGenerate] = useState(false)
```

Replace the `+ Generate` button placeholder:
```jsx
          <Button variant="primary" onClick={() => setShowGenerate(true)}>+ Generate</Button>
```

Add below `{editingTrack && ...}`:
```jsx
      {showGenerate && (
        <GenerateModal
          niches={niches}
          onClose={() => setShowGenerate(false)}
          onGenerated={refetch}
          onPollTrack={(trackId, taskId) => setPendingPolls(p => ({ ...p, [trackId]: taskId }))}
        />
      )}
```

- [ ] **Step 3: Test in browser**

Click "+ Generate", fill in an idea, click "✨ Expand with Gemini", verify the textarea updates with the expanded prompt. Click "Generate", verify a new pending row appears in the library table.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/MusicPage.jsx
git commit -m "feat: add Generate Music modal with Gemini expansion"
```

---

## Task 12: MusicPage — Import modal

**Files:**
- Modify: `console/frontend/src/pages/MusicPage.jsx`

- [ ] **Step 1: Add `ImportModal` component to `MusicPage.jsx`**

Insert before `export default function MusicPage()`:

```jsx
// ── Import Music Modal ────────────────────────────────────────────────────────
function ImportModal({ niches, onClose, onImported }) {
  const [file,         setFile]         = useState(null)
  const [detectedDur,  setDetectedDur]  = useState(null)
  const [title,        setTitle]        = useState('')
  const [selNiches,    setSelNiches]    = useState([])
  const [selMoods,     setSelMoods]     = useState([])
  const [selGenres,    setSelGenres]    = useState([])
  const [isVocal,      setIsVocal]      = useState(false)
  const [volume,       setVolume]       = useState(0.15)
  const [qualityScore, setQualityScore] = useState(80)
  const [uploading,    setUploading]    = useState(false)
  const [toast,        setToast]        = useState(null)
  const showToast = (msg, type='error') => { setToast({msg,type}); setTimeout(()=>setToast(null),3000) }

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    const baseName = f.name.replace(/\.[^.]+$/, '')
    setTitle(baseName)
    // Detect duration client-side
    const url = URL.createObjectURL(f)
    const audio = new Audio(url)
    audio.onloadedmetadata = () => { setDetectedDur(Math.round(audio.duration)); URL.revokeObjectURL(url) }
  }

  const handleImport = async () => {
    if (!file) { showToast('Choose a file first'); return }
    if (!title.trim()) { showToast('Title is required'); return }
    setUploading(true)
    try {
      await musicApi.upload(file, {
        title, niches: selNiches, moods: selMoods, genres: selGenres,
        is_vocal: isVocal, volume, quality_score: qualityScore,
      })
      onImported()
      onClose()
    } catch (e) { showToast(e.message) }
    finally { setUploading(false) }
  }

  return (
    <Modal open onClose={onClose} title="Import Music File" width="max-w-xl"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={uploading} onClick={handleImport}>Import</Button></>}
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Audio file (.mp3 / .wav / .m4a / .ogg)</label>
          <input type="file" accept=".mp3,.wav,.m4a,.ogg" onChange={handleFileChange}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border file:border-[#2a2a32] file:bg-[#222228] file:text-[#e8e8f0] file:text-xs hover:file:bg-[#2a2a32]" />
          {detectedDur !== null && <p className="text-xs text-[#34d399]">Detected duration: {detectedDur}s</p>}
        </div>

        <Input label="Title" value={title} onChange={e => setTitle(e.target.value)} placeholder="Track title" />
        <MultiSelect label="Niches" options={niches.map(n => n.name)} value={selNiches} onChange={setSelNiches} />
        <MultiSelect label="Moods"  options={MOODS}  value={selMoods}  onChange={setSelMoods} />
        <MultiSelect label="Genres" options={GENRES} value={selGenres} onChange={setSelGenres} />

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Volume ({(volume * 100).toFixed(0)}%)</label>
            <input type="range" min="0" max="1" step="0.01" value={volume}
              onChange={e => setVolume(parseFloat(e.target.value))} className="accent-[#7c6af7]" />
          </div>
          <Input label="Quality Score (0–100)" type="number" value={qualityScore}
            onChange={e => setQualityScore(parseInt(e.target.value) || 0)} />
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-sm text-[#9090a8]">
          <input type="checkbox" checked={isVocal} onChange={e => setIsVocal(e.target.checked)} className="accent-[#7c6af7]" />
          With vocals
        </label>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}
```

- [ ] **Step 2: Wire the Import button and state in `MusicPage`**

Add state:
```jsx
  const [showImport, setShowImport] = useState(false)
```

Replace the Import button placeholder:
```jsx
          <Button variant="default" onClick={() => setShowImport(true)}>↑ Import</Button>
```

Add below the GenerateModal:
```jsx
      {showImport && (
        <ImportModal
          niches={niches}
          onClose={() => setShowImport(false)}
          onImported={refetch}
        />
      )}
```

- [ ] **Step 3: Test in browser**

Click "↑ Import", pick an MP3/WAV file, verify the filename prefills the title and duration appears. Fill tags, click Import. Verify the track appears immediately with `status=ready`.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/MusicPage.jsx
git commit -m "feat: add Import Music modal with file upload and metadata form"
```

---

## Task 13: ScriptsPage — music picker in script editor

**Files:**
- Modify: `console/frontend/src/pages/ScriptsPage.jsx`

- [ ] **Step 1: Add `musicApi` import to `ScriptsPage.jsx`**

At the top of `ScriptsPage.jsx`, update the import line:

```jsx
import { scriptsApi, musicApi } from '../api/client.js'
```

- [ ] **Step 2: Add music track loading inside `ScriptEditorModal`**

Inside the `ScriptEditorModal` function, after the existing state declarations, add:

```jsx
  const scriptNiche = data?.script_json?.meta?.niche || data?.niche || ''
  const { data: musicTracks = [] } = useApi(
    () => musicApi.list({ status: 'ready', niche: scriptNiche }),
    [scriptNiche]
  )
```

- [ ] **Step 3: Replace the `music_mood` Select with the music picker in the "Video" section**

Find the existing Mood select in ScriptEditorModal:

```jsx
            <Select label="Mood"    value={video.music_mood || ''} onChange={e => setScriptField('video', 'music_mood', e.target.value)} placeholder="Default" options={MOODS.map(m => ({ value: m, label: m }))} />
```

Replace with two fields:

```jsx
            <div className="flex flex-col gap-1">
              <label className="text-xs text-[#9090a8] font-medium">Background Music</label>
              <select
                value={video.music_track_id || ''}
                onChange={e => setScriptField('video', 'music_track_id', e.target.value ? parseInt(e.target.value) : null)}
                className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
              >
                <option value="">None</option>
                {musicTracks.map(t => (
                  <option key={t.id} value={t.id}>
                    {t.title} · {t.duration_s ? `${t.duration_s.toFixed(0)}s` : '?'} · {(t.genres || []).join(', ')}
                  </option>
                ))}
              </select>
            </div>
            <Select label="Mood" value={video.music_mood || ''} onChange={e => setScriptField('video', 'music_mood', e.target.value)} placeholder="Default" options={MOODS.map(m => ({ value: m, label: m }))} />
```

- [ ] **Step 4: Test in browser**

Open Scripts, click edit on a script. In the Video section, verify the "Background Music" dropdown appears with available tracks filtered to the script's niche, plus "None". Select a track and save — confirm the save succeeds without errors.

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/ScriptsPage.jsx
git commit -m "feat: add music picker to script editor modal"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| `music_tracks` table with all columns | Task 1 |
| `music_track_id` FK on `generated_scripts` | Task 1 |
| Suno provider — submit + poll | Task 2 |
| Lyria provider — clip + pro via genai | Task 3 |
| MusicService — list, get, update, delete, import, expand, usage | Task 4 |
| Celery tasks — Suno polling loop, Lyria sync | Task 5 |
| celery_app includes music_tasks | Task 5 |
| REST API — all 8 endpoints | Task 6 |
| `expand_only=true` path in POST /generate | Task 6 |
| SUNO_API_KEY in .env.example | Task 6 |
| Composer uses DB track with per-track volume | Task 7 |
| Composer usage_count increment | Task 7 |
| Composer falls back to `_select_music()` when no track assigned | Task 7 |
| Script draft auto-selects best niche track | Task 8 |
| `musicApi` client with upload (multipart) | Task 9 |
| Music tab in sidebar between Niches and Composer | Task 10 |
| Library table with all columns | Task 10 |
| Edit modal (title, niches, moods, genres, vocal, favorite, volume, score) | Task 10 |
| Inline audio player with progress bar | Task 10 |
| Pending-track polling every 10s | Task 10 |
| Generate modal with Gemini expansion | Task 11 |
| Import modal with file picker + client-side duration detection | Task 12 |
| ScriptsPage music picker filtered by script niche | Task 13 |
| Mood field kept in script editor | Task 13 |

All spec requirements are covered. No gaps.
