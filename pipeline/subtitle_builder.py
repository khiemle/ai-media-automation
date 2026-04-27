"""
ASS subtitle file builder for word-by-word subtitle burn-in.
"""
from pathlib import Path

_VIDEO_W = 1080  # portrait 9:16 (TikTok / Reels)
_VIDEO_H = 1920

SUBTITLE_STYLES: dict[str, dict] = {
    "tiktok_yellow": {
        "font": "Arial Black", "font_size": 90,
        "primary_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "outline_width": 5, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "tiktok_white": {
        "font": "Arial Black", "font_size": 90,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 5, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "bold_orange": {
        "font": "Arial Black", "font_size": 80,
        "primary_color": "&H0000A5FF",
        "outline_color": "&H00000000",
        "outline_width": 4, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "caption_dark": {
        "font": "Arial", "font_size": 50,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 2, "shadow": 1,
        "bold": False, "uppercase": False,
        "alignment": 2, "margin_v": 80,
        "words_per_entry": 4,
    },
    "minimal": {
        "font": "Arial", "font_size": 40,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 1, "shadow": 1,
        "bold": False, "uppercase": False,
        "alignment": 2, "margin_v": 120,
        "words_per_entry": 4,
    },
}


def _fmt_ass_time(seconds: float) -> str:
    """Format seconds to ASS timecode H:MM:SS.cc (centiseconds)."""
    seconds = max(0.0, seconds)
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = int(seconds * 100) % 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(
    scene_word_timings: list[tuple[float, list[dict]]],
    output_path: str | Path,
    style_name: str,
) -> Path:
    """
    Build an ASS subtitle file from per-scene word timing lists.

    scene_word_timings: [(scene_start_offset_seconds, word_list), ...]
        word_list: [{"word": str, "start": float, "end": float}, ...]
                   where start/end are relative to scene start
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not scene_word_timings or all(not words for _, words in scene_word_timings):
        output_path.write_text("")
        return output_path

    style = SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["tiktok_yellow"])
    bold_int = 1 if style["bold"] else 0

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {_VIDEO_W}",
        f"PlayResY: {_VIDEO_H}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: Default,{style['font']},{style['font_size']},"
            f"{style['primary_color']},{style['outline_color']},&H00000000,"
            f"{bold_int},0,0,0,100,100,0,0,1,{style['outline_width']},"
            f"{style['shadow']},{style['alignment']},10,10,{style['margin_v']},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    wpe = style["words_per_entry"]

    for scene_offset, word_list in scene_word_timings:
        if not word_list:
            continue
        # chunk words into groups of wpe
        for chunk_start in range(0, len(word_list), wpe):
            chunk = word_list[chunk_start:chunk_start + wpe]
            abs_start = scene_offset + chunk[0]["start"]
            abs_end   = scene_offset + chunk[-1]["end"]
            text = " ".join(w["word"] for w in chunk)
            if style["uppercase"]:
                text = text.upper()
            if not text.strip():
                continue
            lines.append(
                f"Dialogue: 0,{_fmt_ass_time(abs_start)},{_fmt_ass_time(abs_end)},"
                f"Default,,0,0,0,,{text}"
            )

    output_path.write_text("\n".join(lines) + "\n")
    return output_path
