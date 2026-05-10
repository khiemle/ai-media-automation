from pathlib import Path
import pytest
from PIL import Image
from pipeline.music_overlay import render_chip_png, render_sidebar_png


class FakeTrack:
    def __init__(self, title): self.title = title


def test_chip_png_is_full_canvas_rgba(tmp_path):
    tracks = [FakeTrack("Moonlit Stream"), FakeTrack("Hollow Echoes"),
              FakeTrack("Forest Veil")]
    out = render_chip_png(
        tracks=tracks, current_index=1,
        output_dir=tmp_path, canvas_w=1920, canvas_h=1080,
        cache_key="t1",
    )
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.mode == "RGBA"


def test_chip_png_truncates_long_title(tmp_path):
    tracks = [FakeTrack("A" * 100)]
    out = render_chip_png(
        tracks=tracks, current_index=0,
        output_dir=tmp_path, canvas_w=1920, canvas_h=1080,
        cache_key="t2",
    )
    assert Path(out).is_file()


def test_chip_png_caches_by_key(tmp_path):
    tracks = [FakeTrack("A"), FakeTrack("B")]
    p1 = render_chip_png(tracks, 0, tmp_path, 1920, 1080, "same-key")
    p2 = render_chip_png(tracks, 0, tmp_path, 1920, 1080, "same-key")
    assert p1 == p2
    p3 = render_chip_png(tracks, 0, tmp_path, 1920, 1080, "other-key")
    assert p3 != p1


def test_sidebar_full_canvas_rgba(tmp_path):
    tracks = [FakeTrack(f"Track {i}") for i in range(5)]
    out = render_sidebar_png(tracks, 2, tmp_path, 1920, 1080, "s1")
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.mode == "RGBA"


def test_sidebar_truncates_to_30_chars(tmp_path):
    tracks = [FakeTrack("A" * 100), FakeTrack("B"), FakeTrack("C")]
    out = render_sidebar_png(tracks, 0, tmp_path, 1920, 1080, "s2")
    assert Path(out).is_file()


def test_sidebar_handles_long_playlist(tmp_path):
    tracks = [FakeTrack(f"Track {i}") for i in range(20)]
    out = render_sidebar_png(tracks, 10, tmp_path, 1920, 1080, "s3")
    assert Path(out).is_file()


from pipeline.music_overlay import render_bottom_bar_png


class FakeTrackWithDuration:
    def __init__(self, title, duration_s):
        self.title = title
        self.duration_s = duration_s


def test_bottom_bar_full_canvas_rgba(tmp_path):
    tracks = [FakeTrackWithDuration(f"Track {i}", 60.0) for i in range(3)]
    out = render_bottom_bar_png(tracks, 1, tmp_path, 1920, 1080, "b1")
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.mode == "RGBA"


def test_bottom_bar_long_title_truncates(tmp_path):
    tracks = [FakeTrackWithDuration("A" * 100, 60.0)]
    out = render_bottom_bar_png(tracks, 0, tmp_path, 1920, 1080, "b2")
    assert Path(out).is_file()
