import subprocess
from pathlib import Path
import pytest
from pipeline.music_audio import build_music_playlist_wav_with_transitions

pytestmark = pytest.mark.render



class FakeTrack:
    def __init__(self, file_path, duration_s, volume=1.0):
        self.file_path = file_path
        self.duration_s = duration_s
        self.volume = volume


@pytest.fixture
def sine_wav(tmp_path):
    """Generate a stereo 5s sine WAV for testing."""
    def make(name: str, dur: float = 5.0, freq: int = 440) -> Path:
        out = tmp_path / f"{name}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency={freq}:duration={dur}",
            "-ar", "44100", "-ac", "2", str(out),
        ], check=True, capture_output=True)
        return out
    return make


def _probe_duration(path: Path) -> float:
    out = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def test_gapless_concat_total_duration(tmp_path, sine_wav):
    a, b, c = sine_wav("a"), sine_wav("b"), sine_wav("c")
    tracks = [FakeTrack(str(a), 5.0), FakeTrack(str(b), 5.0), FakeTrack(str(c), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=15.0, transition="gapless",
        transition_s=2.0, output_dir=tmp_path,
    )
    assert _probe_duration(Path(out)) == pytest.approx(15.0, abs=0.1)


def test_crossfade_total_duration(tmp_path, sine_wav):
    a, b = sine_wav("a"), sine_wav("b")
    tracks = [FakeTrack(str(a), 5.0), FakeTrack(str(b), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=8.0, transition="crossfade",
        transition_s=2.0, output_dir=tmp_path,
    )
    assert _probe_duration(Path(out)) == pytest.approx(8.0, abs=0.15)


def test_gap_total_duration(tmp_path, sine_wav):
    a, b = sine_wav("a"), sine_wav("b")
    tracks = [FakeTrack(str(a), 5.0), FakeTrack(str(b), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=11.5, transition="gap",
        transition_s=1.5, output_dir=tmp_path,
    )
    assert _probe_duration(Path(out)) == pytest.approx(11.5, abs=0.15)


def test_single_track_no_loop(tmp_path, sine_wav):
    a = sine_wav("a", dur=5.0)
    tracks = [FakeTrack(str(a), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=5.0, transition="gapless",
        transition_s=2.0, output_dir=tmp_path,
    )
    assert _probe_duration(Path(out)) == pytest.approx(5.0, abs=0.1)
