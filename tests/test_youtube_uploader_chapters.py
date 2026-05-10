import pytest
from uploader.youtube_uploader import (
    _format_chapters, _fmt_timestamp, build_description_with_chapters,
)


def test_fmt_timestamp_under_hour():
    assert _fmt_timestamp(0)    == "0:00"
    assert _fmt_timestamp(45)   == "0:45"
    assert _fmt_timestamp(120)  == "2:00"
    assert _fmt_timestamp(3599) == "59:59"


def test_fmt_timestamp_over_hour():
    assert _fmt_timestamp(3600)  == "1:00:00"
    assert _fmt_timestamp(3725)  == "1:02:05"
    assert _fmt_timestamp(43200) == "12:00:00"


def test_format_chapters_forces_first_to_zero():
    chapters = [{"seconds": 5, "title": "A"},
                {"seconds": 60, "title": "B"},
                {"seconds": 120, "title": "C"}]
    s = _format_chapters(chapters)
    assert s.startswith("0:00 A")


def test_format_chapters_long_form():
    chapters = [{"seconds": 0, "title": "A"},
                {"seconds": 4350, "title": "B"},
                {"seconds": 9908, "title": "C"}]
    s = _format_chapters(chapters)
    assert "1:12:30 B" in s
    assert "2:45:08 C" in s


def test_build_description_prepends_chapters():
    chapters = [{"seconds": 0, "title": "A"},
                {"seconds": 60, "title": "B"},
                {"seconds": 150, "title": "C"}]
    out = build_description_with_chapters(
        body="My video description.", chapters=chapters,
    )
    lines = out.splitlines()
    assert lines[0] == "0:00 A"
    assert lines[2] == "2:30 C"
    assert lines[3] == ""
    assert lines[4] == "My video description."


def test_build_description_no_chapters_when_under_3():
    out = build_description_with_chapters(
        body="My description.", chapters=[
            {"seconds": 0, "title": "A"},
            {"seconds": 60, "title": "B"},
        ],
    )
    assert out == "My description."


def test_build_description_no_chapters_arg():
    out = build_description_with_chapters(body="Hello", chapters=None)
    assert out == "Hello"
