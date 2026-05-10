import pytest
import logging
from console.backend.services.youtube_video_service import (
    build_chapters_from_tracks,
)


class FakeTrack:
    def __init__(self, title, duration_s):
        self.title = title
        self.duration_s = duration_s


def test_returns_none_for_one_track():
    assert build_chapters_from_tracks([FakeTrack("A", 60)], "gapless", 2.0) is None


def test_returns_none_for_two_tracks():
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("B", 60)], "gapless", 2.0
    )
    assert chapters is None


def test_returns_list_for_three_tracks():
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("B", 90), FakeTrack("C", 30)],
        "gapless", 2.0,
    )
    assert chapters == [
        {"seconds": 0,   "title": "A"},
        {"seconds": 60,  "title": "B"},
        {"seconds": 150, "title": "C"},
    ]


def test_crossfade_adjusts_boundaries():
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("B", 60), FakeTrack("C", 60)],
        "crossfade", 2.0,
    )
    assert chapters == [
        {"seconds": 0,   "title": "A"},
        {"seconds": 58,  "title": "B"},
        {"seconds": 116, "title": "C"},
    ]


def test_empty_title_falls_back(caplog):
    caplog.set_level(logging.WARNING)
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("", 60), FakeTrack(None, 60)],
        "gapless", 2.0,
    )
    assert chapters[1]["title"] == "Track 2"
    assert chapters[2]["title"] == "Track 3"
    warnings = [r for r in caplog.records if "empty title" in r.message.lower()]
    assert len(warnings) == 2


def test_build_chapters_via_service_with_real_orm_video(db):
    """Regression: previous version called video.template.slug which AttributeError'd
    because YoutubeVideo has no `template` relationship — only template_id."""
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.services.youtube_video_service import YoutubeVideoService
    from database.models import MusicTrack

    template = db.query(VideoTemplate).filter_by(slug="music").one()
    tracks = [
        MusicTrack(title=f"T{i}", file_path=f"/tmp/{i}.wav", duration_s=60.0)
        for i in range(3)
    ]
    db.add_all(tracks); db.commit()

    video = YoutubeVideo(
        title="x", template_id=template.id,
        music_track_ids=[t.id for t in tracks],
        track_transition="gapless",
        track_transition_seconds=2.0,
    )
    db.add(video); db.commit()

    chapters = YoutubeVideoService(db).build_chapters(video)
    assert chapters is not None
    assert len(chapters) == 3
    assert chapters[0]["seconds"] == 0


def test_build_chapters_via_service_returns_none_for_asmr(db):
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.services.youtube_video_service import YoutubeVideoService

    template = db.query(VideoTemplate).filter_by(slug="asmr").one()
    video = YoutubeVideo(title="x", template_id=template.id, target_duration_h=8.0)
    db.add(video); db.commit()

    assert YoutubeVideoService(db).build_chapters(video) is None
