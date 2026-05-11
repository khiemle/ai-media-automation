"""Pre-render the 'bars' spectrum visualizer as an alpha-channel video.

The bars style cannot be expressed in a native ffmpeg filtergraph because
fixed-count rounded-corner bars require per-pixel logic that depends on
time-varying audio amplitudes. Instead, this module computes 50 log-binned
frequency band amplitudes per frame using scipy STFT, composes each frame
via NumPy slice-assignment from a pre-built rounded-corner bar template,
and pipes raw RGBA frames to ffmpeg libvpx-vp9 for an alpha-preserving
WebM. The result is overlaid onto the main render as a separate input.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert '#rrggbb' or 'rrggbb' to (r, g, b) tuple."""
    s = hex_color.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _build_bar_template(
    bar_w: int,
    bar_h: int,
    radius: int,
    color_rgb: tuple[int, int, int],
) -> np.ndarray:
    """Build one rounded-top-corner bar as an (bar_h, bar_w, 4) uint8 RGBA array.

    Bottom corners are sharp (bars grow upward from the baseline).
    Top corners use a quarter-circle alpha mask with sub-pixel anti-aliasing.
    """
    arr = np.zeros((bar_h, bar_w, 4), dtype=np.uint8)
    arr[..., 0] = color_rgb[0]
    arr[..., 1] = color_rgb[1]
    arr[..., 2] = color_rgb[2]
    arr[..., 3] = 255

    if radius <= 0:
        return arr

    for y in range(radius):
        for x in range(radius):
            dx = (radius - x) - 0.5
            dy = (radius - y) - 0.5
            dist = (dx * dx + dy * dy) ** 0.5
            coverage = max(0.0, min(1.0, radius - dist + 0.5))
            alpha = int(round(255 * coverage))
            arr[y, x, 3] = alpha                  # top-left
            arr[y, bar_w - 1 - x, 3] = alpha      # top-right
    return arr


def _apply_smoothing(bar_heights: np.ndarray, decay: float = 0.85) -> np.ndarray:
    """In-place exponential decay smoothing: each frame is max(raw, prev * decay)."""
    for k in range(1, bar_heights.shape[0]):
        np.maximum(bar_heights[k], bar_heights[k - 1] * decay, out=bar_heights[k])
    return bar_heights


def compute_bar_heights(
    wav_path: str,
    total_duration_s: float,
    bar_count: int = 50,
    spectrum_fps: int = 15,
    f_low: float = 60.0,
    f_high: float = 16000.0,
    smoothing_decay: float = 0.85,
) -> np.ndarray:
    """Compute (n_target_frames, bar_count) bar heights in [0, 1] from a WAV file."""
    import scipy.io.wavfile
    import scipy.signal

    sample_rate, audio = scipy.io.wavfile.read(wav_path)

    # Normalize to float32 [-1, 1] and mix to mono
    if np.issubdtype(audio.dtype, np.integer):
        audio = audio.astype(np.float32) / float(np.iinfo(audio.dtype).max)
    else:
        audio = audio.astype(np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    nperseg = 2048
    noverlap = 1024
    f, t, Zxx = scipy.signal.stft(
        audio, fs=sample_rate, nperseg=nperseg, noverlap=noverlap, boundary=None
    )
    magnitudes = np.abs(Zxx).astype(np.float32)

    freq_edges = np.geomspace(f_low, f_high, num=bar_count + 1)
    bin_indices = np.searchsorted(f, freq_edges)

    bar_amps = np.zeros((bar_count, magnitudes.shape[1]), dtype=np.float32)
    for i in range(bar_count):
        lo = int(bin_indices[i])
        hi = max(int(bin_indices[i + 1]), lo + 1)
        bar_amps[i] = magnitudes[lo:hi].sum(axis=0)

    bars = np.log1p(bar_amps * 0.05).T
    peak = float(bars.max())
    if peak > 1e-6:
        bars /= peak
    np.clip(bars, 0.0, 1.0, out=bars)

    n_target_frames = int(round(total_duration_s * spectrum_fps))
    if n_target_frames <= 0:
        return np.zeros((0, bar_count), dtype=np.float32)
    src_times = t
    dst_times = np.linspace(0.0, total_duration_s, num=n_target_frames)
    bar_heights = np.empty((n_target_frames, bar_count), dtype=np.float32)
    for i in range(bar_count):
        bar_heights[:, i] = np.interp(dst_times, src_times, bars[:, i])

    _apply_smoothing(bar_heights, decay=smoothing_decay)
    return bar_heights
