"""
ElevenLabs TTS client — uses the official ElevenLabs Python SDK.
Output: 44.1kHz mono WAV via ffmpeg (decoded from MP3 stream).
"""
import base64
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from config.api_config import get_config

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100  # target sample rate for WAV output


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


def _mp3_to_wav(mp3_bytes: bytes, output_path: Path) -> None:
    """Write mp3_bytes to a temp file, convert to WAV via ffmpeg, delete temp."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp = Path(f.name)
        f.write(mp3_bytes)
    try:
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

    logger.info(f"[ElevenLabs] Generated {output_path}")
    return output_path


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

