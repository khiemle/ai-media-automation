import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def _make_video(sfx_overrides=None, visual_asset_id=None, music_track_id=None,
                target_duration_h=3.0, output_quality="1080p",
                music_track_ids=None, sfx_pool=None,
                sfx_density_seconds=None, sfx_seed=None,
                black_from_seconds=None):
    v = MagicMock()
    v.visual_asset_id = visual_asset_id
    v.music_track_id = music_track_id
    v.sfx_overrides = sfx_overrides
    v.target_duration_h = target_duration_h
    v.output_quality = output_quality
    # ASMR/soundscape extension attrs — default to empty / None so existing
    # tests don't accidentally trigger multi-music / SFX-pool / blackout paths.
    v.music_track_ids = music_track_ids if music_track_ids is not None else []
    v.sfx_pool = sfx_pool if sfx_pool is not None else []
    v.sfx_density_seconds = sfx_density_seconds
    v.sfx_seed = sfx_seed
    v.black_from_seconds = black_from_seconds
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


# ── render_landscape ──────────────────────────────────────────────────────────

def test_render_landscape_raises_when_ffmpeg_missing():
    from pipeline.youtube_ffmpeg import render_landscape
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            render_landscape(_make_video(), Path("/tmp/out.mp4"), MagicMock())


def test_render_landscape_calls_ffmpeg_with_landscape_scale(tmp_path):
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock())

    cmd = " ".join(mock_run.call_args[0][0])
    assert "1920:1080" in cmd or "1920x1080" in cmd


def test_render_landscape_uses_duration_from_video(tmp_path):
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(target_duration_h=1.0), output, MagicMock())

    cmd_list = mock_run.call_args[0][0]
    t_idx = cmd_list.index("-t")
    assert cmd_list[t_idx + 1] == "3600"


# ── render_portrait_short ─────────────────────────────────────────────────────

def test_render_portrait_short_raises_when_ffmpeg_missing():
    from pipeline.youtube_ffmpeg import render_portrait_short
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            render_portrait_short(
                _make_video(), _make_template(), Path("/tmp/out.mp4"), MagicMock()
            )


def test_render_portrait_short_uses_portrait_resolution(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch full video!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "1080:1920" in cmd


def test_render_portrait_short_includes_center_crop_filter(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Subscribe!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "crop=ih*9/16:ih:(iw-ih*9/16)/2:0" in cmd


def test_render_portrait_short_includes_drawtext_with_cta_text(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch full video!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(short_duration_s=58), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "drawtext=text=" in cmd
    assert "Watch full video" in cmd


def test_render_portrait_short_cta_enabled_in_last_10s(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(short_duration_s=30), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "between(t,20,30)" in cmd


def test_render_portrait_short_uses_template_duration(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(short_duration_s=45), output, MagicMock())
    cmd_list = mock_run.call_args[0][0]
    t_idx = cmd_list.index("-t")
    assert cmd_list[t_idx + 1] == "45"


def test_render_portrait_short_falls_back_to_template_cta_text(tmp_path):
    video = _make_video(sfx_overrides={})  # no cta key
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(
            video, _make_template(short_cta_text="See link in description!"), output, MagicMock()
        )
    cmd = " ".join(mock_run.call_args[0][0])
    assert "See link in description" in cmd


def test_render_portrait_short_falls_back_to_hardcoded_default_when_no_cta(tmp_path):
    video = _make_video(sfx_overrides={})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(
            video, _make_template(short_cta_text=None), output, MagicMock()
        )
    cmd = " ".join(mock_run.call_args[0][0])
    assert "Watch the full video" in cmd
