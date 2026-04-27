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
