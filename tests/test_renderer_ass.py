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
