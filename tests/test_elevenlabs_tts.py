import base64
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


_FAKE_CONFIG = {
    "elevenlabs": {"api_key": "test-key", "model": "eleven_flash_v2_5"},
}


def test_mp3_to_wav_calls_ffmpeg_and_deletes_temp(tmp_path):
    from pipeline.elevenlabs_tts import _mp3_to_wav
    out = tmp_path / "out.wav"
    tmp_mp3 = tmp_path / "tmp.mp3"
    tmp_mp3.write_bytes(b"")  # pre-create so unlink works
    ntf_instance = MagicMock()
    ntf_instance.name = str(tmp_mp3)
    ntf_instance.__enter__ = MagicMock(return_value=ntf_instance)
    ntf_instance.__exit__ = MagicMock(return_value=False)
    with patch("tempfile.NamedTemporaryFile", return_value=ntf_instance) as mock_ntf, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _mp3_to_wav(b"fake mp3 bytes", out)
    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert "ffmpeg" in cmd
    assert str(out) in cmd


def test_mp3_to_wav_raises_on_ffmpeg_failure(tmp_path):
    from pipeline.elevenlabs_tts import _mp3_to_wav
    out = tmp_path / "out.wav"
    tmp_mp3 = tmp_path / "tmp.mp3"
    tmp_mp3.write_bytes(b"")
    ntf_instance = MagicMock()
    ntf_instance.name = str(tmp_mp3)
    ntf_instance.__enter__ = MagicMock(return_value=ntf_instance)
    ntf_instance.__exit__ = MagicMock(return_value=False)
    with patch("tempfile.NamedTemporaryFile", return_value=ntf_instance), \
         patch("subprocess.run") as mock_run:
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


def test_chars_to_words_basic():
    from pipeline.elevenlabs_tts import _chars_to_words
    # "hi there" — space at index 2 flushes "hi"; final flush gives "there"
    chars  = list("hi there")
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    ends   = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    words = _chars_to_words(chars, starts, ends)
    assert len(words) == 2
    assert words[0] == {"word": "hi",    "start": 0.0, "end": 0.2}
    assert words[1] == {"word": "there", "start": 0.3, "end": 0.8}


def test_chars_to_words_trailing_space():
    from pipeline.elevenlabs_tts import _chars_to_words
    chars  = list("ok ")
    starts = [0.0, 0.1, 0.2]
    ends   = [0.1, 0.2, 0.3]
    words = _chars_to_words(chars, starts, ends)
    assert len(words) == 1
    assert words[0]["word"] == "ok"


def test_generate_tts_elevenlabs_with_timing_returns_word_list(tmp_path):
    from pipeline.elevenlabs_tts import generate_tts_elevenlabs_with_timing
    out = tmp_path / "speech.wav"
    mock_response = MagicMock()
    mock_response.audio_base_64 = base64.b64encode(b"fake mp3 content").decode()
    mock_response.alignment.characters = list("hi")
    mock_response.alignment.character_start_times_seconds = [0.0, 0.1]
    mock_response.alignment.character_end_times_seconds   = [0.1, 0.2]
    with patch("pipeline.elevenlabs_tts.get_config", return_value=_FAKE_CONFIG), \
         patch("pipeline.elevenlabs_tts._mp3_to_wav") as mock_convert, \
         patch("elevenlabs.client.ElevenLabs") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.text_to_speech.convert_with_timestamps.return_value = mock_response
        audio_path, words = generate_tts_elevenlabs_with_timing("hi", "voice-id", 1.0, str(out))
    assert audio_path == Path(out)
    assert words == [{"word": "hi", "start": 0.0, "end": 0.2}]
    mock_convert.assert_called_once()