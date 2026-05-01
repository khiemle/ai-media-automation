# AI Import Autofill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an AI autofill button to the Music, SFX, and Video/Image Asset import modals that sends file metadata + current form values to Gemini and overwrites all form fields with the suggestions.

**Architecture:** A single `POST /api/llm/autofill` endpoint in the existing `routers/llm.py` receives `{ modal_type, metadata, form_values }`, calls `AutofillPromptBuilder.build()` to construct a modal-specific prompt, passes it to the existing `GeminiRouter`, and validates the response with `AutofillResponseParser`. Frontend modals gain an AI button (disabled until file selected) that calls `autofillApi.suggest()` and applies the result.

**Tech Stack:** FastAPI, Pydantic v2, `rag.llm_router.GeminiRouter` (existing), React 18 + hooks, `api/client.js` fetchApi (existing)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `console/backend/services/llm_service.py` | Add `AutofillPromptBuilder`, `AutofillResponseParser`, 3 response Pydantic schemas |
| Modify | `console/backend/routers/llm.py` | Add `_AutofillRequest` schema + `POST /autofill` endpoint |
| Create | `tests/test_llm_autofill.py` | Unit tests for builder, parser, and endpoint |
| Modify | `console/frontend/src/api/client.js` | Add `autofillApi.suggest()` |
| Modify | `console/frontend/src/pages/MusicPage.jsx` | AI button + `handleAutofill` in `ImportModal` |
| Modify | `console/frontend/src/pages/SFXPage.jsx` | AI button + `handleAutofill` in `ImportModal` |
| Modify | `console/frontend/src/pages/VideoAssetsPage.jsx` | AI button + `handleAutofill` in `ImportAssetModal` |

---

## Task 1: Autofill Service Classes (Builder + Parser + Schemas)

**Files:**
- Modify: `console/backend/services/llm_service.py`
- Create: `tests/test_llm_autofill.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm_autofill.py`:

```python
import pytest
from console.backend.services.llm_service import (
    AutofillPromptBuilder,
    AutofillResponseParser,
)


# ── AutofillPromptBuilder ─────────────────────────────────────────────────────

def test_build_music_includes_filename_and_duration():
    prompt = AutofillPromptBuilder().build(
        "music",
        {"filename": "chill-lofi.mp3", "file_size_bytes": 1_000_000, "mime_type": "audio/mpeg", "duration_s": 142.3},
        {},
    )
    assert "chill-lofi.mp3" in prompt
    assert "142.3" in prompt


def test_build_music_with_form_values_includes_hints():
    prompt = AutofillPromptBuilder().build(
        "music",
        {"filename": "track.mp3", "file_size_bytes": 500_000, "mime_type": "audio/mpeg", "duration_s": None},
        {"title": "My Draft Title"},
    )
    assert "My Draft Title" in prompt


def test_build_sfx_includes_filename():
    prompt = AutofillPromptBuilder().build(
        "sfx",
        {"filename": "rain_heavy.wav", "file_size_bytes": 500_000, "mime_type": "audio/wav", "duration_s": None},
        {},
    )
    assert "rain_heavy.wav" in prompt


def test_build_asset_image_includes_image_type():
    prompt = AutofillPromptBuilder().build(
        "asset",
        {"filename": "forest_sunset.jpg", "file_size_bytes": 200_000, "mime_type": "image/jpeg", "duration_s": None},
        {},
    )
    assert "forest_sunset.jpg" in prompt
    assert "image" in prompt.lower()


def test_build_asset_video_includes_video_type():
    prompt = AutofillPromptBuilder().build(
        "asset",
        {"filename": "aerial_city.mp4", "file_size_bytes": 5_000_000, "mime_type": "video/mp4", "duration_s": None},
        {},
    )
    assert "video" in prompt.lower()


def test_build_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown modal_type"):
        AutofillPromptBuilder().build(
            "unknown",
            {"filename": "x", "file_size_bytes": 0, "mime_type": "x", "duration_s": None},
            {},
        )


# ── AutofillResponseParser ────────────────────────────────────────────────────

def test_parse_music_full_response():
    result = AutofillResponseParser().parse("music", {
        "title": "Chill Lo-Fi",
        "niches": ["study", "sleep"],
        "moods": ["calm_focus"],
        "genres": ["ambient", "hip-hop"],
        "volume": 0.15,
        "quality_score": 80,
        "is_vocal": False,
    })
    assert result["title"] == "Chill Lo-Fi"
    assert result["moods"] == ["calm_focus"]
    assert result["is_vocal"] is False


def test_parse_music_partial_response_nulls_missing_fields():
    result = AutofillResponseParser().parse("music", {"title": "Track Only"})
    assert result["title"] == "Track Only"
    assert result["moods"] is None
    assert result["niches"] is None


def test_parse_sfx_valid():
    result = AutofillResponseParser().parse("sfx", {"title": "Heavy Rain", "sound_type": "rain_heavy"})
    assert result["title"] == "Heavy Rain"
    assert result["sound_type"] == "rain_heavy"


def test_parse_asset_valid():
    result = AutofillResponseParser().parse("asset", {
        "description": "Aerial forest shot",
        "keywords": ["forest", "aerial", "nature"],
        "source": "manual",
    })
    assert result["description"] == "Aerial forest shot"
    assert result["keywords"] == ["forest", "aerial", "nature"]


def test_parse_malformed_json_string_returns_empty():
    result = AutofillResponseParser().parse("music", "not json at all {{}")
    assert result == {}


def test_parse_unknown_modal_type_returns_empty():
    result = AutofillResponseParser().parse("unknown", {"title": "x"})
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /path/to/ai-media-automation
pytest tests/test_llm_autofill.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — `AutofillPromptBuilder` and `AutofillResponseParser` don't exist yet.

- [ ] **Step 3: Add prompt templates and service classes to `llm_service.py`**

Append the following to the end of `console/backend/services/llm_service.py` (after the last method of `LLMService`):

```python
# ── Autofill helpers ───────────────────────────────────────────────────────────

from typing import Any, Optional
from pydantic import BaseModel

# ── Response schemas (all fields optional — missing = None, not defaulted) ───

class _MusicAutofill(BaseModel):
    title: Optional[str] = None
    niches: Optional[list[str]] = None
    moods: Optional[list[str]] = None
    genres: Optional[list[str]] = None
    volume: Optional[float] = None
    quality_score: Optional[int] = None
    is_vocal: Optional[bool] = None


class _SFXAutofill(BaseModel):
    title: Optional[str] = None
    sound_type: Optional[str] = None


class _AssetAutofill(BaseModel):
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    source: Optional[str] = None


# ── Prompt templates ─────────────────────────────────────────────────────────

_MUSIC_PROMPT = """\
You are a music metadata assistant. Given information about an audio file, suggest appropriate metadata.

File information:
- Filename: {filename}
- File size: {file_size_bytes} bytes
- MIME type: {mime_type}
- Duration: {duration}

User's current input (treat as strong hints):
{form_section}

Return ONLY valid JSON — no prose, no markdown fences:
{{
  "title": "descriptive track title",
  "niches": [],
  "moods": [],
  "genres": [],
  "volume": 0.15,
  "quality_score": 80,
  "is_vocal": false
}}

Allowed moods (only pick from this list): uplifting, calm_focus, energetic, dramatic, neutral
Allowed genres (only pick from this list): pop, rock, electronic, jazz, classical, hip-hop, ambient, cinematic

Rules:
- Use filename and any user hints to infer title, moods, genres, and niches
- Niches are free-form strings (e.g. study, sleep, fitness, gaming, meditation, relaxation)
- Keep volume at 0.15 and quality_score at 80 unless the filename strongly implies otherwise
- Set is_vocal to true only if the filename contains words like vocal, voice, singer, lyrics, acapella
"""

_SFX_PROMPT = """\
You are a sound effects metadata assistant. Given information about a sound file, suggest metadata.

File information:
- Filename: {filename}
- File size: {file_size_bytes} bytes
- MIME type: {mime_type}

User's current input (treat as strong hints):
{form_section}

Return ONLY valid JSON — no prose, no markdown fences:
{{
  "title": "descriptive sound title",
  "sound_type": "category_type"
}}

Known sound types: rain_heavy, rain_light, rain_drizzle, thunder, thunder_rumble,
stream, ocean_waves, river, waterfall, fire_crackle, fire_roar,
forest_ambience, birds, birds_morning, wind_light, wind_heavy,
city_ambience, traffic, crowd_murmur, cafe_ambience, keyboard_typing,
pink_noise, white_noise, brown_noise, lfo_pulse

Rules:
- Use the filename as the primary signal for both title and sound_type
- Pick the closest match from the known list; if none fits, create a descriptive snake_case type
"""

_ASSET_PROMPT = """\
You are a media asset metadata assistant. Given information about a media file, suggest metadata.

File information:
- Filename: {filename}
- File size: {file_size_bytes} bytes
- MIME type: {mime_type}
- Asset type: {asset_type}

User's current input (treat as strong hints):
{form_section}

Return ONLY valid JSON — no prose, no markdown fences:
{{
  "description": "brief description of what the asset likely shows",
  "keywords": ["keyword1", "keyword2"],
  "source": "manual"
}}

Allowed sources: manual, midjourney, runway, pexels, veo, stock

Rules:
- Infer description and keywords from the filename
- Use 3–7 concise keywords
- Only suggest a non-"manual" source if the filename clearly contains midjourney, pexels, veo, or runway
"""


class AutofillPromptBuilder:
    def build(self, modal_type: str, metadata: dict[str, Any], form_values: dict[str, Any]) -> str:
        form_section = "\n".join(
            f"- {k}: {v}" for k, v in form_values.items() if v not in (None, "", [], {})
        ) or "(none yet)"

        if modal_type == "music":
            dur = f"{metadata['duration_s']}s" if metadata.get("duration_s") else "unknown"
            return _MUSIC_PROMPT.format(
                filename=metadata["filename"],
                file_size_bytes=metadata["file_size_bytes"],
                mime_type=metadata["mime_type"],
                duration=dur,
                form_section=form_section,
            )
        if modal_type == "sfx":
            return _SFX_PROMPT.format(
                filename=metadata["filename"],
                file_size_bytes=metadata["file_size_bytes"],
                mime_type=metadata["mime_type"],
                form_section=form_section,
            )
        if modal_type == "asset":
            asset_type = "image" if (metadata.get("mime_type") or "").startswith("image/") else "video"
            return _ASSET_PROMPT.format(
                filename=metadata["filename"],
                file_size_bytes=metadata["file_size_bytes"],
                mime_type=metadata["mime_type"],
                asset_type=asset_type,
                form_section=form_section,
            )
        raise ValueError(f"Unknown modal_type: {modal_type}")


class AutofillResponseParser:
    _SCHEMAS: dict[str, type] = {
        "music": _MusicAutofill,
        "sfx": _SFXAutofill,
        "asset": _AssetAutofill,
    }

    def parse(self, modal_type: str, raw: dict | str) -> dict:
        schema_cls = self._SCHEMAS.get(modal_type)
        if schema_cls is None:
            return {}
        if isinstance(raw, str):
            try:
                import json as _json
                raw = _json.loads(raw)
            except Exception:
                return {}
        if not isinstance(raw, dict):
            return {}
        try:
            return schema_cls.model_validate(raw).model_dump()
        except Exception:
            return {}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm_autofill.py -v
```

Expected output (all passing):
```
tests/test_llm_autofill.py::test_build_music_includes_filename_and_duration PASSED
tests/test_llm_autofill.py::test_build_music_with_form_values_includes_hints PASSED
tests/test_llm_autofill.py::test_build_sfx_includes_filename PASSED
tests/test_llm_autofill.py::test_build_asset_image_includes_image_type PASSED
tests/test_llm_autofill.py::test_build_asset_video_includes_video_type PASSED
tests/test_llm_autofill.py::test_build_unknown_type_raises PASSED
tests/test_llm_autofill.py::test_parse_music_full_response PASSED
tests/test_llm_autofill.py::test_parse_music_partial_response_nulls_missing_fields PASSED
tests/test_llm_autofill.py::test_parse_sfx_valid PASSED
tests/test_llm_autofill.py::test_parse_asset_valid PASSED
tests/test_llm_autofill.py::test_parse_malformed_json_string_returns_empty PASSED
tests/test_llm_autofill.py::test_parse_unknown_modal_type_returns_empty PASSED
```

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/llm_service.py tests/test_llm_autofill.py
git commit -m "feat: add AutofillPromptBuilder and AutofillResponseParser to llm_service"
```

---

## Task 2: Backend Endpoint

**Files:**
- Modify: `console/backend/routers/llm.py`
- Test: `tests/test_llm_autofill.py`

- [ ] **Step 1: Write failing endpoint tests**

Append to `tests/test_llm_autofill.py`:

```python
# ── Endpoint ──────────────────────────────────────────────────────────────────

from unittest.mock import patch
from fastapi.testclient import TestClient


def _make_client():
    from console.backend.main import app
    from console.backend.auth import require_editor_or_admin
    app.dependency_overrides[require_editor_or_admin] = lambda: {"id": 1, "role": "admin"}
    return TestClient(app)


def test_autofill_endpoint_music_happy_path():
    mock_response = {
        "title": "Lo-Fi Chill",
        "niches": ["study"],
        "moods": ["calm_focus"],
        "genres": ["ambient"],
        "volume": 0.15,
        "quality_score": 80,
        "is_vocal": False,
    }
    with patch("rag.llm_router.get_router") as mock_get_router:
        mock_get_router.return_value.generate.return_value = mock_response
        resp = _make_client().post("/api/llm/autofill", json={
            "modal_type": "music",
            "metadata": {
                "filename": "lofi-chill.mp3",
                "file_size_bytes": 1_024_000,
                "mime_type": "audio/mpeg",
                "duration_s": 120.0,
            },
            "form_values": {"title": "My Track"},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Lo-Fi Chill"
    assert data["moods"] == ["calm_focus"]


def test_autofill_endpoint_rate_limited_returns_429():
    with patch("rag.llm_router.get_router") as mock_get_router:
        mock_get_router.return_value.generate.side_effect = RuntimeError("429 rate limit exceeded")
        resp = _make_client().post("/api/llm/autofill", json={
            "modal_type": "sfx",
            "metadata": {"filename": "rain.wav", "file_size_bytes": 500, "mime_type": "audio/wav"},
            "form_values": {},
        })
    assert resp.status_code == 429


def test_autofill_endpoint_gemini_failure_returns_422():
    with patch("rag.llm_router.get_router") as mock_get_router:
        mock_get_router.return_value.generate.side_effect = RuntimeError("Gemini failed after 3 attempts")
        resp = _make_client().post("/api/llm/autofill", json={
            "modal_type": "asset",
            "metadata": {"filename": "photo.jpg", "file_size_bytes": 200_000, "mime_type": "image/jpeg"},
            "form_values": {},
        })
    assert resp.status_code == 422
```

- [ ] **Step 2: Run to verify the endpoint tests fail**

```bash
pytest tests/test_llm_autofill.py::test_autofill_endpoint_music_happy_path -v
```

Expected: `404 Not Found` — the `/api/llm/autofill` route doesn't exist yet.

- [ ] **Step 3: Add request schema and endpoint to `routers/llm.py`**

Add these imports at the top of `console/backend/routers/llm.py` (after existing imports):

```python
from typing import Any, Literal, Optional
from pydantic import BaseModel
```

Add these classes and endpoint at the end of `console/backend/routers/llm.py` (before or after the runway routes — keep with LLM routes):

```python
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
```

- [ ] **Step 4: Run all autofill tests to verify they pass**

```bash
pytest tests/test_llm_autofill.py -v
```

Expected: All 15 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add console/backend/routers/llm.py tests/test_llm_autofill.py
git commit -m "feat: add POST /api/llm/autofill endpoint"
```

---

## Task 3: Frontend API Client

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Add `autofillApi` export**

At the end of `console/frontend/src/api/client.js`, append:

```js
// ── Autofill ─────────────────────────────────────────────────────────────────
export const autofillApi = {
  suggest: (modal_type, metadata, form_values) => fetchApi('/api/llm/autofill', {
    method: 'POST',
    body: JSON.stringify({ modal_type, metadata, form_values }),
  }),
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add autofillApi.suggest to api client"
```

---

## Task 4: Music ImportModal — AI Button

**Files:**
- Modify: `console/frontend/src/pages/MusicPage.jsx`

- [ ] **Step 1: Import `autofillApi` at the top of MusicPage.jsx**

Find the existing import line for `musicApi` (near the top of the file):

```js
import { musicApi, nichesApi, templatesApi } from '../api/client.js'
```

Replace with:

```js
import { musicApi, nichesApi, templatesApi, autofillApi } from '../api/client.js'
```

- [ ] **Step 2: Add `autofilling` state and `handleAutofill` function inside `ImportModal`**

Find this line inside `ImportModal` (after the existing state declarations):

```js
const [uploading,    setUploading]    = useState(false)
```

Add immediately after it:

```js
const [autofilling,  setAutofilling]  = useState(false)
```

Then find the `handleImport` function inside `ImportModal`:

```js
const handleImport = async () => {
```

Add the following `handleAutofill` function immediately before `handleImport`:

```js
const handleAutofill = async () => {
  if (!file) return
  setAutofilling(true)
  try {
    const metadata = {
      filename: file.name,
      file_size_bytes: file.size,
      mime_type: file.type,
      duration_s: detectedDur,
    }
    const form_values = {
      title, niches: selNiches, moods: selMoods, genres: selGenres,
      volume, quality_score: qualityScore, is_vocal: isVocal,
    }
    const data = await autofillApi.suggest('music', metadata, form_values)
    if (data.title        != null) setTitle(data.title)
    if (data.niches       != null) setSelNiches(data.niches)
    if (data.moods        != null) setSelMoods(data.moods)
    if (data.genres       != null) setSelGenres(data.genres)
    if (data.volume       != null) setVolume(data.volume)
    if (data.quality_score != null) setQualityScore(data.quality_score)
    if (data.is_vocal     != null) setIsVocal(data.is_vocal)
  } catch (e) {
    const msg = e.status === 429
      ? 'AI quota reached — try again later'
      : 'AI suggestion failed — fill in manually'
    showToast(msg)
  } finally {
    setAutofilling(false)
  }
}
```

- [ ] **Step 3: Add AI button to the modal footer**

Find the existing footer prop in the Music `ImportModal`'s `<Modal>` call:

```jsx
footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" loading={uploading} onClick={handleImport}>Import</Button></>}
```

Replace it with:

```jsx
footer={
  <div className="flex items-center gap-2 w-full">
    <Button variant="ghost" disabled={!file || autofilling} loading={autofilling} onClick={handleAutofill}>✨ AI</Button>
    <div className="flex-1" />
    <Button variant="ghost" onClick={onClose}>Cancel</Button>
    <Button variant="primary" loading={uploading} onClick={handleImport}>Import</Button>
  </div>
}
```

- [ ] **Step 4: Verify in browser**

Start the dev server (`npm run dev` in `console/frontend/`) and navigate to the Music page. Click "Import". Verify:
- The modal opens with `[ ✨ AI ]` button on the left of the footer, grayed out
- After selecting an audio file, the AI button becomes active
- Clicking AI shows a spinner and (with a valid Gemini key) fills in all fields
- If no Gemini key is configured, a toast error appears and the form is unchanged

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/MusicPage.jsx
git commit -m "feat: add AI autofill button to Music ImportModal"
```

---

## Task 5: SFX ImportModal — AI Button

**Files:**
- Modify: `console/frontend/src/pages/SFXPage.jsx`

- [ ] **Step 1: Import `autofillApi` at the top of SFXPage.jsx**

Find the existing import line for `sfxApi`:

```js
import { sfxApi } from '../api/client.js'
```

Replace with:

```js
import { sfxApi, autofillApi } from '../api/client.js'
```

- [ ] **Step 2: Add `autofilling` state and `handleAutofill` inside SFX `ImportModal`**

Find this line inside the SFX `ImportModal` function:

```js
const [loading, setLoading] = useState(false)
```

Add immediately after it:

```js
const [autofilling, setAutofilling] = useState(false)
```

Then find the `handleSubmit` function:

```js
const handleSubmit = async () => {
```

Add the following `handleAutofill` function immediately before `handleSubmit`:

```js
const handleAutofill = async () => {
  if (!file) return
  setAutofilling(true)
  try {
    const metadata = {
      filename: file.name,
      file_size_bytes: file.size,
      mime_type: file.type,
      duration_s: null,
    }
    const form_values = { title, sound_type: soundType }
    const data = await autofillApi.suggest('sfx', metadata, form_values)
    if (data.title      != null) setTitle(data.title)
    if (data.sound_type != null) setSoundType(data.sound_type)
  } catch (e) {
    const msg = e.status === 429
      ? 'AI quota reached — try again later'
      : 'AI suggestion failed — fill in manually'
    showToast(msg)
  } finally {
    setAutofilling(false)
  }
}
```

- [ ] **Step 3: Add AI button to the SFX modal footer**

Find the existing footer in the SFX `ImportModal`'s `<Modal>` call:

```jsx
footer={
  <>
    <Button variant="ghost" onClick={onClose}>Cancel</Button>
    <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
  </>
}
```

Replace with:

```jsx
footer={
  <div className="flex items-center gap-2 w-full">
    <Button variant="ghost" disabled={!file || autofilling} loading={autofilling} onClick={handleAutofill}>✨ AI</Button>
    <div className="flex-1" />
    <Button variant="ghost" onClick={onClose}>Cancel</Button>
    <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
  </div>
}
```

- [ ] **Step 4: Verify in browser**

Navigate to the SFX page. Click "Import". Verify:
- `[ ✨ AI ]` button is grayed out until a file is selected
- After selecting a file, clicking AI fills in Title and Sound Type
- Toast appears on error, form unchanged

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/SFXPage.jsx
git commit -m "feat: add AI autofill button to SFX ImportModal"
```

---

## Task 6: VideoAssets ImportAssetModal — AI Button

**Files:**
- Modify: `console/frontend/src/pages/VideoAssetsPage.jsx`

- [ ] **Step 1: Import `autofillApi` at the top of VideoAssetsPage.jsx**

Find the existing import line for `assetsApi`:

```js
import { assetsApi, nichesApi } from '../api/client.js'
```

Replace with:

```js
import { assetsApi, nichesApi, autofillApi } from '../api/client.js'
```

- [ ] **Step 2: Add `autofilling` state and `handleAutofill` inside `ImportAssetModal`**

Find this line inside `ImportAssetModal`:

```js
const [loading, setLoading] = useState(false)
```

Add immediately after it:

```js
const [autofilling, setAutofilling] = useState(false)
```

Then find `handleSubmit` inside `ImportAssetModal`:

```js
const handleSubmit = async () => {
```

Add the following `handleAutofill` immediately before `handleSubmit`:

```js
const handleAutofill = async () => {
  if (!file) return
  setAutofilling(true)
  try {
    const metadata = {
      filename: file.name,
      file_size_bytes: file.size,
      mime_type: file.type,
      duration_s: null,
    }
    const form_values = { description, keywords, source }
    const data = await autofillApi.suggest('asset', metadata, form_values)
    if (data.description != null) setDescription(data.description)
    if (data.keywords    != null) setKeywords(data.keywords.join(', '))
    if (data.source      != null) setSource(data.source)
  } catch (e) {
    const msg = e.status === 429
      ? 'AI quota reached — try again later'
      : 'AI suggestion failed — fill in manually'
    showToast(msg)
  } finally {
    setAutofilling(false)
  }
}
```

- [ ] **Step 3: Add AI button to the `ImportAssetModal` footer**

Find the existing footer in `ImportAssetModal`'s `<Modal>` call:

```jsx
footer={
  <>
    <Button variant="ghost" onClick={onClose}>Cancel</Button>
    <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
  </>
}
```

Replace with:

```jsx
footer={
  <div className="flex items-center gap-2 w-full">
    <Button variant="ghost" disabled={!file || autofilling} loading={autofilling} onClick={handleAutofill}>✨ AI</Button>
    <div className="flex-1" />
    <Button variant="ghost" onClick={onClose}>Cancel</Button>
    <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
  </div>
}
```

- [ ] **Step 4: Verify in browser**

Navigate to the Video Assets page. Click "Import Asset". Verify:
- `[ ✨ AI ]` button is grayed out until a file is selected
- After selecting an image or video file, clicking AI fills in Description, Keywords, and Source
- Toast appears on error, form unchanged

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/VideoAssetsPage.jsx
git commit -m "feat: add AI autofill button to VideoAssets ImportAssetModal"
```
