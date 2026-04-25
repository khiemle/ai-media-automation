"""
ElevenLabs TTS client — for Vietnamese (and other non-English) narration.
Requests PCM output directly, writes as WAV via soundfile.
"""
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ELEVENLABS_MODEL = "eleven_multilingual_v2"
SAMPLE_RATE            = 44100  # pcm_44100 output


def _normalize_text(text: str) -> str:
    """Expand Vietnamese abbreviations for natural TTS pronunciation."""
    simple_replacements = {
        "TP.HCM":  "Thành phố Hồ Chí Minh",
        "TP.HN":   "Thành phố Hà Nội",
        "&":       " và ",
        "%":       " phần trăm",
        "VND":     " đồng",
        "USD":     " đô la Mỹ",
    }
    for src, dst in simple_replacements.items():
        text = text.replace(src, dst)
    # Match k/tr not immediately surrounded by letters (allows numeric context like "10k", "500tr")
    text = re.sub(r'(?<![a-zA-ZÀ-ỹ])k(?![a-zA-ZÀ-ỹ])', ' nghìn', text)
    text = re.sub(r'(?<![a-zA-ZÀ-ỹ])tr(?![a-zA-ZÀ-ỹ])', ' triệu', text)
    return re.sub(r"\s+", " ", text).strip()


def generate_tts_elevenlabs(
    text:       str,
    voice_id:   str,
    speed:      float,
    output_path: str,
) -> Path:
    """
    Generate WAV audio from text using ElevenLabs.
    Raises RuntimeError on any failure.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")  # read dynamically, not from import-time constant
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set in .env")

    if not voice_id:
        raise RuntimeError("voice_id is required for ElevenLabs TTS")

    text = _normalize_text(text)
    if not text:
        raise RuntimeError("TTS text is empty after normalization")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "output_format": "pcm_44100",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "speed": min(max(speed, 0.7), 1.3),
        },
    }

    import httpx  # lazy: not available in test/CI environments without heavy deps
    import numpy as np
    import soundfile as sf

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"ElevenLabs API error {e.response.status_code}: {e.response.text}") from e
    except Exception as e:
        raise RuntimeError(f"ElevenLabs request failed: {e}") from e

    # PCM_44100 = signed 16-bit little-endian, mono
    pcm_bytes = response.content
    if not pcm_bytes:
        raise RuntimeError("ElevenLabs returned empty audio content")
    if len(pcm_bytes) % 2 != 0:
        raise RuntimeError(f"ElevenLabs returned malformed PCM: {len(pcm_bytes)} bytes (not 16-bit aligned)")
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), samples, SAMPLE_RATE)

    logger.info(f"[ElevenLabs] Generated {output_path} ({len(samples)/SAMPLE_RATE:.1f}s)")
    return output_path
