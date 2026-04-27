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

