from pathlib import Path
from unittest.mock import patch, MagicMock


def test_extract_word_timing_returns_word_dicts(tmp_path):
    from pipeline.caption_gen import extract_word_timing
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")
    mock_word = MagicMock()
    mock_word.word = " hello "
    mock_word.start = 0.5
    mock_word.end = 1.0
    mock_seg = MagicMock()
    mock_seg.words = [mock_word]
    with patch("pipeline.caption_gen._get_model") as mock_get_model:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], MagicMock())
        mock_get_model.return_value = mock_model
        result = extract_word_timing(audio, "vi")
    assert result == [{"word": "hello", "start": 0.5, "end": 1.0}]
    mock_model.transcribe.assert_called_once_with(
        str(audio), language="vi", word_timestamps=True
    )


def test_extract_word_timing_returns_empty_when_model_unavailable(tmp_path):
    from pipeline.caption_gen import extract_word_timing
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")
    with patch("pipeline.caption_gen._get_model", return_value=None):
        result = extract_word_timing(audio, "vi")
    assert result == []


def test_extract_word_timing_skips_empty_words(tmp_path):
    from pipeline.caption_gen import extract_word_timing
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")
    word_ok = MagicMock()
    word_ok.word = "hi"
    word_ok.start = 0.0
    word_ok.end = 0.3
    word_blank = MagicMock()
    word_blank.word = "  "
    word_blank.start = 0.3
    word_blank.end = 0.4
    mock_seg = MagicMock()
    mock_seg.words = [word_ok, word_blank]
    with patch("pipeline.caption_gen._get_model") as mock_get:
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], MagicMock())
        mock_get.return_value = mock_model
        result = extract_word_timing(audio, "en")
    assert len(result) == 1
    assert result[0]["word"] == "hi"
