import pytest
from pathlib import Path


def _make_tiny_image(tmp_path: Path) -> Path:
    from PIL import Image
    p = tmp_path / "source.jpg"
    Image.new("RGB", (100, 100), color=(200, 50, 50)).save(p)
    return p


def test_generate_thumbnail_no_text_resizes_to_1280x720(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "out.png"
    result = generate_thumbnail(src, out, text=None)
    from PIL import Image
    assert result == out
    assert out.exists()
    assert Image.open(out).size == (1280, 720)


def test_generate_thumbnail_empty_string_resizes_only(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "out.png"
    generate_thumbnail(src, out, text="")
    from PIL import Image
    assert Image.open(out).size == (1280, 720)


def test_generate_thumbnail_creates_parent_dirs(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "a" / "b" / "c" / "out.png"
    generate_thumbnail(src, out, text=None)
    assert out.exists()


def test_generate_thumbnail_with_text_correct_size(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail, DEFAULT_REGULAR_FONT
    if not DEFAULT_REGULAR_FONT.exists():
        pytest.skip("System font not available in this environment")
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "out.png"
    generate_thumbnail(src, out, text="DEEP FOCUS")
    from PIL import Image
    assert Image.open(out).size == (1280, 720)


def test_wrap_plan_single_word_default_bold_1():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("FOCUS", bold_word_count=1) == [
        [("FOCUS", True)],
    ]


def test_wrap_plan_three_words_default_bold_1():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP SLEEP MUSIC", bold_word_count=1) == [
        [("DEEP", True)],
        [("SLEEP", False)],
        [("MUSIC", False)],
    ]


def test_wrap_plan_four_words_remainder_on_third_line():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP FOCUS STUDY MUSIC", bold_word_count=1) == [
        [("DEEP", True)],
        [("FOCUS", False)],
        [("STUDY", False), ("MUSIC", False)],
    ]


def test_wrap_plan_bold_count_two_spans_two_lines():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP SLEEP MUSIC", bold_word_count=2) == [
        [("DEEP", True)],
        [("SLEEP", True)],
        [("MUSIC", False)],
    ]


def test_wrap_plan_bold_count_three_on_five_words_mixes_third_line():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP FOCUS STUDY MUSIC LOOP", bold_word_count=3) == [
        [("DEEP", True)],
        [("FOCUS", True)],
        [("STUDY", True), ("MUSIC", False), ("LOOP", False)],
    ]


def test_wrap_plan_bold_count_zero_all_regular():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP FOCUS", bold_word_count=0) == [
        [("DEEP", False)],
        [("FOCUS", False)],
    ]


def test_wrap_plan_bold_count_exceeds_word_count_caps():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP", bold_word_count=10) == [
        [("DEEP", True)],
    ]


def test_wrap_plan_empty_text_raises():
    from pipeline.youtube_thumbnail import wrap_plan
    import pytest
    with pytest.raises(ValueError):
        wrap_plan("", bold_word_count=1)


def test_cover_resize_landscape_to_1280x720():
    from pipeline.youtube_thumbnail import cover_resize
    from PIL import Image
    result = cover_resize(Image.new("RGB", (2560, 1440)), (1280, 720))
    assert result.size == (1280, 720)


def test_cover_resize_portrait_to_1280x720():
    from pipeline.youtube_thumbnail import cover_resize
    from PIL import Image
    result = cover_resize(Image.new("RGB", (1080, 1920)), (1280, 720))
    assert result.size == (1280, 720)


def test_generate_thumbnail_bold_pixels_differ_from_regular_pixels(tmp_path):
    """Smoke-test that the bold span renders with visibly different stroke than the regular span.

    We render the same thumbnail twice — once with bold_word_count=0 (all regular)
    and once with bold_word_count=1 — and assert the resulting PNGs differ.
    This catches the regression where bold and regular fonts collapsed to the
    same file."""
    from pipeline.youtube_thumbnail import generate_thumbnail, DEFAULT_BOLD_FONT, DEFAULT_REGULAR_FONT
    import pytest
    if DEFAULT_BOLD_FONT == DEFAULT_REGULAR_FONT:
        pytest.skip("Bold font equals regular font on this system — visual diff not meaningful")

    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1280, 720), color=(50, 60, 70)).save(src)

    out_regular = tmp_path / "out_regular.png"
    out_bold    = tmp_path / "out_bold.png"

    generate_thumbnail(src, out_regular, text="DEEP FOCUS MUSIC", bold_word_count=0)
    generate_thumbnail(src, out_bold,    text="DEEP FOCUS MUSIC", bold_word_count=1)

    assert out_regular.read_bytes() != out_bold.read_bytes(), \
        "Bold and regular thumbnails are byte-identical — bold rendering isn't actually bolding."


def test_generate_thumbnail_accepts_bold_word_count_kwarg(tmp_path):
    """Public API: generate_thumbnail accepts bold_word_count and runs without error."""
    from pipeline.youtube_thumbnail import generate_thumbnail
    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1280, 720), color=(50, 60, 70)).save(src)
    out = tmp_path / "out.png"
    generate_thumbnail(src, out, text="DEEP FOCUS", bold_word_count=2)
    assert out.exists()
