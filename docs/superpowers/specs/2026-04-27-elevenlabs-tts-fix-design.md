# ElevenLabs TTS Fix — Design Spec

**Date:** 2026-04-27  
**Status:** Approved

---

## Problem

When the composer renders TTS for a script, it passes `video.voice` directly to `generate_tts()` as `voice_id`. After the LLM tab improvements, `video.voice` holds either a Kokoro voice name (e.g. `af_heart`) or an ElevenLabs UUID — depending on what was selected in the script editor.

In `tts_router.py`, when routing to ElevenLabs, the current logic is:

```python
voice = voice_id or cfg["elevenlabs"]["voice_id_vi"] or cfg["elevenlabs"]["voice_id_en"]
```

Since `"af_heart"` is truthy, it is passed directly to ElevenLabs → 404 `voice_not_found`.

Additionally, `elevenlabs_tts.py` uses raw `httpx` calls; the official ElevenLabs Python SDK should be used instead.

---

## Design

### 1. `pipeline/composer.py`

In `_process_scene()`, add `tts_service` to the `generate_tts()` call:

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

Default `voice_id` changes from `"af_heart"` to `""` — empty string forces the router to use the configured fallback voice when no explicit voice is set.

### 2. `pipeline/tts_router.py`

Add `tts_service: str = ""` parameter to `generate_tts()`. Updated engine + voice selection:

```python
def generate_tts(text, voice_id, speed, language, output_path, tts_service=""):
    if tts_service == "elevenlabs":
        use_elevenlabs = True
    elif tts_service == "kokoro":
        use_elevenlabs = False
    else:
        # Legacy: env var + language heuristic
        use_elevenlabs = (
            TTS_ENGINE == "elevenlabs"
            or (TTS_ENGINE == "auto" and language == "vietnamese")
        )

    if use_elevenlabs:
        cfg = get_config()
        if not cfg["elevenlabs"]["api_key"]:
            raise RuntimeError("ElevenLabs API key is not configured")

        if tts_service == "elevenlabs":
            # voice_id from script is an ElevenLabs UUID — trust it
            voice = voice_id or cfg["elevenlabs"]["voice_id_vi"] or cfg["elevenlabs"]["voice_id_en"]
        else:
            # Legacy: don't trust voice_id (could be a Kokoro name)
            if language == "vietnamese":
                voice = cfg["elevenlabs"]["voice_id_vi"] or cfg["elevenlabs"]["voice_id_en"]
            else:
                voice = cfg["elevenlabs"]["voice_id_en"] or cfg["elevenlabs"]["voice_id_vi"]

        if not voice:
            raise RuntimeError("No ElevenLabs voice ID configured")

        from pipeline.elevenlabs_tts import generate_tts_elevenlabs
        return generate_tts_elevenlabs(text, voice, speed, output_path)

    return _kokoro_generate(text, voice_id, speed, output_path)
```

### 3. `pipeline/elevenlabs_tts.py`

Replace httpx calls with the official ElevenLabs Python SDK:

```python
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

def generate_tts_elevenlabs(text, voice_id, speed, output_path):
    cfg = get_config()
    api_key = cfg["elevenlabs"]["api_key"]
    model_id = cfg["elevenlabs"].get("model", "eleven_flash_v2_5")

    text = _normalize_text(text)
    if not text:
        raise RuntimeError("TTS text is empty after normalization")

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

    if not pcm_bytes:
        raise RuntimeError("ElevenLabs returned empty audio")
    if len(pcm_bytes) % 2 != 0:
        raise RuntimeError(f"ElevenLabs returned malformed PCM: {len(pcm_bytes)} bytes")

    import numpy as np
    import soundfile as sf
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), samples, SAMPLE_RATE)
    return output_path
```

### 4. `requirements.pipeline.txt`

Add: `elevenlabs>=2.44.0`

---

## Files Changed

| File | Change |
|---|---|
| `pipeline/composer.py` | Pass `tts_service` to `generate_tts()`; default `voice_id` to `""` |
| `pipeline/tts_router.py` | Add `tts_service` param; fix engine + voice resolution |
| `pipeline/elevenlabs_tts.py` | Replace httpx with ElevenLabs Python SDK |
| `requirements.pipeline.txt` | Add `elevenlabs>=2.44.0` |

No DB changes, no frontend changes, no new files.
