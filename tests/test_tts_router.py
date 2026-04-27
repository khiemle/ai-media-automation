import os
import pytest
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


def test_auto_english_calls_kokoro(tmp_path):
    out = tmp_path / "out.wav"
    import importlib
    from pipeline import tts_router
    with patch.dict(os.environ, {"TTS_ENGINE": "auto"}):
        importlib.reload(tts_router)  # reload FIRST so TTS_ENGINE reads "auto"
        with patch.object(tts_router, "_kokoro_generate") as mock_kokoro:
            mock_kokoro.return_value = out
            result = tts_router.generate_tts("Hello", "af_heart", 1.0, "english", str(out))
    mock_kokoro.assert_called_once()
    assert result == out


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


def test_missing_elevenlabs_key_raises():
    empty_config = {**_FAKE_CONFIG, "elevenlabs": {**_FAKE_CONFIG["elevenlabs"], "api_key": ""}}
    with patch("pipeline.tts_router.get_config", return_value=empty_config), \
         patch.dict(os.environ, {"TTS_ENGINE": "elevenlabs"}):
        from pipeline.tts_router import generate_tts
        with pytest.raises(RuntimeError, match="ElevenLabs"):
            generate_tts("text", "voice", 1.0, "vietnamese", "output.wav")


def test_normalize_text_expands_currency():
    from pipeline.elevenlabs_tts import _normalize_text

    assert "10 nghìn" in _normalize_text("giá 10k đồng")
    assert "500 triệu" in _normalize_text("giá 500tr đồng")
    assert _normalize_text("ok") == "ok"
    assert _normalize_text("trong") == "trong"
