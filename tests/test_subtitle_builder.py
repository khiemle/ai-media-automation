from pathlib import Path
import pytest


def test_fmt_ass_time_zero():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(0.0) == "0:00:00.00"


def test_fmt_ass_time_seconds():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(1.45) == "0:00:01.45"


def test_fmt_ass_time_minutes():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(61.5) == "0:01:01.50"


def test_fmt_ass_time_hours():
    from pipeline.subtitle_builder import _fmt_ass_time
    assert _fmt_ass_time(3661.0) == "1:01:01.00"


def test_ass_color_to_rgb_white():
    from pipeline.subtitle_builder import _ass_color_to_rgb
    assert _ass_color_to_rgb("&H00FFFFFF") == (255, 255, 255)


def test_ass_color_to_rgb_black():
    from pipeline.subtitle_builder import _ass_color_to_rgb
    assert _ass_color_to_rgb("&H00000000") == (0, 0, 0)


def test_ass_color_to_rgb_yellow():
    from pipeline.subtitle_builder import _ass_color_to_rgb
    # &H0000FFFF → BB=00, GG=FF, RR=FF → (255, 255, 0)
    assert _ass_color_to_rgb("&H0000FFFF") == (255, 255, 0)


def test_build_ass_creates_file_with_dialogue(tmp_path):
    from pipeline.subtitle_builder import build_ass
    scene_word_timings = [
        (0.0, [
            {"word": "hello", "start": 1.0, "end": 2.0},
            {"word": "world", "start": 2.0, "end": 3.0},
        ]),
        (5.0, [
            {"word": "test", "start": 0.5, "end": 1.0},
        ]),
    ]
    out = tmp_path / "subtitles.ass"
    result = build_ass(scene_word_timings, out, "tiktok_yellow")
    assert result == out
    content = out.read_text()
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    # Uppercase is disabled — original case preserved for Vietnamese support
    assert "hello" in content
    assert "world" in content
    assert "test" in content
    # Scene 2 at offset 5.0s: "test" starts at 0.5s → absolute 5.5s
    assert "0:00:05.50" in content


def test_build_ass_groups_words_per_entry(tmp_path):
    from pipeline.subtitle_builder import build_ass
    # caption_dark has words_per_entry=4 and uppercase=False
    words = [{"word": f"word{i}", "start": float(i), "end": float(i) + 0.5} for i in range(6)]
    out = tmp_path / "subs.ass"
    build_ass([(0.0, words)], out, "caption_dark")
    content = out.read_text()
    dialogues = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 2  # 6 words / 4 per entry = 2 dialogue lines


def test_build_ass_falls_back_to_bold_center_for_unknown_style(tmp_path):
    from pipeline.subtitle_builder import build_ass
    out = tmp_path / "subs.ass"
    build_ass([(0.0, [{"word": "hi", "start": 0.0, "end": 1.0}])], out, "nonexistent_style")
    content = out.read_text()
    # bold_center preserves original case
    assert "hi" in content


def test_build_ass_empty_timings_writes_empty_file(tmp_path):
    from pipeline.subtitle_builder import build_ass
    out = tmp_path / "subs.ass"
    result = build_ass([], out, "tiktok_yellow")
    assert result == out
    assert out.read_text() == ""


def test_build_ass_skips_blank_words(tmp_path):
    from pipeline.subtitle_builder import build_ass
    out = tmp_path / "subs.ass"
    build_ass([(0.0, [{"word": "  ", "start": 0.0, "end": 1.0}])], out, "tiktok_yellow")
    content = out.read_text()
    dialogues = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 0
