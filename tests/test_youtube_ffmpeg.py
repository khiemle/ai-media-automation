import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def _make_video(sfx_overrides=None, visual_asset_id=None, music_track_id=None,
                target_duration_h=3.0, output_quality="1080p"):
    v = MagicMock()
    v.visual_asset_id = visual_asset_id
    v.music_track_id = music_track_id
    v.sfx_overrides = sfx_overrides
    v.target_duration_h = target_duration_h
    v.output_quality = output_quality
    return v


def _make_template(short_duration_s=58, short_cta_text=None):
    t = MagicMock()
    t.short_duration_s = short_duration_s
    t.short_cta_text = short_cta_text
    return t


# ── resolve_visual ────────────────────────────────────────────────────────────

def test_resolve_visual_returns_none_when_no_asset_id():
    from pipeline.youtube_ffmpeg import resolve_visual
    assert resolve_visual(_make_video(visual_asset_id=None), MagicMock()) is None


def test_resolve_visual_returns_file_path():
    fake_asset = MagicMock()
    fake_asset.file_path = "/videos/forest.mp4"
    db = MagicMock()
    db.get.return_value = fake_asset
    from pipeline.youtube_ffmpeg import resolve_visual
    assert resolve_visual(_make_video(visual_asset_id=42), db) == "/videos/forest.mp4"


def test_resolve_visual_returns_none_when_asset_not_found():
    db = MagicMock()
    db.get.return_value = None
    from pipeline.youtube_ffmpeg import resolve_visual
    assert resolve_visual(_make_video(visual_asset_id=99), db) is None


# ── resolve_audio ─────────────────────────────────────────────────────────────

def test_resolve_audio_returns_none_when_no_track_id():
    from pipeline.youtube_ffmpeg import resolve_audio
    assert resolve_audio(_make_video(music_track_id=None), MagicMock()) is None


def test_resolve_audio_returns_file_path():
    fake_track = MagicMock()
    fake_track.file_path = "/music/ambient.mp3"
    db = MagicMock()
    db.get.return_value = fake_track
    from pipeline.youtube_ffmpeg import resolve_audio
    assert resolve_audio(_make_video(music_track_id=7), db) == "/music/ambient.mp3"


# ── resolve_sfx_layers ────────────────────────────────────────────────────────

def test_resolve_sfx_layers_empty_when_no_overrides():
    from pipeline.youtube_ffmpeg import resolve_sfx_layers
    assert resolve_sfx_layers(_make_video(sfx_overrides=None), MagicMock()) == []


def test_resolve_sfx_layers_skips_layer_with_no_asset_id():
    from pipeline.youtube_ffmpeg import resolve_sfx_layers
    video = _make_video(sfx_overrides={"foreground": {"volume": 0.5}})
    assert resolve_sfx_layers(video, MagicMock()) == []


# ── _escape_drawtext ──────────────────────────────────────────────────────────

def test_escape_drawtext_escapes_colon():
    from pipeline.youtube_ffmpeg import _escape_drawtext
    assert _escape_drawtext("Watch: full video") == "Watch\\: full video"


def test_escape_drawtext_escapes_backslash():
    from pipeline.youtube_ffmpeg import _escape_drawtext
    assert _escape_drawtext("Watch\\video") == "Watch\\\\video"
