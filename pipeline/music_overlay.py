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


def render_sidebar_png(
    tracks: list, current_index: int,
    output_dir: Path, canvas_w: int, canvas_h: int,
    cache_key: str,
) -> str:
    """Right-side playlist column showing all tracks, current highlighted.

    For >8 tracks, shows a window of 8 around the current index with
    ellipsis markers above/below.
    """
    out = Path(output_dir) / f"overlay_sidebar_{current_index}_{cache_key}.png"
    if out.is_file():
        return str(out)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    panel_w = int(canvas_w * 0.28)
    margin  = int(canvas_w * 0.03)
    pad     = 18
    header_font = _load_font(13)
    row_font    = _load_font(18)

    n = len(tracks)
    if n <= 8:
        rows = list(range(n))
        show_top_ellipsis = show_bot_ellipsis = False
    else:
        start = max(0, current_index - 3)
        end   = min(n, start + 8)
        if end == n:
            start = max(0, end - 8)
        rows = list(range(start, end))
        show_top_ellipsis = start > 0
        show_bot_ellipsis = end < n

    header = f"Playlist · {n} tracks"
    h_bbox = draw.textbbox((0, 0), header.upper(), font=header_font)
    h_h = h_bbox[3] - h_bbox[1]

    row_h = 28
    panel_h = pad * 2 + h_h + 12 + row_h * (
        len(rows) + (1 if show_top_ellipsis else 0)
        + (1 if show_bot_ellipsis else 0)
    )

    x = canvas_w - margin - panel_w
    y = (canvas_h - panel_h) // 2

    draw.rounded_rectangle(
        (x, y, x + panel_w, y + panel_h),
        radius=8,
        fill=(8, 10, 20, int(0.45 * 255)),
        outline=(255, 255, 255, int(0.08 * 255)),
        width=1,
    )

    hx = x + pad
    hy = y + pad - h_bbox[1]
    draw.text((hx, hy), header.upper(),
              font=header_font, fill=(90, 90, 112, 255))

    cursor_y = y + pad + h_h + 12
    if show_top_ellipsis:
        draw.text((hx, cursor_y), "…", font=row_font, fill=(90, 90, 112, 255))
        cursor_y += row_h

    for i in rows:
        played = i < current_index
        is_current = i == current_index
        marker = "✓" if played else ("▶" if is_current else f"{i+1}")
        title = _truncate(tracks[i].title or f"Track {i+1}", 30)

        if is_current:
            color = (232, 232, 240, 255)
            marker_color = (124, 106, 247, 255)
        elif played:
            color = (106, 106, 128, 255)
            marker_color = (52, 211, 153, 255)
        else:
            color = (106, 106, 128, 255)
            marker_color = (90, 90, 112, 255)

        draw.text((hx, cursor_y), marker, font=row_font, fill=marker_color)
        draw.text((hx + 28, cursor_y), title, font=row_font, fill=color)
        cursor_y += row_h

    if show_bot_ellipsis:
        draw.text((hx, cursor_y), "…", font=row_font, fill=(90, 90, 112, 255))

    img.save(out, "PNG")
    return str(out)


def _fmt_mmss(seconds: float) -> str:
    s = int(round(seconds))
    m, s = divmod(s, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def render_bottom_bar_png(
    tracks: list, current_index: int,
    output_dir: Path, canvas_w: int, canvas_h: int,
    cache_key: str,
) -> str:
    """Bottom-center bar showing 'Track i/n · Title · MM:SS'."""
    out = Path(output_dir) / f"overlay_bottom_bar_{current_index}_{cache_key}.png"
    if out.is_file():
        return str(out)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    track = tracks[current_index]
    title = _truncate(track.title or f"Track {current_index+1}", 50)
    duration = _fmt_mmss(track.duration_s)
    label = f"Track {current_index + 1} / {len(tracks)}   ·   {title}   ·   {duration}"
    font = _load_font(22)

    bar_w = int(canvas_w * 0.60)
    pad_x, pad_y = 24, 16

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bar_h = text_h + pad_y * 2

    margin_y = int(canvas_h * 0.06)
    x = (canvas_w - bar_w) // 2
    y = canvas_h - margin_y - bar_h

    draw.rounded_rectangle(
        (x, y, x + bar_w, y + bar_h),
        radius=6,
        fill=(8, 10, 20, int(0.55 * 255)),
        outline=(255, 255, 255, int(0.08 * 255)),
        width=1,
    )
    tx = x + (bar_w - text_w) // 2 - bbox[0]
    ty = y + (bar_h - text_h) // 2 - bbox[1]
    draw.text((tx, ty), label, font=font, fill=(232, 232, 240, 255))

    img.save(out, "PNG")
    return str(out)


def _playlist_cache_key(tracks: list) -> str:
    """Hash the ordered (id, title) list so cache invalidates on rename."""
    h = hashlib.sha1()
    for t in tracks:
        tid = getattr(t, "id", "?")
        title = (t.title or "").strip()
        h.update(f"{tid}|{title}\n".encode("utf-8"))
    return h.hexdigest()[:12]


_RENDERERS = {
    "chip":       render_chip_png,
    "sidebar":    render_sidebar_png,
    "bottom_bar": render_bottom_bar_png,
}


def build_now_playing_overlay(
    video,
    tracks: list,
    boundaries: list[float],
    total_duration_s: float,
    output_dir: Path,
    canvas_w: int = 1920,
    canvas_h: int = 1080,
) -> list[OverlaySegment]:
    """Build one OverlaySegment per track using video.playlist_overlay_style.

    Returns [] if style is None or fewer than 2 tracks (no overlay needed).
    """
    style = getattr(video, "playlist_overlay_style", None)
    if not style or len(tracks) < 2:
        return []
    renderer = _RENDERERS.get(style)
    if renderer is None:
        raise ValueError(f"Unknown overlay style: {style}")

    cache_key = _playlist_cache_key(tracks)
    segments: list[OverlaySegment] = []
    for i in range(len(tracks)):
        start = boundaries[i]
        end   = boundaries[i + 1] if i + 1 < len(tracks) else total_duration_s
        png   = renderer(
            tracks=tracks, current_index=i,
            output_dir=Path(output_dir),
            canvas_w=canvas_w, canvas_h=canvas_h,
            cache_key=cache_key,
        )
        segments.append(OverlaySegment(png_path=png, start_s=start, end_s=end))
    return segments
