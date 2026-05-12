import uuid
import pytest

from console.backend.models.video_asset import VideoAsset
from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo
from database.models import MusicTrack


def _seed_template(db, output_format: str = "landscape_long") -> VideoTemplate:
    slug = f"recreate-{uuid.uuid4().hex[:8]}"
    t = VideoTemplate(slug=slug, label="Test", output_format=output_format)
    db.add(t); db.flush()
    return t


def _seed_music_track(db) -> MusicTrack:
    t = MusicTrack(title=f"track-{uuid.uuid4().hex[:6]}", file_path="/tmp/t.wav", duration_s=120.0)
    db.add(t); db.flush()
    return t


def _seed_video_asset(db) -> VideoAsset:
    a = VideoAsset(file_path=f"/tmp/asset-{uuid.uuid4().hex[:6]}.mp4")
    db.add(a); db.flush()
    return a


def _seed_full_video(db, template) -> YoutubeVideo:
    """A done video with every recreate-able field populated."""
    track = _seed_music_track(db)
    asset = _seed_video_asset(db)

    v = YoutubeVideo(
        title="Source Video",
        template_id=template.id,
        theme="cozy",
        music_track_id=track.id,
        visual_asset_id=asset.id,
        music_track_ids=[track.id],
        visual_asset_ids=[asset.id],
        visual_clip_durations_s=[5.0, 7.5],
        visual_loop_mode="per_clip",
        sfx_overrides={"foreground": {"asset_id": 99, "volume": 0.7}},
        sfx_pool=[{"asset_id": 50, "weight": 1.0}],
        sfx_density_seconds=30,
        sfx_seed=42,
        seo_title="SEO title",
        seo_description="SEO description",
        seo_tags=["one", "two"],
        target_duration_h=2.0,
        output_quality="1080p",
        sound_layers={"background": {"asset_id": 1}},
        track_transition="crossfade",
        track_transition_seconds=3.5,
        playlist_overlay_style="chip",
        spectrum_enabled=True,
        spectrum_height_pct=0.18,
        spectrum_color="#abcdef",
        spectrum_opacity=0.5,
        spectrum_style="bars",
        spectrum_bar_width_px=12.0,
        spectrum_bar_count=64,
        spectrum_align_horizontal="left",
        spectrum_align_vertical="top",
        thumbnail_asset_id=asset.id,
        thumbnail_text="DEEP FOCUS",
        black_from_seconds=120,
        skip_previews=False,
        # runtime fields (must be reset on recreate)
        status="done",
        output_path="/tmp/source_output.mp4",
        audio_preview_path="/tmp/aud.mp3",
        video_preview_path="/tmp/vid.mp4",
        celery_task_id="task-abc",
        thumbnail_path="/tmp/thumb.png",
        render_parts=[{"part": "1"}],
        parent_youtube_video_id=None,
    )
    db.add(v); db.flush()
    return v


def test_recreate_clones_configuration_fields(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)

    svc = YoutubeVideoService(db)
    new = svc.recreate(source.id)
    db.flush()

    cloned = [
        "template_id", "theme",
        "music_track_id", "visual_asset_id",
        "music_track_ids", "visual_asset_ids",
        "visual_clip_durations_s", "visual_loop_mode",
        "sfx_overrides", "sfx_pool", "sfx_density_seconds", "sfx_seed",
        "seo_title", "seo_description", "seo_tags",
        "target_duration_h", "output_quality",
        "sound_layers",
        "track_transition", "track_transition_seconds", "playlist_overlay_style",
        "spectrum_enabled", "spectrum_height_pct", "spectrum_color",
        "spectrum_opacity", "spectrum_style", "spectrum_bar_width_px",
        "spectrum_bar_count", "spectrum_align_horizontal", "spectrum_align_vertical",
        "thumbnail_asset_id", "thumbnail_text",
        "black_from_seconds", "skip_previews",
    ]
    for field in cloned:
        assert getattr(new, field) == getattr(source, field), \
            f"field {field!r} not cloned correctly: {getattr(new, field)!r} != {getattr(source, field)!r}"


def test_recreate_resets_runtime_fields(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)

    svc = YoutubeVideoService(db)
    new = svc.recreate(source.id)
    db.flush()

    assert new.status == "draft"
    assert new.output_path is None
    assert new.audio_preview_path is None
    assert new.video_preview_path is None
    assert new.celery_task_id is None
    assert new.thumbnail_path is None
    assert new.render_parts == []
    assert new.parent_youtube_video_id is None


def test_recreate_title_appended_with_recreate(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)
    new = YoutubeVideoService(db).recreate(source.id)
    db.flush()
    assert new.title == "Source Video (recreate)"


def test_recreate_assigns_new_id(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)
    new = YoutubeVideoService(db).recreate(source.id)
    db.flush()
    assert new.id is not None
    assert new.id != source.id


def test_recreate_missing_source_raises(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    with pytest.raises(ValueError, match="not found"):
        YoutubeVideoService(db).recreate(999999)


def test_recreate_endpoint_returns_new_id(db, monkeypatch):
    """The POST endpoint returns {id: <new_id>} and persists the draft."""
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.models.youtube_video import YoutubeVideo

    template = _seed_template(db)
    source = _seed_full_video(db, template)
    db.commit()  # endpoint will open its own session

    # Override get_db to share the test session
    def _get_db_override():
        yield db

    class _FakeUser:
        id = 1
        role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with TestClient(app) as client:
            resp = client.post(f"/api/youtube-videos/{source.id}/recreate")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "id" in body
        new_id = body["id"]
        assert new_id != source.id

        new_video = db.get(YoutubeVideo, new_id)
        assert new_video is not None
        assert new_video.status == "draft"
        assert new_video.title == "Source Video (recreate)"
    finally:
        app.dependency_overrides.clear()


def test_recreate_endpoint_404_when_missing(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    def _get_db_override():
        yield db

    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with TestClient(app) as client:
            resp = client.post("/api/youtube-videos/999999/recreate")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
