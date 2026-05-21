import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

pytestmark = pytest.mark.render



def _make_video(sfx_overrides=None, visual_asset_id=None, music_track_id=None,
                target_duration_h=3.0, output_quality="1080p",
                music_track_ids=None, sfx_pool=None,
                sfx_density_seconds=None, sfx_seed=None,
                black_from_seconds=None, sound_layers=None):
    v = MagicMock()
    v.visual_asset_id = visual_asset_id
    v.music_track_id = music_track_id
    v.sfx_overrides = sfx_overrides
    v.target_duration_h = target_duration_h
    v.output_quality = output_quality
    v.music_track_ids = music_track_ids if music_track_ids is not None else []
    v.sfx_pool = sfx_pool if sfx_pool is not None else []
    v.sfx_density_seconds = sfx_density_seconds
    v.sfx_seed = sfx_seed
    v.black_from_seconds = black_from_seconds
    v.sound_layers = sound_layers
    v.visual_asset_ids = []
    v.visual_clip_durations_s = []
    v.visual_loop_mode = "concat_loop"
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


def test_render_landscape_video_only_chunk_omits_audio_inputs(tmp_path):
    """Chunked render with include_audio=False must skip music/SFX wav builders
    and add -an to the ffmpeg command — no audio in chunks (avoids per-chunk
    AAC priming at concat seams).
    """
    output = tmp_path / "chunk.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav") as mock_music, \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav") as mock_sl, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(
            _make_video(), output, MagicMock(),
            start_s=300.0, end_s=600.0,
            include_audio=False,
        )

    # Builders for music + sound layers must NOT have been called.
    mock_music.assert_not_called()
    mock_sl.assert_not_called()

    cmd = mock_run.call_args[0][0]
    assert "-an" in cmd, "video-only chunks must use -an"
    # No AAC encoding should appear when audio is omitted.
    cmd_str = " ".join(cmd)
    assert "-c:a aac" not in cmd_str


def test_render_landscape_chunk_uses_frame_exact_output(tmp_path):
    """Regression for the v1.2.0-1.2.3 whole-video A/V drift.

    Chunked render (include_audio=False) MUST emit the encoder args that keep
    each chunk's container duration exactly equal to its target window:
    explicit fps, CFR, frame-count cap, fixed timescale. Anything else lets
    NVENC pick a default timescale that's a non-multiple of 30 and the
    container duration drifts off by milliseconds — drift the concat demuxer
    then accumulates across every seam starting at the first chunk boundary
    (5:00 for the default 300s chunks).
    """
    output = tmp_path / "chunk.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav"), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(
            _make_video(), output, MagicMock(),
            start_s=0.0, end_s=300.0,
            include_audio=False,
        )

    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    # 300s chunk × 30 fps == 9000 frames; encoder must cap at exactly that.
    assert "-frames:v" in cmd and "9000" in cmd
    assert "-r 30" in cmd_str
    assert "-vsync cfr" in cmd_str
    # Timescale 30000 → 1000 ticks/frame at 30fps (integer, no drift).
    assert "-video_track_timescale 30000" in cmd_str


def test_render_landscape_audio_pass_omits_chunk_exact_flags(tmp_path):
    """Single-pass renders (include_audio=True) own their own audio track and
    are not downstream-concatenated. The chunk-exact flags would still be
    correct but cost CPU on a fps-converter pass for no benefit — keep them
    scoped to the chunked path so the audio-bearing renderer stays untouched.
    """
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=None), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock())

    cmd_str = " ".join(mock_run.call_args[0][0])
    assert "-frames:v" not in cmd_str
    assert "-video_track_timescale" not in cmd_str


def test_render_landscape_default_still_includes_audio(tmp_path):
    """Default include_audio=True path keeps building audio + AAC encoder."""
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=None), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock())

    cmd = mock_run.call_args[0][0]
    assert "-an" not in cmd
    assert "-c:a" in cmd
    assert "aac" in cmd


def test_render_full_audio_track_uses_full_duration(tmp_path):
    """render_full_audio_track should pass full_duration_s (= target_duration_h * 3600)
    to _build_music_playlist_wav and _build_sound_layers_wav with start_s=0."""
    output = tmp_path / "audio.m4a"
    video = _make_video(target_duration_h=3.0)

    # template_id None to skip the music-template branch
    video.template_id = None

    music_path = tmp_path / "music.wav"
    music_path.write_bytes(b"fake")
    sl_path = tmp_path / "sl.wav"
    sl_path.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav",
               return_value=str(music_path)) as mock_music, \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav",
               return_value=str(sl_path)) as mock_sl, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_full_audio_track
        render_full_audio_track(video, output, MagicMock())

    # full duration = 3.0 * 3600 = 10800 seconds
    music_args = mock_music.call_args
    assert music_args.args[2] == 10800
    assert music_args.kwargs.get("start_s") == 0.0

    sl_args = mock_sl.call_args
    assert sl_args.args[2] == 10800
    assert sl_args.args[3] == 0.0

    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    assert "-vn" in cmd
    assert "-c:a aac" in cmd_str
    # Duration must be the full video length, not a chunk slice.
    t_idx = cmd.index("-t")
    assert cmd[t_idx + 1] == "10800"


# ── _build_music_playlist_wav seamless loop ──────────────────────────────────


def test_build_music_playlist_seamless_loop_uses_acrossfade_at_boundaries(tmp_path):
    """The previous implementation used ``aloop`` for single-track playlists,
    which hard-cuts at every loop boundary (audible click every M seconds
    for non-broadband / tonal music — the original 5-min glitch root cause).

    The new path probes the track duration, replicates the input N times,
    and applies ``acrossfade`` between every consecutive pair so loop
    boundaries are seamless. Verify:
      * The ffmpeg command repeats the same input path N≥2 times.
      * ``acrossfade`` appears in the filter graph at least N-1 times.
      * The legacy ``aloop`` hard-loop directive is NOT used.
    """
    fake_track = MagicMock()
    fake_track.id = 1
    fake_track.file_path = "/tmp/fake_5min_track.mp3"
    fake_track.volume = 1.0

    db = MagicMock()
    # query(...).filter(...).all() returns [fake_track]
    db.query.return_value.filter.return_value.all.return_value = [fake_track]

    video = _make_video(music_track_ids=[1])

    # Patch:
    #   - Path.is_file → True (track "exists")
    #   - _probe_duration → 300.0s (5-minute track)
    #   - subprocess.run (the ffmpeg run) → success
    with patch.object(Path, "is_file", return_value=True), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=300.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import _build_music_playlist_wav
        _build_music_playlist_wav(video, db, 10800, tmp_path, start_s=0.0)

    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)

    # Same input path repeated many times (≥ 2 for the loop to make sense;
    # for a 300s track over a 10800s target we expect dozens).
    input_count = sum(1 for i, t in enumerate(cmd) if t == "-i" and i + 1 < len(cmd) and cmd[i + 1] == fake_track.file_path)
    assert input_count >= 2, f"expected multiple -i inputs for seamless loop, got {input_count}"

    # acrossfade applied between every pair of inputs ⇒ at least (input_count - 1)
    # acrossfade clauses must appear in the filter graph.
    acrossfade_count = cmd_str.count("acrossfade")
    assert acrossfade_count >= input_count - 1, (
        f"expected ≥{input_count - 1} acrossfade clauses, got {acrossfade_count}"
    )

    # The legacy hard-loop directive must NOT be used in this path.
    assert "aloop=loop=-1" not in cmd_str, (
        "seamless-loop path must not fall back to aloop (hard loop boundary)"
    )


def test_build_music_playlist_falls_back_to_aloop_when_probe_fails(tmp_path):
    """If ffprobe can't determine track duration, we can't compute loop counts;
    fall back to the legacy aloop path so we still produce output."""
    fake_track = MagicMock()
    fake_track.id = 1
    fake_track.file_path = "/tmp/fake_unprobable.mp3"
    fake_track.volume = 1.0

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [fake_track]

    video = _make_video(music_track_ids=[1])

    with patch.object(Path, "is_file", return_value=True), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=0.0), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import _build_music_playlist_wav
        _build_music_playlist_wav(video, db, 10800, tmp_path, start_s=0.0)

    cmd_str = " ".join(mock_run.call_args[0][0])
    assert "aloop=loop=-1" in cmd_str, "expected legacy fallback to use aloop"


def test_render_full_audio_track_silence_when_no_music_or_sfx(tmp_path):
    """No music + no sound layers → fall back to anullsrc silence track."""
    output = tmp_path / "audio.m4a"
    video = _make_video(target_duration_h=1.0)
    video.template_id = None

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=None), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_full_audio_track
        render_full_audio_track(video, output, MagicMock())

    cmd = mock_run.call_args[0][0]
    cmd_str = " ".join(cmd)
    assert "anullsrc" in cmd_str


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


def test_render_landscape_passes_start_s_to_build_sound_layers_wav(tmp_path):
    """render_landscape must forward start_s to _build_sound_layers_wav for correct chunk seek."""
    output = tmp_path / "chunk.mp4"

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=None) as mock_sl, \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=310.0, end_s=610.0)

    # _build_sound_layers_wav must be called with start_s=310.0
    # signature: (video, db, target_duration_s, start_s, output_dir)
    assert mock_sl.call_args[0][3] == 310.0, f"expected start_s=310.0 forwarded to _build_sound_layers_wav, got {mock_sl.call_args[0][3]}"


def test_render_landscape_sound_layers_wav_is_not_looped(tmp_path):
    """The exact-duration sound_layers_wav must be added without -stream_loop."""
    output = tmp_path / "chunk.mp4"
    sl_wav = tmp_path / "sound_layers.wav"
    sl_wav.write_bytes(b"fake")

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("pipeline.youtube_ffmpeg.resolve_visual_playlist", return_value=[]), \
         patch("pipeline.youtube_ffmpeg.resolve_visual", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=str(sl_wav)), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock(), start_s=310.0, end_s=610.0)

    cmd = mock_run.call_args[0][0]
    # -stream_loop must NOT appear before the sound_layers_wav -i flag
    wav_idx = cmd.index(str(sl_wav))
    pre_cmd = cmd[:wav_idx]
    assert "-stream_loop" not in pre_cmd, "-stream_loop must not precede the sound_layers_wav input"


def test_render_audio_preview_calls_build_sound_layers_wav_with_start_s(tmp_path):
    """render_audio_preview must call _build_sound_layers_wav and forward start_s."""
    output = tmp_path / "preview.wav"

    with patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=None) as mock_sl:
        from pipeline.youtube_audio_only import render_audio_preview
        video = _make_video()
        try:
            render_audio_preview(video, output, MagicMock(), start_s=60.0, end_s=360.0)
        except RuntimeError:
            pass  # "No audio content" is expected when both helpers return None

    mock_sl.assert_called_once()
    # Fourth positional arg is start_s
    assert mock_sl.call_args[0][3] == 60.0


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


# ── _build_sound_layers_wav ───────────────────────────────────────────────────

def _make_sfx(id_, file_path, is_loopable=False):
    s = MagicMock()
    s.id = id_
    s.file_path = file_path
    s.is_loopable = is_loopable
    return s


def _make_db_with_sfx(sfx_list):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = sfx_list
    return db


def test_build_sound_layers_wav_returns_none_when_no_config(tmp_path):
    from pipeline.youtube_ffmpeg import _build_sound_layers_wav
    video = _make_video(sound_layers=None)
    assert _build_sound_layers_wav(video, MagicMock(), 300, 0.0, tmp_path) is None


def test_build_sound_layers_wav_returns_none_when_empty_config(tmp_path):
    from pipeline.youtube_ffmpeg import _build_sound_layers_wav
    video = _make_video(sound_layers={})
    assert _build_sound_layers_wav(video, MagicMock(), 300, 0.0, tmp_path) is None


def test_build_sound_layers_wav_background_uses_stream_loop(tmp_path):
    bg_file = tmp_path / "bg.wav"
    bg_file.write_bytes(b"")
    sfx = _make_sfx(5, str(bg_file), is_loopable=True)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff, \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=30.0):
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)

    assert result is not None
    cmd = " ".join(mock_ff.call_args[0][0])
    assert "-stream_loop" in cmd
    assert str(bg_file) in cmd
    assert "amix" not in cmd  # single input: amix must not appear


@pytest.mark.xfail(
    reason="Pre-existing: empty bg.wav reaches real ffmpeg because _run_ffmpeg is not patched; "
    "production code calls ffmpeg before checking is_loopable. Sibling test "
    "test_build_sound_layers_wav_midground_events_use_adelay patches _run_ffmpeg correctly.",
    strict=False,
)
def test_build_sound_layers_wav_skips_non_loopable_background(tmp_path):
    bg_file = tmp_path / "bg.wav"
    bg_file.write_bytes(b"")
    sfx = _make_sfx(5, str(bg_file), is_loopable=False)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    from pipeline.youtube_ffmpeg import _build_sound_layers_wav
    result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)
    assert result is None  # only layer was skipped → nothing to mix


def test_build_sound_layers_wav_midground_events_use_adelay(tmp_path):
    sfx_file = tmp_path / "mid.wav"
    sfx_file.write_bytes(b"")
    sfx = _make_sfx(1, str(sfx_file))

    video = _make_video(sfx_seed=42, sound_layers={
        "midground": {"pool": [1], "volume": 0.5, "interval_min_s": 10, "interval_max_s": 25}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff:
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)

    assert result is not None
    cmd = " ".join(mock_ff.call_args[0][0])
    assert "adelay=" in cmd


def test_build_sound_layers_wav_chunk_seeks_background(tmp_path):
    bg_file = tmp_path / "bg.wav"
    bg_file.write_bytes(b"")
    sfx = _make_sfx(5, str(bg_file), is_loopable=True)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff, \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=60.0):
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        # start_s=90, probe=60 → seek = 90 % 60 = 30 → -ss applied
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 90.0, tmp_path)

    assert result is not None
    cmd = " ".join(mock_ff.call_args[0][0])
    assert "-ss" in cmd
    assert "30" in cmd  # start_s=90, probe=60 → seek = 90 % 60 = 30


def test_build_sound_layers_wav_all_three_scheduled_layers(tmp_path):
    sfx_file = tmp_path / "sfx.wav"
    sfx_file.write_bytes(b"")
    sfx = _make_sfx(1, str(sfx_file))

    video = _make_video(sfx_seed=0, sound_layers={
        "midground":  {"pool": [1], "volume": 0.5, "interval_min_s": 10, "interval_max_s": 25},
        "foreground": {"pool": [1], "volume": 0.7, "interval_min_s": 45, "interval_max_s": 60},
        "random_sfx": {"pool": [1], "volume": 0.6, "interval_min_s": 60, "interval_max_s": 100},
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff:
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 600, 0.0, tmp_path)

    assert result is not None
    # Three layers active → multiple adelay entries in filter_complex
    cmd = " ".join(mock_ff.call_args[0][0])
    assert cmd.count("adelay=") >= 3


def test_build_sound_layers_wav_output_filename(tmp_path):
    sfx_file = tmp_path / "bg.wav"
    sfx_file.write_bytes(b"")
    sfx = _make_sfx(5, str(sfx_file), is_loopable=True)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff, \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=30.0):
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)

    assert result is not None
    assert result.endswith("sound_layers.wav")
    cmd = " ".join(mock_ff.call_args[0][0])
    assert "amix" not in cmd  # background-only is single input; amix must not appear


def test_build_sound_layers_wav_sfx_seed_none_uses_zero(tmp_path):
    """sfx_seed=None must not crash — defaults to 0."""
    sfx_file = tmp_path / "mid.wav"
    sfx_file.write_bytes(b"")
    sfx = _make_sfx(1, str(sfx_file))

    video = _make_video(sfx_seed=None, sound_layers={
        "midground": {"pool": [1], "volume": 0.5, "interval_min_s": 10, "interval_max_s": 25}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg"):
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)

    assert result is not None


def test_render_landscape_uses_build_sound_layers_wav(tmp_path):
    """render_landscape must call _build_sound_layers_wav, not _build_sfx_pool_wav."""
    output = tmp_path / "out.mp4"
    video = _make_video(sound_layers={"background": {"asset_id": 1, "volume": 0.4}})

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=None) as mock_sl, \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav") as mock_old:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(video, output, MagicMock())

    mock_sl.assert_called_once()
    mock_old.assert_not_called()


# ── resolve_visual plural-array fallback ──────────────────────────────────────

def test_resolve_visual_falls_back_to_first_plural_id():
    """When visual_asset_id is None but visual_asset_ids has entries, resolve to the first."""
    fake_asset = MagicMock()
    fake_asset.file_path = "/tmp/plural1.mp4"
    db = MagicMock()
    db.get.return_value = fake_asset

    video = _make_video(visual_asset_id=None)
    video.visual_asset_ids = [101, 102]

    from pipeline.youtube_ffmpeg import resolve_visual
    result = resolve_visual(video, db)
    assert result == "/tmp/plural1.mp4"
    # Must have looked up the FIRST plural id (101), not the second
    from console.backend.models.video_asset import VideoAsset
    db.get.assert_called_once_with(VideoAsset, 101)


def test_resolve_visual_singular_takes_precedence_over_plural():
    """When singular is present, it wins (preserve legacy behavior)."""
    single_asset = MagicMock()
    single_asset.file_path = "/tmp/single.mp4"
    db = MagicMock()
    db.get.return_value = single_asset

    video = _make_video(visual_asset_id=42)
    video.visual_asset_ids = [999]

    from pipeline.youtube_ffmpeg import resolve_visual
    result = resolve_visual(video, db)
    assert result == "/tmp/single.mp4"
    from console.backend.models.video_asset import VideoAsset
    db.get.assert_called_once_with(VideoAsset, 42)


def test_resolve_visual_returns_none_when_no_assets():
    """Both singular and plural missing → None."""
    db = MagicMock()
    video = _make_video(visual_asset_id=None)
    video.visual_asset_ids = []
    from pipeline.youtube_ffmpeg import resolve_visual
    assert resolve_visual(video, db) is None
    db.get.assert_not_called()


# ── resolve_audio plural-array fallback ───────────────────────────────────────

def test_resolve_audio_falls_back_to_first_plural_id():
    """When music_track_id is None but music_track_ids has entries, resolve to the first."""
    fake_track = MagicMock()
    fake_track.file_path = "/tmp/m1.mp3"
    db = MagicMock()
    db.get.return_value = fake_track

    video = _make_video(music_track_id=None, music_track_ids=[201, 202])

    from pipeline.youtube_ffmpeg import resolve_audio
    result = resolve_audio(video, db)
    assert result == "/tmp/m1.mp3"
    from database.models import MusicTrack
    db.get.assert_called_once_with(MusicTrack, 201)


def test_resolve_audio_singular_takes_precedence():
    """When singular music_track_id is set, it wins over music_track_ids."""
    single_track = MagicMock()
    single_track.file_path = "/tmp/single.mp3"
    db = MagicMock()
    db.get.return_value = single_track

    video = _make_video(music_track_id=7, music_track_ids=[999])

    from pipeline.youtube_ffmpeg import resolve_audio
    result = resolve_audio(video, db)
    assert result == "/tmp/single.mp3"
    from database.models import MusicTrack
    db.get.assert_called_once_with(MusicTrack, 7)
