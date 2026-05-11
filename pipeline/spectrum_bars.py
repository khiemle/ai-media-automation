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
