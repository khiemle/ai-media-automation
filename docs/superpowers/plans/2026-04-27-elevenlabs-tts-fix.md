# ElevenLabs TTS Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the ElevenLabs TTS 404 error caused by Kokoro voice names being passed to the ElevenLabs API, and migrate from raw httpx calls to the official ElevenLabs Python SDK.

**Architecture:** Pass `tts_service` from `script_json.video` through the composer → tts_router call chain so the router knows whether `voice_id` is an ElevenLabs UUID or a Kokoro voice name. Legacy scripts (no `tts_service`) always fall back to the configured ElevenLabs voice from `api_keys.json`. The SDK replaces httpx in `elevenlabs_tts.py` but the WAV-writing logic stays the same.

**Tech Stack:** Python · ElevenLabs Python SDK (`elevenlabs>=2.44.0`) · soundfile · numpy · pytest · unittest.mock

---

## File Map

| File | Action | Change |
|---|---|---|
| `requirements.pipeline.txt` | Modify | Add `elevenlabs>=2.44.0` |
| `pipeline/composer.py` | Modify | Pass `tts_service` to `generate_tts()`; change default `voice_id` from `"af_heart"` to `""` |
| `pipeline/tts_router.py` | Modify | Add `tts_service` param; fix engine + voice resolution |
| `pipeline/elevenlabs_tts.py` | Modify | Replace httpx with ElevenLabs SDK |
| `tests/test_tts_router.py` | Modify | Add tests for `tts_service` routing |

---

## Task 1: Install ElevenLabs SDK

**Files:**
- Modify: `requirements.pipeline.txt`

- [ ] **Step 1: Add the SDK to requirements**

Open `requirements.pipeline.txt`. The current TTS section looks like:

```
# ── TTS ────────────────────────────────────────────────────
kokoro-onnx>=0.4.0                  # Kokoro TTS ONNX inference (requires numpy>=2.0.2)
onnxruntime>=1.18.0                 # ONNX runtime (CPU)
soundfile>=0.12.1                   # WAV file read/write
scipy>=1.13.0                       # Audio resampling (44.1kHz)
numpy>=2.0.2                        # Required by kokoro-onnx 0.4.0
```

Add `elevenlabs>=2.44.0` to that section:

```
# ── TTS ────────────────────────────────────────────────────
kokoro-onnx>=0.4.0                  # Kokoro TTS ONNX inference (requires numpy>=2.0.2)
onnxruntime>=1.18.0                 # ONNX runtime (CPU)
soundfile>=0.12.1                   # WAV file read/write
scipy>=1.13.0                       # Audio resampling (44.1kHz)
numpy>=2.0.2                        # Required by kokoro-onnx 0.4.0
elevenlabs>=2.44.0                  # ElevenLabs TTS SDK
```

- [ ] **Step 2: Install it**

```bash
pip install "elevenlabs>=2.44.0"
```

Expected: `Successfully installed elevenlabs-2.44.0` (or similar).

- [ ] **Step 3: Verify import works**

```bash
python -c "from elevenlabs.client import ElevenLabs; from elevenlabs import VoiceSettings; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add requirements.pipeline.txt
git commit -m "chore: add elevenlabs Python SDK to pipeline requirements"
```

---

## Task 2: Fix `tts_router.py` — add `tts_service` param and fix voice resolution

**Files:**
- Modify: `pipeline/tts_router.py`
- Modify: `tests/test_tts_router.py`

- [ ] **Step 1: Write failing tests for the new `tts_service` behaviour**

Append these tests to `tests/test_tts_router.py`. The existing `_FAKE_CONFIG` at the top of that file is already defined — reuse it, don't redefine it.

```python
def test_explicit_elevenlabs_service_uses_voice_id(tmp_path):
    """When tts_service='elevenlabs', the passed voice_id is used as-is (ElevenLabs UUID)."""
    out = tmp_path / "out.wav"
    cfg = {**_FAKE_CONFIG}
    with patch("pipeline.tts_router.get_config", return_value=cfg), \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
        mock_el.return_value = out
        from pipeline.tts_router import generate_tts
        generate_tts(
            text="Hello",
            voice_id="56AoDkrOh6qfVPDXZ7Pt",
            speed=1.0,
            language="english",
            output_path=str(out),
            tts_service="elevenlabs",
        )
    mock_el.assert_called_once()
    call_args = mock_el.call_args
    assert call_args.args[1] == "56AoDkrOh6qfVPDXZ7Pt"


def test_explicit_kokoro_service_skips_elevenlabs(tmp_path):
    """When tts_service='kokoro', Kokoro is used even for Vietnamese language."""
    out = tmp_path / "out.wav"
    import importlib
    from pipeline import tts_router
    importlib.reload(tts_router)
    with patch.object(tts_router, "_kokoro_generate", return_value=out) as mock_kokoro, \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
        result = tts_router.generate_tts(
            text="Xin chào",
            voice_id="af_heart",
            speed=1.0,
            language="vietnamese",
            output_path=str(out),
            tts_service="kokoro",
        )
    mock_kokoro.assert_called_once()
    mock_el.assert_not_called()
    assert result == out


def test_legacy_vietnamese_ignores_kokoro_voice_id(tmp_path):
    """Legacy path (no tts_service): Vietnamese → ElevenLabs uses config voice, not af_heart."""
    out = tmp_path / "out.wav"
    with patch("pipeline.tts_router.get_config", return_value=_FAKE_CONFIG), \
         patch.dict(os.environ, {"TTS_ENGINE": "auto"}), \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
        mock_el.return_value = out
        from pipeline.tts_router import generate_tts
        generate_tts(
            text="Xin chào",
            voice_id="af_heart",   # Kokoro name — must NOT be passed to ElevenLabs
            speed=1.0,
            language="vietnamese",
            output_path=str(out),
            # tts_service not passed → legacy path
        )
    mock_el.assert_called_once()
    call_args = mock_el.call_args
    # Should use config voice_id_vi, not "af_heart"
    assert call_args.args[1] == "vi-voice-id"
    assert call_args.args[1] != "af_heart"


def test_legacy_english_elevenlabs_mode_uses_config_voice(tmp_path):
    """Legacy path with TTS_ENGINE=elevenlabs and English: uses config voice_id_en, not af_heart."""
    out = tmp_path / "out.wav"
    with patch("pipeline.tts_router.get_config", return_value=_FAKE_CONFIG), \
         patch.dict(os.environ, {"TTS_ENGINE": "elevenlabs"}), \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
        mock_el.return_value = out
        from pipeline.tts_router import generate_tts
        generate_tts(
            text="Hello",
            voice_id="af_heart",
            speed=1.0,
            language="english",
            output_path=str(out),
        )
    call_args = mock_el.call_args
    assert call_args.args[1] == "en-voice-id"
    assert call_args.args[1] != "af_heart"


def test_explicit_elevenlabs_empty_voice_falls_back_to_config(tmp_path):
    """When tts_service='elevenlabs' but voice_id is empty, falls back to config voice."""
    out = tmp_path / "out.wav"
    with patch("pipeline.tts_router.get_config", return_value=_FAKE_CONFIG), \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs") as mock_el:
        mock_el.return_value = out
        from pipeline.tts_router import generate_tts
        generate_tts(
            text="Xin chào",
            voice_id="",
            speed=1.0,
            language="vietnamese",
            output_path=str(out),
            tts_service="elevenlabs",
        )
    call_args = mock_el.call_args
    assert call_args.args[1] in ("vi-voice-id", "en-voice-id")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_tts_router.py::test_explicit_elevenlabs_service_uses_voice_id tests/test_tts_router.py::test_explicit_kokoro_service_skips_elevenlabs tests/test_tts_router.py::test_legacy_vietnamese_ignores_kokoro_voice_id tests/test_tts_router.py::test_legacy_english_elevenlabs_mode_uses_config_voice tests/test_tts_router.py::test_explicit_elevenlabs_empty_voice_falls_back_to_config -v 2>&1 | tail -15
```

Expected: all 5 fail — `generate_tts()` does not accept `tts_service` yet.

- [ ] **Step 3: Rewrite `pipeline/tts_router.py`**

Replace the entire file content:

```python
"""
TTS Router — dispatches to ElevenLabs or Kokoro.

Engine selection priority:
  1. tts_service kwarg ('kokoro' | 'elevenlabs') — explicit per-script choice
  2. TTS_ENGINE env var ('auto' | 'kokoro' | 'elevenlabs') + language heuristic — legacy fallback
"""
import logging
import os
from pathlib import Path

import pipeline.elevenlabs_tts  # register in sys.modules so it can be patched in tests
from config.api_config import get_config

logger = logging.getLogger(__name__)

TTS_ENGINE = os.environ.get("TTS_ENGINE", "auto")


def generate_tts(
    text:        str,
    voice_id:    str,
    speed:       float,
    language:    str,
    output_path: str,
    tts_service: str = "",
) -> Path:
    """
    Generate TTS audio and write to output_path (WAV).

    tts_service ('kokoro' | 'elevenlabs' | ''):
      - 'kokoro'     → always Kokoro; voice_id is a Kokoro voice name
      - 'elevenlabs' → always ElevenLabs; voice_id is an ElevenLabs UUID
      - ''           → legacy: use TTS_ENGINE env var + language heuristic;
                       voice_id is ignored for ElevenLabs (could be a Kokoro name)

    Raises RuntimeError on failure.
    """
    if tts_service == "kokoro":
        return _kokoro_generate(text, voice_id, speed, output_path)

    if tts_service == "elevenlabs":
        use_elevenlabs = True
    else:
        # Legacy: env var + language heuristic
        use_elevenlabs = (
            TTS_ENGINE == "elevenlabs"
            or (TTS_ENGINE == "auto" and language == "vietnamese")
        )

    if use_elevenlabs:
        cfg = get_config()
        if not cfg["elevenlabs"]["api_key"]:
            raise RuntimeError("ElevenLabs API key is not configured in config/api_keys.json")

        if tts_service == "elevenlabs":
            # voice_id from script is an ElevenLabs UUID — use it, fall back to config if empty
            voice = voice_id or cfg["elevenlabs"]["voice_id_vi"] or cfg["elevenlabs"]["voice_id_en"]
        else:
            # Legacy path: don't trust voice_id — it may be a Kokoro voice name
            if language == "vietnamese":
                voice = cfg["elevenlabs"]["voice_id_vi"] or cfg["elevenlabs"]["voice_id_en"]
            else:
                voice = cfg["elevenlabs"]["voice_id_en"] or cfg["elevenlabs"]["voice_id_vi"]

        if not voice:
            raise RuntimeError(
                "No ElevenLabs voice ID configured. Set voice_id_en / voice_id_vi in config/api_keys.json"
            )

        from pipeline.elevenlabs_tts import generate_tts_elevenlabs
        return generate_tts_elevenlabs(text, voice, speed, output_path)

    return _kokoro_generate(text, voice_id, speed, output_path)


def _kokoro_generate(text: str, voice_id: str, speed: float, output_path: str) -> Path:
    from pipeline.tts_engine import generate_tts as kokoro_tts
    return kokoro_tts(text=text, voice=voice_id, speed=speed, output_path=output_path)
```

- [ ] **Step 4: Run all tts_router tests**

```bash
python -m pytest tests/test_tts_router.py -v 2>&1 | tail -20
```

Expected: all 9 tests pass (4 existing + 5 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline/tts_router.py tests/test_tts_router.py
git commit -m "fix: add tts_service param to tts_router — Kokoro voice IDs no longer reach ElevenLabs"
```

---

## Task 3: Fix `pipeline/composer.py` — pass `tts_service`, fix default `voice_id`

**Files:**
- Modify: `pipeline/composer.py` (line ~97)

- [ ] **Step 1: Locate the `generate_tts` call in `_process_scene()`**

Run:

```bash
grep -n "generate_tts\|voice_id\|tts_service" /Volumes/SSD/Workspace/ai-media-automation/pipeline/composer.py
```

Confirm the call is around line 95-101 and looks like:

```python
generate_tts(
    text=scene.get("narration", ""),
    voice_id=video_cfg.get("voice", "af_heart"),
    speed=float(video_cfg.get("voice_speed", 1.1)),
    language=meta.get("language", "vietnamese"),
    output_path=str(audio_path),
)
```

- [ ] **Step 2: Update the call to pass `tts_service` and fix the default `voice_id`**

Replace that block with:

```python
generate_tts(
    text=scene.get("narration", ""),
    voice_id=video_cfg.get("voice", ""),
    speed=float(video_cfg.get("voice_speed", 1.1)),
    language=meta.get("language", "vietnamese"),
    output_path=str(audio_path),
    tts_service=video_cfg.get("tts_service", ""),
)
```

Two changes:
- `voice_id` default: `"af_heart"` → `""` (empty forces config fallback in the router)
- Added: `tts_service=video_cfg.get("tts_service", "")`

- [ ] **Step 3: Run the full test suite to check for regressions**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add pipeline/composer.py
git commit -m "fix: pass tts_service from script_json to generate_tts in composer"
```

---

## Task 4: Migrate `pipeline/elevenlabs_tts.py` to the ElevenLabs SDK

**Files:**
- Modify: `pipeline/elevenlabs_tts.py`

- [ ] **Step 1: Verify the existing `test_normalize_text_expands_currency` test still passes before touching the file**

```bash
python -m pytest tests/test_tts_router.py::test_normalize_text_expands_currency -v
```

Expected: PASS. (This test imports `_normalize_text` from `elevenlabs_tts` — it must keep passing after the rewrite.)

- [ ] **Step 2: Rewrite `pipeline/elevenlabs_tts.py`**

Replace the entire file:

```python
"""
ElevenLabs TTS client — uses the official ElevenLabs Python SDK.
Output: 44.1kHz mono WAV via soundfile.
"""
import logging
import re
from pathlib import Path

from config.api_config import get_config

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100  # pcm_44100 output


def _normalize_text(text: str) -> str:
    """Expand Vietnamese abbreviations for natural TTS pronunciation."""
    simple_replacements = {
        "TP.HCM": "Thành phố Hồ Chí Minh",
        "TP.HN":  "Thành phố Hà Nội",
        "&":      " và ",
        "%":      " phần trăm",
        "VND":    " đồng",
        "USD":    " đô la Mỹ",
    }
    for src, dst in simple_replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r'(?<![a-zA-ZÀ-ỹ])k(?![a-zA-ZÀ-ỹ])', ' nghìn', text)
    text = re.sub(r'(?<![a-zA-ZÀ-ỹ])tr(?![a-zA-ZÀ-ỹ])', ' triệu', text)
    return re.sub(r"\s+", " ", text).strip()


def generate_tts_elevenlabs(
    text:        str,
    voice_id:    str,
    speed:       float,
    output_path: str,
) -> Path:
    """
    Generate WAV audio from text using the ElevenLabs Python SDK.
    Raises RuntimeError on any failure.
    """
    cfg = get_config()
    api_key = cfg["elevenlabs"]["api_key"]
    if not api_key:
        raise RuntimeError("ElevenLabs API key is not configured in config/api_keys.json")
    if not voice_id:
        raise RuntimeError("voice_id is required for ElevenLabs TTS")

    text = _normalize_text(text)
    if not text:
        raise RuntimeError("TTS text is empty after normalization")

    model_id = cfg["elevenlabs"].get("model", "eleven_flash_v2_5")

    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings
    import numpy as np
    import soundfile as sf

    try:
        client = ElevenLabs(api_key=api_key)
        audio_gen = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            output_format="pcm_44100",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                speed=min(max(speed, 0.7), 1.3),
            ),
        )
        pcm_bytes = b"".join(audio_gen)
    except Exception as e:
        raise RuntimeError(f"ElevenLabs SDK error: {e}") from e

    if not pcm_bytes:
        raise RuntimeError("ElevenLabs returned empty audio content")
    if len(pcm_bytes) % 2 != 0:
        raise RuntimeError(
            f"ElevenLabs returned malformed PCM: {len(pcm_bytes)} bytes (not 16-bit aligned)"
        )

    # PCM_44100 = signed 16-bit little-endian, mono
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), samples, SAMPLE_RATE)

    logger.info(f"[ElevenLabs] Generated {output_path} ({len(samples) / SAMPLE_RATE:.1f}s)")
    return output_path
```

- [ ] **Step 3: Run the normalize text test to confirm `_normalize_text` still works**

```bash
python -m pytest tests/test_tts_router.py::test_normalize_text_expands_currency -v
```

Expected: PASS.

- [ ] **Step 4: Run the full test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 5: Smoke-test the SDK call with the real API key**

```bash
python -c "
from config.api_config import get_config
from pipeline.elevenlabs_tts import generate_tts_elevenlabs
import tempfile, os
cfg = get_config()
voice = cfg['elevenlabs']['voice_id_en'] or cfg['elevenlabs']['voice_id_vi']
if not voice:
    print('SKIP: no voice configured')
else:
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        out = f.name
    result = generate_tts_elevenlabs('Hello, this is a test.', voice, 1.0, out)
    size = os.path.getsize(out)
    print(f'OK: {result} ({size} bytes)')
    os.unlink(out)
"
```

Expected: `OK: /tmp/tmp....wav (NNNNN bytes)` with a non-zero file size.

- [ ] **Step 6: Commit**

```bash
git add pipeline/elevenlabs_tts.py
git commit -m "feat: migrate ElevenLabs TTS from httpx to official Python SDK"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Task |
|---|---|
| `composer.py` passes `tts_service` from `video_cfg` | Task 3 |
| `composer.py` default `voice_id` changed from `"af_heart"` to `""` | Task 3 |
| `tts_router.py` `tts_service` param added | Task 2 |
| `tts_router.py` explicit `tts_service="elevenlabs"` → trust `voice_id` as UUID | Task 2 |
| `tts_router.py` explicit `tts_service="kokoro"` → skip ElevenLabs entirely | Task 2 |
| `tts_router.py` legacy (no `tts_service`) → never trust `voice_id` for ElevenLabs | Task 2 |
| `tts_router.py` legacy Vietnamese → use `voice_id_vi` from config | Task 2 |
| `tts_router.py` legacy English → use `voice_id_en` from config | Task 2 |
| `elevenlabs_tts.py` uses ElevenLabs SDK instead of httpx | Task 4 |
| `elevenlabs_tts.py` `_normalize_text` preserved | Task 4 |
| `elevenlabs_tts.py` reads `model` from config | Task 4 |
| `requirements.pipeline.txt` has `elevenlabs>=2.44.0` | Task 1 |

All requirements covered. ✓

### Type consistency

- `generate_tts(tts_service: str = "")` — defined Task 2, called with `tts_service=video_cfg.get("tts_service", "")` in Task 3. ✓
- `generate_tts_elevenlabs(text, voice_id, speed, output_path)` — signature unchanged across Task 2 (mock call site) and Task 4 (implementation). ✓
- `VoiceSettings(stability, similarity_boost, speed)` — matches SDK fields confirmed from source. ✓
