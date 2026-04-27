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
