import uuid

from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo


def _seed_template(db, output_format: str = "landscape_long") -> VideoTemplate:
    """Insert a fresh VideoTemplate with a unique slug (DB session is per-test)."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    t = VideoTemplate(slug=slug, label="Test", output_format=output_format)
    db.add(t)
    db.flush()
    return t


def test_youtube_video_model_has_visual_playlist_columns(db):
    """The new playlist columns are exposed as Mapped attrs with correct defaults."""
    template = _seed_template(db)
    v = YoutubeVideo(title="t", template_id=template.id)
    db.add(v)
    db.flush()

    assert v.visual_asset_ids == []
    assert v.visual_clip_durations_s == []
    assert v.visual_loop_mode == "concat_loop"
