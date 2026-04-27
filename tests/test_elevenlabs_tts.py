import base64
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest


_FAKE_CONFIG = {
    "elevenlabs": {"api_key": "test-key", "model": "eleven_flash_v2_5"},
}


def test_mp3_to_wav_calls_ffmpeg_and_deletes_temp(tmp_path):
    from pipeline.elevenlabs_tts import _mp3_to_wav
    out = tmp_path / "out.wav"
    with patch("subprocess.run") as mock_run, \
         patch("tempfile.mktemp", return_value=str(tmp_path / "tmp.mp3")):
        mock_run.return_value = MagicMock(returncode=0)
        # Create the temp file so unlink doesn't fail
        (tmp_path / "tmp.mp3").write_bytes(b"")
        _mp3_to_wav(b"fake mp3 bytes", out)
    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert "ffmpeg" in cmd
    assert str(out) in cmd


def test_mp3_to_wav_raises_on_ffmpeg_failure(tmp_path):
    from pipeline.elevenlabs_tts import _mp3_to_wav
    out = tmp_path / "out.wav"
    with patch("subprocess.run") as mock_run, \
         patch("tempfile.mktemp", return_value=str(tmp_path / "tmp.mp3")):
        (tmp_path / "tmp.mp3").write_bytes(b"")
        mock_run.return_value = MagicMock(returncode=1, stderr="ffmpeg error")
        with pytest.raises(RuntimeError, match="ffmpeg"):
            _mp3_to_wav(b"bad bytes", out)


def test_generate_tts_elevenlabs_uses_mp3_format(tmp_path):
    """generate_tts_elevenlabs() must request mp3_44100_128, not pcm_44100."""
    from pipeline.elevenlabs_tts import generate_tts_elevenlabs
    out = tmp_path / "speech.wav"
    with patch("pipeline.elevenlabs_tts.get_config", return_value=_FAKE_CONFIG), \
         patch("pipeline.elevenlabs_tts._mp3_to_wav") as mock_convert, \
         patch("elevenlabs.client.ElevenLabs") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.text_to_speech.convert.return_value = iter([b"fake", b"mp3"])
        result = generate_tts_elevenlabs("hello", "voice-id", 1.0, str(out))
    call_kwargs = mock_client.text_to_speech.convert.call_args.kwargs
    assert call_kwargs["output_format"] == "mp3_44100_128"
    mock_convert.assert_called_once()
    assert result == out