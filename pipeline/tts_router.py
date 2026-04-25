"""
TTS Router — dispatches to ElevenLabs (Vietnamese) or Kokoro (English).
Engine selection via TTS_ENGINE env var: auto | kokoro | elevenlabs
"""
import logging
import os
from pathlib import Path

import pipeline.elevenlabs_tts  # register in sys.modules so it can be patched in tests

logger = logging.getLogger(__name__)

TTS_ENGINE             = os.environ.get("TTS_ENGINE", "auto")
ELEVENLABS_VOICE_ID_VI = os.environ.get("ELEVENLABS_VOICE_ID_VI", "")
ELEVENLABS_VOICE_ID_EN = os.environ.get("ELEVENLABS_VOICE_ID_EN", "")


def generate_tts(
    text:        str,
    voice_id:    str,
    speed:       float,
    language:    str,
    output_path: str,
) -> Path:
    """
    Generate TTS audio and write to output_path (WAV).
    Engine selection:
      auto      — vietnamese → ElevenLabs, english → Kokoro
      kokoro    — always Kokoro
      elevenlabs — always ElevenLabs
    Raises RuntimeError on failure.
    """
    engine = TTS_ENGINE
    use_elevenlabs = (
        engine == "elevenlabs"
        or (engine == "auto" and language == "vietnamese")
    )

    if use_elevenlabs:
        elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not elevenlabs_api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not set in .env")
        voice = voice_id or ELEVENLABS_VOICE_ID_VI or ELEVENLABS_VOICE_ID_EN
        if not voice:
            raise RuntimeError("No ElevenLabs voice ID configured. Set ELEVENLABS_VOICE_ID_VI in .env")

        from pipeline.elevenlabs_tts import generate_tts_elevenlabs
        return generate_tts_elevenlabs(text, voice, speed, output_path)

    return _kokoro_generate(text, voice_id, speed, output_path)


def _kokoro_generate(text: str, voice_id: str, speed: float, output_path: str) -> Path:
    from pipeline.tts_engine import generate_tts as kokoro_tts
    return kokoro_tts(text=text, voice=voice_id, speed=speed, output_path=output_path)
