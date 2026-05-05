# ElevenLabs Music Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ElevenLabs as a third music generation provider with a two-phase plan-preview flow in the Music tab, plus optional per-video auto-generation in the render pipeline.

**Architecture:** New `ElevenLabsProvider` class mirrors the existing Lyria/Suno provider pattern. Two new API endpoints handle plan preview and async audio generation. A new Celery task saves generated audio and updates the DB. The Music tab gets a dedicated ElevenLabs modal with prompt/JSON input and a plan editor.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLAlchemy, Alembic, Celery (render_q), elevenlabs SDK, React 18, Tailwind CSS

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pipeline/music_providers/elevenlabs_provider.py` | Create | Provider class: plan creation + audio composition |
| `tests/test_music_providers.py` | Modify | Add ElevenLabs provider tests |
| `database/models.py` | Modify | Add `composition_plan` JSONB column to `MusicTrack` |
| `console/backend/alembic/versions/017_music_track_composition_plan.py` | Create | DB migration |
| `console/backend/services/music_service.py` | Modify | Add `composition_plan` to serializer + `mark_ready_with_plan` |
| `console/backend/tasks/music_tasks.py` | Modify | Add `generate_elevenlabs_music_task` |
| `console/backend/routers/music.py` | Modify | Add `/elevenlabs/plan` + `/elevenlabs/compose` endpoints |
| `config/pipeline_config.yaml` | Modify | Add `auto_music_elevenlabs` config block |
| `console/backend/tasks/production_tasks.py` | Modify | Auto-generate ElevenLabs music before render if enabled |
| `console/frontend/src/api/client.js` | Modify | Add `elevenlabsPlan` + `elevenlabsCompose` to `musicApi` |
| `console/frontend/src/pages/MusicPage.jsx` | Modify | Add ElevenLabs button + modal with plan editor |

---

## Task 1: ElevenLabs Provider Class

**Files:**
- Create: `pipeline/music_providers/elevenlabs_provider.py`
- Modify: `tests/test_music_providers.py`

- [ ] **Step 1: Write failing tests**

Add to the bottom of `tests/test_music_providers.py`:

```python
# ── ElevenLabs provider tests ─────────────────────────────────────────────────

_ELEVENLABS_FAKE_CFG = {**_FAKE_CFG, "elevenlabs": {"api_key": "test-el-key"}}


@pytest.fixture
def _fake_el_keys():
    with patch("pipeline.music_providers.elevenlabs_provider.get_config", return_value=_ELEVENLABS_FAKE_CFG):
        yield


def test_elevenlabs_create_plan_returns_json_plan_as_is(_fake_el_keys):
    """If input is valid composition plan JSON, return it without calling the API."""
    plan = {
        "positive_global_styles": ["upbeat pop"],
        "negative_global_styles": ["dark"],
        "sections": [{"section_name": "Intro", "duration_ms": 8000, "lines": []}],
    }
    from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider
    with patch("pipeline.music_providers.elevenlabs_provider.ElevenLabs"):
        provider = ElevenLabsProvider()
        result = provider.create_plan(json.dumps(plan), 60000)
    assert result == plan


def test_elevenlabs_create_plan_calls_api_for_text_prompt(_fake_el_keys):
    """If input is a text prompt, call composition_plan.create and return the result."""
    expected_plan = {"positive_global_styles": ["calm"], "sections": []}

    mock_plan = MagicMock()
    mock_plan.model_dump.return_value = expected_plan

    with patch("pipeline.music_providers.elevenlabs_provider.ElevenLabs") as MockEL:
        mock_client = MockEL.return_value
        mock_client.music.composition_plan.create.return_value = mock_plan

        from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider
        provider = ElevenLabsProvider()
        result = provider.create_plan("calm ambient music", 60000)

    mock_client.music.composition_plan.create.assert_called_once_with(
        prompt="calm ambient music",
        music_length_ms=60000,
    )
    assert result == expected_plan


def test_elevenlabs_compose_returns_bytes(_fake_el_keys):
    """compose() returns the raw audio bytes from the SDK."""
    fake_audio = b"FAKE_AUDIO_DATA"

    with patch("pipeline.music_providers.elevenlabs_provider.ElevenLabs") as MockEL:
        mock_client = MockEL.return_value
        mock_client.music.compose.return_value = fake_audio

        from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider
        provider = ElevenLabsProvider()
        plan = {"sections": [], "positive_global_styles": ["pop"]}
        result = provider.compose(plan, output_format="mp3_44100_192")

    mock_client.music.compose.assert_called_once_with(
        composition_plan=plan,
        respect_sections_durations=True,
        output_format="mp3_44100_192",
    )
    assert result == fake_audio


def test_elevenlabs_ext_for_format():
    from pipeline.music_providers.elevenlabs_provider import _ext_for_format
    assert _ext_for_format("mp3_44100_192") == ".mp3"
    assert _ext_for_format("pcm_44100") == ".wav"
    assert _ext_for_format("opus_48000_192") == ".opus"
    assert _ext_for_format("ulaw_8000") == ".wav"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_music_providers.py::test_elevenlabs_create_plan_returns_json_plan_as_is tests/test_music_providers.py::test_elevenlabs_create_plan_calls_api_for_text_prompt tests/test_music_providers.py::test_elevenlabs_compose_returns_bytes tests/test_music_providers.py::test_elevenlabs_ext_for_format -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.music_providers.elevenlabs_provider'`

- [ ] **Step 3: Create the provider**

Create `pipeline/music_providers/elevenlabs_provider.py`:

```python
"""ElevenLabs music generation provider — composition plan + compose."""
import json

from config.api_config import get_config

try:
    from elevenlabs.client import ElevenLabs
except ImportError:
    ElevenLabs = None

_FORMAT_TO_EXT = {
    "mp3":  ".mp3",
    "pcm":  ".wav",
    "opus": ".opus",
    "ulaw": ".wav",
    "alaw": ".wav",
}


def _ext_for_format(output_format: str) -> str:
    """Return file extension for a given output_format string (e.g. 'mp3_44100_192' → '.mp3')."""
    prefix = output_format.split("_")[0]
    return _FORMAT_TO_EXT.get(prefix, ".mp3")


class ElevenLabsProvider:
    def __init__(self):
        self._key = get_config()["elevenlabs"]["api_key"]
        if not self._key:
            raise RuntimeError("ElevenLabs API key is not configured in config/api_keys.json")
        if ElevenLabs is None:
            raise RuntimeError("elevenlabs not installed. Run: pip install elevenlabs")

    def create_plan(self, input_text: str, music_length_ms: int = 60000) -> dict:
        """
        Return a composition plan dict.
        If input_text is valid composition plan JSON (has 'sections' or
        'positive_global_styles'), return it as-is without calling the API.
        Otherwise call ElevenLabs to generate a plan from the text prompt.
        """
        try:
            parsed = json.loads(input_text)
            if isinstance(parsed, dict) and (
                "sections" in parsed or "positive_global_styles" in parsed
            ):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        client = ElevenLabs(api_key=self._key)
        plan = client.music.composition_plan.create(
            prompt=input_text,
            music_length_ms=music_length_ms,
        )
        if hasattr(plan, "model_dump"):
            return plan.model_dump()
        return dict(plan)

    def compose(
        self,
        plan: dict,
        output_format: str = "mp3_44100_192",
        respect_sections_durations: bool = True,
    ) -> bytes:
        """Generate audio from a composition plan. Returns raw audio bytes."""
        client = ElevenLabs(api_key=self._key)
        audio = client.music.compose(
            composition_plan=plan,
            respect_sections_durations=respect_sections_durations,
            output_format=output_format,
        )
        if isinstance(audio, bytes):
            return audio
        return b"".join(audio)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_music_providers.py::test_elevenlabs_create_plan_returns_json_plan_as_is tests/test_music_providers.py::test_elevenlabs_create_plan_calls_api_for_text_prompt tests/test_music_providers.py::test_elevenlabs_compose_returns_bytes tests/test_music_providers.py::test_elevenlabs_ext_for_format -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add pipeline/music_providers/elevenlabs_provider.py tests/test_music_providers.py
git commit -m "feat: add ElevenLabsProvider for music generation"
```

---

## Task 2: DB Migration + Model Update

**Files:**
- Create: `console/backend/alembic/versions/017_music_track_composition_plan.py`
- Modify: `database/models.py` (add `composition_plan` column to `MusicTrack`)

- [ ] **Step 1: Add column to MusicTrack model**

In `database/models.py`, find the `MusicTrack` class. After `generation_prompt = Column(Text)`, add:

```python
    composition_plan  = Column(JSONB, nullable=True)
```

The full block of the MusicTrack class columns should look like:
```python
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
    provider          = Column(String(20))
    provider_task_id  = Column(String(200))
    generation_status = Column(String(20), default="pending")
    generation_prompt = Column(Text)
    composition_plan  = Column(JSONB, nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Create migration file**

Create `console/backend/alembic/versions/017_music_track_composition_plan.py`:

```python
"""Add composition_plan column to music_tracks

Revision ID: 017
Revises: 016
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "music_tracks",
        sa.Column(
            "composition_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("music_tracks", "composition_plan")
```

- [ ] **Step 3: Run migration**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic upgrade head
```

Expected output ends with: `Running upgrade 016 -> 017, Add composition_plan column to music_tracks`

- [ ] **Step 4: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add database/models.py console/backend/alembic/versions/017_music_track_composition_plan.py
git commit -m "feat: add composition_plan column to music_tracks"
```

---

## Task 3: MusicService — Serializer + mark_ready_with_plan

**Files:**
- Modify: `console/backend/services/music_service.py`

- [ ] **Step 1: Update `_track_to_dict` to include `composition_plan`**

In `console/backend/services/music_service.py`, find the `_track_to_dict` function. Add `"composition_plan"` to the returned dict, after `"generation_prompt"`:

```python
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
        "composition_plan": t.composition_plan,
        "created_at":       t.created_at.isoformat() if t.created_at else None,
    }
```

- [ ] **Step 2: Add `mark_ready_with_plan` method**

In `MusicService`, after the existing `mark_failed` method, add:

```python
    def mark_ready_with_plan(
        self, track_id: int, file_path: str, duration_s: float, composition_plan: dict
    ) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.file_path = file_path
            t.duration_s = duration_s
            t.composition_plan = composition_plan
            t.generation_status = "ready"
            self.db.commit()
```

- [ ] **Step 3: Verify the service still imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -c "from console.backend.services.music_service import MusicService; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/music_service.py
git commit -m "feat: add composition_plan to MusicService serializer and mark_ready_with_plan"
```

---

## Task 4: Celery Task — generate_elevenlabs_music_task

**Files:**
- Modify: `console/backend/tasks/music_tasks.py`

- [ ] **Step 1: Add the task**

At the bottom of `console/backend/tasks/music_tasks.py`, add:

```python
@celery_app.task(
    bind=True,
    name="console.backend.tasks.music_tasks.generate_elevenlabs_music_task",
    queue="render_q",
)
def generate_elevenlabs_music_task(
    self,
    track_id: int,
    composition_plan: dict,
    output_format: str = "mp3_44100_192",
    respect_sections_durations: bool = True,
):
    """Generate music via ElevenLabs compose API, save to disk, update DB."""
    from console.backend.database import SessionLocal
    from console.backend.services.music_service import MusicService
    from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider, _ext_for_format

    db = SessionLocal()
    try:
        svc = MusicService(db)
        provider = ElevenLabsProvider()

        audio_bytes = provider.compose(
            plan=composition_plan,
            output_format=output_format,
            respect_sections_durations=respect_sections_durations,
        )

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        ext = _ext_for_format(output_format)
        dest = MUSIC_DIR / f"{track_id}{ext}"
        dest.write_bytes(audio_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready_with_plan(track_id, str(dest), duration, composition_plan)
        logger.info(f"[music_tasks] ElevenLabs track {track_id} ready: {dest} ({duration:.1f}s)")
        return {"status": "ready", "track_id": track_id, "file_path": str(dest)}

    except Exception:
        try:
            MusicService(db).mark_failed(track_id)
        except Exception:
            pass
        raise
    finally:
        db.close()
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -c "from console.backend.tasks.music_tasks import generate_elevenlabs_music_task; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add console/backend/tasks/music_tasks.py
git commit -m "feat: add generate_elevenlabs_music_task Celery task"
```

---

## Task 5: Backend Endpoints — /elevenlabs/plan and /elevenlabs/compose

**Files:**
- Modify: `console/backend/routers/music.py`

- [ ] **Step 1: Add Pydantic schemas**

In `console/backend/routers/music.py`, after the existing `UpdateBody` class, add:

```python
class ElevenLabsPlanBody(BaseModel):
    input: str
    music_length_ms: int = 60000


class ElevenLabsComposeBody(BaseModel):
    composition_plan: dict
    title: str = ""
    niches: list[str] = []
    moods: list[str] = []
    genres: list[str] = []
    output_format: str = "mp3_44100_192"
    respect_sections_durations: bool = True
```

- [ ] **Step 2: Add the two endpoints**

Add before the `@router.get("/{track_id}")` endpoint (to avoid the catch-all swallowing these routes):

```python
@router.post("/elevenlabs/plan")
def elevenlabs_preview_plan(
    body: ElevenLabsPlanBody,
    _user=Depends(require_editor_or_admin),
):
    """Generate or parse a composition plan. Returns plan JSON for editor preview."""
    from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider
    try:
        provider = ElevenLabsProvider()
        plan = provider.create_plan(body.input, body.music_length_ms)
        return {"composition_plan": plan}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/elevenlabs/compose", status_code=201)
def elevenlabs_compose(
    body: ElevenLabsComposeBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Create MusicTrack row and dispatch ElevenLabs audio generation task."""
    import json as _json

    svc = MusicService(db)
    title = body.title or "ElevenLabs Track"
    track = svc.create_pending(
        title=title,
        niches=body.niches,
        moods=body.moods,
        genres=body.genres,
        is_vocal=False,
        volume=0.15,
        provider="elevenlabs",
        prompt=_json.dumps(body.composition_plan),
    )
    track_id = track["id"]

    from console.backend.tasks.music_tasks import generate_elevenlabs_music_task
    celery_task = generate_elevenlabs_music_task.delay(
        track_id,
        body.composition_plan,
        body.output_format,
        body.respect_sections_durations,
    )
    return {"task_id": celery_task.id, "track_id": track_id}
```

- [ ] **Step 3: Verify FastAPI app imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -c "from console.backend.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/music.py
git commit -m "feat: add /music/elevenlabs/plan and /music/elevenlabs/compose endpoints"
```

---

## Task 6: Per-Video Auto-Generation Config + Render Task Hook

**Files:**
- Modify: `config/pipeline_config.yaml`
- Modify: `console/backend/tasks/production_tasks.py`

- [ ] **Step 1: Add config to pipeline_config.yaml**

In `config/pipeline_config.yaml`, find the `production:` section. Add three new lines after `music_volume: 0.08`:

```yaml
production:
  target_width: 1080
  target_height: 1920
  target_fps: 30
  render_workers: 2
  music_volume: 0.08
  auto_music_elevenlabs: false
  auto_music_elevenlabs_format: mp3_44100_192
  auto_music_elevenlabs_length_ms: 0   # 0 = derive from video duration * 1000
```

- [ ] **Step 2: Add auto-music helper function to production_tasks.py**

In `console/backend/tasks/production_tasks.py`, after the existing imports, add a module-level helper:

```python
def _auto_generate_elevenlabs_music(db, script_id: int, niche: str, mood: str, duration_s: float) -> None:
    """If auto_music_elevenlabs is enabled and no library track exists, generate one."""
    import os
    import yaml
    from pathlib import Path
    from sqlalchemy import text

    cfg_path = Path(__file__).parents[4] / "config" / "pipeline_config.yaml"
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
    except Exception:
        return

    prod_cfg = cfg.get("production", {})
    if not prod_cfg.get("auto_music_elevenlabs", False):
        return

    output_format = prod_cfg.get("auto_music_elevenlabs_format", "mp3_44100_192")
    length_ms = prod_cfg.get("auto_music_elevenlabs_length_ms", 0) or int((duration_s or 60) * 1000)

    from console.backend.services.music_service import MusicService
    svc = MusicService(db)
    existing = svc.list_tracks(niche=niche, mood=mood, status="ready")
    if existing:
        track_id = existing[0]["id"]
        db.execute(
            text("UPDATE generated_scripts SET music_track_id = :tid WHERE id = :sid"),
            {"tid": track_id, "sid": script_id},
        )
        db.commit()
        return

    prompt = f"{mood or 'uplifting'} background music for a {niche or 'lifestyle'} video, {int(duration_s or 60)}s, instrumental"
    try:
        from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider, _ext_for_format
        provider = ElevenLabsProvider()
        plan = provider.create_plan(prompt, length_ms)
        audio_bytes = provider.compose(plan, output_format)

        MUSIC_DIR = Path(os.environ.get("MUSIC_PATH", "./assets/music"))
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)

        track = svc.create_pending(
            title=f"{niche or 'auto'} {mood or 'uplifting'} auto-generated",
            niches=[niche] if niche else [],
            moods=[mood] if mood else [],
            genres=[],
            is_vocal=False,
            volume=0.15,
            provider="elevenlabs",
            prompt=prompt,
        )
        track_id = track["id"]
        ext = _ext_for_format(output_format)
        dest = MUSIC_DIR / f"{track_id}{ext}"
        dest.write_bytes(audio_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready_with_plan(track_id, str(dest), duration, plan)

        db.execute(
            text("UPDATE generated_scripts SET music_track_id = :tid WHERE id = :sid"),
            {"tid": track_id, "sid": script_id},
        )
        db.commit()
        logger.info(f"[render] Auto-generated ElevenLabs track {track_id} for script {script_id}")
    except Exception as e:
        logger.warning(f"[render] Auto ElevenLabs music failed for script {script_id}: {e}")
```

- [ ] **Step 3: Call auto-music helper inside render_video_task**

In `render_video_task`, after loading the `script` object and before the `# Step 1: Compose` comment, add:

```python
        # Auto-generate ElevenLabs music if configured and no track assigned
        meta = (script.script_json or {}).get("meta", {})
        if not script.music_track_id:
            _auto_generate_elevenlabs_music(
                db=db,
                script_id=script_id,
                niche=meta.get("niche", ""),
                mood=meta.get("mood", "uplifting"),
                duration_s=meta.get("duration_s", 60.0),
            )
            db.refresh(script)
```

The insertion point is after this existing block:
```python
        script.status = "producing"
        db.commit()

        # Step 1: Compose
```

So it becomes:
```python
        script.status = "producing"
        db.commit()

        # Auto-generate ElevenLabs music if configured and no track assigned
        meta = (script.script_json or {}).get("meta", {})
        if not script.music_track_id:
            _auto_generate_elevenlabs_music(
                db=db,
                script_id=script_id,
                niche=meta.get("niche", ""),
                mood=meta.get("mood", "uplifting"),
                duration_s=meta.get("duration_s", 60.0),
            )
            db.refresh(script)

        # Step 1: Compose
```

- [ ] **Step 4: Verify the task module imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -c "from console.backend.tasks.production_tasks import render_video_task; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add config/pipeline_config.yaml console/backend/tasks/production_tasks.py
git commit -m "feat: auto-generate ElevenLabs music in render pipeline when enabled"
```

---

## Task 7: Frontend API Client

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Add ElevenLabs methods to musicApi**

In `console/frontend/src/api/client.js`, find the `musicApi` object. After the `listTemplates` line, add two new methods:

```js
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
  listTemplates: () => fetchApi('/api/music/templates'),
  elevenlabsPlan: (input, music_length_ms = 60000) =>
    fetchApi('/api/music/elevenlabs/plan', {
      method: 'POST',
      body: JSON.stringify({ input, music_length_ms }),
    }),
  elevenlabsCompose: (body) =>
    fetchApi('/api/music/elevenlabs/compose', { method: 'POST', body: JSON.stringify(body) }),
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add elevenlabsPlan and elevenlabsCompose to musicApi"
```

---

## Task 8: Frontend — ElevenLabs Modal + Music Tab Button

**Files:**
- Modify: `console/frontend/src/pages/MusicPage.jsx`

- [ ] **Step 1: Add ElevenLabs badge color to PROVIDER_COLORS**

Find `const PROVIDER_COLORS = {` in `MusicPage.jsx`. Add an entry for `elevenlabs`:

```js
const PROVIDER_COLORS = {
  sunoapi:      'bg-[#1a0e2e] text-[#7c6af7] border-[#2a1a50]',
  suno:         'bg-[#1e0a3e] text-[#a78bfa] border-[#3d1a70]',
  'lyria-clip': 'bg-[#001624] text-[#4a9eff] border-[#002840]',
  'lyria-pro':  'bg-[#001e12] text-[#34d399] border-[#003020]',
  elevenlabs:   'bg-[#1a1000] text-[#fbbf24] border-[#3a2800]',
  import:       'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]',
}
```

- [ ] **Step 2: Add the ElevenLabsModal component**

Add this new component before the `// ── MusicPage ──` line (or before the main page export):

```jsx
// ── ElevenLabs Modal ─────────────────────────────────────────────────────────
const OUTPUT_FORMATS = [
  { value: 'mp3_44100_192', label: 'MP3 44.1kHz 192kbps (default)' },
  { value: 'pcm_44100',     label: 'PCM 44.1kHz WAV (lossless)' },
  { value: 'opus_48000_192',label: 'Opus 48kHz 192kbps' },
]

function ElevenLabsModal({ niches, onClose, onGenerated, onPollTrack }) {
  const [input,        setInput]        = useState('')
  const [lengthMs,     setLengthMs]     = useState(60000)
  const [outputFormat, setOutputFormat] = useState('mp3_44100_192')
  const [selNiches,    setSelNiches]    = useState([])
  const [selMoods,     setSelMoods]     = useState([])
  const [title,        setTitle]        = useState('')
  const [planJson,     setPlanJson]     = useState('')
  const [showPlanEditor, setShowPlanEditor] = useState(false)
  const [previewing,   setPreviewing]   = useState(false)
  const [generating,   setGenerating]   = useState(false)
  const [toast,        setToast]        = useState(null)
  const showToast = (msg, type = 'error') => { setToast({ msg, type }); setTimeout(() => setToast(null), 4000) }

  // Detect if input looks like a composition plan JSON
  const isJsonPlan = (() => {
    try {
      const p = JSON.parse(input.trim())
      return typeof p === 'object' && p !== null && ('sections' in p || 'positive_global_styles' in p)
    } catch { return false }
  })()

  const handlePreviewPlan = async () => {
    if (!input.trim()) { showToast('Enter a prompt or paste a composition plan JSON'); return }
    setPreviewing(true)
    try {
      const res = await musicApi.elevenlabsPlan(input.trim(), isJsonPlan ? undefined : lengthMs)
      setPlanJson(JSON.stringify(res.composition_plan, null, 2))
      setShowPlanEditor(true)
    } catch (e) { showToast(e.message) }
    finally { setPreviewing(false) }
  }

  const handleGenerateDirect = async () => {
    if (!input.trim()) { showToast('Enter a prompt or paste a composition plan JSON'); return }
    setGenerating(true)
    try {
      let plan
      if (isJsonPlan) {
        plan = JSON.parse(input.trim())
      } else {
        const res = await musicApi.elevenlabsPlan(input.trim(), lengthMs)
        plan = res.composition_plan
      }
      await _submitCompose(plan)
    } catch (e) { showToast(e.message) }
    finally { setGenerating(false) }
  }

  const handleGenerateFromEditor = async () => {
    let plan
    try {
      plan = JSON.parse(planJson)
    } catch {
      showToast('Invalid JSON in plan editor — fix syntax before generating', 'error')
      return
    }
    setGenerating(true)
    try {
      await _submitCompose(plan)
    } catch (e) { showToast(e.message) }
    finally { setGenerating(false) }
  }

  const _submitCompose = async (plan) => {
    const res = await musicApi.elevenlabsCompose({
      composition_plan: plan,
      title: title || 'ElevenLabs Track',
      niches: selNiches,
      moods: selMoods,
      output_format: outputFormat,
    })
    onPollTrack(res.track_id, res.task_id)
    onGenerated()
    onClose()
  }

  if (showPlanEditor) {
    return (
      <Modal open onClose={() => setShowPlanEditor(false)} title="Edit Composition Plan" width="max-w-2xl"
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowPlanEditor(false)}>Back</Button>
            <Button variant="primary" loading={generating} onClick={handleGenerateFromEditor}>Generate Audio</Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <p className="text-xs text-[#9090a8]">Review and edit the composition plan JSON before generating. Changes here affect the final audio.</p>
          <textarea
            value={planJson}
            onChange={e => setPlanJson(e.target.value)}
            rows={28}
            spellCheck={false}
            className="w-full bg-[#0d0d0f] border border-[#2a2a32] rounded-lg px-3 py-2 text-xs font-mono text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] resize-y leading-relaxed"
          />
        </div>
      </Modal>
    )
  }

  return (
    <Modal open onClose={onClose} title="Generate with ElevenLabs" width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="default" loading={previewing} onClick={handlePreviewPlan}>Preview Plan</Button>
          <Button variant="primary" loading={generating} onClick={handleGenerateDirect}>Generate Direct</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <label className="text-xs text-[#9090a8] font-medium">Prompt or Composition Plan JSON</label>
            <span className={`text-xs font-mono px-2 py-0.5 rounded border ${
              isJsonPlan
                ? 'bg-[#001e12] text-[#34d399] border-[#003020]'
                : 'bg-[#16161a] text-[#9090a8] border-[#2a2a32]'
            }`}>
              {isJsonPlan ? 'JSON plan' : 'text prompt'}
            </span>
          </div>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            rows={6}
            placeholder={'e.g. "uplifting background music for a fitness video, 90s, instrumental"\n\nor paste a full composition plan JSON'}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-2 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y font-mono"
          />
        </div>

        {!isJsonPlan && (
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Duration (ms)</label>
            <input
              type="number" min={3000} max={600000} step={1000}
              value={lengthMs}
              onChange={e => setLengthMs(parseInt(e.target.value) || 60000)}
              className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] w-40"
            />
            <p className="text-xs text-[#5a5a70]">{(lengthMs / 1000).toFixed(0)}s</p>
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Output Format</label>
          <select
            value={outputFormat}
            onChange={e => setOutputFormat(e.target.value)}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
          >
            {OUTPUT_FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </div>

        <Input label="Title" value={title} onChange={e => setTitle(e.target.value)} placeholder="Track title (optional)" />
        <MultiSelect label="Niches" options={niches.map(n => n.name)} value={selNiches} onChange={setSelNiches} />
        <MultiSelect label="Moods"  options={MOODS} value={selMoods} onChange={setSelMoods} />
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}
```

- [ ] **Step 3: Add state and button in the main MusicPage component**

In the main `MusicPage` (or `MusicLibraryPage`) component, add state for the ElevenLabs modal alongside the existing modal state:

Find this block:
```jsx
  const [showImport,   setShowImport]   = useState(false)
  const [showGenerate, setShowGenerate] = useState(false)
```

Add below it:
```jsx
  const [showElevenLabs, setShowElevenLabs] = useState(false)
```

- [ ] **Step 4: Add the ElevenLabs button in the action bar**

Find the action bar buttons block:
```jsx
        <div className="flex gap-2">
          <Button variant="default" onClick={() => setShowImport(true)}>↑ Import</Button>
          <Button variant="primary" onClick={() => setShowGenerate(true)}>+ Generate</Button>
        </div>
```

Replace with:
```jsx
        <div className="flex gap-2">
          <Button variant="default" onClick={() => setShowImport(true)}>↑ Import</Button>
          <Button variant="default" onClick={() => setShowElevenLabs(true)}>♪ ElevenLabs</Button>
          <Button variant="primary" onClick={() => setShowGenerate(true)}>+ Generate</Button>
        </div>
```

- [ ] **Step 5: Render the ElevenLabsModal**

Find where `ImportModal` and `GenerateModal` are rendered (near the bottom of the return statement). Add `ElevenLabsModal` alongside them:

```jsx
      {showElevenLabs && (
        <ElevenLabsModal
          niches={niches}
          onClose={() => setShowElevenLabs(false)}
          onGenerated={refetch}
          onPollTrack={(trackId, taskId) => setPendingPolls(p => ({ ...p, [trackId]: taskId }))}
        />
      )}
```

- [ ] **Step 6: Update elCount stat (optional, follow existing pattern)**

Find the stats block:
```jsx
  const sunoCount    = trackList.filter(t => t.provider === 'sunoapi').length
  const lyriaCount   = trackList.filter(t => t.provider?.startsWith('lyria')).length
  const importCount  = trackList.filter(t => t.provider === 'import').length
```

Add:
```jsx
  const elCount      = trackList.filter(t => t.provider === 'elevenlabs').length
```

And add a `<StatBox label="ElevenLabs" value={elCount} />` in the stats row alongside the existing ones.

- [ ] **Step 7: Start dev server and smoke-test the feature**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run dev
```

Open `http://localhost:5173` → navigate to Music tab → click "♪ ElevenLabs".

Verify:
- Modal opens with textarea + detect badge showing `text prompt`
- Pasting the example composition plan JSON from the spec switches badge to `JSON plan` and disables the Duration field
- "Preview Plan" button is visible (no API call needed to verify UI)
- "Generate Direct" button is visible
- Plan editor shows a 28-row monospace textarea when opened

- [ ] **Step 8: Commit**

```bash
git add console/frontend/src/pages/MusicPage.jsx console/frontend/src/api/client.js
git commit -m "feat: add ElevenLabs music generation modal to Music tab"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Provider class with plan creation + compose ✓ (Task 1)
  - DB migration + JSONB column ✓ (Task 2)
  - `mark_ready_with_plan` for storing composition plan ✓ (Task 3)
  - Celery task saving audio + updating DB ✓ (Task 4)
  - `/elevenlabs/plan` and `/elevenlabs/compose` endpoints ✓ (Task 5)
  - `auto_music_elevenlabs` config + render task hook ✓ (Task 6)
  - Frontend API client methods ✓ (Task 7)
  - ElevenLabs modal with detect badge, plan editor, Generate Direct ✓ (Task 8)
  - `PROVIDER_COLORS` entry for `elevenlabs` ✓ (Task 8 Step 1)
  - Output format → file extension mapping ✓ (`_ext_for_format` in Task 1)

- [x] **No placeholders** — all steps have complete code

- [x] **Type consistency:**
  - `ElevenLabsProvider.create_plan(input_text, music_length_ms)` matches usage in Task 4 (`generate_elevenlabs_music_task`) and Task 6 (`_auto_generate_elevenlabs_music`) ✓
  - `ElevenLabsProvider.compose(plan, output_format, respect_sections_durations)` called consistently ✓
  - `MusicService.mark_ready_with_plan(track_id, file_path, duration_s, composition_plan)` called the same way in Tasks 4 and 6 ✓
  - `musicApi.elevenlabsPlan(input, music_length_ms)` and `musicApi.elevenlabsCompose(body)` match Task 8 usage ✓
  - `_ext_for_format` imported from the same module in Tasks 4 and 6 ✓
