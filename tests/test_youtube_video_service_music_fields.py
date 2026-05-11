"""Round-trip tests for the 8 music-template fields on create_video and update_video."""
import uuid

import pytest
from pydantic import ValidationError

from console.backend.models.video_template import VideoTemplate
from console.backend.routers.youtube_videos import YoutubeVideoCreate, YoutubeVideoUpdate
from console.backend.services.youtube_video_service import YoutubeVideoService


def _seed_template(db) -> VideoTemplate:
    slug = f"asmr-{uuid.uuid4().hex[:8]}"
    t = VideoTemplate(slug=slug, label="ASMR Test", output_format="landscape_long")
    db.add(t)
    db.flush()
    return t


def test_music_fields_round_trip_create(db):
    template = _seed_template(db)
    svc = YoutubeVideoService(db)
    result = svc.create_video({
        "title": "x",
        "template_id": template.id,
        "track_transition": "crossfade",
        "track_transition_seconds": 3.5,
        "spectrum_enabled": True,
        "spectrum_color": "#7c6af7",
    }, user_id=None)

    assert result["track_transition"] == "crossfade"
    assert result["track_transition_seconds"] == 3.5
    assert result["spectrum_enabled"] is True
    assert result["spectrum_color"] == "#7c6af7"
    # Defaults preserved for unspecified fields
    assert result["spectrum_position"] == "bottom"
    assert result["spectrum_height_pct"] == 0.12
    assert result["spectrum_opacity"] == 0.6
    assert result["playlist_overlay_style"] is None


def test_music_fields_defaults_on_create(db):
    """Fields not supplied get their spec defaults, not None."""
    template = _seed_template(db)
    svc = YoutubeVideoService(db)
    result = svc.create_video({"title": "defaults", "template_id": template.id}, user_id=None)

    assert result["track_transition"] == "gapless"
    assert result["track_transition_seconds"] == 2.0
    assert result["playlist_overlay_style"] is None
    assert result["spectrum_enabled"] is False
    assert result["spectrum_position"] == "bottom"
    assert result["spectrum_height_pct"] == 0.12
    assert result["spectrum_color"] == "#ffffff"
    assert result["spectrum_opacity"] == 0.6


def test_music_fields_round_trip_update(db):
    template = _seed_template(db)
    svc = YoutubeVideoService(db)
    created = svc.create_video({"title": "x", "template_id": template.id}, user_id=None)
    video_id = created["id"]

    updated = svc.update_video(video_id, {
        "playlist_overlay_style": "sidebar",
        "spectrum_enabled": True,
    }, user_id=None)

    assert updated["playlist_overlay_style"] == "sidebar"
    assert updated["spectrum_enabled"] is True
    # Other music fields stay at their creation defaults
    assert updated["track_transition"] == "gapless"
    assert updated["spectrum_color"] == "#ffffff"


# ── Issue 1: NOT NULL fields reject explicit null on Create ───────────────────


def test_create_rejects_null_spectrum_enabled():
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_enabled=None)


def test_create_rejects_null_track_transition():
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, track_transition=None)


def test_create_rejects_null_spectrum_position():
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_position=None)


def test_create_rejects_null_spectrum_color():
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_color=None)


# ── Issue 2: Range validators on Create ──────────────────────────────────────


def test_create_rejects_out_of_range_height():
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_height_pct=0.6)
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_height_pct=0.0)


def test_create_rejects_out_of_range_opacity():
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_opacity=1.5)


def test_create_rejects_out_of_range_transition_seconds():
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, track_transition_seconds=0.1)
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, track_transition_seconds=15.0)


# ── Range validators on Update ───────────────────────────────────────────────


def test_update_rejects_out_of_range_height():
    with pytest.raises(ValidationError):
        YoutubeVideoUpdate(spectrum_height_pct=0.9)
    with pytest.raises(ValidationError):
        YoutubeVideoUpdate(spectrum_height_pct=0.0)


def test_update_rejects_out_of_range_opacity():
    with pytest.raises(ValidationError):
        YoutubeVideoUpdate(spectrum_opacity=-0.1)


def test_update_rejects_out_of_range_transition_seconds():
    with pytest.raises(ValidationError):
        YoutubeVideoUpdate(track_transition_seconds=0.1)
    with pytest.raises(ValidationError):
        YoutubeVideoUpdate(track_transition_seconds=99.0)


# ── Issue 1: Service guard rejects explicit null on Update ───────────────────


def test_update_rejects_explicit_null_for_not_null_field(db):
    template = _seed_template(db)
    svc = YoutubeVideoService(db)
    created = svc.create_video({"title": "x", "template_id": template.id}, user_id=None)
    with pytest.raises(ValueError, match="cannot be null"):
        svc.update_video(created["id"], {"spectrum_enabled": None}, user_id=None)


def test_update_rejects_explicit_null_transition(db):
    template = _seed_template(db)
    svc = YoutubeVideoService(db)
    created = svc.create_video({"title": "x", "template_id": template.id}, user_id=None)
    with pytest.raises(ValueError, match="cannot be null"):
        svc.update_video(created["id"], {"track_transition": None}, user_id=None)


def test_update_allows_null_playlist_overlay_style(db):
    """playlist_overlay_style IS legitimately nullable — setting it to None is allowed."""
    template = _seed_template(db)
    svc = YoutubeVideoService(db)
    created = svc.create_video(
        {"title": "x", "template_id": template.id, "playlist_overlay_style": "chip"},
        user_id=None,
    )
    updated = svc.update_video(created["id"], {"playlist_overlay_style": None}, user_id=None)
    assert updated["playlist_overlay_style"] is None


# ── spectrum_style round-trip tests ─────────────────────────────────────────


def test_spectrum_style_round_trip_create(db):
    from console.backend.models.video_template import VideoTemplate
    from console.backend.services.youtube_video_service import YoutubeVideoService
    from database.models import MusicTrack

    music = db.query(VideoTemplate).filter_by(slug="music").one()
    t = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=60.0)
    db.add(t); db.commit()
    svc = YoutubeVideoService(db)
    result = svc.create_video({
        "title": "x", "template_id": music.id,
        "music_track_ids": [t.id],
        "spectrum_enabled": True,
        "spectrum_style": "bars",
    }, user_id=None)
    assert result["spectrum_style"] == "bars"


def test_spectrum_style_defaults_to_classic(db):
    from console.backend.models.video_template import VideoTemplate
    from console.backend.services.youtube_video_service import YoutubeVideoService
    asmr = db.query(VideoTemplate).filter_by(slug="asmr").one()
    svc = YoutubeVideoService(db)
    result = svc.create_video({
        "title": "x", "template_id": asmr.id,
        "target_duration_h": 8.0,
    }, user_id=None)
    assert result["spectrum_style"] == "classic"


def test_spectrum_style_update_rejects_null(db):
    import pytest
    from console.backend.models.video_template import VideoTemplate
    from console.backend.services.youtube_video_service import YoutubeVideoService
    asmr = db.query(VideoTemplate).filter_by(slug="asmr").one()
    svc = YoutubeVideoService(db)
    created = svc.create_video({"title": "x", "template_id": asmr.id}, user_id=None)
    with pytest.raises(ValueError, match="cannot be null"):
        svc.update_video(created["id"], {"spectrum_style": None}, user_id=None)


def test_spectrum_style_pydantic_rejects_invalid():
    import pytest
    from pydantic import ValidationError
    from console.backend.routers.youtube_videos import YoutubeVideoCreate
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_style="rainbow")
