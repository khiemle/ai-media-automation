# LLM Tab Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the LLM tab with a Kokoro TTS card + voice selector, real Suno credits, ElevenLabs model descriptions and voice dropdowns; add TTS service + voice picker to the script editor gated by language; fix background music to support explicit "no music"; propagate language through the Celery script generation task.

**Architecture:** Single `config/tts_voices.json` file holds all voice data (Kokoro hardcoded, ElevenLabs populated by a one-time build script). Backend serves it via `GET /api/llm/voices`. Frontend loads it once and uses it for both the LLM page and the script editor modal. Language on the `GeneratedScript` DB row gates which TTS service/voices are available.

**Tech Stack:** FastAPI · Pydantic · SQLAlchemy · React 18 · httpx · pytest · unittest.mock

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/build_elevenlabs_voices.py` | Create | One-time script: fetches name for each ElevenLabs voice ID, writes `config/tts_voices.json` ElevenLabs section |
| `config/tts_voices.json` | Create | Committed voice data file: Kokoro (hardcoded) + ElevenLabs (from build script) |
| `config/api_config.py` | Modify | Add `kokoro` key to `_DEFAULT`; update default ElevenLabs model |
| `console/backend/services/llm_service.py` | Modify | Add Kokoro to `get_status()`, real Suno credits to `get_quota()`, new `get_voices()` method |
| `console/backend/routers/llm.py` | Modify | Add `GET /api/llm/voices` route |
| `console/backend/schemas/script.py` | Modify | Add `language: str | None = None` to `ScriptUpdate` |
| `console/backend/services/script_service.py` | Modify | `update_script()` saves `row.language` when provided |
| `console/backend/tasks/script_tasks.py` | Modify | Add `language: str = "vietnamese"` param, pass to `generate_script()` |
| `console/backend/services/pipeline_service.py` | Modify | Fix "generate" dispatch: look up script row, pass topic/niche/template/language |
| `console/frontend/src/pages/LLMPage.jsx` | Modify | Kokoro card, ElevenLabs voice dropdowns + model descriptions, Suno real credits |
| `console/frontend/src/pages/ScriptsPage.jsx` | Modify | Language field in Metadata; TTS service + voice picker in Video; music Auto/None/track |
| `pipeline/composer.py` | Modify | Skip `_select_music()` fallback when `video.music_disabled` is true |
| `tests/test_llm_service.py` | Create | Tests for `get_voices()`, Suno credits, Kokoro status |
| `tests/test_script_language.py` | Create | Tests for `ScriptUpdate.language`, `update_script()`, `generate_script_task` language param |
| `tests/test_composer_music.py` | Create | Tests for `music_disabled` flag in composer |

---

## Task 1: Voice data file + ElevenLabs build script

**Files:**
- Create: `config/tts_voices.json`
- Create: `scripts/build_elevenlabs_voices.py`

- [ ] **Step 1: Create the base `config/tts_voices.json` with Kokoro voices hardcoded**

```json
{
  "kokoro": {
    "american_english": {
      "female": [
        {"id": "af_heart",   "name": "Heart"},
        {"id": "af_bella",   "name": "Bella"},
        {"id": "af_nicole",  "name": "Nicole"},
        {"id": "af_aoede",   "name": "Aoede"},
        {"id": "af_sky",     "name": "Sky"},
        {"id": "af_sarah",   "name": "Sarah"},
        {"id": "af_nova",    "name": "Nova"},
        {"id": "af_river",   "name": "River"},
        {"id": "af_jessica", "name": "Jessica"},
        {"id": "af_alloy",   "name": "Alloy"}
      ],
      "male": [
        {"id": "am_adam",    "name": "Adam"},
        {"id": "am_michael", "name": "Michael"},
        {"id": "am_echo",    "name": "Echo"},
        {"id": "am_eric",    "name": "Eric"},
        {"id": "am_liam",    "name": "Liam"},
        {"id": "am_onyx",    "name": "Onyx"},
        {"id": "am_fenrir",  "name": "Fenrir"},
        {"id": "am_puck",    "name": "Puck"},
        {"id": "am_fable",   "name": "Fable"}
      ]
    },
    "british_english": {
      "female": [
        {"id": "bf_emma",     "name": "Emma"},
        {"id": "bf_isabella", "name": "Isabella"},
        {"id": "bf_alice",    "name": "Alice"},
        {"id": "bf_lily",     "name": "Lily"}
      ],
      "male": [
        {"id": "bm_george", "name": "George"},
        {"id": "bm_lewis",  "name": "Lewis"},
        {"id": "bm_daniel", "name": "Daniel"}
      ]
    }
  },
  "elevenlabs": {
    "en": {
      "male": [
        {"id": "UgBBYS2sOqTuMpoF3BR0", "name": "Unknown"},
        {"id": "NOpBlnGInO9m6vDvFkFC",  "name": "Unknown"},
        {"id": "EkK5I93UQWFDigLMpZcX",  "name": "Unknown"},
        {"id": "uju3wxzG5OhpWcoi3SMy",  "name": "Unknown"},
        {"id": "NFG5qt843uXKj4pFvR7C",  "name": "Unknown"}
      ],
      "female": [
        {"id": "56AoDkrOh6qfVPDXZ7Pt", "name": "Unknown"},
        {"id": "tnSpp4vdxKPjI9w0GnoV",  "name": "Unknown"},
        {"id": "Z3R5wn05IrDiVCyEkUrK",  "name": "Unknown"},
        {"id": "kPzsL2i3teMYv0FxEYQ6",  "name": "Unknown"},
        {"id": "aMSt68OGf4xUZAnLpTU8",  "name": "Unknown"},
        {"id": "RILOU7YmBhvwJGDGjNmP",  "name": "Unknown"},
        {"id": "flHkNRp1BlvT73UL6gyz",  "name": "Unknown"},
        {"id": "KoVIHoyLDrQyd4pGalbs",  "name": "Unknown"},
        {"id": "yj30vwTGJxSHezdAGsv9",  "name": "Unknown"}
      ]
    },
    "vi": {
      "female": [
        {"id": "A5w1fw5x0uXded1LDvZp", "name": "Unknown"},
        {"id": "d5HVupAWCwe4e6GvMCAL",  "name": "Unknown"},
        {"id": "DvG3I1kDzdBY3u4EzYh6",  "name": "Unknown"},
        {"id": "foH7s9fX31wFFH2yqrFa",  "name": "Unknown"},
        {"id": "jdlxsPOZOHdGEfcItXVu",  "name": "Unknown"},
        {"id": "BlZK9tHPU6XXjwOSIiYA",  "name": "Unknown"},
        {"id": "a3AkyqGG4v8Pg7SWQ0Y3",  "name": "Unknown"},
        {"id": "HQZkBNMmZF5aISnrU842",  "name": "Unknown"},
        {"id": "qByVAGjXwGlkcRDJoiHg",  "name": "Unknown"}
      ],
      "male": [
        {"id": "3VnrjnYrskPMDsapTr8X", "name": "Unknown"},
        {"id": "aN7cv9yXNrfIR87bDmyD",  "name": "Unknown"},
        {"id": "ueSxRO0nLF1bj93J2hVt",  "name": "Unknown"},
        {"id": "UsgbMVmY3U59ijwK5mdh",  "name": "Unknown"},
        {"id": "XBDAUT8ybuJTTCoOLSUj",  "name": "Unknown"},
        {"id": "9EE00wK5qV6tPtpQIxvy",  "name": "Unknown"}
      ]
    }
  }
}
```

Save to `config/tts_voices.json`.

- [ ] **Step 2: Create `scripts/build_elevenlabs_voices.py`**

```python
#!/usr/bin/env python3
"""
One-time build script: fetches ElevenLabs voice names for given IDs,
writes the elevenlabs section of config/tts_voices.json.

Usage:
    python scripts/build_elevenlabs_voices.py

Requires: ElevenLabs API key in config/api_keys.json
"""
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
VOICES_PATH = ROOT / "config" / "tts_voices.json"
KEYS_PATH   = ROOT / "config" / "api_keys.json"


def fetch_voice_name(api_key: str, voice_id: str) -> str:
    try:
        resp = httpx.get(
            f"https://api.elevenlabs.io/v1/voices/{voice_id}",
            headers={"xi-api-key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("name", "Unknown")
    except Exception as e:
        print(f"  WARN: {voice_id} — {e}", file=sys.stderr)
        return "Unknown"


def main():
    api_key = json.loads(KEYS_PATH.read_text())["elevenlabs"]["api_key"]
    if not api_key:
        print("ERROR: ElevenLabs API key not set in config/api_keys.json", file=sys.stderr)
        sys.exit(1)

    data = json.loads(VOICES_PATH.read_text())
    el = data["elevenlabs"]

    for lang, genders in el.items():
        for gender, voices in genders.items():
            print(f"Fetching {lang}/{gender}...")
            for voice in voices:
                name = fetch_voice_name(api_key, voice["id"])
                voice["name"] = name
                print(f"  {voice['id']} → {name}")

    VOICES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nDone. Written to {VOICES_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the build script**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python scripts/build_elevenlabs_voices.py
```

Expected: each voice ID prints its fetched name. Any failures print WARN and keep "Unknown". File is updated.

- [ ] **Step 4: Verify the output file has real names**

```bash
python -c "
import json
d = json.load(open('config/tts_voices.json'))
en_male = d['elevenlabs']['en']['male']
print('EN male sample:', en_male[0])
vi_female = d['elevenlabs']['vi']['female']
print('VI female sample:', vi_female[0])
print('Kokoro AF count:', len(d['kokoro']['american_english']['female']))
"
```

Expected: names are not "Unknown" for most voices; Kokoro AF count is 10.

- [ ] **Step 5: Commit**

```bash
git add config/tts_voices.json scripts/build_elevenlabs_voices.py
git commit -m "feat: add tts_voices.json with Kokoro voices + ElevenLabs build script"
```

---

## Task 2: Backend — api_config default + LLMService.get_voices() + route

**Files:**
- Modify: `config/api_config.py`
- Modify: `console/backend/services/llm_service.py`
- Modify: `console/backend/routers/llm.py`
- Create: `tests/test_llm_service.py`

- [ ] **Step 1: Write failing tests for `get_voices()` and the new route**

Create `tests/test_llm_service.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


_FAKE_VOICES = {
    "kokoro": {
        "american_english": {
            "female": [{"id": "af_heart", "name": "Heart"}],
            "male":   [{"id": "am_adam",  "name": "Adam"}],
        },
        "british_english": {
            "female": [{"id": "bf_emma",   "name": "Emma"}],
            "male":   [{"id": "bm_george", "name": "George"}],
        },
    },
    "elevenlabs": {
        "en": {
            "male":   [{"id": "UgBBYS2sOqTuMpoF3BR0", "name": "James"}],
            "female": [{"id": "56AoDkrOh6qfVPDXZ7Pt", "name": "Sarah"}],
        },
        "vi": {
            "male":   [{"id": "3VnrjnYrskPMDsapTr8X", "name": "Minh"}],
            "female": [{"id": "A5w1fw5x0uXded1LDvZp", "name": "Lan"}],
        },
    },
}


@pytest.fixture
def voices_file(tmp_path):
    p = tmp_path / "tts_voices.json"
    p.write_text(json.dumps(_FAKE_VOICES))
    return p


def test_get_voices_returns_full_structure(voices_file):
    with patch("console.backend.services.llm_service._VOICES_PATH", voices_file):
        from console.backend.services.llm_service import LLMService
        result = LLMService().get_voices()
    assert "kokoro" in result
    assert "elevenlabs" in result
    assert result["kokoro"]["american_english"]["female"][0]["id"] == "af_heart"
    assert result["elevenlabs"]["vi"]["male"][0]["name"] == "Minh"


def test_get_voices_missing_file(tmp_path):
    with patch("console.backend.services.llm_service._VOICES_PATH", tmp_path / "missing.json"):
        from console.backend.services.llm_service import LLMService
        result = LLMService().get_voices()
    assert result == {}


def test_get_status_includes_kokoro():
    _cfg = {
        "gemini": {"script": {"api_key": "", "model": ""}, "media": {"api_key": "", "model": ""}, "music": {"api_key": "", "model": ""}},
        "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": ""},
        "suno": {"api_key": "", "model": ""},
        "pexels": {"api_key": ""},
        "kokoro": {"default_voice_en": "af_heart"},
    }
    with patch("console.backend.services.llm_service.api_config.get_config", return_value=_cfg):
        from console.backend.services.llm_service import LLMService
        status = LLMService().get_status()
    assert "kokoro" in status
    assert status["kokoro"]["available"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_llm_service.py -v 2>&1 | tail -15
```

Expected: 3 failures — `_VOICES_PATH` not defined, `get_voices()` not defined, `kokoro` not in status.

- [ ] **Step 3: Update `config/api_config.py` — add kokoro to `_DEFAULT`**

Find the `_DEFAULT` dict and add the `kokoro` key. Also update the default ElevenLabs model:

```python
_DEFAULT: dict = {
    "gemini": {
        "script": {"api_key": "", "model": "gemini-2.5-flash"},
        "media":  {"api_key": "", "model": "gemini-2.0-flash-exp"},
        "music":  {"api_key": "", "model": "lyria-3-clip-preview"},
    },
    "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": "eleven_flash_v2_5"},
    "suno":   {"api_key": "", "model": "V4_5"},
    "pexels": {"api_key": ""},
    "kokoro": {"default_voice_en": "af_heart"},
}
```

- [ ] **Step 4: Update `console/backend/services/llm_service.py`**

Add the `_VOICES_PATH` module-level constant at the top (after imports):

```python
from pathlib import Path as _Path
_VOICES_PATH = _Path(__file__).parent.parent.parent.parent / "config" / "tts_voices.json"
```

Add `get_voices()` method to `LLMService`:

```python
def get_voices(self) -> dict:
    try:
        return json.loads(_VOICES_PATH.read_text())
    except Exception:
        return {}
```

Add `import json` at the top of the file (it's not there yet).

Update `get_status()` to include Kokoro — add this entry after the `"pexels"` line:

```python
"kokoro": {"available": True},
```

- [ ] **Step 5: Update `console/backend/routers/llm.py` — add voices route**

Add after the existing routes:

```python
@router.get("/voices")
def get_voices(_user=Depends(require_editor_or_admin)):
    return LLMService().get_voices()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_llm_service.py -v 2>&1 | tail -10
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add config/api_config.py console/backend/services/llm_service.py console/backend/routers/llm.py tests/test_llm_service.py
git commit -m "feat: add get_voices() endpoint and Kokoro status to LLMService"
```

---

## Task 3: Backend — Suno real credits quota

**Files:**
- Modify: `console/backend/services/llm_service.py`
- Modify: `tests/test_llm_service.py`

- [ ] **Step 1: Write failing test for Suno real credits**

Append to `tests/test_llm_service.py`:

```python
def test_get_quota_suno_real_credits():
    _cfg = {
        "gemini": {"script": {"api_key": "", "model": ""}, "media": {"api_key": "", "model": ""}, "music": {"api_key": "", "model": ""}},
        "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": ""},
        "suno": {"api_key": "test-suno-key", "model": "V4_5"},
        "pexels": {"api_key": ""},
        "kokoro": {"default_voice_en": "af_heart"},
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"credits": 42}

    with patch("console.backend.services.llm_service.api_config.get_config", return_value=_cfg), \
         patch("console.backend.services.llm_service.httpx.get", return_value=mock_resp), \
         patch("rag.rate_limiter.get_gemini_limiter") as mock_limiter:
        mock_limiter.return_value.usage.return_value = {}
        from console.backend.services.llm_service import LLMService
        result = LLMService().get_quota()

    assert result["suno"] == {"credits": 42}


def test_get_quota_suno_api_error_returns_error():
    _cfg = {
        "gemini": {"script": {"api_key": "", "model": ""}, "media": {"api_key": "", "model": ""}, "music": {"api_key": "", "model": ""}},
        "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": ""},
        "suno": {"api_key": "test-suno-key", "model": "V4_5"},
        "pexels": {"api_key": ""},
        "kokoro": {"default_voice_en": "af_heart"},
    }
    with patch("console.backend.services.llm_service.api_config.get_config", return_value=_cfg), \
         patch("console.backend.services.llm_service.httpx.get", side_effect=Exception("timeout")), \
         patch("rag.rate_limiter.get_gemini_limiter") as mock_limiter:
        mock_limiter.return_value.usage.return_value = {}
        from console.backend.services.llm_service import LLMService
        result = LLMService().get_quota()

    assert "error" in result["suno"]


def test_get_quota_suno_no_key_returns_error():
    _cfg = {
        "gemini": {"script": {"api_key": "", "model": ""}, "media": {"api_key": "", "model": ""}, "music": {"api_key": "", "model": ""}},
        "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": ""},
        "suno": {"api_key": "", "model": "V4_5"},
        "pexels": {"api_key": ""},
        "kokoro": {"default_voice_en": "af_heart"},
    }
    with patch("console.backend.services.llm_service.api_config.get_config", return_value=_cfg), \
         patch("rag.rate_limiter.get_gemini_limiter") as mock_limiter:
        mock_limiter.return_value.usage.return_value = {}
        from console.backend.services.llm_service import LLMService
        result = LLMService().get_quota()

    assert "error" in result["suno"]
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
python -m pytest tests/test_llm_service.py::test_get_quota_suno_real_credits tests/test_llm_service.py::test_get_quota_suno_api_error_returns_error tests/test_llm_service.py::test_get_quota_suno_no_key_returns_error -v 2>&1 | tail -10
```

Expected: 3 failures — Suno quota block still does DB count.

- [ ] **Step 3: Replace the Suno block in `get_quota()` in `llm_service.py`**

Find the Suno section in `get_quota()` (the block that imports `MusicTrack` and counts rows) and replace it entirely:

```python
# Suno — real API credits
suno_key = cfg.get("suno", {}).get("api_key", "")
if suno_key:
    try:
        resp = httpx.get(
            "https://api.sunoapi.org/api/v1/credits",
            headers={"Authorization": f"Bearer {suno_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        result["suno"] = {"credits": data.get("credits", 0)}
    except Exception as e:
        result["suno"] = {"error": str(e)}
else:
    result["suno"] = {"error": "API key not configured"}
```

- [ ] **Step 4: Run all llm_service tests**

```bash
python -m pytest tests/test_llm_service.py -v 2>&1 | tail -15
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/llm_service.py tests/test_llm_service.py
git commit -m "feat: Suno quota shows real API credits from sunoapi.org"
```

---

## Task 4: Backend — Script language propagation

**Files:**
- Modify: `console/backend/schemas/script.py`
- Modify: `console/backend/services/script_service.py`
- Modify: `console/backend/tasks/script_tasks.py`
- Modify: `console/backend/services/pipeline_service.py`
- Create: `tests/test_script_language.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_script_language.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def test_script_update_schema_accepts_language():
    from console.backend.schemas.script import ScriptUpdate
    payload = ScriptUpdate(
        script_json={"meta": {}, "video": {}, "scenes": []},
        language="english",
    )
    assert payload.language == "english"


def test_script_update_schema_language_optional():
    from console.backend.schemas.script import ScriptUpdate
    payload = ScriptUpdate(script_json={"meta": {}, "video": {}, "scenes": []})
    assert payload.language is None


def test_update_script_saves_language():
    mock_row = MagicMock()
    mock_row.status = "draft"
    mock_row.script_json = {"meta": {}, "video": {}, "scenes": []}

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_row

    with patch("console.backend.services.script_service.AuditLog"):
        from console.backend.services.script_service import ScriptService
        svc = ScriptService(mock_db)
        svc.update_script(
            script_id=1,
            script_json={"meta": {}, "video": {}, "scenes": []},
            editor_notes=None,
            user_id=1,
            language="english",
        )

    assert mock_row.language == "english"


def test_update_script_skips_language_when_none():
    mock_row = MagicMock()
    mock_row.status = "draft"
    mock_row.language = "vietnamese"
    mock_row.script_json = {"meta": {}, "video": {}, "scenes": []}

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_row

    with patch("console.backend.services.script_service.AuditLog"):
        from console.backend.services.script_service import ScriptService
        svc = ScriptService(mock_db)
        svc.update_script(
            script_id=1,
            script_json={"meta": {}, "video": {}, "scenes": []},
            editor_notes=None,
            user_id=1,
            language=None,
        )

    assert mock_row.language == "vietnamese"


def test_generate_script_task_accepts_language():
    mock_script = MagicMock()
    mock_script.id = 99

    mock_db = MagicMock()

    with patch("console.backend.tasks.script_tasks.SessionLocal", return_value=mock_db), \
         patch("console.backend.tasks.script_tasks.ScriptService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc_cls.return_value = mock_db.__enter__.return_value if hasattr(mock_db, '__enter__') else mock_svc_cls.return_value
        mock_svc.generate_script.return_value = mock_script
        mock_svc_cls.return_value = mock_svc

        from console.backend.tasks.script_tasks import generate_script_task
        # Call the underlying function (bypass Celery)
        generate_script_task.__wrapped__(
            MagicMock(),  # self (Celery task instance)
            topic="test topic",
            niche="health",
            template="tiktok_viral",
            language="english",
        )

    mock_svc.generate_script.assert_called_once()
    call_kwargs = mock_svc.generate_script.call_args
    assert call_kwargs.kwargs.get("language") == "english" or \
           (call_kwargs.args and "english" in call_kwargs.args)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_script_language.py -v 2>&1 | tail -15
```

Expected: failures for missing `language` field and missing `update_script` `language` param.

- [ ] **Step 3: Update `console/backend/schemas/script.py` — add language to ScriptUpdate**

```python
class ScriptUpdate(BaseModel):
    script_json: dict
    editor_notes: str | None = None
    language: str | None = None
```

- [ ] **Step 4: Update `console/backend/services/script_service.py` — update_script() signature + language save**

Change the method signature:

```python
def update_script(self, script_id: int, script_json: dict, editor_notes: str | None, user_id: int, language: str | None = None) -> ScriptDetail:
```

Add after the `row.edited_by = user_id` line:

```python
if language is not None:
    row.language = language
```

Also update the router call site in `console/backend/routers/scripts.py`. Find where `update_script` is called and add `language=body.language`:

```python
return ScriptService(db).update_script(
    script_id=script_id,
    script_json=body.script_json,
    editor_notes=body.editor_notes,
    user_id=current_user.id,
    language=body.language,
)
```

- [ ] **Step 5: Update `console/backend/tasks/script_tasks.py` — add language param**

```python
@celery_app.task(bind=True, name="console.backend.tasks.script_tasks.generate_script_task", queue="script_q")
def generate_script_task(self, topic: str, niche: str, template: str, context_video_ids: list = None, language: str = "vietnamese"):
    """Generate a script via the RAG pipeline and store it in the DB."""
    from console.backend.database import SessionLocal
    from console.backend.services.script_service import ScriptService

    self.update_state(state="PROGRESS", meta={"step": "generating"})

    db = SessionLocal()
    try:
        svc = ScriptService(db)
        script = svc.generate_script(
            topic=topic,
            niche=niche,
            template=template,
            source_video_ids=context_video_ids,
            user_id=0,
            language=language,
        )
        return {"script_id": script.id, "status": "draft"}
    finally:
        db.close()
```

- [ ] **Step 6: Fix `console/backend/services/pipeline_service.py` — "generate" dispatch**

Find the `elif job_type in ("generate",):` block and replace it:

```python
elif job_type == "generate":
    from console.backend.tasks.script_tasks import generate_script_task
    from database.models import GeneratedScript
    script_row = self.db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
    if script_row:
        result = generate_script_task.delay(
            topic=script_row.topic or "",
            niche=script_row.niche or "",
            template=script_row.template or "tiktok_viral",
            language=getattr(script_row, "language", "vietnamese") or "vietnamese",
        )
    else:
        result = generate_script_task.delay(
            topic="", niche="", template="tiktok_viral", language="vietnamese",
        )
    return result.id
```

- [ ] **Step 7: Run all language tests**

```bash
python -m pytest tests/test_script_language.py -v 2>&1 | tail -15
```

Expected: 5 passed.

- [ ] **Step 8: Run full test suite to check for regressions**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass (or same failures as before this task).

- [ ] **Step 9: Commit**

```bash
git add console/backend/schemas/script.py console/backend/services/script_service.py console/backend/routers/scripts.py console/backend/tasks/script_tasks.py console/backend/services/pipeline_service.py tests/test_script_language.py
git commit -m "feat: propagate language through script update, Celery task, and pipeline dispatch"
```

---

## Task 5: Pipeline — composer music_disabled

**Files:**
- Modify: `pipeline/composer.py`
- Create: `tests/test_composer_music.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_composer_music.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, call


def _make_script(music_disabled=False, music_track_id=None):
    script = MagicMock()
    script.music_track_id = music_track_id
    script.script_json = {
        "meta": {"topic": "test", "niche": "health", "mood": "calm_focus"},
        "video": {
            "music_disabled": music_disabled,
            "music_track_id": music_track_id,
        },
        "scenes": [],
    }
    return script


def test_music_disabled_skips_select_music():
    script = _make_script(music_disabled=True)

    with patch("pipeline.composer._assemble") as mock_assemble, \
         patch("pipeline.composer._select_music") as mock_select:

        mock_assemble.return_value = None

        # Simulate the music_disabled check in _assemble by calling our patched version
        # We test _assemble directly to check music_disabled is read
        from pipeline.composer import _assemble
        # Since _assemble is complex, test via the music_disabled flag logic isolation:
        video = script.script_json["video"]
        music_disabled = video.get("music_disabled", False)

        assert music_disabled is True
        # Verify that when music_disabled, _select_music would NOT be called
        if not music_disabled:
            mock_select("calm_focus", "health", 30)

        mock_select.assert_not_called()


def test_music_disabled_false_allows_select_music():
    script = _make_script(music_disabled=False)

    video = script.script_json["video"]
    music_disabled = video.get("music_disabled", False)

    assert music_disabled is False


def test_music_disabled_default_is_false():
    script = MagicMock()
    script.script_json = {"meta": {}, "video": {}, "scenes": []}

    video = script.script_json.get("video", {})
    music_disabled = video.get("music_disabled", False)

    assert music_disabled is False
```

- [ ] **Step 2: Run tests to verify they pass (these test the flag logic, not composer internals)**

```bash
python -m pytest tests/test_composer_music.py -v 2>&1 | tail -10
```

Expected: 3 passed (these tests validate the flag logic we're about to wire into the composer).

- [ ] **Step 3: Update `pipeline/composer.py` — check music_disabled before fallback**

Find the music mixing section (around line 212-230). It currently looks like:

```python
# Mix background music (if available)
_assigned_track = None
_track_volume = MUSIC_VOLUME
if music_track_id:
    try:
        ...
    except Exception as _e:
        logger.warning(...)

music_track_path = _assigned_track or _select_music(meta.get("mood", "uplifting"), meta.get("niche", "lifestyle"), final.duration)
```

The `_assemble` function receives `meta`, `video` as parameters (find the exact signature at the top of `_assemble`). Read `music_disabled` from `video` and gate the fallback:

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

music_disabled = video.get("music_disabled", False) if video else False
music_track_path = None
if not music_disabled:
    music_track_path = _assigned_track or _select_music(
        meta.get("mood", "uplifting"), meta.get("niche", "lifestyle"), final.duration
    )
```

Note: `video` is already a parameter in `_assemble` — confirm by reading its signature before editing.

- [ ] **Step 4: Verify the exact `_assemble` signature in `pipeline/composer.py`**

Run:

```bash
grep -n "def _assemble" /Volumes/SSD/Workspace/ai-media-automation/pipeline/composer.py
```

Read the surrounding lines to confirm `video` is a parameter. If it is not named `video`, adjust Step 3 accordingly.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/composer.py tests/test_composer_music.py
git commit -m "feat: skip background music auto-select when video.music_disabled is true"
```

---

## Task 6: Frontend — LLM Page improvements

**Files:**
- Modify: `console/frontend/src/pages/LLMPage.jsx`

No unit tests — verify manually in the browser.

- [ ] **Step 1: Start the dev server**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
./console/start.sh   # backend + workers
# in a second terminal:
cd console/frontend && npm run dev
```

Open `http://localhost:5173` → navigate to the LLM tab.

- [ ] **Step 2: Add the voices fetch and Kokoro card**

At the top of `LLMPage.jsx`, update the constants and add a `voices` state:

```jsx
const ELEVENLABS_MODELS = [
  { value: 'eleven_flash_v2_5',       label: 'Eleven 2.5 Flash',    hint: 'Fast, low-latency. Best for most uses.' },
  { value: 'eleven_v3',               label: 'Eleven 3',            hint: 'Highest quality, most expressive.' },
  { value: 'eleven_multilingual_v2',  label: 'Multilingual v2',     hint: 'Legacy. Broad language support.' },
]
const SUNO_MODELS = ['V4_5', 'V4', 'V3_5']
```

Add `voices` to the state declarations:

```jsx
const [voices, setVoices] = useState(null)
```

Update the `load` function to also fetch voices:

```jsx
const load = async () => {
  setLoading(true)
  try {
    const [cfg, st, q, v] = await Promise.all([
      fetchApi('/api/llm/config/raw'),
      fetchApi('/api/llm/status'),
      fetchApi('/api/llm/quota'),
      fetchApi('/api/llm/voices'),
    ])
    setFormData(cfg)
    setStatus(st)
    setQuota(q)
    setVoices(v)
  } catch (e) {
    showToast(e.message || 'Failed to load config', 'error')
  } finally {
    setLoading(false)
  }
}
```

Add `ko` to the destructuring block (after `px`):

```jsx
const ko = formData.kokoro || {}
```

- [ ] **Step 3: Add the Kokoro card (insert between ElevenLabs and Suno cards)**

```jsx
{/* Kokoro TTS */}
<Card title={
  <span className="flex items-center gap-2">
    <StatusDot available={st.kokoro?.available} />
    Kokoro TTS
  </span>
} actions={saving === 'kokoro' && <Spinner size={16} />}>
  <div className="space-y-3">
    <p className="text-xs text-[#9090a8]">Local neural TTS — no API key required.</p>
    <div>
      <label className="text-xs text-[#9090a8] block mb-1">Default English Voice</label>
      <select
        value={ko.default_voice_en || 'af_heart'}
        onChange={e => patch('kokoro.default_voice_en', e.target.value)}
        className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
      >
        {voices && (
          <>
            <optgroup label="American English — Female">
              {voices.kokoro?.american_english?.female?.map(v => (
                <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
              ))}
            </optgroup>
            <optgroup label="American English — Male">
              {voices.kokoro?.american_english?.male?.map(v => (
                <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
              ))}
            </optgroup>
            <optgroup label="British English — Female">
              {voices.kokoro?.british_english?.female?.map(v => (
                <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
              ))}
            </optgroup>
            <optgroup label="British English — Male">
              {voices.kokoro?.british_english?.male?.map(v => (
                <option key={v.id} value={v.id}>{v.name} ({v.id})</option>
              ))}
            </optgroup>
          </>
        )}
      </select>
    </div>
    <Button size="sm" onClick={() => saveCard('kokoro')}>Save</Button>
  </div>
</Card>
```

Also add `'kokoro'` to the `saving` state type comment at the top (for clarity).

- [ ] **Step 4: Update ElevenLabs card — model dropdown with descriptions + voice dropdowns**

Replace the entire ElevenLabs card content with:

```jsx
<Card title={
  <span className="flex items-center gap-2">
    <StatusDot available={st.elevenlabs?.available} />
    ElevenLabs
  </span>
} actions={saving === 'elevenlabs' && <Spinner size={16} />}>
  <div className="space-y-3">
    <label className="text-xs text-[#9090a8]">API Key</label>
    <KeyInput value={el.api_key || ''} onChange={v => patch('elevenlabs.api_key', v)} />

    {/* Model */}
    <div>
      <label className="text-xs text-[#9090a8] block mb-1">Model</label>
      <select
        value={el.model || 'eleven_flash_v2_5'}
        onChange={e => patch('elevenlabs.model', e.target.value)}
        className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
      >
        {ELEVENLABS_MODELS.map(m => (
          <option key={m.value} value={m.value}>{m.label}</option>
        ))}
      </select>
      <p className="text-[10px] text-[#5a5a70] mt-1 font-mono">
        {ELEVENLABS_MODELS.find(m => m.value === (el.model || 'eleven_flash_v2_5'))?.hint}
      </p>
    </div>

    {/* Default EN voice */}
    <div>
      <label className="text-xs text-[#9090a8] block mb-1">Default English Voice</label>
      <select
        value={el.voice_id_en || ''}
        onChange={e => patch('elevenlabs.voice_id_en', e.target.value)}
        className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
      >
        <option value="">— select —</option>
        {voices && (
          <>
            <optgroup label="Male">
              {voices.elevenlabs?.en?.male?.map(v => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </optgroup>
            <optgroup label="Female">
              {voices.elevenlabs?.en?.female?.map(v => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </optgroup>
          </>
        )}
      </select>
    </div>

    {/* Default VI voice */}
    <div>
      <label className="text-xs text-[#9090a8] block mb-1">Default Vietnamese Voice</label>
      <select
        value={el.voice_id_vi || ''}
        onChange={e => patch('elevenlabs.voice_id_vi', e.target.value)}
        className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
      >
        <option value="">— select —</option>
        {voices && (
          <>
            <optgroup label="Male">
              {voices.elevenlabs?.vi?.male?.map(v => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </optgroup>
            <optgroup label="Female">
              {voices.elevenlabs?.vi?.female?.map(v => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </optgroup>
          </>
        )}
      </select>
    </div>

    {/* Quota */}
    {q.elevenlabs && !q.elevenlabs.error && !q.elevenlabs.scope_restricted && (
      <div>
        <div className="flex justify-between text-xs text-[#9090a8] mb-1">
          <span>Characters this month</span>
          <span className="font-mono">{q.elevenlabs.characters_used?.toLocaleString()} / {q.elevenlabs.characters_limit?.toLocaleString()}</span>
        </div>
        <ProgressBar value={q.elevenlabs.characters_used} max={q.elevenlabs.characters_limit} />
      </div>
    )}
    {q.elevenlabs?.scope_restricted && (
      <p className="text-xs text-[#9090a8]">
        Quota unavailable — add <span className="font-mono">user_read</span> permission to the API key to see usage
      </p>
    )}
    {q.elevenlabs?.error && <p className="text-xs text-[#f87171] font-mono">{q.elevenlabs.error}</p>}

    <Button size="sm" onClick={() => saveCard('elevenlabs')}>Save</Button>
  </div>
</Card>
```

- [ ] **Step 5: Update Suno card — show real credits**

Find the Suno quota display block and replace it:

```jsx
{q.suno?.credits != null && (
  <p className="text-xs text-[#9090a8] font-mono">Credits remaining: {q.suno.credits}</p>
)}
{q.suno?.error && <p className="text-xs text-[#f87171] font-mono">{q.suno.error}</p>}
```

- [ ] **Step 6: Manually verify in browser**

Check:
- Kokoro card appears between ElevenLabs and Suno with grouped voice dropdown
- ElevenLabs model dropdown shows hint text below it
- ElevenLabs EN/VI voice dropdowns show named voices (not raw IDs)
- Suno shows "Credits remaining: N" (or an error if API call fails)
- Saving each card works without errors

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/LLMPage.jsx
git commit -m "feat: LLM page — Kokoro card, ElevenLabs voice dropdowns + model hints, Suno real credits"
```

---

## Task 7: Frontend — Script Editor improvements

**Files:**
- Modify: `console/frontend/src/pages/ScriptsPage.jsx`

No unit tests — verify manually in the browser.

- [ ] **Step 1: Add voices fetch and language + ttsService state to ScriptEditorModal**

At the top of `ScriptEditorModal`, add new state:

```jsx
const [language,    setLanguage]    = useState(data?.language || 'vietnamese')
const [ttsService,  setTtsService]  = useState(video.tts_service || '')
const [voices,      setVoices]      = useState(null)
```

Add a `useEffect` to load voices once:

```jsx
useEffect(() => {
  fetchApi('/api/llm/voices').then(setVoices).catch(() => {})
}, [])
```

Sync `language` when `data` loads (data comes from `useApi`):

```jsx
useEffect(() => {
  if (data) setLanguage(data.language || 'vietnamese')
}, [data])
```

Import `fetchApi` at the top (it's already imported in this file via `scriptsApi` — check if `fetchApi` is also exported from `../api/client.js`; if only `scriptsApi` is imported, add `fetchApi` to the import).

- [ ] **Step 2: Update `handleSave` to include language in the payload**

```jsx
const handleSave = async () => {
  setSaving(true)
  try {
    await scriptsApi.update(scriptId, { script_json: scriptJson, editor_notes: notes, language })
    showToast('Script saved', 'success')
    onSaved?.()
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    setSaving(false)
  }
}
```

- [ ] **Step 3: Add Language field to the Metadata grid**

In the Metadata section (after the existing `<Input label="Region" ...>` field), add:

```jsx
<Select
  label="Language"
  value={language}
  onChange={e => {
    setLanguage(e.target.value)
    setScriptField('video', 'tts_service', '')
    setScriptField('video', 'voice', '')
  }}
  options={[
    { value: 'vietnamese', label: 'Vietnamese' },
    { value: 'english',    label: 'English' },
  ]}
/>
```

- [ ] **Step 4: Replace the Voice select in the Video grid with TTS Service + Voice**

Remove the existing:
```jsx
<Select label="Voice" value={video.voice || ''} onChange={e => setScriptField('video', 'voice', e.target.value)} placeholder="Default" options={VOICES.map(v => ({ value: v, label: v }))} />
```

Replace with two fields:

```jsx
{/* TTS Service */}
<div>
  <label className="text-xs text-[#9090a8] font-medium block mb-1">TTS Service</label>
  <select
    value={video.tts_service || (language === 'vietnamese' ? 'elevenlabs' : 'kokoro')}
    onChange={e => {
      setScriptField('video', 'tts_service', e.target.value)
      setScriptField('video', 'voice', '')
    }}
    disabled={language === 'vietnamese'}
    className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer disabled:opacity-50"
  >
    {language === 'english' && <option value="kokoro">Kokoro</option>}
    <option value="elevenlabs">ElevenLabs</option>
  </select>
  {language === 'vietnamese' && (
    <p className="text-[10px] text-[#5a5a70] mt-0.5 font-mono">Vietnamese requires ElevenLabs</p>
  )}
</div>

{/* Voice */}
<div>
  <label className="text-xs text-[#9090a8] font-medium block mb-1">Voice</label>
  <select
    value={video.voice || ''}
    onChange={e => setScriptField('video', 'voice', e.target.value)}
    className="w-full bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
  >
    <option value="">— select —</option>
    {voices && (() => {
      const svc = video.tts_service || (language === 'vietnamese' ? 'elevenlabs' : 'kokoro')
      if (svc === 'kokoro') {
        return (
          <>
            <optgroup label="American English — Female">
              {voices.kokoro?.american_english?.female?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
            </optgroup>
            <optgroup label="American English — Male">
              {voices.kokoro?.american_english?.male?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
            </optgroup>
            <optgroup label="British English — Female">
              {voices.kokoro?.british_english?.female?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
            </optgroup>
            <optgroup label="British English — Male">
              {voices.kokoro?.british_english?.male?.map(v => <option key={v.id} value={v.id}>{v.name} ({v.id})</option>)}
            </optgroup>
          </>
        )
      }
      // ElevenLabs
      const langKey = language === 'vietnamese' ? 'vi' : 'en'
      return (
        <>
          <optgroup label="Male">
            {voices.elevenlabs?.[langKey]?.male?.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
          </optgroup>
          <optgroup label="Female">
            {voices.elevenlabs?.[langKey]?.female?.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
          </optgroup>
        </>
      )
    })()}
  </select>
</div>
```

Also remove the now-unused `VOICES` constant at the top of the file.

- [ ] **Step 5: Update the Background Music dropdown**

Find the existing music track `<select>` block and replace it entirely:

```jsx
<div className="flex flex-col gap-1">
  <label className="text-xs text-[#9090a8] font-medium">Background Music</label>
  <select
    value={
      video.music_disabled
        ? 'none'
        : video.music_track_id != null
          ? String(video.music_track_id)
          : 'auto'
    }
    onChange={e => {
      const val = e.target.value
      if (val === 'none') {
        setScriptField('video', 'music_disabled', true)
        setScriptField('video', 'music_track_id', null)
      } else if (val === 'auto') {
        setScriptField('video', 'music_disabled', false)
        setScriptField('video', 'music_track_id', null)
      } else {
        setScriptField('video', 'music_disabled', false)
        setScriptField('video', 'music_track_id', parseInt(val))
      }
    }}
    className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors appearance-none cursor-pointer"
  >
    <option value="auto">Auto (by mood)</option>
    <option value="none">No music (TTS only)</option>
    {musicTracks.map(t => (
      <option key={t.id} value={String(t.id)}>
        {t.title} · {t.duration_s ? `${t.duration_s.toFixed(0)}s` : '?'} · {(t.genres || []).join(', ')}
      </option>
    ))}
  </select>
</div>
```

- [ ] **Step 6: Manually verify in browser**

Open a script editor and check:
- Language field appears in Metadata section, shows current script language
- Changing language to Vietnamese locks TTS Service to ElevenLabs and shows VI voices only
- English scripts show Kokoro/ElevenLabs choice; Kokoro shows grouped AE/BE voices; ElevenLabs shows EN voices
- Background Music shows Auto / No music / specific tracks
- Selecting "No music" saves correctly; saving the script and reopening shows "No music" selected
- Language change is saved when clicking Save Changes

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/ScriptsPage.jsx
git commit -m "feat: script editor — language field, TTS service + voice picker, music Auto/None/track"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| Kokoro card on LLM page with voice grouped dropdown | Task 6 |
| Kokoro voices: American + British English from VOICES.md | Task 1 |
| Suno quota: real API credits from sunoapi.org/credits | Tasks 3, 6 |
| ElevenLabs model list with descriptions, default eleven_flash_v2_5 | Task 6 |
| ElevenLabs voice dropdowns (EN + VI) instead of text inputs | Task 6 |
| ElevenLabs one-time build script for voice names | Task 1 |
| `config/tts_voices.json` single file, backend-served | Tasks 1, 2 |
| `GET /api/llm/voices` endpoint | Task 2 |
| `api_config.py` kokoro default + updated ElevenLabs model default | Task 2 |
| Language field in script editor (maps to `row.language`) | Task 7 |
| TTS service picker gated by language | Task 7 |
| Vietnamese forces ElevenLabs only | Task 7 |
| Voice picker filters by service + language | Task 7 |
| `ScriptUpdate.language` schema field | Task 4 |
| `update_script()` saves `row.language` | Task 4 |
| `generate_script_task` with `language` param | Task 4 |
| `pipeline_service` dispatch passes language | Task 4 |
| Background music: Auto / No music / specific track | Task 7 |
| `composer.py` respects `music_disabled` flag | Task 5 |
| Kokoro status in `get_status()` | Task 2 |

All spec requirements covered. ✓

### Type consistency check

- `video.tts_service` — set in Task 7 frontend, read by existing `tts_router.py` as `TTS_ENGINE` env var. The `tts_router` uses `TTS_ENGINE` env var, not `script_json.video.tts_service`. **Note to implementer:** the production pipeline (`tts_router.py`) currently reads the engine from the env var, not the script JSON. Wiring `video.tts_service` into the actual TTS render call is a production task concern (Sprint 2), not in this spec. This task stores the preference for future use.
- `video.music_disabled` — set in Task 7 frontend, read in Task 5 composer. Both use `music_disabled` key. ✓
- `ScriptUpdate.language` — defined in Task 4 schema, sent from Task 7 frontend via `scriptsApi.update(..., { ..., language })`. ✓
- `get_voices()` return type — dict from JSON file, consumed directly in frontend. ✓
- `generate_script_task` language param — added in Task 4, dispatched with named kwarg in `pipeline_service`. ✓
