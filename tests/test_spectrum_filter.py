from pipeline.youtube_ffmpeg import build_spectrum_filter


def test_disabled_returns_empty():
    chain, inputs = build_spectrum_filter(
        enabled=False, position="bottom", height_pct=0.12,
        color="#ffffff", opacity=0.6, canvas_w=1920, canvas_h=1080,
    )
    assert chain == ""
    assert inputs == []


def test_bottom_position_renders_overlay_at_bottom():
    chain, inputs = build_spectrum_filter(
        enabled=True, position="bottom", height_pct=0.10,
        color="#ffffff", opacity=0.5, canvas_w=1920, canvas_h=1080,
    )
    assert "showfreqs" in chain
    assert "size=1920x108" in chain  # 1080 * 0.10
    assert "overlay=0:972" in chain  # 1080 - 108
    assert "colorchannelmixer=aa=0.5" in chain
    assert inputs == []


def test_center_position():
    chain, _ = build_spectrum_filter(
        enabled=True, position="center", height_pct=0.20,
        color="#7c6af7", opacity=0.8, canvas_w=1920, canvas_h=1080,
    )
    # height = 216, y = (1080 - 216) // 2 = 432
    assert "size=1920x216" in chain
    assert "overlay=0:432" in chain
