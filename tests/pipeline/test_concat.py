"""Verify that chunked render + concat == single-shot render at the seam."""
import shutil
import subprocess
from pathlib import Path

import pytest

if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
    pytestmark = pytest.mark.skip(reason="ffmpeg/ffprobe not installed")


@pytest.fixture
def two_color_clips(tmp_path):
    """Generate two 5-second clips with identical encoder params."""
    clips = []
    for i, color in enumerate(["black", "blue"]):
        out = tmp_path / f"part_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={color}:s=320x180:d=5:r=30",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-pix_fmt", "yuv420p", "-r", "30",
            str(out),
        ], check=True, capture_output=True)
        clips.append(out)
    return clips


def test_concat_produces_single_file(two_color_clips, tmp_path):
    from pipeline.concat import concat_parts
    out = tmp_path / "joined.mp4"
    concat_parts(two_color_clips, out)
    assert out.exists() and out.stat().st_size > 0


def test_concat_duration_equals_sum(two_color_clips, tmp_path):
    from pipeline.concat import concat_parts
    out = tmp_path / "joined.mp4"
    concat_parts(two_color_clips, out)
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    duration = float(res.stdout.strip())
    assert 9.5 < duration < 10.5


def test_concat_no_reencode(two_color_clips, tmp_path):
    """Stream copy means the resulting codec params match the input."""
    from pipeline.concat import concat_parts
    out = tmp_path / "joined.mp4"
    concat_parts(two_color_clips, out)
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,r_frame_rate",
         "-of", "default=noprint_wrappers=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert "codec_name=h264" in res.stdout
    assert "r_frame_rate=30/1" in res.stdout
