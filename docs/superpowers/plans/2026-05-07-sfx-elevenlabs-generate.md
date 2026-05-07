# SFX ElevenLabs Generate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Generate SFX" button and modal to the SFX Library page that calls the ElevenLabs `text_to_sound_effects.convert()` API and saves the result into the existing SFX library.

**Architecture:** Thin synchronous endpoint `POST /api/sfx/generate` in the existing `sfx.py` router calls ElevenLabs inline and delegates file persistence to the existing `SfxService.import_sfx()`. A new `is_loopable` boolean column on `sfx_assets` stores whether the sound was generated with `loop=True`. The frontend adds a `GenerateSFXModal` alongside the existing `ImportModal` in `SFXPage.jsx`.

**Tech Stack:** Python `elevenlabs` SDK, FastAPI, SQLAlchemy/Alembic (PostgreSQL), React 18, `fetchApi` wrapper in `client.js`.

---

## File Map

| File | Change |
|---|---|
| `console/backend/models/sfx_asset.py` | Add `is_loopable: bool` column |
| `console/backend/alembic/versions/020_sfx_is_loopable.py` | Create — add column migration |
| `console/backend/services/sfx_service.py` | Update `_sfx_to_dict` + `import_sfx` signature |
| `console/backend/routers/sfx.py` | Add `GenerateBody` + `POST /generate` endpoint |
| `console/frontend/src/api/client.js` | Add `sfxApi.generate()` |
| `console/frontend/src/pages/SFXPage.jsx` | Add `GenerateSFXModal` + "Generate SFX" button |
| `tests/test_sfx_service.py` | Add `is_loopable` tests |
| `tests/test_sfx_generate_endpoint.py` | Create — router-level tests with mocked ElevenLabs |

---

## Task 1: Add `is_loopable` to model, migration, and service

**Files:**
- Modify: `console/backend/models/sfx_asset.py`
- Create: `console/backend/alembic/versions/020_sfx_is_loopable.py`
- Modify: `console/backend/services/sfx_service.py`
- Test: `tests/test_sfx_service.py`

- [ ] **Step 1: Write two failing tests**

Append to `tests/test_sfx_service.py`:

```python
def test_import_sfx_is_loopable_true(db, tmp_path):
    svc = SfxService(db)
    fake = b"ID3" + b"\x00" * 40
    track = svc.import_sfx(
        title="Loop Campfire",
        sound_type=None,
        source="elevenlabs",
        file_bytes=fake,
        filename="sfx.mp3",
        is_loopable=True,
        sfx_dir=tmp_path,
    )
    assert track["is_loopable"] is True


def test_import_sfx_is_loopable_defaults_false(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    track = svc.import_sfx(
        title="Rain",
        sound_type="rain_heavy",
        source="import",
        file_bytes=fake,
        filename="r.wav",
        sfx_dir=tmp_path,
    )
    assert track["is_loopable"] is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_sfx_service.py::test_import_sfx_is_loopable_true tests/test_sfx_service.py::test_import_sfx_is_loopable_defaults_false -v
```

Expected: FAIL — `import_sfx()` does not accept `is_loopable` and dict has no `is_loopable` key.

- [ ] **Step 3: Add `is_loopable` to `SfxAsset` model**

Replace the full content of `console/backend/models/sfx_asset.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class SfxAsset(Base):
    __tablename__ = "sfx_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="import", server_default="import")
    sound_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_loopable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 4: Create Alembic migration**

Create `console/backend/alembic/versions/020_sfx_is_loopable.py`:

```python
"""add is_loopable to sfx_assets

Revision ID: 020
Revises: 019
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sfx_assets",
        sa.Column("is_loopable", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("sfx_assets", "is_loopable")
```

- [ ] **Step 5: Run the migration**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic upgrade head
```

Expected: `Running upgrade 019 -> 020, add is_loopable to sfx_assets`

- [ ] **Step 6: Update `_sfx_to_dict` and `import_sfx` in service**

Replace the full content of `console/backend/services/sfx_service.py`:

```python
import os
from pathlib import Path

from sqlalchemy.orm import Session

SFX_DIR = Path(os.environ.get("SFX_PATH", "./assets/sfx"))


def _sfx_to_dict(s) -> dict:
    return {
        "id":          s.id,
        "title":       s.title,
        "file_path":   s.file_path,
        "source":      s.source,
        "sound_type":  s.sound_type,
        "duration_s":  s.duration_s,
        "usage_count": s.usage_count,
        "is_loopable": s.is_loopable,
        "created_at":  s.created_at.isoformat() if s.created_at else None,
    }


class SfxService:
    def __init__(self, db: Session):
        self.db = db

    def _model(self):
        from console.backend.models.sfx_asset import SfxAsset
        return SfxAsset

    def list_sfx(self, sound_type: str | None = None, search: str | None = None) -> list[dict]:
        SfxAsset = self._model()
        q = self.db.query(SfxAsset)
        if sound_type:
            q = q.filter(SfxAsset.sound_type == sound_type)
        if search:
            q = q.filter(SfxAsset.title.ilike(f"%{search}%"))
        return [_sfx_to_dict(s) for s in q.order_by(SfxAsset.created_at.desc()).all()]

    def list_sound_types(self) -> list[str]:
        SfxAsset = self._model()
        rows = (
            self.db.query(SfxAsset.sound_type)
            .distinct()
            .filter(SfxAsset.sound_type.isnot(None))
            .all()
        )
        return sorted([r[0] for r in rows])

    def import_sfx(
        self,
        title: str,
        sound_type: str | None,
        source: str,
        file_bytes: bytes,
        filename: str,
        is_loopable: bool = False,
        sfx_dir: Path | None = None,
    ) -> dict:
        SfxAsset = self._model()
        sfx_dir = sfx_dir or SFX_DIR
        sfx_dir.mkdir(parents=True, exist_ok=True)

        row = SfxAsset(
            title=title,
            sound_type=sound_type,
            source=source,
            file_path="",
            is_loopable=is_loopable,
        )
        self.db.add(row)
        self.db.flush()

        ext = Path(filename).suffix or ".wav"
        dest = sfx_dir / f"sfx_{row.id}{ext}"
        dest.write_bytes(file_bytes)
        row.file_path = str(dest)
        self.db.commit()
        self.db.refresh(row)
        return _sfx_to_dict(row)

    def delete_sfx(self, sfx_id: int) -> None:
        SfxAsset = self._model()
        row = self.db.get(SfxAsset, sfx_id)
        if not row:
            raise KeyError(f"SFX {sfx_id} not found")
        path = Path(row.file_path)
        self.db.delete(row)
        self.db.commit()
        if path.exists():
            path.unlink(missing_ok=True)
```

- [ ] **Step 7: Run the full sfx service test suite**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_sfx_service.py -v
```

Expected: all 7 tests PASS (5 existing + 2 new).

- [ ] **Step 8: Commit**

```bash
git add console/backend/models/sfx_asset.py \
        console/backend/alembic/versions/020_sfx_is_loopable.py \
        console/backend/services/sfx_service.py \
        tests/test_sfx_service.py
git commit -m "feat: add is_loopable column to sfx_assets"
```

---

## Task 2: Add `POST /api/sfx/generate` endpoint

**Files:**
- Modify: `console/backend/routers/sfx.py`
- Create: `tests/test_sfx_generate_endpoint.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sfx_generate_endpoint.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

_FAKE_CFG = {"elevenlabs": {"api_key": "test-el-key"}}
_FAKE_AUDIO = b"ID3" + b"\x00" * 100


def _make_client(db_session):
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.routers.sfx import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_editor_or_admin] = lambda: {"id": 1, "role": "admin"}
    return TestClient(app)


def test_generate_sfx_success(db, tmp_path):
    mock_instance = MagicMock()
    mock_instance.text_to_sound_effects.convert.return_value = iter([_FAKE_AUDIO])
    mock_class = MagicMock(return_value=mock_instance)

    with patch("console.backend.routers.sfx.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.routers.sfx.ElevenLabs", mock_class), \
         patch("console.backend.services.sfx_service.SFX_DIR", tmp_path):
        client = _make_client(db)
        resp = client.post("/api/generate", json={
            "text": "Crackling campfire with gentle wind",
            "loop": True,
            "duration_seconds": 10.0,
            "title": "Campfire Loop",
        })

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Campfire Loop"
    assert data["source"] == "elevenlabs"
    assert data["is_loopable"] is True
    mock_instance.text_to_sound_effects.convert.assert_called_once_with(
        text="Crackling campfire with gentle wind",
        loop=True,
        duration_seconds=10.0,
    )


def test_generate_sfx_auto_title_from_prompt(db, tmp_path):
    mock_instance = MagicMock()
    mock_instance.text_to_sound_effects.convert.return_value = iter([_FAKE_AUDIO])
    mock_class = MagicMock(return_value=mock_instance)

    with patch("console.backend.routers.sfx.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.routers.sfx.ElevenLabs", mock_class), \
         patch("console.backend.services.sfx_service.SFX_DIR", tmp_path):
        client = _make_client(db)
        resp = client.post("/api/generate", json={
            "text": "A very long prompt that exceeds sixty characters and should be truncated properly",
            "loop": False,
        })

    assert resp.status_code == 201
    assert len(resp.json()["title"]) <= 60


def test_generate_sfx_missing_api_key_returns_503(db):
    with patch("console.backend.routers.sfx.get_config", return_value={"elevenlabs": {"api_key": ""}}):
        client = _make_client(db)
        resp = client.post("/api/generate", json={"text": "rain"})
    assert resp.status_code == 503


def test_generate_sfx_elevenlabs_error_returns_502(db, tmp_path):
    mock_instance = MagicMock()
    mock_instance.text_to_sound_effects.convert.side_effect = RuntimeError("quota exceeded")
    mock_class = MagicMock(return_value=mock_instance)

    with patch("console.backend.routers.sfx.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.routers.sfx.ElevenLabs", mock_class):
        client = _make_client(db)
        resp = client.post("/api/generate", json={"text": "thunder"})

    assert resp.status_code == 502
    assert "quota exceeded" in resp.json()["detail"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_sfx_generate_endpoint.py -v
```

Expected: FAIL — `POST /api/generate` does not exist yet.

- [ ] **Step 3: Add `GenerateBody` and `generate_sfx_elevenlabs` to the router**

Replace the full content of `console/backend/routers/sfx.py`:

```python
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.api_config import get_config
from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.sfx_service import SfxService

try:
    from elevenlabs import ElevenLabs
except ImportError:
    ElevenLabs = None

router = APIRouter(prefix="/sfx", tags=["sfx"])

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}
MEDIA_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


class GenerateBody(BaseModel):
    text: str
    loop: bool = False
    duration_seconds: float | None = None
    title: str = ""


@router.get("")
def list_sfx(
    sound_type: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return SfxService(db).list_sfx(sound_type=sound_type, search=search)


@router.get("/sound-types")
def list_sound_types(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return SfxService(db).list_sound_types()


@router.post("/generate", status_code=201)
def generate_sfx_elevenlabs(
    body: GenerateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    if ElevenLabs is None:
        raise HTTPException(status_code=503, detail="elevenlabs package is not installed")

    try:
        key = get_config().get("elevenlabs", {}).get("api_key", "")
    except Exception:
        key = ""
    if not key:
        raise HTTPException(status_code=503, detail="ElevenLabs API key is not configured")

    try:
        client = ElevenLabs(api_key=key)
        kwargs: dict = {"text": body.text, "loop": body.loop}
        if body.duration_seconds is not None:
            kwargs["duration_seconds"] = body.duration_seconds
        audio_bytes = b"".join(client.text_to_sound_effects.convert(**kwargs))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {e}")

    title = body.title.strip() or body.text[:60]
    return SfxService(db).import_sfx(
        title=title,
        sound_type=None,
        source="elevenlabs",
        file_bytes=audio_bytes,
        filename="sfx.mp3",
        is_loopable=body.loop,
    )


@router.post("/import", status_code=201)
async def import_sfx(
    file: UploadFile = File(...),
    title: str = Form(...),
    sound_type: str = Form(...),
    source: str = Form(default="import"),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
    return SfxService(db).import_sfx(
        title=title,
        sound_type=sound_type,
        source=source,
        file_bytes=content,
        filename=file.filename or "sfx.wav",
    )


@router.delete("/{sfx_id}", status_code=204)
def delete_sfx(
    sfx_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        SfxService(db).delete_sfx(sfx_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{sfx_id}/stream")
def stream_sfx(sfx_id: int, db: Session = Depends(get_db)):
    """Stream SFX audio — no auth required so browser <audio> tags can load it directly."""
    from console.backend.models.sfx_asset import SfxAsset
    row = db.get(SfxAsset, sfx_id)
    if not row:
        raise HTTPException(status_code=404, detail="SFX not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    ext = path.suffix.lower()
    media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(str(path), media_type=media_type)
```

- [ ] **Step 4: Run endpoint tests**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_sfx_generate_endpoint.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add console/backend/routers/sfx.py tests/test_sfx_generate_endpoint.py
git commit -m "feat: add POST /api/sfx/generate endpoint using ElevenLabs text-to-sound-effects"
```

---

## Task 3: Add `sfxApi.generate()` to the frontend API client

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Add `generate` method to `sfxApi`**

In `console/frontend/src/api/client.js`, find this block (around line 213):

```js
  delete: (id) =>
    fetchApi(`/api/sfx/${id}`, { method: 'DELETE' }),
  streamUrl: (id) => `/api/sfx/${id}/stream`,
```

Replace it with:

```js
  delete: (id) =>
    fetchApi(`/api/sfx/${id}`, { method: 'DELETE' }),
  generate: (body) =>
    fetchApi('/api/sfx/generate', { method: 'POST', body: JSON.stringify(body) }),
  streamUrl: (id) => `/api/sfx/${id}/stream`,
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add sfxApi.generate() to frontend API client"
```

---

## Task 4: Add `GenerateSFXModal` and button to `SFXPage.jsx`

**Files:**
- Modify: `console/frontend/src/pages/SFXPage.jsx`

- [ ] **Step 1: Add `GenerateSFXModal` component**

In `console/frontend/src/pages/SFXPage.jsx`, insert the `GenerateSFXModal` component immediately after the closing `}` of `ImportModal` (before `export default function SFXPage()`):

```jsx
function GenerateSFXModal({ onClose, onGenerated }) {
  const [prompt, setPrompt] = useState('')
  const [title, setTitle] = useState('')
  const [titleTouched, setTitleTouched] = useState(false)
  const [loop, setLoop] = useState(false)
  const [duration, setDuration] = useState('')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const handlePromptChange = (e) => {
    const val = e.target.value
    setPrompt(val)
    if (!titleTouched) setTitle(val.slice(0, 60))
  }

  const handleTitleChange = (e) => {
    setTitle(e.target.value)
    setTitleTouched(true)
  }

  const handleSubmit = async () => {
    if (!prompt.trim()) {
      showToast('Prompt is required')
      return
    }
    setLoading(true)
    try {
      const body = {
        text: prompt.trim(),
        loop,
        title: title.trim(),
        duration_seconds: duration !== '' ? parseFloat(duration) : undefined,
      }
      await sfxApi.generate(body)
      onGenerated()
      onClose()
    } catch (e) {
      showToast(e.message || 'Generation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Generate SFX"
      width="max-w-lg"
      footer={<>
        <div className="flex-1" />
        <Button variant="ghost" onClick={onClose} disabled={loading}>Cancel</Button>
        <Button variant="primary" loading={loading} onClick={handleSubmit}>Generate</Button>
      </>}
    >
      {toast && <Toast message={toast.msg} type={toast.type} />}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Prompt <span className="text-[#f87171]">*</span></label>
          <textarea
            value={prompt}
            onChange={handlePromptChange}
            rows={3}
            placeholder="Crackling campfire with gentle wind and distant crickets"
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] resize-none focus:outline-none focus:border-[#7c6af7]"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Title <span className="text-[#5a5a70]">(optional)</span></label>
          <input
            value={title}
            onChange={handleTitleChange}
            placeholder="Auto-filled from prompt"
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
          />
        </div>
        <div className="flex gap-4 items-end">
          <div className="flex flex-col gap-1 flex-1">
            <label className="text-xs text-[#9090a8] font-medium">Duration (seconds) <span className="text-[#5a5a70]">(optional, 0.5–22)</span></label>
            <input
              type="number"
              min="0.5"
              max="22"
              step="0.5"
              value={duration}
              onChange={e => setDuration(e.target.value)}
              placeholder="Let ElevenLabs decide"
              className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
            />
          </div>
          <label className="flex items-center gap-2 pb-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={loop}
              onChange={e => setLoop(e.target.checked)}
              className="w-4 h-4 rounded accent-[#7c6af7]"
            />
            <span className="text-sm text-[#e8e8f0]">Loop</span>
          </label>
        </div>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 2: Add `showGenerate` state and "Generate SFX" button to `SFXPage`**

In `SFXPage`, find this line (around line 138):

```jsx
  const [showImport, setShowImport] = useState(false)
```

Replace with:

```jsx
  const [showImport, setShowImport] = useState(false)
  const [showGenerate, setShowGenerate] = useState(false)
```

- [ ] **Step 3: Add the "Generate SFX" button to the header**

Find this line in `SFXPage`:

```jsx
        <Button variant="primary" onClick={() => setShowImport(true)}>+ Import SFX</Button>
```

Replace with:

```jsx
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setShowGenerate(true)}>✨ Generate SFX</Button>
          <Button variant="primary" onClick={() => setShowImport(true)}>+ Import SFX</Button>
        </div>
```

- [ ] **Step 4: Render `GenerateSFXModal` at the bottom of `SFXPage`**

Find this line at the bottom of the `SFXPage` return:

```jsx
      {showImport && <ImportModal onClose={() => setShowImport(false)} onImported={load} />}
```

Replace with:

```jsx
      {showImport && <ImportModal onClose={() => setShowImport(false)} onImported={load} />}
      {showGenerate && <GenerateSFXModal onClose={() => setShowGenerate(false)} onGenerated={load} />}
```

- [ ] **Step 5: Start dev server and verify in browser**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run dev
```

Open `http://localhost:5173` and navigate to the SFX page. Verify:
- "✨ Generate SFX" button appears next to "+ Import SFX"
- Clicking it opens the modal with Prompt (textarea), Title (input), Duration (number), Loop (checkbox)
- Typing in Prompt auto-fills Title (truncated to 60 chars)
- Manually editing Title stops the auto-fill
- Clicking Cancel closes the modal without errors
- Submitting with empty prompt shows an error toast

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/SFXPage.jsx
git commit -m "feat: add GenerateSFXModal with ElevenLabs SFX generation to SFX Library page"
```

---

## Spec Coverage Check

| Spec requirement | Task covering it |
|---|---|
| `is_loopable` column on `sfx_assets` | Task 1 |
| Alembic migration 020 | Task 1 |
| `import_sfx` accepts `is_loopable` param | Task 1 |
| `_sfx_to_dict` returns `is_loopable` | Task 1 |
| `POST /api/sfx/generate` endpoint | Task 2 |
| `GenerateBody`: text, loop, duration_seconds, title | Task 2 |
| 503 on missing API key | Task 2 |
| 502 on ElevenLabs error | Task 2 |
| Auto-title from `text[:60]` if title is empty | Task 2 |
| `source="elevenlabs"` on generated rows | Task 2 |
| `sfxApi.generate()` in client.js | Task 3 |
| `GenerateSFXModal` with 4 inputs | Task 4 |
| Title auto-fills from prompt, stops on manual edit | Task 4 |
| "Generate SFX" button in SFXPage header | Task 4 |
| Grid refreshes after successful generation | Task 4 |
