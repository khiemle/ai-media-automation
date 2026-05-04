from unittest.mock import MagicMock


def _make_video(visual_asset_ids=None, visual_clip_durations_s=None,
                visual_loop_mode="concat_loop", visual_asset_id=None):
    v = MagicMock()
    v.visual_asset_ids = visual_asset_ids if visual_asset_ids is not None else []
    v.visual_clip_durations_s = visual_clip_durations_s if visual_clip_durations_s is not None else []
    v.visual_loop_mode = visual_loop_mode
    v.visual_asset_id = visual_asset_id
    return v


def test_resolve_visual_playlist_returns_empty_when_no_ids():
    from pipeline.youtube_ffmpeg import resolve_visual_playlist
    assert resolve_visual_playlist(_make_video(), MagicMock()) == []


def test_resolve_visual_playlist_returns_assets_in_order(tmp_path):
    p1 = tmp_path / "a1.mp4"; p1.write_bytes(b"x")
    p2 = tmp_path / "a2.jpg"; p2.write_bytes(b"x")
    a1 = MagicMock(); a1.id = 1; a1.file_path = str(p1); a1.asset_type = "video_clip"
    a2 = MagicMock(); a2.id = 2; a2.file_path = str(p2); a2.asset_type = "still_image"
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [a2, a1]  # DB order != playlist order

    from pipeline.youtube_ffmpeg import resolve_visual_playlist
    result = resolve_visual_playlist(_make_video(visual_asset_ids=[1, 2]), db)
    assert [r.id for r in result] == [1, 2]  # preserves playlist order, not DB order


def test_resolve_visual_playlist_drops_assets_with_missing_files(tmp_path):
    real = tmp_path / "real.mp4"
    real.write_bytes(b"x")  # ensures Path.is_file() is True for the first asset
    a1 = MagicMock(); a1.id = 1; a1.file_path = str(real); a1.asset_type = "video_clip"
    a2 = MagicMock(); a2.id = 2; a2.file_path = str(tmp_path / "definitely_missing.mp4"); a2.asset_type = "video_clip"
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [a1, a2]

    from pipeline.youtube_ffmpeg import resolve_visual_playlist
    result = resolve_visual_playlist(_make_video(visual_asset_ids=[1, 2]), db)
    assert [r.id for r in result] == [1]


def test_build_visual_segment_uses_native_length_for_videos_in_concat_loop(monkeypatch, tmp_path):
    """In concat_loop mode, video items with duration=0 should use -i without -t (native length)."""
    asset_path_str = str(tmp_path / "v.mp4")
    a = MagicMock(); a.file_path = asset_path_str; a.asset_type = "video_clip"
    (tmp_path / "v.mp4").write_bytes(b"fake")

    captured = {"all_cmds": []}
    def fake_run(cmd, timeout):
        captured["all_cmds"].append(cmd)
        captured["cmd"] = cmd
    monkeypatch.setattr("pipeline.youtube_ffmpeg._run_ffmpeg", fake_run)

    from pipeline.youtube_ffmpeg import _build_visual_segment
    out = _build_visual_segment(
        playlist=[a],
        durations=[0.0],
        loop_mode="concat_loop",
        w=1920, h=1080, target_dur_s=60,
        output_dir=tmp_path,
    )
    assert out is not None
    # Join all captured ffmpeg calls to check any of them used the input path
    all_cmds = " ".join(" ".join(c) for c in captured["all_cmds"])
    # Sanity: ffmpeg should be invoked with the input path and produce an mp4 in output_dir
    assert "v.mp4" in all_cmds
    assert str(out).endswith(".mp4")
    # The first ffmpeg call is the per-item normalize step; assert it has NO -t flag
    # (native-length means we let the input play to its end, no time cap)
    item_cmd = captured["all_cmds"][0]
    assert "-t" not in item_cmd, f"per-item cmd unexpectedly has -t: {item_cmd}"
    assert asset_path_str in item_cmd


def test_build_visual_segment_per_clip_mode_uses_per_item_duration(monkeypatch, tmp_path):
    a1 = MagicMock(); a1.file_path = str(tmp_path / "v1.mp4"); a1.asset_type = "video_clip"
    a2 = MagicMock(); a2.file_path = str(tmp_path / "img.jpg"); a2.asset_type = "still_image"
    (tmp_path / "v1.mp4").write_bytes(b"fake")
    (tmp_path / "img.jpg").write_bytes(b"fake")

    captured = {"all_cmds": []}
    def fake_run(cmd, timeout):
        captured["all_cmds"].append(cmd)
        captured["cmd"] = cmd
    monkeypatch.setattr("pipeline.youtube_ffmpeg._run_ffmpeg", fake_run)

    from pipeline.youtube_ffmpeg import _build_visual_segment
    out = _build_visual_segment(
        playlist=[a1, a2],
        durations=[10.0, 3.0],
        loop_mode="per_clip",
        w=1920, h=1080, target_dur_s=60,
        output_dir=tmp_path,
    )
    # First call = first item (video, 10s slot, with -stream_loop for filling the slot)
    item1_cmd = captured["all_cmds"][0]
    assert "-stream_loop" in item1_cmd
    assert "-t" in item1_cmd
    assert "10.0" in item1_cmd  # exact float repr matches the duration we passed

    # Second call = second item (image, 3s, with -loop 1)
    item2_cmd = captured["all_cmds"][1]
    assert "-loop" in item2_cmd
    assert "1" in item2_cmd
    assert "-t" in item2_cmd
    assert "3.0" in item2_cmd


def test_render_landscape_skips_ss_when_using_playlist_segment(monkeypatch, tmp_path):
    """Chunked render with a playlist segment must NOT apply -ss start_s — that would
    seek past the pre-cut segment's end. Regression test for the chunked-render bug.
    """
    from unittest.mock import MagicMock

    # Stub out the playlist resolver and segment builder so they return a fake segment
    fake_segment = tmp_path / "vseg.mp4"
    fake_segment.write_bytes(b"x")

    monkeypatch.setattr(
        "pipeline.youtube_ffmpeg.resolve_visual_playlist",
        lambda video, db: [MagicMock()],
    )
    monkeypatch.setattr(
        "pipeline.youtube_ffmpeg._build_visual_segment",
        lambda **kwargs: fake_segment,
    )
    # Stub audio resolvers so they don't try to query the DB
    monkeypatch.setattr("pipeline.youtube_ffmpeg.resolve_visual", lambda v, db: None)
    monkeypatch.setattr("pipeline.youtube_ffmpeg.resolve_sfx_layers", lambda v, db: [])
    monkeypatch.setattr("pipeline.youtube_ffmpeg._build_music_playlist_wav", lambda *a, **k: None)
    monkeypatch.setattr("pipeline.youtube_ffmpeg._build_sfx_pool_wav", lambda *a, **k: None)

    captured = {}
    def fake_run(cmd, timeout):
        captured["cmd"] = cmd
    monkeypatch.setattr("pipeline.youtube_ffmpeg._run_ffmpeg", fake_run)

    video = MagicMock()
    video.target_duration_h = 1.0
    video.output_quality = "1080p"
    video.visual_asset_ids = [1]
    video.visual_clip_durations_s = [0.0]
    video.visual_loop_mode = "concat_loop"
    video.black_from_seconds = None

    from pipeline.youtube_ffmpeg import render_landscape
    render_landscape(video, tmp_path / "chunk.mp4", db=MagicMock(), start_s=900.0, end_s=1200.0)

    cmd = captured["cmd"]
    # The fake segment is exactly target_dur (300s); -ss 900 would seek past its end
    assert "-ss" not in cmd, f"render_landscape applied -ss with playlist segment: {cmd}"
    # But -t MUST still bound the output to the chunk duration
    assert "-t" in cmd
    t_idx = cmd.index("-t")
    assert cmd[t_idx + 1] == "300"


def test_build_visual_segment_concat_list_uses_basenames(monkeypatch, tmp_path):
    """Regression: concat list must use basenames, not full paths.

    ffmpeg's concat demuxer resolves entries relative to the LIST FILE's directory.
    Writing the full output_dir-prefixed path doubles the prefix and produces
    'output_dir/output_dir/vseg_0.mp4' which doesn't exist.
    """
    a = MagicMock(); a.file_path = str(tmp_path / "v.mp4"); a.asset_type = "video_clip"
    (tmp_path / "v.mp4").write_bytes(b"fake")

    # Stub _run_ffmpeg so the per-item ffmpeg calls don't actually need to run,
    # but we still capture what the code WOULD have written into vseg_list.txt.
    monkeypatch.setattr("pipeline.youtube_ffmpeg._run_ffmpeg", lambda cmd, timeout: None)

    from pipeline.youtube_ffmpeg import _build_visual_segment
    _build_visual_segment(
        playlist=[a],
        durations=[0.0],
        loop_mode="concat_loop",
        w=1920, h=1080, target_dur_s=60,
        output_dir=tmp_path,
    )

    list_text = (tmp_path / "vseg_list.txt").read_text()
    # Each non-empty line must be 'file 'BASENAME'' — no path separators inside the quotes
    for line in list_text.splitlines():
        if not line.strip():
            continue
        assert line.startswith("file '") and line.endswith("'"), f"unexpected line: {line!r}"
        inner = line[len("file '"):-1]
        assert "/" not in inner, f"concat list contains path separator: {inner!r}"
        assert inner == "vseg_0.mp4", f"expected basename 'vseg_0.mp4', got: {inner!r}"
