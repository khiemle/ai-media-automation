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
