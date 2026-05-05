"""Thumbnail generation utility for YouTube videos.

Canonical entry point: generate_thumbnail().
make_youtube_thumbnail.py delegates to this module as a thin CLI wrapper.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

THUMBNAIL_SIZE = (1280, 720)
DEFAULT_REGULAR_FONT = Path("/System/Library/Fonts/SFNS.ttf")
DEFAULT_BOLD_FONT = Path("/System/Library/Fonts/SFNS.ttf")


def split_text(text: str) -> list[str]:
    words = text.strip().split()
    if not words:
        raise ValueError("Text cannot be empty.")
    if len(words) <= 3:
        return words
    return [words[0], words[1], " ".join(words[2:])]


def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize(
        (round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def load_font(path: Path, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    if not path.exists():
        raise FileNotFoundError(f"Font file not found: {path}")
    font = ImageFont.truetype(str(path), size=size)
    if variation:
        try:
            font.set_variation_by_name(variation)
        except (AttributeError, OSError, ValueError):
            pass
    return font


def measure_lines(
    draw: ImageDraw.ImageDraw,
    lines: Iterable[str],
    font_size: int,
    regular_font_path: Path,
    bold_font_path: Path,
    bold_first_word: bool,
) -> tuple[int, int, list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]]:
    measured = []
    widths: list[int] = []
    heights: list[int] = []
    stroke_width = max(2, round(font_size * 0.045))
    spacing = max(8, round(font_size * 0.17))

    for index, line in enumerate(lines):
        is_bold = index == 0 and bold_first_word
        font_path = bold_font_path if is_bold else regular_font_path
        font = load_font(font_path, font_size, "Bold" if is_bold else "Regular")
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
        measured.append((line, font, stroke_width, bbox))

    total_height = sum(heights) + spacing * max(0, len(heights) - 1)
    return max(widths), total_height, measured


def fit_text(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    regular_font_path: Path,
    bold_font_path: Path,
    bold_first_word: bool,
    max_width: int,
    max_height: int,
    preferred_size: int,
    min_size: int,
) -> tuple[int, int, list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]]:
    for font_size in range(preferred_size, min_size - 1, -2):
        width, height, measured = measure_lines(
            draw, lines, font_size, regular_font_path, bold_font_path, bold_first_word
        )
        if width <= max_width and height <= max_height:
            return font_size, height, measured
    raise ValueError(
        f"Text is too large to fit. Try shorter text or lower min_font_size below {min_size}."
    )


def generate_thumbnail(
    source_path: Path | str,
    output_path: Path | str,
    text: str | None = None,
    font: Path = DEFAULT_REGULAR_FONT,
    bold_font: Path = DEFAULT_BOLD_FONT,
    bold_first_word: bool = True,
    preferred_font_size: int = 162,
    min_font_size: int = 48,
    margin_x: int = 58,
    margin_bottom: int = 48,
    fill: str = "#F7F2E8",
    stroke_fill: str = "#06100C",
) -> Path:
    """Generate a 1280x720 YouTube thumbnail PNG.

    text=None or empty: cover-resize only, no overlay.
    text provided: resize then draw text bottom-left with stroke.
    Returns output_path as a Path.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    image = Image.open(source_path).convert("RGB")
    canvas = cover_resize(image, THUMBNAIL_SIZE)

    if text and text.strip():
        draw = ImageDraw.Draw(canvas)
        lines = split_text(text.upper())
        max_width = THUMBNAIL_SIZE[0] - margin_x * 2
        max_height = THUMBNAIL_SIZE[1] - margin_bottom * 2
        font_size, block_height, measured = fit_text(
            draw, lines, font, bold_font, bold_first_word,
            max_width, max_height, preferred_font_size, min_font_size,
        )
        spacing = max(8, round(font_size * 0.17))
        x = margin_x
        y = THUMBNAIL_SIZE[1] - margin_bottom - block_height
        for line, line_font, stroke_width, bbox in measured:
            draw.text(
                (x - bbox[0], y - bbox[1]),
                line,
                font=line_font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
            y += (bbox[3] - bbox[1]) + spacing

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path
