"""
TTS Engine — Kokoro ONNX neural text-to-speech.
Output: 44.1kHz mono WAV. Falls back to silent track on error.
"""
import logging
import os
import re
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MODELS_PATH  = os.environ.get("MODELS_PATH", "./models")
KOKORO_MODEL = os.path.join(MODELS_PATH, "kokoro", "kokoro.onnx")
KOKORO_VOICES = os.path.join(MODELS_PATH, "kokoro", "voices")
SAMPLE_RATE  = 44100

_kokoro = None


def _resolve_voices_path(voices_path: str) -> str:
    path = Path(voices_path)
    if path.is_file():
        return str(path)
    if path.is_dir():
        voice_files = sorted(path.glob("*.bin"))
        if voice_files:
            return str(voice_files[0])
    return voices_path


def _patch_kokoro_compat(kokoro) -> None:
    input_names = {item.name for item in kokoro.sess.get_inputs()}
    if "tokens" in input_names or "input_ids" not in input_names:
        return

    def _create_audio_compat(self, phonemes: str, voice, speed: float):
        import numpy as np

        max_phoneme_length = getattr(self.config, "MAX_PHONEME_LENGTH", None)
        if max_phoneme_length is None:
            from kokoro_onnx.config import MAX_PHONEME_LENGTH

            max_phoneme_length = MAX_PHONEME_LENGTH

        if len(phonemes) > max_phoneme_length:
            logger.warning(
                f"[TTS] Truncating phonemes from {len(phonemes)} to {max_phoneme_length}"
            )
            phonemes = phonemes[:max_phoneme_length]

        start_t = time.time()
        tokens = self.tokenizer.tokenize(phonemes)
        voice_style = voice[len(tokens)]
        feed = {
            "input_ids": np.asarray([[0, *tokens, 0]], dtype=np.int64),
            "style": np.asarray(voice_style, dtype=np.float32),
            "speed": np.asarray([int(round(speed))], dtype=np.int32),
        }
        audio = self.sess.run(None, feed)[0]
        sample_rate = getattr(self.config, "SAMPLE_RATE", None)
        if sample_rate is None:
            from kokoro_onnx.config import SAMPLE_RATE as KOKORO_SAMPLE_RATE

            sample_rate = KOKORO_SAMPLE_RATE

        audio_duration = len(audio) / sample_rate if len(audio) else 0.0
        create_duration = time.time() - start_t
        if audio_duration > 0:
            logger.debug(
                f"[TTS] Kokoro compatibility path generated {audio_duration:.2f}s in {create_duration:.2f}s"
            )
        return audio, sample_rate

    kokoro._create_audio = _create_audio_compat.__get__(kokoro, type(kokoro))


def _pick_supported_voice(kokoro, requested_voice: str) -> str:
    voices: list[str] = list(kokoro.get_voices())
    if requested_voice in voices:
        return requested_voice

    prefix = requested_voice.split("_", 1)[0]
    for voice in voices:
        if voice.startswith(f"{prefix}_"):
            logger.warning(
                f"[TTS] Voice '{requested_voice}' unavailable, using '{voice}' instead"
            )
            return voice

    fallback_voice = voices[0]
    logger.warning(
        f"[TTS] Voice '{requested_voice}' unavailable, using '{fallback_voice}' instead"
    )
    return fallback_voice


def _pick_supported_lang(voice: str) -> str:
    if voice.startswith(("zf_", "zm_")):
        return "cmn"
    return "en-us"


def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        try:
            from kokoro_onnx import Kokoro

            voices_path = _resolve_voices_path(KOKORO_VOICES)
            _kokoro = Kokoro(KOKORO_MODEL, voices_path)
            _patch_kokoro_compat(_kokoro)
            logger.info(f"[TTS] Kokoro loaded from {KOKORO_MODEL} with voices {voices_path}")
        except Exception as e:
            logger.error(f"[TTS] Failed to load Kokoro: {e}")
            _kokoro = None
    return _kokoro


def _normalize_text(text: str) -> str:
    """Normalize Vietnamese text for natural TTS pronunciation."""
    # Expand common abbreviations
    replacements = {
        "TP.HCM":     "Thành phố Hồ Chí Minh",
        "TP.HN":      "Thành phố Hà Nội",
        "&":          " và ",
        "%":          " phần trăm",
        "VND":        " đồng",
        "USD":        " đô la Mỹ",
        "k":          " nghìn",
        "tr":         " triệu",
        "tỷ":         " tỷ đồng",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def generate_tts(
    text: str,
    voice: str = "af_heart",
    speed: float = 1.1,
    output_path: str | None = None,
) -> Path:
    """
    Generate a WAV audio file from text using Kokoro ONNX TTS.
    Returns path to the generated WAV file.
    Falls back to a silent WAV track on any error.
    """
    import numpy as np
    import soundfile as sf

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    text = _normalize_text(text)
    if not text:
        return _silent_wav(output_path, duration_s=3.0)

    kokoro = _get_kokoro()
    if kokoro is None:
        logger.warning("[TTS] Kokoro unavailable, generating silent track")
        return _silent_wav(output_path, duration_s=5.0)

    for attempt in range(2):
        try:
            _speed = speed if attempt == 0 else 1.0  # fallback: normal speed
            resolved_voice = _pick_supported_voice(kokoro, voice)
            resolved_lang = _pick_supported_lang(resolved_voice)
            samples, sr = kokoro.create(
                text,
                voice=resolved_voice,
                speed=_speed,
                lang=resolved_lang,
            )

            # Resample to 44.1kHz if needed
            if sr != SAMPLE_RATE:
                try:
                    from scipy.signal import resample_poly
                    from math import gcd
                    g = gcd(SAMPLE_RATE, sr)
                    samples = resample_poly(samples, SAMPLE_RATE // g, sr // g)
                except Exception:
                    pass  # use as-is if scipy not available

            # Ensure mono
            if samples.ndim > 1:
                samples = samples.mean(axis=1)

            sf.write(str(output_path), samples.astype(np.float32), SAMPLE_RATE)
            logger.info(f"[TTS] Generated {output_path} ({len(samples)/SAMPLE_RATE:.1f}s)")
            return output_path

        except Exception as e:
            if attempt == 0:
                logger.warning(f"[TTS] Attempt 1 failed: {e}, retrying at speed=1.0")
            else:
                logger.error(f"[TTS] Both attempts failed: {e}, generating silent track")
                return _silent_wav(output_path, duration_s=5.0)

    return _silent_wav(output_path, duration_s=5.0)


def _silent_wav(path: Path, duration_s: float = 5.0) -> Path:
    """Write a silent WAV file as fallback."""
    import numpy as np
    import soundfile as sf
    samples = np.zeros(int(SAMPLE_RATE * duration_s), dtype=np.float32)
    sf.write(str(path), samples, SAMPLE_RATE)
    logger.info(f"[TTS] Wrote silent track ({duration_s}s) → {path}")
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = generate_tts("Xin chào, đây là bài kiểm tra tổng hợp giọng nói.", output_path="/tmp/test_tts.wav")
    print(f"TTS output: {out}")
