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


def render_spectrum_bars_video(
    music_wav: str,
    out_path: Path,
    total_duration_s: float,
    canvas_w: int,
    canvas_h: int,
    height_pct: float,
    color_hex: str,
    bar_count: int = 50,
    bar_width_px: float = 10.0,
    bar_gap_px: int = 2,
    corner_radius_px: int = 2,
    spectrum_fps: int = 15,
) -> Path:
    """Pre-render the spectrum as a qtrle .mov with rgba (lossless alpha).

    Bars are centered horizontally as a block of (bar_count * bar_width_px +
    (bar_count-1) * bar_gap_px) pixels, with transparent space on either side.

    Encoder is qtrle in MOV container with rgba — preserves alpha exactly
    (no chroma subsampling, no background tint artifacts). Caches by mtime:
    if out_path exists and is newer than the music WAV, returns immediately.
    """
    out_path = Path(out_path)
    music_path = Path(music_wav)
    if not music_path.is_file():
        raise FileNotFoundError(f"Music WAV not found: {music_wav}")

    if out_path.is_file() and out_path.stat().st_mtime >= music_path.stat().st_mtime:
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    strip_h = max(1, int(canvas_h * height_pct))
    bar_w = max(1, int(round(bar_width_px)))
    slot_w = bar_w + bar_gap_px

    # Center the bars block within the canvas width
    total_block_w = bar_count * bar_w + (bar_count - 1) * bar_gap_px
    x_offset = max(0, (canvas_w - total_block_w) // 2)

    color_rgb = _hex_to_rgb(color_hex)
    template = _build_bar_template(
        bar_w=bar_w, bar_h=strip_h,
        radius=corner_radius_px, color_rgb=color_rgb,
    )

    bar_heights = compute_bar_heights(
        wav_path=music_wav,
        total_duration_s=total_duration_s,
        bar_count=bar_count,
        spectrum_fps=spectrum_fps,
    )
    if bar_heights.shape[0] == 0:
        raise RuntimeError("compute_bar_heights returned zero frames")

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgba",
        "-video_size", f"{canvas_w}x{strip_h}",
        "-framerate", str(spectrum_fps),
        "-i", "pipe:0",
        "-c:v", "qtrle",
        "-pix_fmt", "rgba",
        "-t", str(total_duration_s),
        "-an",
        str(out_path),
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    frame_buf = np.zeros((strip_h, canvas_w, 4), dtype=np.uint8)
    try:
        for k in range(bar_heights.shape[0]):
            frame_buf.fill(0)
            for i in range(bar_count):
                h_px = int(round(float(bar_heights[k, i]) * strip_h))
                if h_px <= 0:
                    continue
                x_start = x_offset + i * slot_w
                x_end = x_start + bar_w
                if x_end > canvas_w:
                    x_end = canvas_w
                bar_slice_w = x_end - x_start
                if bar_slice_w <= 0:
                    continue
                tpl_slice = template[strip_h - h_px:, :bar_slice_w]
                frame_buf[strip_h - h_px:, x_start:x_end] = tpl_slice
            proc.stdin.write(frame_buf.tobytes())
    finally:
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait()

    if proc.returncode != 0:
        err = proc.stderr.read().decode("utf-8", "ignore")[-500:]
        raise RuntimeError(f"spectrum bars ffmpeg failed (rc={proc.returncode}): {err}")
    return out_path
