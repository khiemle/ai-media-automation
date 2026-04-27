# LLM & Integrations Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace env-var API key management with a JSON config file editable from the web UI, adding Gemini (script/media/music), ElevenLabs, Suno, and Pexels key management to the LLM page.

**Architecture:** A shared `config/api_config.py` module with a 30-second cache reads/writes `config/api_keys.json`. All pipeline files are updated to call `get_config()` instead of `os.environ.get(...)`. The console backend gains three new endpoints and the LLM page becomes six self-contained provider cards.

**Tech Stack:** Python (pathlib, json, time), FastAPI (existing patterns), React 18 + Tailwind (existing components from `components/index.jsx`), httpx (already in pexels_client.py)

---

## File Map

| Action | File |
|---|---|
| Create | `config/api_keys.json.example` |
| Create | `config/api_config.py` |
| Create | `tests/test_api_config.py` |
| Modify | `rag/llm_router.py` |
| Modify | `tests/test_llm_router.py` |
| Modify | `pipeline/veo_client.py` |
| Modify | `pipeline/music_providers/lyria_provider.py` |
| Modify | `pipeline/elevenlabs_tts.py` |
| Modify | `pipeline/tts_router.py` |
| Modify | `tests/test_tts_router.py` |
| Modify | `pipeline/pexels_client.py` |
| Modify | `pipeline/music_providers/suno_provider.py` |
| Modify | `console/backend/services/llm_service.py` |
| Modify | `console/backend/routers/llm.py` |
| Modify | `console/frontend/src/pages/LLMPage.jsx` |
| Modify | `.gitignore` |

---

## Task 1: Shared Config Module

**Files:**
- Create: `config/api_keys.json.example`
- Create: `config/api_config.py`
- Create: `tests/test_api_config.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add api_keys.json to .gitignore**

Open `.gitignore` and add this line in the `# Environment` section (after `*.env.local`):

```
config/api_keys.json
```

- [ ] **Step 2: Create config/api_keys.json.example**

```json
{
  "gemini": {
    "script": {
      "api_key": "",
      "model": "gemini-2.5-flash"
    },
    "media": {
      "api_key": "",
      "model": "gemini-2.0-flash-exp"
    },
    "music": {
      "api_key": "",
      "model": "lyria-3-clip-preview"
    }
  },
  "elevenlabs": {
    "api_key": "",
    "voice_id_en": "",
    "voice_id_vi": "",
    "model": "eleven_multilingual_v2"
  },
  "suno": {
    "api_key": "",
    "model": "V4_5"
  },
  "pexels": {
    "api_key": ""
  }
}
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_api_config.py`:

```python
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def config_file(tmp_path):
    data = {
        "gemini": {
            "script": {"api_key": "sk-script", "model": "gemini-2.5-flash"},
            "media":  {"api_key": "sk-media",  "model": "gemini-2.0-flash-exp"},
            "music":  {"api_key": "sk-music",  "model": "lyria-3-clip-preview"},
        },
        "elevenlabs": {"api_key": "el-key", "voice_id_en": "en-id", "voice_id_vi": "vi-id", "model": "eleven_multilingual_v2"},
        "suno":       {"api_key": "suno-key", "model": "V4_5"},
        "pexels":     {"api_key": "pexels-key"},
    }
    p = tmp_path / "api_keys.json"
    p.write_text(json.dumps(data))
    return p


def _reset_cache():
    import config.api_config as m
    m._cache = {}
    m._cache_time = 0.0


def test_get_config_reads_file(config_file):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", config_file):
        from config.api_config import get_config
        cfg = get_config()
    assert cfg["gemini"]["script"]["api_key"] == "sk-script"
    assert cfg["pexels"]["api_key"] == "pexels-key"


def test_get_config_caches(config_file):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", config_file):
        from config.api_config import get_config
        cfg1 = get_config()
        # mutate file — should not affect cached result within TTL
        config_file.write_text(json.dumps({"gemini": {}}))
        cfg2 = get_config()
    assert cfg1 is cfg2


def test_get_config_missing_file(tmp_path):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", tmp_path / "missing.json"):
        from config.api_config import get_config
        cfg = get_config()
    assert cfg["gemini"]["script"]["api_key"] == ""
    assert cfg["pexels"]["api_key"] == ""


def test_save_config_writes_and_busts_cache(config_file):
    _reset_cache()
    with patch("config.api_config._CONFIG_PATH", config_file):
        from config.api_config import get_config, save_config
        get_config()  # prime cache
        new = {"gemini": {"script": {"api_key": "new-key", "model": "m"}}}
        save_config(new)
        cfg = get_config()
    assert cfg["gemini"]["script"]["api_key"] == "new-key"
    written = json.loads(config_file.read_text())
    assert written["gemini"]["script"]["api_key"] == "new-key"
```

- [ ] **Step 4: Run tests — expect ImportError (module not yet created)**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_api_config.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'config.api_config'`

- [ ] **Step 5: Create config/api_config.py**

```python
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "api_keys.json"
_CACHE_TTL = 30.0
_cache: dict = {}
_cache_time: float = 0.0

_DEFAULT: dict = {
    "gemini": {
        "script": {"api_key": "", "model": "gemini-2.5-flash"},
        "media":  {"api_key": "", "model": "gemini-2.0-flash-exp"},
        "music":  {"api_key": "", "model": "lyria-3-clip-preview"},
    },
    "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": "eleven_multilingual_v2"},
    "suno":   {"api_key": "", "model": "V4_5"},
    "pexels": {"api_key": ""},
}


def get_config() -> dict:
    global _cache, _cache_time
    now = time.monotonic()
    if _cache and now - _cache_time < _CACHE_TTL:
        return _cache
    if not _CONFIG_PATH.exists():
        logger.warning("config/api_keys.json not found — all API keys will be empty")
        import copy
        return copy.deepcopy(_DEFAULT)
    try:
        data = json.loads(_CONFIG_PATH.read_text())
        _cache = data
        _cache_time = now
        return _cache
    except Exception as e:
        logger.error("Failed to read config/api_keys.json: %s", e)
        return _cache if _cache else _DEFAULT.copy()


def save_config(data: dict) -> None:
    global _cache, _cache_time
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))
    _cache = data
    _cache_time = time.monotonic()
```

- [ ] **Step 6: Run tests — expect all pass**

```bash
python -m pytest tests/test_api_config.py -v
```

Expected output:
```
tests/test_api_config.py::test_get_config_reads_file PASSED
tests/test_api_config.py::test_get_config_caches PASSED
tests/test_api_config.py::test_get_config_missing_file PASSED
tests/test_api_config.py::test_save_config_writes_and_busts_cache PASSED
4 passed
```

- [ ] **Step 7: Commit**

```bash
git add config/api_config.py config/api_keys.json.example tests/test_api_config.py .gitignore
git commit -m "feat: add shared api_config module with 30s cache"
```

---

## Task 2: Migrate rag/llm_router.py

**Files:**
- Modify: `rag/llm_router.py`
- Modify: `tests/test_llm_router.py`

- [ ] **Step 1: Read current state**

Run:
```bash
grep -n "GEMINI_API_KEY\|GEMINI_MODEL\|os.environ" rag/llm_router.py
```

You will see `api_key = os.environ.get("GEMINI_API_KEY", "")` and `model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")` inside the `generate()` method.

- [ ] **Step 2: Update test file first (tests fail before code change)**

Replace the `_fake_gemini_key` fixture in `tests/test_llm_router.py`:

```python
import pytest
from unittest.mock import patch, MagicMock

_FAKE_CONFIG = {
    "gemini": {
        "script": {"api_key": "fake-key", "model": "gemini-2.5-flash"},
        "media":  {"api_key": "", "model": "gemini-2.0-flash-exp"},
        "music":  {"api_key": "", "model": "lyria-3-clip-preview"},
    },
    "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": "eleven_multilingual_v2"},
    "suno":   {"api_key": "", "model": "V4_5"},
    "pexels": {"api_key": ""},
}


@pytest.fixture(autouse=True)
def _fake_config():
    with patch("rag.llm_router.get_config", return_value=_FAKE_CONFIG):
        yield
```

Keep all existing test functions unchanged — only replace the fixture.

- [ ] **Step 3: Run tests — expect failure**

```bash
python -m pytest tests/test_llm_router.py -v 2>&1 | head -20
```

Expected: tests fail because `rag.llm_router` has no `get_config` name yet.

- [ ] **Step 4: Update rag/llm_router.py**

At the top of the file, after the existing imports, add:

```python
from config.api_config import get_config
```

Remove any `load_dotenv` calls that were only needed for `GEMINI_API_KEY`.

Inside `GeminiRouter.generate()`, replace:

```python
api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set in .env")
```

with:

```python
cfg = get_config()
api_key = cfg["gemini"]["script"]["api_key"]
if not api_key:
    raise RuntimeError("Gemini script API key is not configured in config/api_keys.json")
```

Replace:

```python
model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
```

with:

```python
model = cfg["gemini"]["script"]["model"]
```

In `_fetch_gemini_models` (used by `LLMService`), the method already accepts an explicit `api_key` argument, so no change needed there.

- [ ] **Step 5: Run tests — expect all pass**

```bash
python -m pytest tests/test_llm_router.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add rag/llm_router.py tests/test_llm_router.py
git commit -m "feat: migrate llm_router to read key/model from api_keys.json"
```

---

## Task 3: Migrate pipeline/veo_client.py

**Files:**
- Modify: `pipeline/veo_client.py`

- [ ] **Step 1: Read the module-level constants**

```bash
grep -n "GEMINI_MEDIA_KEY\|VEO_MODEL\|ASSET_DB_PATH" pipeline/veo_client.py
```

You will see lines ~20–22 that read from env at import time.

- [ ] **Step 2: Delete module-level constants and add import**

At the top of `pipeline/veo_client.py`, remove these three lines:

```python
GEMINI_MEDIA_KEY = os.environ.get("GEMINI_MEDIA_API_KEY", "")
VEO_MODEL        = os.environ.get("VEO_MODEL", "veo-3.1-lite-generate-preview")
ASSET_DB_PATH    = os.environ.get("ASSET_DB_PATH", "./assets/video_db")
```

Replace with:

```python
from config.api_config import get_config
ASSET_DB_PATH = os.environ.get("ASSET_DB_PATH", "./assets/video_db")
```

(`ASSET_DB_PATH` stays env-based — it's operational config, not an API key.)

- [ ] **Step 3: Update VeoClient.__init__**

Find the `__init__` method. Replace every reference to `GEMINI_MEDIA_KEY` and `VEO_MODEL`:

```python
def __init__(self):
    cfg = get_config()
    key = cfg["gemini"]["media"]["api_key"]
    self._model = cfg["gemini"]["media"]["model"]
    if not key:
        raise RuntimeError("Gemini media API key is not configured in config/api_keys.json")
    if genai is None:
        raise RuntimeError("google-genai not installed. Run: pip install google-genai")
    self._client = genai.Client(api_key=key)
```

- [ ] **Step 4: Replace VEO_MODEL usage in generate method**

Find the line `model=VEO_MODEL,` (around line 55) and replace with:

```python
model=self._model,
```

- [ ] **Step 5: Verify no remaining env references for API key**

```bash
grep -n "GEMINI_MEDIA\|VEO_MODEL\|os.environ" pipeline/veo_client.py
```

Expected: only `ASSET_DB_PATH` lines remain for `os.environ`.

- [ ] **Step 6: Commit**

```bash
git add pipeline/veo_client.py
git commit -m "feat: migrate veo_client to read key/model from api_keys.json"
```

---

## Task 4: Migrate pipeline/music_providers/lyria_provider.py

**Files:**
- Modify: `pipeline/music_providers/lyria_provider.py`

- [ ] **Step 1: Add import and update __init__**

At the top of `pipeline/music_providers/lyria_provider.py`, after the existing imports, add:

```python
from config.api_config import get_config
```

In `LyriaProvider.__init__`, replace:

```python
self._key = os.environ.get("GEMINI_MEDIA_API_KEY", "")
if not self._key:
    raise RuntimeError("GEMINI_MEDIA_API_KEY is not set")
```

with:

```python
self._key = get_config()["gemini"]["music"]["api_key"]
if not self._key:
    raise RuntimeError("Gemini music API key is not configured in config/api_keys.json")
```

Remove the `import os` line if it is no longer used elsewhere in the file. Check:

```bash
grep -n "os\." pipeline/music_providers/lyria_provider.py
```

If no other `os.` references exist, remove `import os`.

- [ ] **Step 2: Verify**

```bash
grep -n "GEMINI_MEDIA\|os.environ" pipeline/music_providers/lyria_provider.py
```

Expected: no matches.

- [ ] **Step 3: Commit**

```bash
git add pipeline/music_providers/lyria_provider.py
git commit -m "feat: migrate lyria_provider to read key from api_keys.json"
```

---

## Task 5: Migrate pipeline/elevenlabs_tts.py

**Files:**
- Modify: `pipeline/elevenlabs_tts.py`

- [ ] **Step 1: Locate the constants and key read**

```bash
grep -n "ELEVENLABS_MODEL\|ELEVENLABS_API_KEY\|os.environ" pipeline/elevenlabs_tts.py
```

You will see `ELEVENLABS_MODEL = "eleven_multilingual_v2"` at module level and `api_key = os.environ.get("ELEVENLABS_API_KEY", "")` inside `generate_tts_elevenlabs()`.

- [ ] **Step 2: Add import and update the function**

After the existing imports at the top of the file, add:

```python
from config.api_config import get_config
```

Remove the module-level constant:

```python
ELEVENLABS_MODEL = "eleven_multilingual_v2"
```

Inside `generate_tts_elevenlabs()`, replace:

```python
api_key = os.environ.get("ELEVENLABS_API_KEY", "")  # read dynamically, not from import-time constant
if not api_key:
    raise RuntimeError("ELEVENLABS_API_KEY is not set in .env")
```

with:

```python
cfg = get_config()
api_key = cfg["elevenlabs"]["api_key"]
if not api_key:
    raise RuntimeError("ElevenLabs API key is not configured in config/api_keys.json")
```

Find the payload line `"model_id": ELEVENLABS_MODEL,` and replace with:

```python
"model_id": cfg["elevenlabs"]["model"],
```

- [ ] **Step 3: Verify**

```bash
grep -n "ELEVENLABS_MODEL\|ELEVENLABS_API_KEY\|os.environ" pipeline/elevenlabs_tts.py
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add pipeline/elevenlabs_tts.py
git commit -m "feat: migrate elevenlabs_tts to read key/model from api_keys.json"
```

---

## Task 6: Migrate pipeline/tts_router.py

**Files:**
- Modify: `pipeline/tts_router.py`
- Modify: `tests/test_tts_router.py`

`tts_router.py` has three module-level reads. `TTS_ENGINE` stays env-based (operational config). `ELEVENLABS_VOICE_ID_VI` and `ELEVENLABS_VOICE_ID_EN` move to `get_config()` inside the function.

- [ ] **Step 1: Update tests first**

In `tests/test_tts_router.py`, add this helper at the top after imports:

```python
_FAKE_CONFIG = {
    "gemini": {
        "script": {"api_key": "", "model": "gemini-2.5-flash"},
        "media":  {"api_key": "", "model": "gemini-2.0-flash-exp"},
        "music":  {"api_key": "", "model": "lyria-3-clip-preview"},
    },
    "elevenlabs": {"api_key": "test-key", "voice_id_en": "en-voice-id", "voice_id_vi": "vi-voice-id", "model": "eleven_multilingual_v2"},
    "suno":   {"api_key": "", "model": "V4_5"},
    "pexels": {"api_key": ""},
}
```

Replace `test_auto_vietnamese_calls_elevenlabs`:

```python
def test_auto_vietnamese_calls_elevenlabs(tmp_path):
    out = tmp_path / "out.wav"
    with patch("pipeline.tts_router.get_config", return_value=_FAKE_CONFIG), \
         patch.dict(os.environ, {"TTS_ENGINE": "auto"}), \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
        mock_el.return_value = out
        from pipeline.tts_router import generate_tts
        result = generate_tts("Xin chào", "vi-voice-id", 1.0, "vietnamese", str(out))
    mock_el.assert_called_once()
    assert result == out
```

Replace `test_force_elevenlabs_mode`:

```python
def test_force_elevenlabs_mode(tmp_path):
    out = tmp_path / "out.wav"
    with patch("pipeline.tts_router.get_config", return_value=_FAKE_CONFIG), \
         patch.dict(os.environ, {"TTS_ENGINE": "elevenlabs"}), \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
        mock_el.return_value = out
        from pipeline.tts_router import generate_tts
        result = generate_tts("Xin chào", "vi-id", 1.0, "vietnamese", str(out))
    assert result == out
    mock_el.assert_called_once()
```

Replace `test_missing_elevenlabs_key_raises`:

```python
def test_missing_elevenlabs_key_raises():
    empty_config = {**_FAKE_CONFIG, "elevenlabs": {**_FAKE_CONFIG["elevenlabs"], "api_key": ""}}
    with patch("pipeline.tts_router.get_config", return_value=empty_config), \
         patch.dict(os.environ, {"TTS_ENGINE": "elevenlabs"}):
        from pipeline.tts_router import generate_tts
        with pytest.raises(RuntimeError, match="ElevenLabs"):
            generate_tts("text", "voice", 1.0, "vietnamese", "output.wav")
```

`test_auto_english_calls_kokoro` and `test_normalize_text_expands_currency` need no changes.

- [ ] **Step 2: Run tests — expect failure**

```bash
python -m pytest tests/test_tts_router.py -v 2>&1 | head -20
```

- [ ] **Step 3: Update pipeline/tts_router.py**

Remove the module-level voice ID reads:

```python
ELEVENLABS_VOICE_ID_VI = os.environ.get("ELEVENLABS_VOICE_ID_VI", "")
ELEVENLABS_VOICE_ID_EN = os.environ.get("ELEVENLABS_VOICE_ID_EN", "")
```

Keep `TTS_ENGINE = os.environ.get("TTS_ENGINE", "auto")` as module-level (it's operational config, not an API key).

Add import at the top:

```python
from config.api_config import get_config
```

Inside `generate_tts()`, replace references to `ELEVENLABS_VOICE_ID_VI` and `ELEVENLABS_VOICE_ID_EN`:

```python
# Before:
elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY", "")
...
voice = voice_id or ELEVENLABS_VOICE_ID_VI or ELEVENLABS_VOICE_ID_EN

# After:
cfg = get_config()
...
voice = voice_id or cfg["elevenlabs"]["voice_id_vi"] or cfg["elevenlabs"]["voice_id_en"]
```

Also remove the `elevenlabs_api_key = os.environ.get(...)` line inside `generate_tts()` since the key is now read inside `elevenlabs_tts.generate_tts_elevenlabs()` via `get_config()`.

The check `if not elevenlabs_api_key: raise RuntimeError(...)` that was inside `generate_tts()` can be removed — `generate_tts_elevenlabs()` raises its own error for a missing key.

- [ ] **Step 4: Run tests — expect all pass**

```bash
python -m pytest tests/test_tts_router.py -v
```

Expected: 5 tests pass (no module reloads needed anymore).

- [ ] **Step 5: Commit**

```bash
git add pipeline/tts_router.py tests/test_tts_router.py
git commit -m "feat: migrate tts_router to read voice IDs from api_keys.json"
```

---

## Task 7: Migrate pipeline/pexels_client.py

**Files:**
- Modify: `pipeline/pexels_client.py`

- [ ] **Step 1: Read current state**

```bash
grep -n "PEXELS_API_KEY\|os.environ" pipeline/pexels_client.py | head -10
```

You will see `PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")` at module level (~line 20) and it referenced in `search_and_download()`.

- [ ] **Step 2: Update pexels_client.py**

Remove the module-level constant:

```python
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
```

Add import (after existing imports):

```python
from config.api_config import get_config
```

Inside `search_and_download()`, replace:

```python
if not PEXELS_API_KEY:
    logger.warning("[Pexels] PEXELS_API_KEY not set — skipping")
    return None
```

with:

```python
pexels_key = get_config()["pexels"]["api_key"]
if not pexels_key:
    logger.warning("[Pexels] pexels.api_key not configured — skipping")
    return None
```

Replace every subsequent `PEXELS_API_KEY` in the function with `pexels_key`.

- [ ] **Step 3: Verify**

```bash
grep -n "PEXELS_API_KEY\|os.environ" pipeline/pexels_client.py
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add pipeline/pexels_client.py
git commit -m "feat: migrate pexels_client to read key from api_keys.json"
```

---

## Task 8: Migrate pipeline/music_providers/suno_provider.py

**Files:**
- Modify: `pipeline/music_providers/suno_provider.py`

- [ ] **Step 1: Read current state**

```bash
grep -n "SUNO_MODEL\|SUNO_API_KEY\|os.environ" pipeline/music_providers/suno_provider.py
```

You will see `SUNO_MODEL = "V4_5"` at module level (~line 7) and `self._key = os.environ.get("SUNO_API_KEY", "")` in `__init__`.

- [ ] **Step 2: Update suno_provider.py**

Remove the module-level constant `SUNO_MODEL = "V4_5"`.

Add import after existing imports:

```python
from config.api_config import get_config
```

In `SunoProvider.__init__`, replace:

```python
self._key = os.environ.get("SUNO_API_KEY", "")
if not self._key:
    raise RuntimeError("SUNO_API_KEY is not set")
```

with:

```python
cfg = get_config()
self._key = cfg["suno"]["api_key"]
self._model = cfg["suno"]["model"]
if not self._key:
    raise RuntimeError("Suno API key is not configured in config/api_keys.json")
```

Find the payload line `"model": SUNO_MODEL,` and replace with:

```python
"model": self._model,
```

- [ ] **Step 3: Verify**

```bash
grep -n "SUNO_MODEL\|SUNO_API_KEY\|os.environ" pipeline/music_providers/suno_provider.py
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add pipeline/music_providers/suno_provider.py
git commit -m "feat: migrate suno_provider to read key/model from api_keys.json"
```

---

## Task 9: Rewrite console/backend/services/llm_service.py

**Files:**
- Modify: `console/backend/services/llm_service.py`

This task replaces the entire file content. The new service: reads/writes via `api_config`, checks provider status per use-case, fetches quota from ElevenLabs API + DB + Pexels ping.

- [ ] **Step 1: Write new llm_service.py**

Replace the entire file with:

```python
"""LLMService — config CRUD + per-provider status and quota."""
import logging
from datetime import datetime, timezone

import httpx

from config import api_config

logger = logging.getLogger(__name__)


def _mask(key: str) -> str:
    if not key:
        return ""
    return "••••" + key[-4:] if len(key) > 4 else "••••"


def _mask_config(cfg: dict) -> dict:
    import copy
    masked = copy.deepcopy(cfg)
    for use_case in ("script", "media", "music"):
        if use_case in masked.get("gemini", {}):
            masked["gemini"][use_case]["api_key"] = _mask(
                cfg["gemini"][use_case].get("api_key", "")
            )
    for provider in ("elevenlabs", "suno", "pexels"):
        if provider in masked:
            masked[provider]["api_key"] = _mask(
                cfg[provider].get("api_key", "")
            )
    return masked


class LLMService:

    def get_config_masked(self) -> dict:
        return _mask_config(api_config.get_config())

    def get_config_raw(self) -> dict:
        return api_config.get_config()

    def save_config(self, data: dict) -> None:
        api_config.save_config(data)

    def get_status(self) -> dict:
        cfg = api_config.get_config()
        g = cfg.get("gemini", {})
        return {
            "gemini": {
                "script": self._gemini_script_status(g.get("script", {})),
                "media":  self._simple_status(g.get("media", {}).get("api_key", ""), g.get("media", {}).get("model", "")),
                "music":  self._simple_status(g.get("music", {}).get("api_key", ""), g.get("music", {}).get("model", "")),
            },
            "elevenlabs": self._simple_status(cfg.get("elevenlabs", {}).get("api_key", "")),
            "suno":       self._simple_status(cfg.get("suno", {}).get("api_key", "")),
            "pexels":     self._simple_status(cfg.get("pexels", {}).get("api_key", "")),
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }

    def get_quota(self, db=None) -> dict:
        cfg = api_config.get_config()
        result = {}

        # Gemini script — Redis-based rate limiter
        try:
            from rag.rate_limiter import get_gemini_limiter
            result["gemini_script"] = get_gemini_limiter().usage()
        except Exception as e:
            result["gemini_script"] = {"error": str(e)}

        # ElevenLabs — subscription endpoint
        el_key = cfg.get("elevenlabs", {}).get("api_key", "")
        if el_key:
            try:
                resp = httpx.get(
                    "https://api.elevenlabs.io/v1/user/subscription",
                    headers={"xi-api-key": el_key},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                result["elevenlabs"] = {
                    "characters_used":  data.get("character_count", 0),
                    "characters_limit": data.get("character_limit", 0),
                }
            except Exception as e:
                result["elevenlabs"] = {"error": str(e)}
        else:
            result["elevenlabs"] = {"error": "API key not configured"}

        # Suno — count from DB
        if db is not None:
            try:
                from database.models import MusicTrack
                count = db.query(MusicTrack).filter(MusicTrack.provider == "suno").count()
                result["suno"] = {"tracks_generated": count}
            except Exception as e:
                result["suno"] = {"error": str(e)}
        else:
            result["suno"] = {"tracks_generated": None}

        # Pexels — lightweight ping
        pexels_key = cfg.get("pexels", {}).get("api_key", "")
        if pexels_key:
            try:
                resp = httpx.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": "nature", "per_page": 1},
                    headers={"Authorization": pexels_key},
                    timeout=10,
                )
                resp.raise_for_status()
                result["pexels"] = {"status": "ok"}
            except Exception as e:
                result["pexels"] = {"status": str(e)}
        else:
            result["pexels"] = {"status": "API key not configured"}

        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _gemini_script_status(self, script_cfg: dict) -> dict:
        api_key = script_cfg.get("api_key", "")
        model   = script_cfg.get("model", "")
        if not api_key:
            return {"api_key_set": False, "available": False, "model": model, "models": []}
        try:
            models = self._fetch_gemini_models(api_key)
            return {"api_key_set": True, "available": True, "model": model, "models": models}
        except Exception as e:
            return {"api_key_set": True, "available": False, "model": model, "models": [], "error": str(e)}

    def _simple_status(self, api_key: str, model: str = "") -> dict:
        key_set = bool(api_key)
        result = {"api_key_set": key_set, "available": key_set}
        if model:
            result["model"] = model
        return result

    def _fetch_gemini_models(self, api_key: str) -> list[str]:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            names = []
            for m in client.models.list():
                name = getattr(m, "name", "") or ""
                supported = getattr(m, "supported_actions", None) or getattr(m, "supportedActions", None)
                if supported is not None:
                    if "generateContent" not in supported:
                        continue
                elif "gemini" not in name.lower() or "embedding" in name.lower():
                    continue
                names.append(name.replace("models/", ""))
            return sorted(set(names))
        except Exception as e:
            logger.warning("Could not fetch Gemini model list: %s", e)
            return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
```

- [ ] **Step 2: Verify imports**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -c "from console.backend.services.llm_service import LLMService; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add console/backend/services/llm_service.py
git commit -m "feat: rewrite llm_service with per-provider status, config CRUD, and quota"
```

---

## Task 10: Extend console/backend/routers/llm.py

**Files:**
- Modify: `console/backend/routers/llm.py`

- [ ] **Step 1: Replace routers/llm.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.llm_service import LLMService

router = APIRouter(prefix="/llm", tags=["llm"])


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
```

- [ ] **Step 2: Verify the router starts**

```bash
python -c "
from console.backend.routers.llm import router
routes = [r.path for r in router.routes]
print(routes)
"
```

Expected output includes: `['/llm/status', '/llm/quota', '/llm/config', '/llm/config/raw', '/llm/config']`

- [ ] **Step 3: Commit**

```bash
git add console/backend/routers/llm.py
git commit -m "feat: add config/config-raw/save endpoints to llm router"
```

---

## Task 11: Rewrite console/frontend/src/pages/LLMPage.jsx

**Files:**
- Modify: `console/frontend/src/pages/LLMPage.jsx`

This is the largest task. The page becomes six self-contained provider cards. Read the full existing file first to understand the Toast/showToast pattern, then replace it entirely.

- [ ] **Step 1: Read the existing component structure**

```bash
grep -n "useState\|useEffect\|showToast\|fetchApi" console/frontend/src/pages/LLMPage.jsx
```

Note the `showToast` helper and `toastTimer` ref pattern — you will reuse it.

- [ ] **Step 2: Replace LLMPage.jsx**

```jsx
import { useState, useEffect, useRef } from 'react'
import { Card, Button, Select, Spinner, Toast, ProgressBar } from '../components/index.jsx'
import { fetchApi } from '../api/client.js'

const GEMINI_MEDIA_MODELS = ['veo-3.1-lite-generate-preview', 'veo-2.0-flash', 'veo-2.0-flash-lite']
const GEMINI_MUSIC_MODELS = ['lyria-3-clip-preview', 'lyria-3-pro-preview']
const ELEVENLABS_MODELS   = ['eleven_multilingual_v2', 'eleven_turbo_v2', 'eleven_monolingual_v1']
const SUNO_MODELS         = ['V4_5', 'V4', 'V3_5']

function KeyInput({ value, onChange, placeholder = '••••••••' }) {
  const [shown, setShown] = useState(false)
  return (
    <div className="flex gap-2 items-center">
      <input
        type={shown ? 'text' : 'password'}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 bg-[#16161a] border border-[#2a2a32] rounded px-3 py-1.5 text-sm font-mono text-[#e8e8f0] placeholder-[#5a5a70] focus:outline-none focus:border-[#7c6af7]"
      />
      <button
        type="button"
        onClick={() => setShown(s => !s)}
        className="text-xs text-[#9090a8] hover:text-[#e8e8f0] px-2"
      >
        {shown ? 'hide' : 'show'}
      </button>
    </div>
  )
}

function StatusDot({ available }) {
  return (
    <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 inline-block ${available ? 'bg-[#34d399]' : 'bg-[#f87171]'}`} />
  )
}

export default function LLMPage() {
  const [formData, setFormData] = useState(null)
  const [status,   setStatus]   = useState(null)
  const [quota,    setQuota]    = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(null)  // 'script'|'media'|'music'|'elevenlabs'|'suno'|'pexels'
  const [toast,    setToast]    = useState(null)
  const timerRef = useRef(null)

  const showToast = (msg, type = 'success') => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setToast({ msg, type })
    timerRef.current = setTimeout(() => setToast(null), 3000)
  }

  const load = async () => {
    setLoading(true)
    try {
      const [cfg, st, q] = await Promise.all([
        fetchApi('/api/llm/config/raw'),
        fetchApi('/api/llm/status'),
        fetchApi('/api/llm/quota'),
      ])
      setFormData(cfg)
      setStatus(st)
      setQuota(q)
    } catch (e) {
      showToast(e.message || 'Failed to load config', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current) }, [])

  const patch = (path, value) => {
    setFormData(prev => {
      const next = JSON.parse(JSON.stringify(prev))
      const keys = path.split('.')
      let obj = next
      for (let i = 0; i < keys.length - 1; i++) obj = obj[keys[i]]
      obj[keys[keys.length - 1]] = value
      return next
    })
  }

  const saveCard = async (cardKey) => {
    setSaving(cardKey)
    try {
      await fetchApi('/api/llm/config', { method: 'PUT', body: JSON.stringify(formData) })
      showToast(`${cardKey} settings saved`)
      // Refresh status after save
      const st = await fetchApi('/api/llm/status')
      setStatus(st)
    } catch (e) {
      showToast(e.message || 'Save failed', 'error')
    } finally {
      setSaving(null)
    }
  }

  if (loading || !formData) return (
    <div className="flex items-center justify-center h-64"><Spinner /></div>
  )

  const g  = formData.gemini || {}
  const el = formData.elevenlabs || {}
  const su = formData.suno || {}
  const px = formData.pexels || {}
  const st = status || {}
  const q  = quota  || {}

  return (
    <div className="space-y-5 max-w-2xl">

      {/* Gemini — Script */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.gemini?.script?.available} />
          Gemini — Script
        </span>
      } actions={saving === 'script' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={g.script?.api_key || ''} onChange={v => patch('gemini.script.api_key', v)} />
          <Select
            label="Model"
            value={g.script?.model || ''}
            onChange={e => patch('gemini.script.model', e.target.value)}
            options={(st.gemini?.script?.models?.length
              ? st.gemini.script.models
              : ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro']
            ).map(m => ({ value: m, label: m }))}
          />
          {q.gemini_script && !q.gemini_script.error && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="bg-[#16161a] rounded-lg p-3 border border-[#2a2a32]">
                <div className="text-[#9090a8] text-xs mb-1">Requests / Min</div>
                <div className="font-mono text-[#e8e8f0]">{q.gemini_script.rpm ?? '—'} <span className="text-[#5a5a70] text-xs">/ {q.gemini_script.rpm_limit ?? '—'}</span></div>
              </div>
              <div className="bg-[#16161a] rounded-lg p-3 border border-[#2a2a32]">
                <div className="text-[#9090a8] text-xs mb-1">Requests / Day</div>
                <div className="font-mono text-[#e8e8f0]">{q.gemini_script.rpd ?? '—'} <span className="text-[#5a5a70] text-xs">/ {q.gemini_script.rpd_limit ?? '—'}</span></div>
              </div>
            </div>
          )}
          <Button size="sm" onClick={() => saveCard('script')}>Save</Button>
        </div>
      </Card>

      {/* Gemini — Media (Veo) */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.gemini?.media?.available} />
          Gemini — Media (Veo)
        </span>
      } actions={saving === 'media' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={g.media?.api_key || ''} onChange={v => patch('gemini.media.api_key', v)} />
          <Select
            label="Model"
            value={g.media?.model || ''}
            onChange={e => patch('gemini.media.model', e.target.value)}
            options={GEMINI_MEDIA_MODELS.map(m => ({ value: m, label: m }))}
          />
          <p className="text-[10px] text-[#5a5a70] font-mono">Quota managed by Google AI Studio</p>
          <Button size="sm" onClick={() => saveCard('media')}>Save</Button>
        </div>
      </Card>

      {/* Gemini — Music (Lyria) */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.gemini?.music?.available} />
          Gemini — Music (Lyria)
        </span>
      } actions={saving === 'music' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={g.music?.api_key || ''} onChange={v => patch('gemini.music.api_key', v)} />
          <Select
            label="Model"
            value={g.music?.model || ''}
            onChange={e => patch('gemini.music.model', e.target.value)}
            options={GEMINI_MUSIC_MODELS.map(m => ({ value: m, label: m }))}
          />
          <p className="text-[10px] text-[#5a5a70] font-mono">Quota managed by Google AI Studio</p>
          <Button size="sm" onClick={() => saveCard('music')}>Save</Button>
        </div>
      </Card>

      {/* ElevenLabs */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.elevenlabs?.available} />
          ElevenLabs
        </span>
      } actions={saving === 'elevenlabs' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={el.api_key || ''} onChange={v => patch('elevenlabs.api_key', v)} />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-[#9090a8] block mb-1">Voice ID (EN)</label>
              <input
                type="text"
                value={el.voice_id_en || ''}
                onChange={e => patch('elevenlabs.voice_id_en', e.target.value)}
                placeholder="voice ID"
                className="w-full bg-[#16161a] border border-[#2a2a32] rounded px-3 py-1.5 text-sm font-mono text-[#e8e8f0] placeholder-[#5a5a70] focus:outline-none focus:border-[#7c6af7]"
              />
            </div>
            <div>
              <label className="text-xs text-[#9090a8] block mb-1">Voice ID (VI)</label>
              <input
                type="text"
                value={el.voice_id_vi || ''}
                onChange={e => patch('elevenlabs.voice_id_vi', e.target.value)}
                placeholder="voice ID"
                className="w-full bg-[#16161a] border border-[#2a2a32] rounded px-3 py-1.5 text-sm font-mono text-[#e8e8f0] placeholder-[#5a5a70] focus:outline-none focus:border-[#7c6af7]"
              />
            </div>
          </div>
          <Select
            label="Model"
            value={el.model || ''}
            onChange={e => patch('elevenlabs.model', e.target.value)}
            options={ELEVENLABS_MODELS.map(m => ({ value: m, label: m }))}
          />
          {q.elevenlabs && !q.elevenlabs.error && (
            <div>
              <div className="flex justify-between text-xs text-[#9090a8] mb-1">
                <span>Characters this month</span>
                <span className="font-mono">{q.elevenlabs.characters_used?.toLocaleString()} / {q.elevenlabs.characters_limit?.toLocaleString()}</span>
              </div>
              <ProgressBar value={q.elevenlabs.characters_used} max={q.elevenlabs.characters_limit} />
            </div>
          )}
          {q.elevenlabs?.error && <p className="text-xs text-[#f87171] font-mono">{q.elevenlabs.error}</p>}
          <Button size="sm" onClick={() => saveCard('elevenlabs')}>Save</Button>
        </div>
      </Card>

      {/* Suno */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.suno?.available} />
          Suno
        </span>
      } actions={saving === 'suno' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={su.api_key || ''} onChange={v => patch('suno.api_key', v)} />
          <Select
            label="Model"
            value={su.model || ''}
            onChange={e => patch('suno.model', e.target.value)}
            options={SUNO_MODELS.map(m => ({ value: m, label: m }))}
          />
          {q.suno?.tracks_generated != null && (
            <p className="text-xs text-[#9090a8] font-mono">{q.suno.tracks_generated} tracks generated</p>
          )}
          {q.suno?.error && <p className="text-xs text-[#f87171] font-mono">{q.suno.error}</p>}
          <Button size="sm" onClick={() => saveCard('suno')}>Save</Button>
        </div>
      </Card>

      {/* Pexels */}
      <Card title={
        <span className="flex items-center gap-2">
          <StatusDot available={st.pexels?.available} />
          Pexels
        </span>
      } actions={saving === 'pexels' && <Spinner size={16} />}>
        <div className="space-y-3">
          <label className="text-xs text-[#9090a8]">API Key</label>
          <KeyInput value={px.api_key || ''} onChange={v => patch('pexels.api_key', v)} />
          {q.pexels?.status === 'ok'
            ? <p className="text-xs text-[#34d399] font-mono">Connected ✓</p>
            : q.pexels?.status
              ? <p className="text-xs text-[#f87171] font-mono">{q.pexels.status}</p>
              : null
          }
          <Button size="sm" onClick={() => saveCard('pexels')}>Save</Button>
        </div>
      </Card>

      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
```

- [ ] **Step 3: Start the dev server and verify the page loads**

In one terminal:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 --reload
```

In another:
```bash
cd console/frontend && npm run dev
```

Open `http://localhost:5173`, log in as admin, navigate to LLM tab.

Expected: Six cards visible. Each has an API key input with hide/show toggle. Status dots show red (no keys configured yet). No console errors.

- [ ] **Step 4: Create config/api_keys.json from example and enter one key**

```bash
cp config/api_keys.json.example config/api_keys.json
```

Open the LLM page, enter a real Gemini Script API key in the Script card, click Save. Expected: toast "script settings saved", status dot turns green.

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/LLMPage.jsx
git commit -m "feat: rewrite LLM page with six provider cards and per-card save"
```

---

## Self-Review Against Spec

| Spec Requirement | Task |
|---|---|
| JSON config at `config/api_keys.json` | Task 1 |
| `.gitignore` + `.example` file | Task 1 |
| `get_config()` with 30s cache and missing-file fallback | Task 1 |
| `save_config()` busts cache | Task 1 |
| Migrate `rag/llm_router.py` | Task 2 |
| Migrate `pipeline/veo_client.py` (media key + model) | Task 3 |
| Migrate `pipeline/music_providers/lyria_provider.py` (music key) | Task 4 |
| Migrate `pipeline/elevenlabs_tts.py` (key + model) | Task 5 |
| Migrate `pipeline/tts_router.py` (voice IDs) | Task 6 |
| Migrate `pipeline/pexels_client.py` | Task 7 |
| Migrate `pipeline/music_providers/suno_provider.py` (key + model) | Task 8 |
| `GET /api/llm/config` masked | Task 10 |
| `GET /api/llm/config/raw` unmasked | Task 10 |
| `PUT /api/llm/config` saves JSON | Task 9 + 10 |
| `GET /api/llm/status` per-use-case Gemini + all providers | Task 9 |
| `GET /api/llm/quota` — Gemini RPM/RPD, ElevenLabs chars, Suno DB count, Pexels ping | Task 9 |
| Admin-only for config endpoints | Task 10 |
| 6 provider cards with masked key input, model selector, save button | Task 11 |
| ElevenLabs usage progress bar | Task 11 |
| Gemini Media/Music: "Quota managed by Google AI Studio" note | Task 11 |
| Gemini Script: dynamic model list from API | Task 11 (reads from status.gemini.script.models) |
