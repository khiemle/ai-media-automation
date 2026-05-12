"""Thumbnail generation utility for YouTube videos.

Canonical entry point: generate_thumbnail().
make_youtube_thumbnail.py delegates to this module as a thin CLI wrapper.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

THUMBNAIL_SIZE = (1280, 720)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Production path: fonts-liberation installed via apt in Dockerfile.api / Dockerfile.render.
# Dev convenience: bundled Roboto in assets/fonts/ (gitignored + dockerignored — local only).
# Resolution chain (first existing file wins):
#   1. THUMBNAIL_FONT_PATH / THUMBNAIL_BOLD_FONT_PATH env overrides
#   2. System Liberation Sans (container default)
#   3. Bundled Roboto (dev mac default)
#   4. Other system fonts (last-resort, may not provide a distinct bold)
_REGULAR_CANDIDATES = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    _REPO_ROOT / "assets" / "fonts" / "Roboto-Regular.ttf",
    Path("/System/Library/Fonts/SFNS.ttf"),                                    # macOS fallback
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),                   # common Linux
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),                               # Arch
    Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),                 # Fedora/RHEL
]
_BOLD_CANDIDATES = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    _REPO_ROOT / "assets" / "fonts" / "Roboto-Black.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"),
]


def _first_existing(candidates: list[Path]) -> Path | None:
    for p in candidates:
        if p.exists():
            return p
    return None


def _resolve_regular_font() -> Path:
    override = os.environ.get("THUMBNAIL_FONT_PATH")
    if override:
        return Path(override)
    found = _first_existing(_REGULAR_CANDIDATES)
    if found:
        return found
    raise FileNotFoundError(
        "No regular font found. Install fonts-liberation (apt) or set THUMBNAIL_FONT_PATH."
    )


def _resolve_bold_font(regular: Path) -> Path:
    override = os.environ.get("THUMBNAIL_BOLD_FONT_PATH")
    if override:
        return Path(override)
    found = _first_existing(_BOLD_CANDIDATES)
    if found:
        return found
    # Last-resort: fall back to regular. Bold will visually equal regular —
    # this is the silent-failure mode this fix was meant to prevent, so log loudly.
    import logging
    logging.getLogger(__name__).warning(
        "No bold font found; bold spans will render identically to regular. "
        "Install fonts-liberation (apt) or set THUMBNAIL_BOLD_FONT_PATH."
    )
    return regular


def _find_system_font() -> Path:
    """Backwards-compatible export used by existing tests / scripts."""
    return _resolve_regular_font()


DEFAULT_REGULAR_FONT = _resolve_regular_font()
DEFAULT_BOLD_FONT    = _resolve_bold_font(DEFAULT_REGULAR_FONT)

import logging as _thumb_log
_thumb_log.getLogger(__name__).info(
    "Thumbnail fonts resolved: regular=%s bold=%s",
    DEFAULT_REGULAR_FONT, DEFAULT_BOLD_FONT,
)


def wrap_plan(text: str, bold_word_count: int) -> list[list[tuple[str, bool]]]:
    """Wrap thumbnail text into lines, tagging each word as bold or regular.

    Layout (preserved from previous split_text):
      - 1-3 words → one word per line
      - 4+ words  → line1=word1, line2=word2, line3=remaining-words

    `bold_word_count` words from the start (in reading order, left-to-right,
    top-to-bottom) are tagged is_bold=True; the rest are False. Counts beyond
    the total number of words are clamped.
    """
    words = text.strip().split()
    if not words:
        raise ValueError("Text cannot be empty.")

    if len(words) <= 3:
        line_words: list[list[str]] = [[w] for w in words]
    else:
        line_words = [[words[0]], [words[1]], words[2:]]

    n = max(0, bold_word_count)
    plan: list[list[tuple[str, bool]]] = []
    seen = 0
    for line in line_words:
        segs: list[tuple[str, bool]] = []
        for w in line:
            segs.append((w, seen < n))
            seen += 1
        plan.append(segs)
    return plan


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


def _measure_word(
    draw: ImageDraw.ImageDraw,
    word: str,
    font: ImageFont.FreeTypeFont,
    stroke_width: int,
) -> tuple[int, int, tuple[int, int, int, int]]:
    bbox = draw.textbbox((0, 0), word, font=font, stroke_width=stroke_width)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox


def measure_plan(
    draw: ImageDraw.ImageDraw,
    plan: list[list[tuple[str, bool]]],
    font_size: int,
    regular_font_path: Path,
    bold_font_path: Path,
) -> tuple[int, int, list[list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]]]:
    """Measure a wrap plan; return (max_line_width, total_block_height, per_word_metadata).

    per_word_metadata is one inner list per line. Each item is
    (word, font, stroke_width, bbox) — ready for the draw loop.
    """
    stroke_width = max(2, round(font_size * 0.045))
    spacing = max(8, round(font_size * 0.17))

    regular_font = load_font(regular_font_path, font_size)
    bold_font    = load_font(bold_font_path,    font_size)
    space_w, _, _ = _measure_word(draw, " ", regular_font, stroke_width)

    measured_plan: list[list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]] = []
    line_widths:   list[int] = []
    line_heights:  list[int] = []

    for line in plan:
        words_meta = []
        line_w = 0
        line_h = 0
        for i, (word, is_bold) in enumerate(line):
            font = bold_font if is_bold else regular_font
            w, h, bbox = _measure_word(draw, word, font, stroke_width)
            if i > 0:
                line_w += space_w
            line_w += w
            line_h = max(line_h, h)
            words_meta.append((word, font, stroke_width, bbox))
        measured_plan.append(words_meta)
        line_widths.append(line_w)
        line_heights.append(line_h)

    total_height = sum(line_heights) + spacing * max(0, len(line_heights) - 1)
    return max(line_widths), total_height, measured_plan


def load_font(path: Path, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    if not path.exists():
        raise FileNotFoundError(f"Font file not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def fit_text_plan(
    draw: ImageDraw.ImageDraw,
    plan: list[list[tuple[str, bool]]],
    regular_font_path: Path,
    bold_font_path: Path,
    max_width: int,
    max_height: int,
    preferred_size: int,
    min_size: int,
) -> tuple[int, int, list]:
    for font_size in range(preferred_size, min_size - 1, -2):
        width, height, measured = measure_plan(
            draw, plan, font_size, regular_font_path, bold_font_path
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
    bold_word_count: int = 1,
    preferred_font_size: int = 162,
    min_font_size: int = 48,
    margin_x: int = 58,
    margin_bottom: int = 48,
    fill: str = "#F7F2E8",
    stroke_fill: str = "#06100C",
) -> Path:
    """Generate a 1280x720 YouTube thumbnail PNG.

    text=None or empty: cover-resize only, no overlay.
    text provided: resize then draw text bottom-left with stroke; the first
        `bold_word_count` words (default 1) are drawn in the bold font.
    Returns output_path as a Path.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    image = Image.open(source_path).convert("RGB")
    canvas = cover_resize(image, THUMBNAIL_SIZE)

    if text and text.strip():
        draw = ImageDraw.Draw(canvas)
        plan = wrap_plan(text.upper(), bold_word_count)
        max_width = THUMBNAIL_SIZE[0] - margin_x * 2
        max_height = THUMBNAIL_SIZE[1] - margin_bottom * 2
        font_size, block_height, measured = fit_text_plan(
            draw, plan, font, bold_font,
            max_width, max_height, preferred_font_size, min_font_size,
        )
        spacing = max(8, round(font_size * 0.17))
        regular_for_space = load_font(font, font_size)
        space_w, _, _ = _measure_word(draw, " ", regular_for_space,
                                       max(2, round(font_size * 0.045)))

        y = THUMBNAIL_SIZE[1] - margin_bottom - block_height
        for line in measured:
            x = margin_x
            line_h = max((bbox[3] - bbox[1]) for (_, _, _, bbox) in line)
            for i, (word, word_font, stroke_width, bbox) in enumerate(line):
                if i > 0:
                    x += space_w
                draw.text(
                    (x - bbox[0], y - bbox[1]),
                    word,
                    font=word_font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_fill,
                )
                x += (bbox[2] - bbox[0])
            y += line_h + spacing

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path
