from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def _make_raw(tmp_path):
    raw = tmp_path / "raw_video.mp4"
    raw.write_bytes(b"fake video")
    return raw


def test_renderer_burns_ass_when_no_srt(tmp_path):
    raw = _make_raw(tmp_path)
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("[Script Info]\nPlayResX: 1080\n")
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Create the output file that ffmpeg would normally create
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" in vf_str
    assert "subtitles.ass" in vf_str


def test_renderer_prefers_srt_over_ass(tmp_path):
    raw = _make_raw(tmp_path)
    srt_file = tmp_path / "captions.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("[Script Info]\nPlayResX: 1080\n")
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw, srt_path=srt_file)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "captions.srt" in vf_str
    assert "subtitles.ass" not in vf_str


def test_renderer_skips_empty_ass(tmp_path):
    raw = _make_raw(tmp_path)
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("")  # empty file — should be skipped
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" not in vf_str


def test_renderer_no_subtitle_when_neither_file_exists(tmp_path):
    raw = _make_raw(tmp_path)
    # No srt_path, no subtitles.ass in tmp_path
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" not in vf_str


def test_renderer_moviepy_fallback_when_libass_unavailable(tmp_path):
    """When libass is unavailable, renderer calls _burn_subtitles_moviepy."""
    raw = _make_raw(tmp_path)
    srt_file = tmp_path / "captions.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello world\n")
    final_path = tmp_path / "video_final.mp4"

    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=False), \
         patch("pipeline.renderer._burn_subtitles_moviepy", return_value=True) as mock_burn, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        final_path.write_bytes(b"fake final")
        from pipeline.renderer import render_final
        result = render_final(raw_video_path=raw, srt_path=srt_file)

    mock_burn.assert_called_once()
    # ffmpeg should NOT have been called (MoviePy handled it)
    mock_run.assert_not_called()


def test_renderer_logs_warning_when_subtitles_filter_unavailable(tmp_path):
    """When libass is unavailable and MoviePy fallback also fails, log warning and continue."""
    raw = _make_raw(tmp_path)
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("[Script Info]\nPlayResX: 1080\n")
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=False), \
         patch("pipeline.renderer._burn_subtitles_moviepy", return_value=False), \
         patch("subprocess.run") as mock_run, \
         patch("pipeline.renderer.logger") as mock_logger:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" not in vf_str
    mock_logger.warning.assert_called()


def test_parse_srt_basic():
    from pipeline.renderer import _parse_srt
    import tempfile, os
    content = "1\n00:00:01,000 --> 00:00:02,500\nHello world\n\n2\n00:00:03,000 --> 00:00:04,000\nTest\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        f.write(content)
        name = f.name
    try:
        entries = _parse_srt(Path(name))
        assert len(entries) == 2
        assert abs(entries[0]['start'] - 1.0) < 0.01
        assert abs(entries[0]['end'] - 2.5) < 0.01
        assert entries[0]['text'] == 'Hello world'
        assert entries[1]['text'] == 'Test'
    finally:
        os.unlink(name)


def test_parse_srt_strips_html_tags():
    from pipeline.renderer import _parse_srt
    import tempfile, os
    content = "1\n00:00:00,000 --> 00:00:01,000\n<i>Italic</i> text\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
        f.write(content)
        name = f.name
    try:
        entries = _parse_srt(Path(name))
        assert entries[0]['text'] == 'Italic text'
    finally:
        os.unlink(name)


def test_renderer_prefers_srt_over_ass(tmp_path):
    raw = _make_raw(tmp_path)
    srt_file = tmp_path / "captions.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("[Script Info]\nPlayResX: 1080\n")
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw, srt_path=srt_file)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "captions.srt" in vf_str
    assert "subtitles.ass" not in vf_str


def test_renderer_skips_empty_ass(tmp_path):
    raw = _make_raw(tmp_path)
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("")  # empty file — should be skipped
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" not in vf_str


def test_renderer_no_subtitle_when_neither_file_exists(tmp_path):
    raw = _make_raw(tmp_path)
    # No srt_path, no subtitles.ass in tmp_path
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" not in vf_str


def test_renderer_logs_warning_when_subtitles_filter_unavailable(tmp_path):
    raw = _make_raw(tmp_path)
    ass_file = tmp_path / "subtitles.ass"
    ass_file.write_text("[Script Info]\nPlayResX: 1080\n")
    with patch("pipeline.renderer._check_nvenc", return_value=False), \
         patch("pipeline.renderer._check_subtitles_filter", return_value=False), \
         patch("subprocess.run") as mock_run, \
         patch("pipeline.renderer.logger") as mock_logger:
        mock_run.return_value = MagicMock(returncode=0)
        (tmp_path / "video_final.mp4").write_bytes(b"fake final")
        from pipeline.renderer import render_final
        render_final(raw_video_path=raw)
    cmd = mock_run.call_args.args[0]
    vf_str = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" not in vf_str
    mock_logger.warning.assert_called()
