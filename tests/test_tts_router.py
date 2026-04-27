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
         patch("pipeline.tts_router.TTS_ENGINE", "elevenlabs"), \
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
