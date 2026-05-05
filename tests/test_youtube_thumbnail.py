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


def test_split_text_single_word():
    from pipeline.youtube_thumbnail import split_text
    assert split_text("FOCUS") == ["FOCUS"]


def test_split_text_three_words():
    from pipeline.youtube_thumbnail import split_text
    assert split_text("DEEP SLEEP MUSIC") == ["DEEP", "SLEEP", "MUSIC"]


def test_split_text_four_words_third_line_joins_remainder():
    from pipeline.youtube_thumbnail import split_text
    assert split_text("DEEP FOCUS STUDY MUSIC") == ["DEEP", "FOCUS", "STUDY MUSIC"]


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
