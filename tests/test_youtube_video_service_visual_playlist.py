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


def test_create_video_persists_visual_playlist_fields(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    from console.backend.models.video_asset import VideoAsset

    template = _seed_template(db)
    a1 = VideoAsset(file_path="/tmp/a1.mp4", source="manual", asset_type="video_clip")
    a2 = VideoAsset(file_path="/tmp/a2.jpg", source="manual", asset_type="still_image")
    db.add_all([a1, a2])
    db.flush()

    svc = YoutubeVideoService(db)
    out = svc.create_video({
        "title": "t",
        "template_id": template.id,
        "visual_asset_ids":        [a1.id, a2.id],
        "visual_clip_durations_s": [0.0, 3.0],
        "visual_loop_mode":        "per_clip",
    })

    assert out["visual_asset_ids"]        == [a1.id, a2.id]
    assert out["visual_clip_durations_s"] == [0.0, 3.0]
    assert out["visual_loop_mode"]        == "per_clip"


def test_youtube_video_model_has_visual_playlist_columns(db):
    """The new playlist columns are exposed as Mapped attrs with correct defaults."""
    template = _seed_template(db)
    v = YoutubeVideo(title="t", template_id=template.id)
    db.add(v)
    db.flush()

    assert v.visual_asset_ids == []
    assert v.visual_clip_durations_s == []
    assert v.visual_loop_mode == "concat_loop"
