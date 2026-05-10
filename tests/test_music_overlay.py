from pathlib import Path
import pytest
from PIL import Image
from pipeline.music_overlay import render_chip_png


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
