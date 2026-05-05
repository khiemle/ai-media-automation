#!/usr/bin/env python3
"""
Create a YouTube thumbnail from an image and overlay large readable text.

Usage:
  python3 make_youtube_thumbnail.py input.png --text "DEEP FOCUS" --output output.png

Text layout:
  - 1 to 3 words: one word per line.
  - More than 3 words: first word on line 1, second word on line 2,
    all remaining words on line 3.
  - The first word is bold by default.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.youtube_thumbnail import (
    DEFAULT_BOLD_FONT,
    DEFAULT_REGULAR_FONT,
    generate_thumbnail,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a YouTube thumbnail with safe bottom-left text."
    )
    parser.add_argument("image", type=Path, help="Input image path.")
    parser.add_argument("--text", required=True, help='Thumbnail text, e.g. "DEEP FOCUS".')
    parser.add_argument("--output", type=Path, default=Path("youtube-thumbnail.png"))
    parser.add_argument("--font", type=Path, default=DEFAULT_REGULAR_FONT)
    parser.add_argument("--bold-font", type=Path, default=DEFAULT_BOLD_FONT)
    parser.add_argument(
        "--no-bold-first-word", dest="no_bold_first_word", action="store_true",
        help="Use regular style for every word.",
    )
    parser.add_argument(
        "--no-bold-first-line", dest="no_bold_first_word", action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--preferred-font-size", type=int, default=162)
    parser.add_argument("--min-font-size", type=int, default=48)
    parser.add_argument("--margin-x", type=int, default=58)
    parser.add_argument("--margin-bottom", type=int, default=48)
    parser.add_argument("--fill", default="#F7F2E8")
    parser.add_argument("--stroke-fill", default="#06100C")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_thumbnail(
        source_path=args.image,
        output_path=args.output,
        text=args.text,
        font=args.font,
        bold_font=args.bold_font,
        bold_first_word=not args.no_bold_first_word,
        preferred_font_size=args.preferred_font_size,
        min_font_size=args.min_font_size,
        margin_x=args.margin_x,
        margin_bottom=args.margin_bottom,
        fill=args.fill,
        stroke_fill=args.stroke_fill,
    )


if __name__ == "__main__":
    main()
