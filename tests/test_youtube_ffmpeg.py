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


# ── _probe_duration ────────────────────────────────────────────────────────────

def test_probe_duration_returns_float_from_ffprobe_stdout():
    from pipeline.youtube_ffmpeg import _probe_duration
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="120.5\n", stderr="")
        result = _probe_duration("/some/file.mp4")
    assert result == pytest.approx(120.5)


def test_probe_duration_returns_zero_on_bad_output():
    from pipeline.youtube_ffmpeg import _probe_duration
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="not_a_float\n", stderr="")
        result = _probe_duration("/some/file.mp4")
    assert result == 0.0


def test_probe_duration_returns_zero_on_timeout():
    import subprocess
    from pipeline.youtube_ffmpeg import _probe_duration
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 15)):
        result = _probe_duration("/some/file.mp4")
    assert result == 0.0


def test_render_landscape_chunk_places_ss_before_visual_input(tmp_path):
    """start_s=300, file_dur=120 → effective_seek=60 → -ss 60 is BEFORE -i visual_path"""
    output = tmp_path / "chunk.mp4"
    visual = tmp_path / "visual.mp4"
    visual.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=str(visual)), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=120.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=300.0, end_s=600.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" in cmd
    ss_idx = cmd.index("-ss")
    i_idx = cmd.index(str(visual))
    assert ss_idx < i_idx, "-ss must appear before -i visual_path"
    assert cmd[ss_idx + 1] == "60", f"expected effective_seek=60, got {cmd[ss_idx + 1]}"


def test_render_landscape_chunk_no_ss_when_effective_seek_is_zero(tmp_path):
    """start_s=360, file_dur=120 → effective_seek=0 → no -ss in cmd"""
    output = tmp_path / "chunk.mp4"
    visual = tmp_path / "visual.mp4"
    visual.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=str(visual)), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=120.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=360.0, end_s=660.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" not in cmd, "effective_seek=0 should produce no -ss flag"


def test_render_landscape_no_output_side_ss_after_map(tmp_path):
    """Even with start_s > 0, -ss must never appear after -map in the command."""
    output = tmp_path / "chunk.mp4"
    visual = tmp_path / "visual.mp4"
    visual.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=str(visual)), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=120.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=300.0, end_s=600.0)

    cmd = mock_run.call_args[0][0]
    # If -map exists, -ss must not appear after it (output-side seek is forbidden)
    if "-map" in cmd:
        map_idx = cmd.index("-map")
        assert "-ss" not in cmd[map_idx:], "-ss must not appear after -map (no output-side seek)"
    else:
        # No -map means no complex filter path, so any -ss would be input-side only, which is fine
        pass


# ── _build_music_playlist_wav ─────────────────────────────────────────────────

def _make_music_video_and_db(tmp_path):
    """Return (video_mock, db_mock) with one music track file on disk."""
    music_file = tmp_path / "track.mp3"
    music_file.write_bytes(b"fake")

    track = MagicMock()
    track.id = 1
    track.file_path = str(music_file)
    track.volume = 1.0

    video = MagicMock()
    video.music_track_ids = [1]
    video.music_track_id = None

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [track]
    return video, db


def test_build_music_playlist_wav_uses_start_s_in_atrim(tmp_path):
    """start_s=300, target_dur=300 → atrim=start=300.0:end=600.0"""
    video, db = _make_music_video_and_db(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        from pipeline.youtube_ffmpeg import _build_music_playlist_wav
        _build_music_playlist_wav(video, db, 300, tmp_path, start_s=300.0)

    cmd = " ".join(mock_run.call_args[0][0])
    assert "atrim=start=300.0:end=600.0" in cmd
    assert "asetpts=PTS-STARTPTS" in cmd


def test_build_music_playlist_wav_default_start_s_is_zero(tmp_path):
    """Default start_s=0 → atrim=start=0:end=300"""
    video, db = _make_music_video_and_db(tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        from pipeline.youtube_ffmpeg import _build_music_playlist_wav
        _build_music_playlist_wav(video, db, 300, tmp_path)

    cmd = " ".join(mock_run.call_args[0][0])
    assert "atrim=start=0" in cmd
    assert "asetpts=PTS-STARTPTS" in cmd


def test_render_landscape_sfx_layer_uses_input_side_seek(tmp_path):
    """SFX override layer with start_s=310, file_dur=60 → effective_seek=10 → -ss 10 before -i sfx_path"""
    output = tmp_path / "chunk.mp4"
    sfx_file = tmp_path / "ambient.wav"
    sfx_file.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[(str(sfx_file), 0.5)]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=60.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=310.0, end_s=610.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" in cmd
    ss_idx = cmd.index("-ss")
    i_idx = cmd.index(str(sfx_file))
    assert ss_idx < i_idx, "-ss must appear before -i sfx_path"
    assert cmd[ss_idx + 1] == "10", f"expected effective_seek=10, got {cmd[ss_idx + 1]}"


def test_render_landscape_sfx_layer_no_ss_when_start_s_is_zero(tmp_path):
    """SFX override layers with start_s=0 → no -ss in cmd"""
    output = tmp_path / "chunk.mp4"
    sfx_file = tmp_path / "ambient.wav"
    sfx_file.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg.resolve_sfx_layers", return_value=[(str(sfx_file), 0.5)]), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=60.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=0.0, end_s=300.0)

    cmd = mock_run.call_args[0][0]
    assert "-ss" not in cmd


# ── _nvenc_available ───────────────────────────────────────────────────────────
# The implementation does a real encode probe (not encoder listing).
# It returns True only when returncode==0 AND stderr is empty.

def test_nvenc_available_returns_true_when_encode_probe_succeeds():
    from pipeline.youtube_ffmpeg import _nvenc_available
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert _nvenc_available() is True


def test_nvenc_available_returns_false_when_encode_probe_has_stderr():
    from pipeline.youtube_ffmpeg import _nvenc_available
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="Cannot load libnvidia-encode.so.1",
        )
        assert _nvenc_available() is False


def test_render_landscape_uses_h264_nvenc_when_nvenc_available(tmp_path):
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg._nvenc_available", return_value=True), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "h264_nvenc" in cmd
    assert "libx264" not in cmd


def test_render_landscape_uses_libx264_when_nvenc_not_available(tmp_path):
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg._nvenc_available", return_value=False), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "libx264" in cmd
    assert "h264_nvenc" not in cmd
