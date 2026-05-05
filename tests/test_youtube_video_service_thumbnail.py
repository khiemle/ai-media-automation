# tests/test_youtube_video_service_thumbnail.py
from unittest.mock import MagicMock


def _make_video(**kwargs):
    v = MagicMock()
    defaults = dict(
        id=1, title="Test", template_id=1, theme=None, status="draft",
        music_track_id=None, visual_asset_id=None, parent_youtube_video_id=None,
        sfx_overrides=None, target_duration_h=1.0, output_quality="1080p",
        seo_title=None, seo_description=None, seo_tags=None, celery_task_id=None,
        output_path=None, music_track_ids=[], sfx_pool=[], sfx_density_seconds=None,
        sfx_seed=None, black_from_seconds=None, skip_previews=True, render_parts=[],
        audio_preview_path=None, video_preview_path=None, visual_asset_ids=[],
        visual_clip_durations_s=[], visual_loop_mode="concat_loop",
        thumbnail_asset_id=None, thumbnail_text=None, thumbnail_path=None,
        created_at=None, updated_at=None,
    )
    defaults.update(kwargs)
    for k, val in defaults.items():
        setattr(v, k, val)
    return v


def test_video_to_dict_includes_thumbnail_fields():
    from console.backend.services.youtube_video_service import _video_to_dict
    v = _make_video(
        thumbnail_asset_id=5,
        thumbnail_text="DEEP FOCUS",
        thumbnail_path="/assets/thumbnails/generated/yt_1.png",
    )
    d = _video_to_dict(v)
    assert d["thumbnail_asset_id"] == 5
    assert d["thumbnail_text"] == "DEEP FOCUS"
    assert d["thumbnail_path"] == "/assets/thumbnails/generated/yt_1.png"


def test_video_to_dict_thumbnail_fields_default_none():
    from console.backend.services.youtube_video_service import _video_to_dict
    v = _make_video()
    d = _video_to_dict(v)
    assert d["thumbnail_asset_id"] is None
    assert d["thumbnail_text"] is None
    assert d["thumbnail_path"] is None
