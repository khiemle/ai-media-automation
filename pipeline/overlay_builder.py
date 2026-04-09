"""
Overlay Builder — renders styled text as a transparent RGBA PNG.
5 built-in styles. Output: 1080×1920 RGBA.
"""
import logging
import os
import textwrap
from pathlib import Path
import tempfile

logger = logging.getLogger(__name__)

CANVAS_W, CANVAS_H = 1080, 1920

OVERLAY_STYLES = {
    "big_white_center": {
        "font_size":      72,
        "color":          (255, 255, 255, 255),
        "shadow":         (0, 0, 0, 180),
        "shadow_offset":  (3, 3),
        "position":       "center",
        "max_width_px":   900,
        "line_spacing":   1.2,
        "bg":             None,
    },
    "bottom_caption": {
        "font_size":      40,
        "color":          (255, 255, 255, 255),
        "shadow":         (0, 0, 0, 200),
        "shadow_offset":  (2, 2),
        "position":       "bottom",
        "max_width_px":   960,
        "line_spacing":   1.1,
        "bg":             (0, 0, 0, 140),
    },
    "top_title": {
        "font_size":      56,
        "color":          (255, 255, 255, 255),
        "shadow":         (0, 0, 0, 160),
        "shadow_offset":  (2, 2),
        "position":       "top",
        "max_width_px":   900,
        "line_spacing":   1.2,
        "bg":             None,
    },
    "highlight_box": {
        "font_size":      48,
        "color":          (20, 20, 20, 255),
        "shadow":         None,
        "shadow_offset":  (0, 0),
        "position":       "center",
        "max_width_px":   800,
        "line_spacing":   1.2,
        "bg":             (255, 204, 0, 220),
    },
    "minimal": {
        "font_size":      36,
        "color":          (255, 255, 255, 200),
        "shadow":         (0, 0, 0, 100),
        "shadow_offset":  (1, 1),
        "position":       "lower_third",
        "max_width_px":   900,
        "line_spacing":   1.1,
        "bg":             None,
    },
}


def build_overlay(scene: dict, output_path: str | None = None) -> Path:
    """
    Render a text overlay PNG for a scene.
    Returns path to a 1080×1920 RGBA PNG (transparent if no text).
    """
    text  = (scene.get("text_overlay") or "").strip()
    style_name = scene.get("overlay_style") or "minimal"
    style = OVERLAY_STYLES.get(style_name, OVERLAY_STYLES["minimal"])

    if output_path is None:
        scene_num = scene.get("scene_number", 0)
        output_path = os.path.join(tempfile.mkdtemp(), f"overlay_{scene_num}.png")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Pillow not installed. Run: pip install pillow")
        return _blank_png(output_path)

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))

    if not text:
        canvas.save(str(output_path), "PNG")
        return output_path

    draw     = ImageDraw.Draw(canvas)
    font     = _load_font(style["font_size"])
    max_w    = style["max_width_px"]

    # Word-wrap text
    avg_char_w = style["font_size"] * 0.55
    chars_per_line = max(1, int(max_w / avg_char_w))
    lines = textwrap.wrap(text, width=chars_per_line)

    line_h  = int(style["font_size"] * style["line_spacing"])
    block_h = line_h * len(lines)
    block_w = max(draw.textlength(line, font=font) for line in lines) if lines else 0

    # Position
    pos = style["position"]
    if pos == "center":
        x = (CANVAS_W - block_w) // 2
        y = (CANVAS_H - block_h) // 2
    elif pos == "top":
        x = (CANVAS_W - block_w) // 2
        y = int(CANVAS_H * 0.10)
    elif pos == "bottom":
        x = (CANVAS_W - block_w) // 2
        y = CANVAS_H - block_h - int(CANVAS_H * 0.05)
    else:  # lower_third
        x = (CANVAS_W - block_w) // 2
        y = int(CANVAS_H * 0.72)

    # Background bar
    if style.get("bg"):
        pad = 20
        bg_rect = [x - pad, y - pad, x + block_w + pad, y + block_h + pad]
        draw.rectangle(bg_rect, fill=style["bg"])

    # Draw each line
    for i, line in enumerate(lines):
        lx = x
        ly = y + i * line_h

        # Shadow
        if style.get("shadow") and style.get("shadow_offset"):
            sx, sy = style["shadow_offset"]
            draw.text((lx + sx, ly + sy), line, font=font, fill=style["shadow"])

        draw.text((lx, ly), line, font=font, fill=style["color"])

    canvas.save(str(output_path), "PNG")
    logger.debug(f"[Overlay] Rendered '{text[:30]}' → {output_path}")
    return output_path


def _load_font(size: int):
    from PIL import ImageFont
    # Try to load a nice font, fall back to default
    font_candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arial.ttf",
    ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _blank_png(path: Path) -> Path:
    try:
        from PIL import Image
        img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        img.save(str(path), "PNG")
    except Exception:
        path.write_bytes(b"")
    return path
