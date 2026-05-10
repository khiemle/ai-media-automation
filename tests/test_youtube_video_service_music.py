import pytest
from console.backend.services.youtube_video_service import YoutubeVideoService
from console.backend.models.video_template import VideoTemplate
from database.models import MusicTrack


@pytest.fixture
def music_template(db):
    return db.query(VideoTemplate).filter_by(slug="music").one()


@pytest.fixture
def two_tracks(db):
    a = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=120.0)
    b = MusicTrack(title="B", file_path="/tmp/b.wav", duration_s=180.0)
    db.add_all([a, b]); db.commit()
    return [a.id, b.id]


def test_music_rejects_target_duration(db, music_template, two_tracks):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="derives duration"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": two_tracks,
            "target_duration_h": 8.0,
        }, user_id=None)


def test_music_rejects_blackout(db, music_template, two_tracks):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="does not support blackout"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": two_tracks,
            "black_from_seconds": 60,
        }, user_id=None)


def test_music_rejects_sound_layers(db, music_template, two_tracks):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="does not support SFX layers"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": two_tracks,
            "sound_layers": {"background": {"asset_id": 1, "volume": 0.1}},
        }, user_id=None)


def test_music_requires_at_least_one_track(db, music_template):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="at least 1 music track"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": [],
        }, user_id=None)


def test_single_track_nullifies_overlay_style(db, music_template):
    a = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=120.0)
    db.add(a); db.commit()
    svc = YoutubeVideoService(db)
    result = svc.create_video({
        "title": "x", "template_id": music_template.id,
        "music_track_ids": [a.id],
        "playlist_overlay_style": "chip",
    }, user_id=None)
    assert result["playlist_overlay_style"] is None


def test_crossfade_too_long_rejected(db, music_template):
    short = MusicTrack(title="short", file_path="/tmp/s.wav", duration_s=4.0)
    long  = MusicTrack(title="long",  file_path="/tmp/l.wav", duration_s=120.0)
    db.add_all([short, long]); db.commit()
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="exceeds half"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": [short.id, long.id],
            "track_transition": "crossfade",
            "track_transition_seconds": 3.0,
        }, user_id=None)


def test_asmr_template_unaffected(db):
    asmr = db.query(VideoTemplate).filter_by(slug="asmr").one()
    svc = YoutubeVideoService(db)
    result = svc.create_video({
        "title": "x", "template_id": asmr.id,
        "target_duration_h": 8.0,
        "black_from_seconds": 7200,
    }, user_id=None)
    assert result["target_duration_h"] == 8.0
