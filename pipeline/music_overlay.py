"""PNG renderer for now-playing playlist overlays.

Generates one transparent RGBA PNG per (style, current_index, cache_key).
The render pipeline overlays these onto the visual video using ffmpeg's
overlay+enable filter, switching which PNG is "active" at each track
boundary.

Three styles supported:
  - chip:        compact bottom-left pill (this file)
  - sidebar:     right-side playlist (added in Task 8)
  - bottom_bar:  bottom-center bar (added in Task 9)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


_FONT_CANDIDATES = [
    "/Library/Fonts/IBMPlexSans-Medium.ttf",
    "/usr/share/fonts/truetype/ibm-plex/IBMPlexSans-Medium.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


@dataclass
class OverlaySegment:
    png_path: str
    start_s: float
    end_s: float


def render_chip_png(
    tracks: list, current_index: int,
    output_dir: Path, canvas_w: int, canvas_h: int,
    cache_key: str,
) -> str:
    """Bottom-left pill with [{i+1}/{n} · title]."""
    out = Path(output_dir) / f"overlay_chip_{current_index}_{cache_key}.png"
    if out.is_file():
        return str(out)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    title = _truncate(tracks[current_index].title or f"Track {current_index+1}", 40)
    label = f"{current_index + 1} / {len(tracks)}  ·  {title}"
    font = _load_font(28)

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x, pad_y = 24, 14
    dot_r = 7
    dot_gap = 14
    pill_w = dot_r * 2 + dot_gap + text_w + pad_x * 2
    pill_h = max(text_h, dot_r * 2) + pad_y * 2

    margin = int(canvas_w * 0.04)
    x = margin
    y = canvas_h - margin - pill_h

    draw.rounded_rectangle(
        (x, y, x + pill_w, y + pill_h),
        radius=pill_h // 2,
        fill=(10, 14, 28, int(0.55 * 255)),
        outline=(255, 255, 255, int(0.10 * 255)),
        width=1,
    )
    cx = x + pad_x + dot_r
    cy = y + pill_h // 2
    draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
                 fill=(124, 106, 247, 255))
    tx = cx + dot_r + dot_gap
    ty = y + (pill_h - text_h) // 2 - bbox[1]
    draw.text((tx, ty), label, font=font, fill=(232, 232, 240, 255))

    img.save(out, "PNG")
    return str(out)
