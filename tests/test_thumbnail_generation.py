import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_generate_thumbnail_returns_path_on_success(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_1.mp4"
    video.write_bytes(b"\x00" * 16)
    thumb = tmp_path / "asset_1_thumb.jpg"
    thumb.write_bytes(b"\xff\xd8\xff")  # fake JPEG so is_file() is True

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = generate_video_thumbnail(str(video))

    assert result == str(thumb)


def test_generate_thumbnail_returns_none_on_ffmpeg_failure(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_2.mp4"
    video.write_bytes(b"\x00" * 16)

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = generate_video_thumbnail(str(video))

    assert result is None


def test_generate_thumbnail_returns_none_when_ffmpeg_missing(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_3.mp4"
    video.write_bytes(b"\x00" * 16)

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError
        result = generate_video_thumbnail(str(video))

    assert result is None


def test_generate_thumbnail_returns_none_on_timeout(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_4.mp4"
    video.write_bytes(b"\x00" * 16)

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)
        result = generate_video_thumbnail(str(video))

    assert result is None


def test_generate_thumbnail_uses_correct_ffmpeg_args(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 16)
    thumb = tmp_path / "clip_thumb.jpg"
    thumb.write_bytes(b"\xff\xd8\xff")

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        generate_video_thumbnail(str(video))

    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "ffmpeg"
    assert "-ss" in call_args
    assert "1" in call_args
    assert str(thumb) in call_args
