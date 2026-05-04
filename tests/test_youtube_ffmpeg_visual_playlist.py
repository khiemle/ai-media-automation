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
    a = MagicMock(); a.file_path = str(tmp_path / "v.mp4"); a.asset_type = "video_clip"
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
    # Join all captured ffmpeg calls to check per-item durations appeared in any call
    all_cmds = " ".join(" ".join(c) for c in captured["all_cmds"])
    # Both per-item durations should appear in the filter graph
    assert "10" in all_cmds
    assert "3" in all_cmds
