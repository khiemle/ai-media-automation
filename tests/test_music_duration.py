import pytest
from console.backend.services.youtube_video_service import (
    _compute_music_total_duration,
)

pytestmark = pytest.mark.render



class FakeTrack:
    def __init__(self, duration_s: float):
        self.duration_s = duration_s


def test_gapless_sums_durations():
    tracks = [FakeTrack(60.0), FakeTrack(45.0), FakeTrack(90.0)]
    total, boundaries = _compute_music_total_duration(tracks, "gapless", 2.0)
    assert total == pytest.approx(195.0)
    assert boundaries == [0.0, 60.0, 105.0]


def test_crossfade_subtracts_overlap():
    tracks = [FakeTrack(60.0), FakeTrack(60.0), FakeTrack(60.0)]
    total, boundaries = _compute_music_total_duration(tracks, "crossfade", 2.0)
    assert total == pytest.approx(176.0)
    assert boundaries == pytest.approx([0.0, 58.0, 116.0])


def test_gap_adds_silence():
    tracks = [FakeTrack(60.0), FakeTrack(60.0)]
    total, boundaries = _compute_music_total_duration(tracks, "gap", 1.5)
    assert total == pytest.approx(121.5)
    assert boundaries == pytest.approx([0.0, 61.5])


def test_single_track_ignores_transition():
    tracks = [FakeTrack(120.0)]
    total, boundaries = _compute_music_total_duration(tracks, "crossfade", 2.0)
    assert total == pytest.approx(120.0)
    assert boundaries == [0.0]


def test_empty_tracks_returns_zero():
    total, boundaries = _compute_music_total_duration([], "gapless", 2.0)
    assert total == 0.0
    assert boundaries == []


from console.backend.services.youtube_video_service import _resolve_music_tracks
from database.models import MusicTrack


class FakeVideo:
    def __init__(self, music_track_ids=None, music_track_id=None):
        self.music_track_ids = music_track_ids
        self.music_track_id = music_track_id


def test_resolve_preserves_order(db):
    a = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=10.0)
    b = MusicTrack(title="B", file_path="/tmp/b.wav", duration_s=20.0)
    db.add_all([a, b]); db.commit()
    video = FakeVideo(music_track_ids=[b.id, a.id])
    result = _resolve_music_tracks(video, db)
    assert [t.id for t in result] == [b.id, a.id]


def test_resolve_falls_back_to_single_id(db):
    a = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=10.0)
    db.add(a); db.commit()
    video = FakeVideo(music_track_ids=[], music_track_id=a.id)
    result = _resolve_music_tracks(video, db)
    assert [t.id for t in result] == [a.id]


def test_resolve_returns_empty_for_no_ids(db):
    video = FakeVideo()
    assert _resolve_music_tracks(video, db) == []


def test_resolve_raises_for_missing_id(db):
    a = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=10.0)
    db.add(a); db.commit()
    video = FakeVideo(music_track_ids=[a.id, 999999])
    with pytest.raises(ValueError, match="music_track_ids not found"):
        _resolve_music_tracks(video, db)
