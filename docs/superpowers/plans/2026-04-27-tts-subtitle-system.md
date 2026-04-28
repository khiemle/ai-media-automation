# TTS Audio Fix + Word-by-Word Subtitle System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix ElevenLabs silent audio (PCM → MP3+ffmpeg), add per-word timing extraction for both TTS engines, build an ASS subtitle file from those timings, wire it through the composer and renderer, and expose a subtitle_style picker in the script editor.

**Architecture:** The ElevenLabs client switches from raw PCM bytes to MP3+ffmpeg decode to fix silent audio. A new `convert_with_timestamps()` path returns character-level alignment alongside the audio, which is reconstructed into word timings. Kokoro audio goes through faster-whisper post-hoc to get the same word-timing format. A new `subtitle_builder.py` converts word timings into an ASS file; the composer gathers them per scene with offsets; the renderer auto-detects `subtitles.ass` and burns it in. The frontend adds a single `subtitle_style` select field to the script editor.

**Tech Stack:** Python · ElevenLabs Python SDK (`convert_with_timestamps`) · ffmpeg · faster-whisper · MoviePy · pytest · React 18 + Tailwind

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pipeline/elevenlabs_tts.py` | Modify | Fix silent audio (PCM→MP3); add `_mp3_to_wav()`, `_chars_to_words()`, `generate_tts_elevenlabs_with_timing()` |
| `pipeline/caption_gen.py` | Modify | Add `extract_word_timing()` using faster-whisper word timestamps |
| `pipeline/tts_router.py` | Modify | Extract `_use_elevenlabs()` + `_resolve_elevenlabs_voice()` helpers; add `generate_tts_with_timing()` |
| `pipeline/subtitle_builder.py` | Create | `SUBTITLE_STYLES`, `build_ass()`, `_fmt_ass_time()` |
| `pipeline/composer.py` | Modify | `_process_scene()` calls timing variant when subtitle_style set; `_assemble()` calls `build_ass()` |
| `pipeline/renderer.py` | Modify | Auto-detect `subtitles.ass`; unify SRT/ASS subtitle handling |
| `console/frontend/src/pages/ScriptsPage.jsx` | Modify | Add `subtitle_style` select field to video config section |
| `tests/test_elevenlabs_tts.py` | Create | Tests for `_mp3_to_wav`, `_chars_to_words`, `generate_tts_elevenlabs_with_timing` |
| `tests/test_subtitle_builder.py` | Create | Tests for `_fmt_ass_time`, `build_ass` |
| `tests/test_tts_router_timing.py` | Create | Tests for `generate_tts_with_timing` |
| `tests/test_renderer_ass.py` | Create | Tests for ASS subtitle auto-detection in renderer |

---

## Task 1: Fix ElevenLabs silent audio — switch from PCM to MP3+ffmpeg

The current `generate_tts_elevenlabs()` requests `output_format="pcm_44100"` and decodes with numpy. If ElevenLabs returns anything other than raw 16-bit PCM (e.g., after model changes), the numpy decode silently produces garbage or silence. Switching to MP3 + ffmpeg decode is format-safe.

**Files:**
- Modify: `pipeline/elevenlabs_tts.py`
- Create: `tests/test_elevenlabs_tts.py`

- [ ] **Step 1: Write failing tests for `_mp3_to_wav` and the updated `generate_tts_elevenlabs`**

Create `tests/test_elevenlabs_tts.py`:

```python
import base64
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest


_FAKE_CONFIG = {
    "elevenlabs": {"api_key": "test-key", "model": "eleven_flash_v2_5"},
}


def test_mp3_to_wav_calls_ffmpeg_and_deletes_temp(tmp_path):
    from pipeline.elevenlabs_tts import _mp3_to_wav
    out = tmp_path / "out.wav"
    with patch("subprocess.run") as mock_run, \
         patch("tempfile.mktemp", return_value=str(tmp_path / "tmp.mp3")):
        mock_run.return_value = MagicMock(returncode=0)
        # Create the temp file so unlink doesn't fail
        (tmp_path / "tmp.mp3").write_bytes(b"")
        _mp3_to_wav(b"fake mp3 bytes", out)
    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert "ffmpeg" in cmd
    assert str(out) in cmd


def test_mp3_to_wav_raises_on_ffmpeg_failure(tmp_path):
    from pipeline.elevenlabs_tts import _mp3_to_wav
    out = tmp_path / "out.wav"
    with patch("subprocess.run") as mock_run, \
         patch("tempfile.mktemp", return_value=str(tmp_path / "tmp.mp3")):
        (tmp_path / "tmp.mp3").write_bytes(b"")
        mock_run.return_value = MagicMock(returncode=1, stderr="ffmpeg error")
        with pytest.raises(RuntimeError, match="ffmpeg"):
            _mp3_to_wav(b"bad bytes", out)


def test_generate_tts_elevenlabs_uses_mp3_format(tmp_path):
    """generate_tts_elevenlabs() must request mp3_44100_128, not pcm_44100."""
    from pipeline.elevenlabs_tts import generate_tts_elevenlabs
    out = tmp_path / "speech.wav"
    with patch("pipeline.elevenlabs_tts.get_config", return_value=_FAKE_CONFIG), \
         patch("pipeline.elevenlabs_tts._mp3_to_wav") as mock_convert, \
         patch("pipeline.elevenlabs_tts.ElevenLabs") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.text_to_speech.convert.return_value = iter([b"fake", b"mp3"])
        result = generate_tts_elevenlabs("hello", "voice-id", 1.0, str(out))
    call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
    assert call_kwargs["output_format"] == "mp3_44100_128"
    mock_convert.assert_called_once()
    assert result == out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_elevenlabs_tts.py -v 2>&1 | tail -15
```

Expected: 3 failures — `_mp3_to_wav` and `generate_tts_elevenlabs` don't exist with these signatures yet.

- [ ] **Step 3: Add `_mp3_to_wav()` to `pipeline/elevenlabs_tts.py`**

Add these imports at the top of the file (after existing imports):

```python
import base64
import subprocess
import tempfile
```

Add this function after `_normalize_text()` and before `generate_tts_elevenlabs()`:

```python
def _mp3_to_wav(mp3_bytes: bytes, output_path: Path) -> None:
    """Write mp3_bytes to a temp file, convert to WAV via ffmpeg, delete temp."""
    tmp = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        tmp.write_bytes(mp3_bytes)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp), str(output_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg MP3→WAV failed: {result.stderr[-500:]}")
    finally:
        tmp.unlink(missing_ok=True)
```

- [ ] **Step 4: Update `generate_tts_elevenlabs()` to use MP3 + `_mp3_to_wav()`**

In `pipeline/elevenlabs_tts.py`, replace the import block and `generate_tts_elevenlabs` body.

Remove these imports from inside the function:
```python
    import numpy as np
    import soundfile as sf
```

Replace the `try` block (from `client = ElevenLabs(...)` through `sf.write(...)`) with:

```python
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings

    try:
        client = ElevenLabs(api_key=api_key)
        audio_gen = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            output_format="mp3_44100_128",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                speed=min(max(speed, 0.7), 1.3),
            ),
        )
        mp3_bytes = b"".join(audio_gen)
    except Exception as e:
        raise RuntimeError(f"ElevenLabs SDK error: {e}") from e

    if not mp3_bytes:
        raise RuntimeError("ElevenLabs returned empty audio content")

    output_path = Path(output_path)
    _mp3_to_wav(mp3_bytes, output_path)
```

Also remove the old PCM-specific block (the `if len(pcm_bytes) % 2 != 0:` check, `samples = np.frombuffer(...)`, and `sf.write(...)` lines), and update the log line:

```python
    logger.info(f"[ElevenLabs] Generated {output_path}")
    return output_path
```

- [ ] **Step 5: Run the new tests**

```bash
python -m pytest tests/test_elevenlabs_tts.py -v 2>&1 | tail -15
```

Expected: 3 PASS.

- [ ] **Step 6: Run the full test suite for regressions**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass (including `test_normalize_text_expands_currency`).

- [ ] **Step 7: Commit**

```bash
git add pipeline/elevenlabs_tts.py tests/test_elevenlabs_tts.py
git commit -m "fix: switch ElevenLabs TTS from pcm_44100+numpy to mp3_44100_128+ffmpeg"
```

---

## Task 2: Add `_chars_to_words()` and `generate_tts_elevenlabs_with_timing()`

The ElevenLabs `convert_with_timestamps()` SDK endpoint returns character-level alignment alongside the audio. This task adds the character→word reconstruction and the timing-aware TTS function.

**Files:**
- Modify: `pipeline/elevenlabs_tts.py`
- Modify: `tests/test_elevenlabs_tts.py`

- [ ] **Step 1: Write failing tests for `_chars_to_words` and `generate_tts_elevenlabs_with_timing`**

Append to `tests/test_elevenlabs_tts.py`:

```python
def test_chars_to_words_basic():
    from pipeline.elevenlabs_tts import _chars_to_words
    # "hi there" — space at index 2 flushes "hi"; final flush gives "there"
    chars  = list("hi there")
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    ends   = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    words = _chars_to_words(chars, starts, ends)
    assert len(words) == 2
    assert words[0] == {"word": "hi",    "start": 0.0, "end": 0.2}
    assert words[1] == {"word": "there", "start": 0.3, "end": 0.8}


def test_chars_to_words_trailing_space():
    from pipeline.elevenlabs_tts import _chars_to_words
    chars  = list("ok ")
    starts = [0.0, 0.1, 0.2]
    ends   = [0.1, 0.2, 0.3]
    words = _chars_to_words(chars, starts, ends)
    assert len(words) == 1
    assert words[0]["word"] == "ok"


def test_generate_tts_elevenlabs_with_timing_returns_word_list(tmp_path):
    from pipeline.elevenlabs_tts import generate_tts_elevenlabs_with_timing
    out = tmp_path / "speech.wav"
    mock_response = MagicMock()
    mock_response.audio_base64 = base64.b64encode(b"fake mp3 content").decode()
    mock_response.alignment.characters = list("hi")
    mock_response.alignment.character_start_times_seconds = [0.0, 0.1]
    mock_response.alignment.character_end_times_seconds   = [0.1, 0.2]
    with patch("pipeline.elevenlabs_tts.get_config", return_value=_FAKE_CONFIG), \
         patch("pipeline.elevenlabs_tts._mp3_to_wav") as mock_convert, \
         patch("pipeline.elevenlabs_tts.ElevenLabs") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.text_to_speech.convert_with_timestamps.return_value = mock_response
        audio_path, words = generate_tts_elevenlabs_with_timing("hi", "voice-id", 1.0, str(out))
    assert audio_path == Path(out)
    assert words == [{"word": "hi", "start": 0.0, "end": 0.2}]
    mock_convert.assert_called_once()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_elevenlabs_tts.py::test_chars_to_words_basic tests/test_elevenlabs_tts.py::test_chars_to_words_trailing_space tests/test_elevenlabs_tts.py::test_generate_tts_elevenlabs_with_timing_returns_word_list -v 2>&1 | tail -15
```

Expected: 3 failures.

- [ ] **Step 3: Add `_chars_to_words()` to `pipeline/elevenlabs_tts.py`**

Add after `_mp3_to_wav()`:

```python
def _chars_to_words(
    chars:  list[str],
    starts: list[float],
    ends:   list[float],
) -> list[dict]:
    """Reconstruct word-level timing from ElevenLabs character-level alignment."""
    words = []
    buf = []
    word_start = 0.0
    word_end = 0.0
    for ch, s, e in zip(chars, starts, ends):
        if ch == " ":
            if buf:
                words.append({"word": "".join(buf), "start": word_start, "end": word_end})
                buf = []
        else:
            if not buf:
                word_start = s
            buf.append(ch)
            word_end = e
    if buf:
        words.append({"word": "".join(buf), "start": word_start, "end": word_end})
    return words
```

- [ ] **Step 4: Add `generate_tts_elevenlabs_with_timing()` to `pipeline/elevenlabs_tts.py`**

Add after `generate_tts_elevenlabs()`:

```python
def generate_tts_elevenlabs_with_timing(
    text:        str,
    voice_id:    str,
    speed:       float,
    output_path: str,
) -> tuple[Path, list[dict]]:
    """
    Generate WAV audio + word timing via ElevenLabs convert_with_timestamps().
    Returns (output_path, word_list) where word_list is
    [{"word": str, "start": float, "end": float}, ...].
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

    try:
        client = ElevenLabs(api_key=api_key)
        response = client.text_to_speech.convert_with_timestamps(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
        )
    except Exception as e:
        raise RuntimeError(f"ElevenLabs SDK error: {e}") from e

    mp3_bytes = base64.b64decode(response.audio_base64)
    output_path = Path(output_path)
    _mp3_to_wav(mp3_bytes, output_path)

    words = _chars_to_words(
        response.alignment.characters,
        response.alignment.character_start_times_seconds,
        response.alignment.character_end_times_seconds,
    )
    logger.info(f"[ElevenLabs] Generated {output_path} with {len(words)} word timings")
    return output_path, words
```

- [ ] **Step 5: Run all elevenlabs tests**

```bash
python -m pytest tests/test_elevenlabs_tts.py -v 2>&1 | tail -15
```

Expected: all 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/elevenlabs_tts.py tests/test_elevenlabs_tts.py
git commit -m "feat: add _chars_to_words and generate_tts_elevenlabs_with_timing"
```

---

## Task 3: Add `extract_word_timing()` to `caption_gen.py`

Kokoro generates audio but has no timing API. This function runs faster-whisper on the generated WAV to extract word-level timestamps in the same format as the ElevenLabs timing path.

**Files:**
- Modify: `pipeline/caption_gen.py`

- [ ] **Step 1: Write a failing test**

Create `tests/test_caption_word_timing.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_extract_word_timing_returns_word_dicts(tmp_path):
    from pipeline.caption_gen import extract_word_timing
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")
    mock_word = MagicMock()
    mock_word.word = " hello "
    mock_word.start = 0.5
    mock_word.end = 1.0
    mock_seg = MagicMock()
    mock_seg.words = [mock_word]
    with patch("pipeline.caption_gen._get_model") as mock_get_model:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], MagicMock())
        mock_get_model.return_value = mock_model
        result = extract_word_timing(audio, "vi")
    assert result == [{"word": "hello", "start": 0.5, "end": 1.0}]
    mock_model.transcribe.assert_called_once_with(
        str(audio), language="vi", word_timestamps=True
    )


def test_extract_word_timing_returns_empty_when_model_unavailable(tmp_path):
    from pipeline.caption_gen import extract_word_timing
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")
    with patch("pipeline.caption_gen._get_model", return_value=None):
        result = extract_word_timing(audio, "vi")
    assert result == []


def test_extract_word_timing_skips_empty_words(tmp_path):
    from pipeline.caption_gen import extract_word_timing
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")
    word_ok = MagicMock()
    word_ok.word = "hi"
    word_ok.start = 0.0
    word_ok.end = 0.3
    word_blank = MagicMock()
    word_blank.word = "  "
    word_blank.start = 0.3
    word_blank.end = 0.4
    mock_seg = MagicMock()
    mock_seg.words = [word_ok, word_blank]
    with patch("pipeline.caption_gen._get_model") as mock_get:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], MagicMock())
        mock_get.return_value = mock_model
        result = extract_word_timing(audio, "en")
    assert len(result) == 1
    assert result[0]["word"] == "hi"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/test_caption_word_timing.py -v 2>&1 | tail -15
```

Expected: 3 failures — `extract_word_timing` not defined.

- [ ] **Step 3: Add `extract_word_timing()` to `pipeline/caption_gen.py`**

Add after `generate_captions()`:

```python
def extract_word_timing(audio_path: str | Path, language: str = "vi") -> list[dict]:
    """
    Transcribe audio and return word-level timestamps.
    Returns [{"word": str, "start": float, "end": float}, ...].
    Returns [] if faster-whisper is unavailable.
    """
    audio_path = Path(audio_path)
    model = _get_model()
    if model is None:
        return []
    try:
        segments, _ = model.transcribe(
            str(audio_path), language=language, word_timestamps=True
        )
        return [
            {"word": w.word.strip(), "start": w.start, "end": w.end}
            for seg in segments
            for w in (seg.words or [])
            if w.word.strip()
        ]
    except Exception as e:
        logger.error(f"[Caption] extract_word_timing failed: {e}")
        return []
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_caption_word_timing.py -v 2>&1 | tail -15
```

Expected: 3 PASS.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/caption_gen.py tests/test_caption_word_timing.py
git commit -m "feat: add extract_word_timing to caption_gen using faster-whisper"
```

---

## Task 4: Refactor `tts_router.py` — extract helpers + add `generate_tts_with_timing()`

Extract the ElevenLabs routing logic into `_use_elevenlabs()` and `_resolve_elevenlabs_voice()` so that both `generate_tts()` and the new `generate_tts_with_timing()` can reuse them without duplication.

**Files:**
- Modify: `pipeline/tts_router.py`
- Create: `tests/test_tts_router_timing.py`

- [ ] **Step 1: Write failing tests for `generate_tts_with_timing()`**

Create `tests/test_tts_router_timing.py`:

```python
import os
import pytest
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock


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


def test_generate_tts_with_timing_elevenlabs_returns_path_and_words(tmp_path):
    out = tmp_path / "out.wav"
    from pipeline import tts_router
    importlib.reload(tts_router)
    expected_words = [{"word": "hello", "start": 0.0, "end": 1.0}]
    with patch("pipeline.tts_router.get_config", return_value=_FAKE_CONFIG), \
         patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs_with_timing") as mock_timing:
        mock_timing.return_value = (out, expected_words)
        audio, words = tts_router.generate_tts_with_timing(
            text="hello",
            voice_id="vi-voice-id",
            speed=1.0,
            language="vietnamese",
            output_path=str(out),
            tts_service="elevenlabs",
        )
    assert audio == out
    assert words == expected_words
    mock_timing.assert_called_once()


def test_generate_tts_with_timing_kokoro_uses_whisper(tmp_path):
    out = tmp_path / "out.wav"
    from pipeline import tts_router
    importlib.reload(tts_router)
    expected_words = [{"word": "test", "start": 0.0, "end": 0.5}]
    with patch.object(tts_router, "_kokoro_generate", return_value=out), \
         patch("pipeline.caption_gen.extract_word_timing", return_value=expected_words) as mock_wt:
        audio, words = tts_router.generate_tts_with_timing(
            text="test",
            voice_id="af_heart",
            speed=1.0,
            language="english",
            output_path=str(out),
            tts_service="kokoro",
        )
    assert audio == out
    assert words == expected_words
    mock_wt.assert_called_once_with(out, "en")


def test_generate_tts_with_timing_auto_vietnamese_calls_elevenlabs_timing(tmp_path):
    out = tmp_path / "out.wav"
    from pipeline import tts_router
    with patch.dict(os.environ, {"TTS_ENGINE": "auto"}):
        importlib.reload(tts_router)
        with patch("pipeline.tts_router.get_config", return_value=_FAKE_CONFIG), \
             patch("pipeline.elevenlabs_tts.generate_tts_elevenlabs_with_timing") as mock_timing:
            mock_timing.return_value = (out, [])
            tts_router.generate_tts_with_timing(
                text="xin chào",
                voice_id="",
                speed=1.0,
                language="vietnamese",
                output_path=str(out),
            )
    mock_timing.assert_called_once()


def test_generate_tts_with_timing_auto_english_calls_kokoro_timing(tmp_path):
    out = tmp_path / "out.wav"
    from pipeline import tts_router
    with patch.dict(os.environ, {"TTS_ENGINE": "auto"}):
        importlib.reload(tts_router)
        with patch.object(tts_router, "_kokoro_generate", return_value=out), \
             patch("pipeline.caption_gen.extract_word_timing", return_value=[]) as mock_wt:
            tts_router.generate_tts_with_timing(
                text="hello",
                voice_id="af_heart",
                speed=1.0,
                language="english",
                output_path=str(out),
            )
    mock_wt.assert_called_once_with(out, "en")
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/test_tts_router_timing.py -v 2>&1 | tail -15
```

Expected: 4 failures — `generate_tts_with_timing` not defined.

- [ ] **Step 3: Add helpers and `generate_tts_with_timing()` to `pipeline/tts_router.py`**

Add these two private helper functions after the `TTS_ENGINE` constant and before `generate_tts()`:

```python
def _use_elevenlabs(tts_service: str, language: str) -> bool:
    """Return True if the ElevenLabs engine should handle this request."""
    if tts_service == "elevenlabs":
        return True
    if tts_service == "kokoro":
        return False
    return TTS_ENGINE == "elevenlabs" or (TTS_ENGINE == "auto" and language == "vietnamese")


def _resolve_elevenlabs_voice(cfg: dict, voice_id: str, tts_service: str, language: str) -> str:
    """Pick the correct ElevenLabs voice ID from script config or api_keys config."""
    if tts_service == "elevenlabs":
        voice = voice_id or cfg["elevenlabs"].get("voice_id_vi") or cfg["elevenlabs"].get("voice_id_en")
    elif language == "vietnamese":
        voice = cfg["elevenlabs"].get("voice_id_vi") or cfg["elevenlabs"].get("voice_id_en")
    else:
        voice = cfg["elevenlabs"].get("voice_id_en") or cfg["elevenlabs"].get("voice_id_vi")
    if not voice:
        raise RuntimeError(
            "No ElevenLabs voice ID configured. Set voice_id_en / voice_id_vi in config/api_keys.json"
        )
    return voice
```

Then add `generate_tts_with_timing()` after `generate_tts()`:

```python
def generate_tts_with_timing(
    text:        str,
    voice_id:    str,
    speed:       float,
    language:    str,
    output_path: str,
    tts_service: str = "",
) -> tuple[Path, list[dict]]:
    """
    Generate TTS audio and return (audio_path, word_timing).
    word_timing is [{"word": str, "start": float, "end": float}, ...].
    Kokoro path uses faster-whisper post-hoc; ElevenLabs uses convert_with_timestamps().
    """
    if tts_service == "kokoro" or not _use_elevenlabs(tts_service, language):
        audio = _kokoro_generate(text, voice_id, speed, output_path)
        lang_code = "vi" if language == "vietnamese" else "en"
        from pipeline.caption_gen import extract_word_timing
        return audio, extract_word_timing(audio, lang_code)

    cfg = get_config()
    if not cfg["elevenlabs"]["api_key"]:
        raise RuntimeError("ElevenLabs API key is not configured in config/api_keys.json")
    voice = _resolve_elevenlabs_voice(cfg, voice_id, tts_service, language)
    from pipeline.elevenlabs_tts import generate_tts_elevenlabs_with_timing
    return generate_tts_elevenlabs_with_timing(text, voice, speed, output_path)
```

- [ ] **Step 4: Run the new timing tests**

```bash
python -m pytest tests/test_tts_router_timing.py -v 2>&1 | tail -15
```

Expected: 4 PASS.

- [ ] **Step 5: Run the full test suite for regressions**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass (all existing tts_router tests still pass because `generate_tts()` behavior is unchanged).

- [ ] **Step 6: Commit**

```bash
git add pipeline/tts_router.py tests/test_tts_router_timing.py
git commit -m "feat: add generate_tts_with_timing to tts_router with _use_elevenlabs helper"
```

---

## Task 5: Create `pipeline/subtitle_builder.py`

This new file converts per-scene word timing lists into an ASS subtitle file that ffmpeg can burn into the video.

**Files:**
- Create: `pipeline/subtitle_builder.py`
- Create: `tests/test_subtitle_builder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_subtitle_builder.py`:

```python
from pathlib import Path
import pytest


def test_fmt_ass_time_zero():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(0.0) == "0:00:00.00"


def test_fmt_ass_time_seconds():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(1.45) == "0:00:01.45"


def test_fmt_ass_time_minutes():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(61.5) == "0:01:01.50"


def test_fmt_ass_time_hours():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(3661.0) == "1:01:01.00"


def test_build_ass_creates_file_with_dialogue(tmp_path):
    from pipeline.subtitle_builder import build_ass
    scene_word_timings = [
        (0.0, [
            {"word": "hello", "start": 1.0, "end": 2.0},
            {"word": "world", "start": 2.0, "end": 3.0},
        ]),
        (5.0, [
            {"word": "test", "start": 0.5, "end": 1.0},
        ]),
    ]
    out = tmp_path / "subtitles.ass"
    result = build_ass(scene_word_timings, out, "tiktok_yellow")
    assert result == out
    content = out.read_text()
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    # tiktok_yellow is uppercase + words_per_entry=1
    assert "HELLO" in content
    assert "WORLD" in content
    assert "TEST" in content
    # Scene 2 at offset 5.0s: "test" starts at 0.5s → absolute 5.5s
    assert "0:00:05.50" in content


def test_build_ass_groups_words_per_entry(tmp_path):
    from pipeline.subtitle_builder import build_ass
    # caption_dark has words_per_entry=4 and uppercase=False
    words = [{"word": f"word{i}", "start": float(i), "end": float(i) + 0.5} for i in range(6)]
    out = tmp_path / "subs.ass"
    build_ass([(0.0, words)], out, "caption_dark")
    content = out.read_text()
    dialogues = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 2  # 6 words / 4 per entry = 2 dialogue lines


def test_build_ass_falls_back_to_tiktok_yellow_for_unknown_style(tmp_path):
    from pipeline.subtitle_builder import build_ass
    out = tmp_path / "subs.ass"
    build_ass([(0.0, [{"word": "hi", "start": 0.0, "end": 1.0}])], out, "nonexistent_style")
    content = out.read_text()
    assert "HI" in content  # tiktok_yellow is uppercase


def test_build_ass_empty_timings_writes_empty_file(tmp_path):
    from pipeline.subtitle_builder import build_ass
    out = tmp_path / "subs.ass"
    result = build_ass([], out, "tiktok_yellow")
    assert result == out
    assert out.read_text() == ""
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/test_subtitle_builder.py -v 2>&1 | tail -15
```

Expected: 8 failures.

- [ ] **Step 3: Create `pipeline/subtitle_builder.py`**

```python
"""
ASS subtitle file builder for word-by-word subtitle burn-in.
"""
from pathlib import Path

SUBTITLE_STYLES: dict[str, dict] = {
    "tiktok_yellow": {
        "font": "Arial Black", "font_size": 90,
        "primary_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "outline_width": 5, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "tiktok_white": {
        "font": "Arial Black", "font_size": 90,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 5, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "bold_orange": {
        "font": "Arial Black", "font_size": 80,
        "primary_color": "&H0000A5FF",
        "outline_color": "&H00000000",
        "outline_width": 4, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "caption_dark": {
        "font": "Arial", "font_size": 50,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 2, "shadow": 1,
        "bold": False, "uppercase": False,
        "alignment": 2, "margin_v": 80,
        "words_per_entry": 4,
    },
    "minimal": {
        "font": "Arial", "font_size": 40,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 1, "shadow": 1,
        "bold": False, "uppercase": False,
        "alignment": 2, "margin_v": 120,
        "words_per_entry": 4,
    },
}


def _fmt_ass_time(seconds: float) -> str:
    """Format seconds to ASS timecode H:MM:SS.cc (centiseconds)."""
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = int(seconds * 100) % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(
    scene_word_timings: list[tuple[float, list[dict]]],
    output_path: str | Path,
    style_name: str,
) -> Path:
    """
    Build an ASS subtitle file from per-scene word timing lists.

    scene_word_timings: [(scene_start_offset_seconds, word_list), ...]
        word_list: [{"word": str, "start": float, "end": float}, ...]
                   where start/end are relative to scene start
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not scene_word_timings or all(not words for _, words in scene_word_timings):
        output_path.write_text("")
        return output_path

    style = SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["tiktok_yellow"])
    bold_int = 1 if style["bold"] else 0

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: Default,{style['font']},{style['font_size']},"
            f"{style['primary_color']},{style['outline_color']},&H00000000,"
            f"{bold_int},0,0,0,100,100,0,0,1,{style['outline_width']},"
            f"{style['shadow']},{style['alignment']},10,10,{style['margin_v']},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    wpe = style["words_per_entry"]

    for scene_offset, word_list in scene_word_timings:
        if not word_list:
            continue
        # chunk words into groups of wpe
        for chunk_start in range(0, len(word_list), wpe):
            chunk = word_list[chunk_start:chunk_start + wpe]
            abs_start = scene_offset + chunk[0]["start"]
            abs_end   = scene_offset + chunk[-1]["end"]
            text = " ".join(w["word"] for w in chunk)
            if style["uppercase"]:
                text = text.upper()
            lines.append(
                f"Dialogue: 0,{_fmt_ass_time(abs_start)},{_fmt_ass_time(abs_end)},"
                f"Default,,0,0,0,,{text}"
            )

    output_path.write_text("\n".join(lines) + "\n")
    return output_path
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_subtitle_builder.py -v 2>&1 | tail -15
```

Expected: all 8 PASS.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/subtitle_builder.py tests/test_subtitle_builder.py
git commit -m "feat: add subtitle_builder.py with ASS style definitions and build_ass()"
```

---

## Task 6: Wire `composer.py` — timing path in `_process_scene()` and `build_ass()` in `_assemble()`

When `subtitle_style` is set in `video_cfg`, the composer must use `generate_tts_with_timing()` instead of `generate_tts()` and store the word timings so `_assemble()` can call `build_ass()`.

**Files:**
- Modify: `pipeline/composer.py`

- [ ] **Step 1: Update `_process_scene()` to use timing variant when subtitle_style is set**

In `pipeline/composer.py`, find the TTS block in `_process_scene()` (lines ~93–105):

```python
    # 1. TTS
    audio_path = out_dir / f"audio_{idx}.wav"
    try:
        from pipeline.tts_router import generate_tts
        generate_tts(
            text=scene.get("narration", ""),
            voice_id=video_cfg.get("voice", ""),
            speed=float(video_cfg.get("voice_speed", 1.1)),
            language=meta.get("language", "vietnamese"),
            output_path=str(audio_path),
            tts_service=video_cfg.get("tts_service", ""),
        )
    except Exception as e:
        logger.warning(f"[Composer] Scene {idx} TTS failed: {e}")
        audio_path = None
```

Replace with:

```python
    # 1. TTS
    audio_path = out_dir / f"audio_{idx}.wav"
    word_timing: list[dict] | None = None
    subtitle_style = video_cfg.get("subtitle_style") or ""
    try:
        if subtitle_style:
            from pipeline.tts_router import generate_tts_with_timing
            audio_path, word_timing = generate_tts_with_timing(
                text=scene.get("narration", ""),
                voice_id=video_cfg.get("voice", ""),
                speed=float(video_cfg.get("voice_speed", 1.1)),
                language=meta.get("language", "vietnamese"),
                output_path=str(audio_path),
                tts_service=video_cfg.get("tts_service", ""),
            )
        else:
            from pipeline.tts_router import generate_tts
            generate_tts(
                text=scene.get("narration", ""),
                voice_id=video_cfg.get("voice", ""),
                speed=float(video_cfg.get("voice_speed", 1.1)),
                language=meta.get("language", "vietnamese"),
                output_path=str(audio_path),
                tts_service=video_cfg.get("tts_service", ""),
            )
    except Exception as e:
        logger.warning(f"[Composer] Scene {idx} TTS failed: {e}")
        audio_path = None
```

- [ ] **Step 2: Add `word_timing` to the return dict of `_process_scene()`**

Find the return statement at the end of `_process_scene()`:

```python
    return {
        "scene":        scene,
        "duration":     duration,
        "audio_path":   str(audio_path) if audio_path and audio_path.exists() else None,
        "clip_path":    str(clip_path)  if clip_path and clip_path.exists() else None,
        "overlay_path": str(overlay_path) if overlay_path and overlay_path.exists() else None,
    }
```

Replace with:

```python
    return {
        "scene":        scene,
        "duration":     duration,
        "audio_path":   str(audio_path) if audio_path and audio_path.exists() else None,
        "clip_path":    str(clip_path)  if clip_path and clip_path.exists() else None,
        "overlay_path": str(overlay_path) if overlay_path and overlay_path.exists() else None,
        "word_timing":  word_timing,
    }
```

- [ ] **Step 3: Add `build_ass()` call in `_assemble()`**

In `_assemble()`, find the line just before `final.write_videofile(...)`:

```python
    # Write raw video (libx264 fast, will be re-encoded by renderer)
    final.write_videofile(
```

Insert this block before it:

```python
    # Build ASS subtitle file if subtitle_style is set
    subtitle_style = video_cfg.get("subtitle_style") or "" if video_cfg else ""
    if subtitle_style:
        from pipeline.subtitle_builder import build_ass
        scene_offsets = []
        offset = 0.0
        for idx in range(len(scenes)):
            scene_offsets.append(offset)
            offset += scene_assets.get(idx, {}).get("duration", 5)
        scene_word_timings = [
            (scene_offsets[idx], scene_assets.get(idx, {}).get("word_timing") or [])
            for idx in range(len(scenes))
        ]
        ass_path = output_path.parent / "subtitles.ass"
        build_ass(scene_word_timings, ass_path, subtitle_style)
        logger.info(f"[Composer] ASS subtitles → {ass_path}")

```

- [ ] **Step 4: Run the full test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass. (Composer is not directly unit-tested; existing tests exercise the modules it calls.)

- [ ] **Step 5: Commit**

```bash
git add pipeline/composer.py
git commit -m "feat: wire generate_tts_with_timing and build_ass into composer"
```

---

## Task 7: Update `renderer.py` — auto-detect `subtitles.ass`

The renderer currently only burns SRT subtitles. It must fall back to `subtitles.ass` in the same directory if no SRT is provided (SRT takes priority).

**Files:**
- Modify: `pipeline/renderer.py`
- Create: `tests/test_renderer_ass.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_renderer_ass.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def _make_raw(tmp_path):
    raw = tmp_path / "raw_video.mp4"
    raw.write_bytes(b"fake video")
    return raw


def test_renderer_burns_ass_when_no_srt(tmp_path):
    raw = _make_raw(tmp_path)
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("[Script Info]\nPlayResX: 1080\n")
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Create the output file that ffmpeg would normally create
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" in vf_str
    assert "subtitles.ass" in vf_str


def test_renderer_prefers_srt_over_ass(tmp_path):
    raw = _make_raw(tmp_path)
    srt_file = tmp_path / "captions.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("[Script Info]\nPlayResX: 1080\n")
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw, srt_path=srt_file)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "captions.srt" in vf_str
    assert "subtitles.ass" not in vf_str


def test_renderer_skips_empty_ass(tmp_path):
    raw = _make_raw(tmp_path)
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("")  # empty file — should be skipped
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" not in vf_str
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/test_renderer_ass.py -v 2>&1 | tail -15
```

Expected: 3 failures — renderer doesn't detect `subtitles.ass` yet.

- [ ] **Step 3: Update the subtitle block in `render_final()` in `pipeline/renderer.py`**

Find the existing subtitle burn-in block (lines ~59–65):

```python
    # Burn-in subtitles
    if srt_path and Path(srt_path).exists() and Path(srt_path).stat().st_size > 0:
        if _check_subtitles_filter():
            srt_escaped = Path(srt_path).resolve().as_posix().replace(":", "\\:")
            sub_filter = f"subtitles=filename='{srt_escaped}'"
            vf_filters.append(sub_filter)
        else:
            logger.warning("[Renderer] ffmpeg subtitles filter unavailable, skipping subtitle burn-in")
```

Replace with:

```python
    # Burn-in subtitles: SRT takes priority; fall back to subtitles.ass in same directory
    ass_candidate = Path(raw_path_obj).parent / "subtitles.ass"
    subtitle_file = None
    if srt_path and Path(srt_path).exists() and Path(srt_path).stat().st_size > 0:
        subtitle_file = Path(srt_path)
    elif ass_candidate.exists() and ass_candidate.stat().st_size > 0:
        subtitle_file = ass_candidate

    if subtitle_file and _check_subtitles_filter():
        escaped = subtitle_file.resolve().as_posix().replace(":", "\\:")
        vf_filters.append(f"subtitles=filename='{escaped}'")
    elif subtitle_file:
        logger.warning("[Renderer] ffmpeg subtitles filter unavailable, skipping subtitle burn-in")
```

- [ ] **Step 4: Run the new renderer tests**

```bash
python -m pytest tests/test_renderer_ass.py -v 2>&1 | tail -15
```

Expected: 3 PASS.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/renderer.py tests/test_renderer_ass.py
git commit -m "feat: renderer auto-detects subtitles.ass; SRT takes priority over ASS"
```

---

## Task 8: Add `subtitle_style` dropdown to the script editor frontend

Add a select field for `subtitle_style` to the Video section of `ScriptEditorModal` in `ScriptsPage.jsx`, near the TTS service and voice fields.

**Files:**
- Modify: `console/frontend/src/pages/ScriptsPage.jsx`

- [ ] **Step 1: Add the `SUBTITLE_STYLES` constant near the top of `ScriptsPage.jsx`**

Find this block (around line 16–18):

```javascript
const MOODS     = ['uplifting', 'calm_focus', 'energetic', 'dramatic', 'neutral']
const SCENE_TYPES = ['hook', 'body', 'transition', 'cta']
const OVERLAY_STYLES = ['bold_center', 'subtitle_bottom', 'corner_tag', 'full_overlay', 'minimal']
```

Add after it:

```javascript
const SUBTITLE_STYLE_OPTIONS = [
  { value: '',              label: 'None' },
  { value: 'tiktok_yellow', label: 'TikTok Yellow' },
  { value: 'tiktok_white',  label: 'TikTok White' },
  { value: 'bold_orange',   label: 'Bold Orange' },
  { value: 'caption_dark',  label: 'Caption Dark' },
  { value: 'minimal',       label: 'Minimal' },
]
```

- [ ] **Step 2: Add the select field inside the Video grid in `ScriptEditorModal`**

Find the line near the end of the Video grid section (around line 334):

```javascript
            <Select label="Mood"    value={video.music_mood || ''} onChange={e => setScriptField('video', 'music_mood', e.target.value)} placeholder="Default" options={MOODS.map(m => ({ value: m, label: m }))} />
            <Input label="Voice Speed" type="number" value={video.voice_speed ?? 1} onChange={e => setScriptField('video', 'voice_speed', parseFloat(e.target.value))} />
```

Add the subtitle_style select directly after the `Voice Speed` input:

```javascript
            <Select
              label="Subtitle Style"
              value={video.subtitle_style || ''}
              onChange={e => setScriptField('video', 'subtitle_style', e.target.value || null)}
              options={SUBTITLE_STYLE_OPTIONS}
            />
```

- [ ] **Step 3: Start the dev server and verify the dropdown appears**

```bash
cd console/frontend && npm run dev
```

Open http://localhost:5173, log in, go to Scripts, open any script for editing. In the Video section, confirm:
- A "Subtitle Style" select field appears after "Voice Speed"
- The options are: None, TikTok Yellow, TikTok White, Bold Orange, Caption Dark, Minimal
- Selecting an option and saving updates `script_json.video.subtitle_style`
- Selecting "None" saves `null` (not the string `"None"`)

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/ScriptsPage.jsx
git commit -m "feat: add subtitle_style dropdown to script editor video config"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Task |
|---|---|
| `elevenlabs_tts.py` — switch `pcm_44100` → `mp3_44100_128` + ffmpeg decode | Task 1 |
| `elevenlabs_tts.py` — add `_mp3_to_wav()` | Task 1 |
| `elevenlabs_tts.py` — add `_chars_to_words()` | Task 2 |
| `elevenlabs_tts.py` — add `generate_tts_elevenlabs_with_timing()` | Task 2 |
| `caption_gen.py` — add `extract_word_timing()` | Task 3 |
| `tts_router.py` — extract `_use_elevenlabs()` + `_resolve_elevenlabs_voice()` | Task 4 |
| `tts_router.py` — add `generate_tts_with_timing()` | Task 4 |
| `subtitle_builder.py` — `SUBTITLE_STYLES` dict with 5 styles | Task 5 |
| `subtitle_builder.py` — `build_ass()` with scene offsets, chunking, uppercase | Task 5 |
| `subtitle_builder.py` — `_fmt_ass_time()` in H:MM:SS.cc format | Task 5 |
| `subtitle_builder.py` — empty timing list writes empty file | Task 5 |
| `composer.py` — `_process_scene()` uses timing variant when subtitle_style set | Task 6 |
| `composer.py` — `_assemble()` calls `build_ass()` with cumulative offsets | Task 6 |
| `renderer.py` — auto-detect `subtitles.ass`; SRT takes priority | Task 7 |
| Frontend — `subtitle_style` select in video config section | Task 8 |
| No new pip dependencies | All tasks use existing: elevenlabs SDK, faster-whisper, ffmpeg subprocess |

All spec requirements covered. ✓

### Placeholder scan

No TBD, TODO, "implement later", "fill in details", "add appropriate error handling", "similar to Task N", or reference to undefined types. ✓

### Type consistency

| Symbol | Defined in | Used in |
|---|---|---|
| `_mp3_to_wav(mp3_bytes: bytes, output_path: Path) -> None` | Task 1, `elevenlabs_tts.py` | Task 2, `generate_tts_elevenlabs_with_timing()` |
| `_chars_to_words(chars, starts, ends) -> list[dict]` | Task 2, `elevenlabs_tts.py` | Task 2, `generate_tts_elevenlabs_with_timing()` |
| `generate_tts_elevenlabs_with_timing(text, voice_id, speed, output_path) -> tuple[Path, list[dict]]` | Task 2, `elevenlabs_tts.py` | Task 4, `tts_router.py` |
| `extract_word_timing(audio_path, language) -> list[dict]` | Task 3, `caption_gen.py` | Task 4, `tts_router.py` |
| `_use_elevenlabs(tts_service, language) -> bool` | Task 4, `tts_router.py` | Task 4, `generate_tts_with_timing()` |
| `_resolve_elevenlabs_voice(cfg, voice_id, tts_service, language) -> str` | Task 4, `tts_router.py` | Task 4, `generate_tts_with_timing()` |
| `generate_tts_with_timing(text, voice_id, speed, language, output_path, tts_service) -> tuple[Path, list[dict]]` | Task 4, `tts_router.py` | Task 6, `composer.py` |
| `build_ass(scene_word_timings, output_path, style_name) -> Path` | Task 5, `subtitle_builder.py` | Task 6, `composer.py` |
| `_fmt_ass_time(seconds: float) -> str` | Task 5, `subtitle_builder.py` | Task 5, `build_ass()` |
| `scene_word_timings: list[tuple[float, list[dict]]]` | Task 5, `build_ass()` parameter | Task 6, `composer._assemble()` construction |
| `word_timing` key in `scene_assets[idx]` | Task 6, `_process_scene()` return dict | Task 6, `_assemble()` retrieval |
| `subtitle_style` key in `video_cfg` | Task 6, `composer.py` | Task 8, frontend writes to `script_json.video.subtitle_style` |

All consistent. ✓
