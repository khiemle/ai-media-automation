"""
Tests for _build_subtitle_clips() — MoviePy-based subtitle compositing in composer.
No libass / ffmpeg subtitle filter required.
"""
import pytest


WORD_TIMINGS = [
    (0.0, [
        {"word": "hello", "start": 0.5, "end": 1.0},
        {"word": "world", "start": 1.0, "end": 1.5},
    ]),
    (5.0, [
        {"word": "test", "start": 0.2, "end": 0.8},
    ]),
]


def test_build_subtitle_clips_returns_list():
    from pipeline.composer import _build_subtitle_clips
    clips = _build_subtitle_clips(WORD_TIMINGS, "bold_center")
    # 3 words, words_per_entry=1 → 3 clips
    assert len(clips) == 3


def test_build_subtitle_clips_timing():
    from pipeline.composer import _build_subtitle_clips
    clips = _build_subtitle_clips(WORD_TIMINGS, "bold_center")
    # First clip: scene_offset=0, word start=0.5 → abs_start=0.5
    assert abs(clips[0].start - 0.5) < 0.01
    assert abs(clips[0].end - 1.0) < 0.01
    # Third clip: scene_offset=5.0, word start=0.2 → abs_start=5.2
    assert abs(clips[2].start - 5.2) < 0.01
    assert abs(clips[2].end - 5.8) < 0.01


def test_build_subtitle_clips_empty_timings():
    from pipeline.composer import _build_subtitle_clips
    clips = _build_subtitle_clips([], "bold_center")
    assert clips == []


def test_build_subtitle_clips_no_word_timing():
    from pipeline.composer import _build_subtitle_clips
    clips = _build_subtitle_clips([(0.0, []), (5.0, [])], "bold_center")
    assert clips == []


def test_build_subtitle_clips_skips_blank_words():
    from pipeline.composer import _build_subtitle_clips
    timings = [(0.0, [{"word": "  ", "start": 0.0, "end": 1.0}])]
    clips = _build_subtitle_clips(timings, "bold_center")
    assert clips == []


def test_build_subtitle_clips_groups_words_per_entry():
    from pipeline.composer import _build_subtitle_clips
    # caption_dark has words_per_entry=4
    words = [{"word": f"w{i}", "start": float(i), "end": float(i) + 0.5} for i in range(6)]
    clips = _build_subtitle_clips([(0.0, words)], "caption_dark")
    assert len(clips) == 2  # ceil(6/4) = 2


def test_build_subtitle_clips_unknown_style_falls_back():
    from pipeline.composer import _build_subtitle_clips
    clips = _build_subtitle_clips(WORD_TIMINGS, "nonexistent_style")
    # Falls back to bold_center → words_per_entry=1 → 3 clips
    assert len(clips) == 3
