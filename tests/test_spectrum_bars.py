import numpy as np
import pytest

from pipeline.spectrum_bars import _build_bar_template


def test_bar_template_shape_and_dtype():
    tpl = _build_bar_template(bar_w=20, bar_h=100, radius=2, color_rgb=(255, 255, 255))
    assert tpl.shape == (100, 20, 4)
    assert tpl.dtype == np.uint8


def test_bar_template_interior_fully_opaque():
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[50, 10, 3] == 255   # center
    assert tpl[99, 10, 3] == 255   # bottom-middle
    assert tuple(tpl[50, 10, :3]) == (255, 255, 255)


def test_bar_template_top_corners_anti_aliased():
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[0, 0, 3] < 255             # top-left corner alpha < 255
    assert tpl[0, 19, 3] < 255            # top-right corner alpha < 255


def test_bar_template_bottom_corners_NOT_rounded():
    """Bars grow upward; bottom corners should be sharp (full alpha)."""
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[99, 0, 3] == 255
    assert tpl[99, 19, 3] == 255


def test_bar_template_zero_radius_is_pure_rectangle():
    tpl = _build_bar_template(20, 100, 0, (255, 255, 255))
    assert np.all(tpl[..., 3] == 255)


def test_bar_template_respects_color():
    tpl = _build_bar_template(20, 100, 2, (124, 106, 247))
    assert tuple(tpl[50, 10, :3]) == (124, 106, 247)
