import numpy as np
import pytest

from pipeline.spectrum_bars import _build_bar_template


def test_bar_template_shape_and_dtype():
    tpl = _build_bar_template(bar_w=20, bar_h=100, radius=2, color_rgb=(255, 255, 255))
    assert tpl.shape == (100, 20, 4)
    assert tpl.dtype == np.uint8


def test_bar_template_interior_fully_opaque():
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[50, 10, 3] == 255   # center
    assert tpl[99, 10, 3] == 255   # bottom-middle
    assert tuple(tpl[50, 10, :3]) == (255, 255, 255)


def test_bar_template_top_corners_anti_aliased():
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[0, 0, 3] < 255             # top-left corner alpha < 255
    assert tpl[0, 19, 3] < 255            # top-right corner alpha < 255


def test_bar_template_bottom_corners_NOT_rounded():
    """Bars grow upward; bottom corners should be sharp (full alpha)."""
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[99, 0, 3] == 255
    assert tpl[99, 19, 3] == 255


def test_bar_template_zero_radius_is_pure_rectangle():
    tpl = _build_bar_template(20, 100, 0, (255, 255, 255))
    assert np.all(tpl[..., 3] == 255)


def test_bar_template_respects_color():
    tpl = _build_bar_template(20, 100, 2, (124, 106, 247))
    assert tuple(tpl[50, 10, :3]) == (124, 106, 247)


import subprocess
from pipeline.spectrum_bars import compute_bar_heights


@pytest.fixture
def sine_wav(tmp_path):
    """Create a stereo 44.1kHz sine WAV for testing."""
    def _make(name: str, dur: float, freq: int) -> str:
        out = tmp_path / f"{name}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency={freq}:duration={dur}",
            "-ar", "44100", "-ac", "2", str(out),
        ], check=True, capture_output=True)
        return str(out)
    return _make


def test_compute_bar_heights_shape(sine_wav):
    """5s WAV @ 15fps → (75, 50) bar_heights."""
    path = sine_wav("a", dur=5.0, freq=1000)
    heights = compute_bar_heights(
        wav_path=path, total_duration_s=5.0,
        bar_count=50, spectrum_fps=15,
    )
    assert heights.shape == (75, 50)
    assert heights.dtype == np.float32


def test_compute_bar_heights_range_normalized(sine_wav):
    """All values in [0, 1]."""
    path = sine_wav("a", dur=2.0, freq=440)
    heights = compute_bar_heights(
        wav_path=path, total_duration_s=2.0,
        bar_count=50, spectrum_fps=15,
    )
    assert heights.min() >= 0.0
    assert heights.max() <= 1.0


def test_compute_bar_heights_mid_freq_dominates_for_1khz(sine_wav):
    """1kHz sine should produce a peak in a mid-range bar."""
    path = sine_wav("a", dur=2.0, freq=1000)
    heights = compute_bar_heights(
        wav_path=path, total_duration_s=2.0,
        bar_count=50, spectrum_fps=15,
    )
    energy_per_bar = heights.sum(axis=0)
    peak_bar = int(np.argmax(energy_per_bar))
    # log spacing 60Hz..16kHz over 50 bars; 1kHz is at log(1000/60) / log(16000/60) * 50 ≈ 25
    assert 18 <= peak_bar <= 32, f"Peak bar {peak_bar} not near expected ~25 for 1kHz"


def test_compute_bar_heights_smoothing_prevents_sudden_drops():
    from pipeline.spectrum_bars import _apply_smoothing
    raw = np.array([
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ], dtype=np.float32)
    smoothed = _apply_smoothing(raw.copy(), decay=0.85)
    assert np.all(smoothed[1] >= 0.85)
    assert np.all(smoothed[2] >= 0.85 * 0.85)


def test_compute_bar_heights_handles_mono(tmp_path):
    out = tmp_path / "mono.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=500:duration=2",
        "-ar", "44100", "-ac", "1", str(out),
    ], check=True, capture_output=True)
    heights = compute_bar_heights(
        wav_path=str(out), total_duration_s=2.0,
        bar_count=50, spectrum_fps=15,
    )
    assert heights.shape == (30, 50)
