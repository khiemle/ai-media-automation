"""Verify that chunked render + concat == single-shot render at the seam."""
import shutil
import subprocess
from pathlib import Path

import pytest

if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
    pytestmark = [pytest.mark.render, pytest.mark.skip(reason="ffmpeg/ffprobe not installed")]
else:
    pytestmark = pytest.mark.render


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


# ── concat_video_and_mux_audio ───────────────────────────────────────────────


@pytest.fixture
def two_video_only_clips(tmp_path):
    """Two 5-second video-only clips with identical encoder params (no audio)."""
    clips = []
    for i, color in enumerate(["black", "blue"]):
        out = tmp_path / f"vpart_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={color}:s=320x180:d=5:r=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-an",
            str(out),
        ], check=True, capture_output=True)
        clips.append(out)
    return clips


@pytest.fixture
def ten_second_aac_audio(tmp_path):
    """A single 10-second AAC-in-MP4 audio file (continuous encode, no chunk seams)."""
    out = tmp_path / "audio_full.m4a"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10:sample_rate=44100",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-vn",
        str(out),
    ], check=True, capture_output=True)
    return out


def test_concat_video_and_mux_produces_file(two_video_only_clips, ten_second_aac_audio, tmp_path):
    from pipeline.concat import concat_video_and_mux_audio
    out = tmp_path / "final.mp4"
    concat_video_and_mux_audio(two_video_only_clips, ten_second_aac_audio, out)
    assert out.exists() and out.stat().st_size > 0


def test_concat_video_and_mux_has_both_streams(
    two_video_only_clips, ten_second_aac_audio, tmp_path,
):
    from pipeline.concat import concat_video_and_mux_audio
    out = tmp_path / "final.mp4"
    concat_video_and_mux_audio(two_video_only_clips, ten_second_aac_audio, out)

    res = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "stream=codec_type,codec_name",
         "-of", "default=noprint_wrappers=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert "codec_type=video" in res.stdout
    assert "codec_type=audio" in res.stdout
    assert "codec_name=h264" in res.stdout
    assert "codec_name=aac" in res.stdout


def test_concat_video_and_mux_audio_is_single_continuous_encode(
    two_video_only_clips, ten_second_aac_audio, tmp_path,
):
    """Regression for the long-form chunk audio glitch.

    The whole point of routing audio through ``concat_video_and_mux_audio``
    is that the audio stream in the final file is the *exact* AAC bitstream
    produced by a single continuous encode — no per-chunk priming samples
    glued at the seams. Probe both files and confirm the byte count of the
    AAC payload matches.
    """
    from pipeline.concat import concat_video_and_mux_audio
    out = tmp_path / "final.mp4"
    concat_video_and_mux_audio(two_video_only_clips, ten_second_aac_audio, out)

    def _audio_packet_count(path: Path) -> int:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-count_packets", "-show_entries", "stream=nb_read_packets",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return int(res.stdout.strip())

    # The muxed file should have the same number of AAC packets as the source
    # audio (stream-copy: no re-encoding, no extra priming inserted).
    assert _audio_packet_count(out) == _audio_packet_count(ten_second_aac_audio)


def test_concat_video_and_mux_uses_pts_normalization_flags(
    two_video_only_clips, ten_second_aac_audio, tmp_path, monkeypatch,
):
    """Regression for the v1.2.0-1.2.3 whole-video A/V drift.

    Even with v1.2.4 frame-exact chunks, the concat+mux step keeps its own
    defensive flags: ``-fflags +genpts`` regenerates PTS at the seam if a
    chunk's container drifted by a sub-millisecond, and ``-avoid_negative_ts
    make_zero`` prevents the muxer from rounding small negative DTS values
    (which concat can emit when rebasing the next chunk's first packet) into
    the next chunk's PTS space.
    """
    import subprocess as real_subprocess
    captured_cmd: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):  # noqa: ARG001
        captured_cmd.append(list(cmd))
        return real_subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    from pipeline import concat as concat_mod
    monkeypatch.setattr(concat_mod.subprocess, "run", fake_run)
    # Output is never actually written by the fake — stub size/unlink calls.
    out = tmp_path / "final.mp4"
    out.write_bytes(b"fake")

    concat_mod.concat_video_and_mux_audio(two_video_only_clips, ten_second_aac_audio, out)

    assert captured_cmd, "ffmpeg was never invoked"
    cmd_str = " ".join(captured_cmd[0])
    assert "-fflags +genpts" in cmd_str
    assert "-avoid_negative_ts make_zero" in cmd_str
    assert "-c copy" in cmd_str
    assert "-shortest" in cmd_str


def test_concat_video_and_mux_rejects_empty_parts(ten_second_aac_audio, tmp_path):
    from pipeline.concat import concat_video_and_mux_audio
    with pytest.raises(ValueError):
        concat_video_and_mux_audio([], ten_second_aac_audio, tmp_path / "x.mp4")


def test_concat_video_and_mux_rejects_missing_audio(two_video_only_clips, tmp_path):
    from pipeline.concat import concat_video_and_mux_audio
    with pytest.raises(FileNotFoundError):
        concat_video_and_mux_audio(
            two_video_only_clips, tmp_path / "no_such_audio.m4a", tmp_path / "x.mp4",
        )
