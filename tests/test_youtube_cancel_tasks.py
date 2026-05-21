"""Tests for cancel-all-tasks: revoke all chunk + concat Celery task IDs on cancel/delete."""
import pytest
from unittest.mock import MagicMock, patch


def _make_video(parts=None, celery_task_id=None, status="rendering"):
    v = MagicMock()
    v.id = 42
    v.status = status
    v.celery_task_id = celery_task_id
    v.render_parts = parts
    return v


def test_revoke_all_render_jobs_revokes_each_chunk_task_id():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)

    video = _make_video(
        parts=[
            {"idx": 0, "task_id": "chunk-uuid-0", "status": "completed"},
            {"idx": 1, "task_id": "chunk-uuid-1", "status": "running"},
            {"idx": 2, "task_id": "chunk-uuid-2", "status": "pending"},
        ],
        celery_task_id="concat-uuid",
    )

    with patch("console.backend.celery_app.celery_app.control.revoke") as mock_revoke:
        svc._revoke_all_render_jobs(video)

    revoked = {c.args[0] for c in mock_revoke.call_args_list}
    assert "chunk-uuid-0" in revoked
    assert "chunk-uuid-1" in revoked
    assert "chunk-uuid-2" in revoked
    assert "concat-uuid" in revoked
    for c in mock_revoke.call_args_list:
        assert c.kwargs.get("terminate") is True
        assert c.kwargs.get("signal") == "SIGTERM"


def test_revoke_all_render_jobs_skips_parts_without_task_id():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)

    video = _make_video(
        parts=[{"idx": 0, "status": "pending"}],  # no task_id key
        celery_task_id=None,
    )

    with patch("console.backend.celery_app.celery_app.control.revoke") as mock_revoke:
        svc._revoke_all_render_jobs(video)

    mock_revoke.assert_not_called()


def test_revoke_all_render_jobs_handles_empty_render_parts():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)

    video = _make_video(parts=None, celery_task_id="concat-uuid")

    with patch("console.backend.celery_app.celery_app.control.revoke") as mock_revoke:
        svc._revoke_all_render_jobs(video)

    mock_revoke.assert_called_once_with("concat-uuid", terminate=True, signal="SIGTERM")


def test_cancel_chunked_render_sets_status_to_failed():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(
        parts=[
            {"idx": 0, "task_id": "t0", "status": "completed"},
            {"idx": 1, "task_id": "t1", "status": "running"},
        ],
        celery_task_id="concat-uuid",
        status="rendering",
    )
    db.get.return_value = video

    result = svc.cancel_chunked_render(video_id=42)

    assert result["status"] == "failed"
    assert video.status == "failed"


def test_cancel_chunked_render_marks_non_completed_parts_cancelled():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(
        parts=[
            {"idx": 0, "status": "completed"},
            {"idx": 1, "status": "running"},
            {"idx": 2, "status": "pending"},
        ],
        celery_task_id="concat-uuid",
        status="rendering",
    )
    db.get.return_value = video

    svc.cancel_chunked_render(video_id=42)

    statuses = {p["idx"]: p["status"] for p in video.render_parts}
    assert statuses[0] == "completed"  # preserved
    assert statuses[1] == "cancelled"
    assert statuses[2] == "cancelled"


def test_cancel_chunked_render_clears_celery_task_id():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(celery_task_id="some-uuid", status="rendering")
    db.get.return_value = video

    svc.cancel_chunked_render(video_id=42)

    assert video.celery_task_id is None


def test_cancel_chunked_render_calls_revoke_all():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(status="rendering")
    db.get.return_value = video

    svc.cancel_chunked_render(video_id=42)

    svc._revoke_all_render_jobs.assert_called_once_with(video)


def test_delete_video_revokes_all_render_jobs():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(
        parts=[{"idx": 0, "task_id": "t0", "status": "running"}],
        celery_task_id="concat-uuid",
        status="rendering",
    )
    db.get.return_value = video

    svc.delete_video(video_id=42)

    svc._revoke_all_render_jobs.assert_called_once_with(video)


def test_orchestrator_writes_task_ids_before_chord_dispatch():
    """render_parts must have task_id populated and committed BEFORE chord dispatch."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.celery_task_id = "old-orch-id"
    video.sfx_seed = 1  # non-None → skips random.randint branch
    video.target_duration_h = 1 / 60  # 60s → 1 chunk
    video.render_parts = None
    video.status = "rendering"

    db = MagicMock()
    db.get.return_value = video

    write_order = []
    committed_state = {}

    def on_commit():
        if not committed_state:
            committed_state["parts"] = list(video.render_parts or [])
            committed_state["celery_task_id"] = video.celery_task_id
        write_order.append("commit")
    db.commit.side_effect = on_commit

    mock_chord_partial = MagicMock(side_effect=lambda _sig: write_order.append("dispatch"))
    mock_chord_cls = MagicMock(return_value=mock_chord_partial)

    # chord, group and SessionLocal are imported inside the function body,
    # so patch them at their source modules, not at the task module level.
    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("console.backend.tasks.youtube_render_task._is_superseded", return_value=False), \
         patch("celery.chord", mock_chord_cls), \
         patch("celery.group", MagicMock()), \
         patch("sqlalchemy.orm.attributes.flag_modified"):
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        render_youtube_chunked_orchestrator_task.apply(args=[42])

    # commit must precede dispatch
    assert "commit" in write_order, "orchestrator must commit before dispatching"
    assert "dispatch" in write_order, "orchestrator must dispatch chord"
    assert write_order.index("commit") < write_order.index("dispatch"), \
        f"commit must precede dispatch; got order: {write_order}"

    # all pending parts must have task_id at commit time
    for p in committed_state["parts"]:
        assert p.get("task_id"), f"part {p.get('idx')} missing task_id at commit time"

    # celery_task_id must have changed from old orch ID to concat UUID
    assert committed_state["celery_task_id"] != "old-orch-id"
    assert committed_state["celery_task_id"] is not None


def test_chunk_task_returns_early_when_video_is_failed():
    """render_youtube_chunk_task must not call render_landscape if video.status == 'failed'."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.status = "failed"

    db = MagicMock()
    db.get.return_value = video

    # The status guard returns before _update_chunk_status is called, so no need to patch it.
    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("pipeline.youtube_ffmpeg.render_landscape") as mock_render:
        from console.backend.tasks.youtube_render_task import render_youtube_chunk_task
        result = render_youtube_chunk_task.apply(args=[42, 0, 0.0, 300.0]).get()

    mock_render.assert_not_called()
    assert result["status"] == "skipped"


def test_concat_task_returns_early_when_video_is_failed():
    """concat_youtube_chunks_task must not call concat_parts if video.status == 'failed'."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.status = "failed"

    db = MagicMock()
    db.get.return_value = video

    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("pipeline.concat.concat_parts") as mock_concat:
        from console.backend.tasks.youtube_render_task import concat_youtube_chunks_task
        result = concat_youtube_chunks_task.apply(args=[[], 42]).get()

    mock_concat.assert_not_called()
    assert result["status"] == "skipped"


def test_orchestrator_skips_when_video_is_failed():
    """orchestrator must not dispatch chord if video.status == 'failed'."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.status = "failed"
    video.celery_task_id = None  # cleared by cancel before orchestrator ran

    db = MagicMock()
    db.get.return_value = video

    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("console.backend.tasks.youtube_render_task._is_superseded", return_value=False), \
         patch("celery.chord") as mock_chord:
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        result = render_youtube_chunked_orchestrator_task.apply(args=[42]).get()

    mock_chord.assert_not_called()
    assert result["status"] == "skipped"


def test_orchestrator_invalidates_legacy_chunks_without_video_suffix():
    """Pre-v1.2.4 chunks (any filename other than chunk.video.cfr.mp4) have the
    wrong on-disk encoder timing. The orchestrator must NOT preserve them — it
    must mark them pending so they get re-rendered with the v1.2.4 CFR /
    fixed-timescale flags.
    """
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.celery_task_id = "old-orch-id"
    video.sfx_seed = 1
    video.target_duration_h = 1 / 60 * 3  # 180s → 1 chunk of ≤300s
    video.status = "rendering"
    # Existing render_parts: one "completed" chunk pointing to LEGACY filename
    video.render_parts = [{
        "idx": 0, "start_s": 0, "end_s": 180,
        "status": "completed",
        "file_path": "/tmp/youtube_42/chunk_0/chunk.mp4",  # pre-v1.2.1
    }]

    db = MagicMock()
    db.get.return_value = video

    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("console.backend.tasks.youtube_render_task._is_superseded", return_value=False), \
         patch("celery.chord", MagicMock()), \
         patch("celery.group", MagicMock()), \
         patch("sqlalchemy.orm.attributes.flag_modified"):
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        render_youtube_chunked_orchestrator_task.apply(args=[42])

    # The single existing chunk must be invalidated (status pending, file_path None)
    parts = video.render_parts
    assert len(parts) == 1
    assert parts[0]["status"] == "pending", \
        f"legacy chunk should be invalidated, got status={parts[0]['status']!r}"
    assert parts[0]["file_path"] is None, \
        f"legacy chunk file_path should be cleared, got {parts[0]['file_path']!r}"


def test_orchestrator_invalidates_v121_chunks_lacking_cfr_suffix():
    """v1.2.1..v1.2.3 chunks (file_path ends with .video.mp4) were video-only
    but were encoded without the v1.2.4 CFR / frame-count / fixed-timescale
    flags. Their tkhd duration can be off by ~ms and ``-c copy`` concat
    accumulates that drift across seams. The orchestrator must invalidate
    them on resume so they get re-rendered with the v1.2.4 encoder args.
    """
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.celery_task_id = "old-orch-id"
    video.sfx_seed = 1
    video.target_duration_h = 1 / 60 * 3  # 180s → 1 chunk
    video.status = "rendering"
    video.render_parts = [{
        "idx": 0, "start_s": 0, "end_s": 180,
        "status": "completed",
        "file_path": "/tmp/youtube_42/chunk_0/chunk.video.mp4",  # v1.2.1..v1.2.3
    }]

    db = MagicMock()
    db.get.return_value = video

    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("console.backend.tasks.youtube_render_task._is_superseded", return_value=False), \
         patch("celery.chord", MagicMock()), \
         patch("celery.group", MagicMock()), \
         patch("sqlalchemy.orm.attributes.flag_modified"):
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        render_youtube_chunked_orchestrator_task.apply(args=[42])

    parts = video.render_parts
    assert len(parts) == 1
    assert parts[0]["status"] == "pending", \
        f"v1.2.1..v1.2.3 chunk should be invalidated, got status={parts[0]['status']!r}"
    assert parts[0]["file_path"] is None


def test_orchestrator_preserves_v124_cfr_chunks():
    """v1.2.4+ chunks (file_path ends with .video.cfr.mp4) carry the
    frame-exact / CFR / fixed-timescale encoder args and are safe to preserve
    across resume."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.celery_task_id = "old-orch-id"
    video.sfx_seed = 1
    video.target_duration_h = 1 / 60 * 3  # 180s → 1 chunk
    video.status = "rendering"
    video.render_parts = [{
        "idx": 0, "start_s": 0, "end_s": 180,
        "status": "completed",
        "file_path": "/tmp/youtube_42/chunk_0/chunk.video.cfr.mp4",  # v1.2.4+
    }]

    db = MagicMock()
    db.get.return_value = video

    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("console.backend.tasks.youtube_render_task._is_superseded", return_value=False), \
         patch("celery.chord", MagicMock()), \
         patch("celery.group", MagicMock()), \
         patch("sqlalchemy.orm.attributes.flag_modified"):
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        render_youtube_chunked_orchestrator_task.apply(args=[42])

    parts = video.render_parts
    assert len(parts) == 1
    assert parts[0]["status"] == "completed", \
        f"v1.2.4 chunk should be preserved, got status={parts[0]['status']!r}"
    assert parts[0]["file_path"].endswith(".video.cfr.mp4")


def test_chunk_task_writes_to_cfr_suffix_path():
    """render_youtube_chunk_task must persist chunks as chunk.video.cfr.mp4 so
    the orchestrator's invalidator can recognise them as the current
    encoder-args generation."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.status = "rendering"

    db = MagicMock()
    db.get.return_value = video

    captured_path = {}

    def fake_render_landscape(_video, out_path, _db, **_kwargs):
        captured_path["path"] = str(out_path)
        # Simulate a successful render so the chunk gets marked completed.
        from pathlib import Path
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"fake")

    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("console.backend.tasks.youtube_render_task._update_chunk_status"), \
         patch("console.backend.tasks.youtube_render_task._publish_youtube_render_event"), \
         patch("pipeline.youtube_ffmpeg.render_landscape", side_effect=fake_render_landscape):
        from console.backend.tasks.youtube_render_task import render_youtube_chunk_task
        render_youtube_chunk_task.apply(args=[42, 0, 0.0, 300.0]).get()

    assert captured_path["path"].endswith("chunk.video.cfr.mp4"), \
        f"chunk must be written as chunk.video.cfr.mp4, got {captured_path['path']!r}"


def test_concat_task_rejects_chunks_with_embedded_audio(tmp_path):
    """concat_youtube_chunks_task must ffprobe each chunk and abort if any
    still has an audio stream (defensive against partially-stale render_parts)."""
    import subprocess
    import shutil
    from unittest.mock import patch, MagicMock

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not installed")

    # Build one chunk WITH audio (simulating a legacy pre-v1.2.1 chunk).
    legacy_chunk = tmp_path / "legacy_chunk.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=black:s=320x180:d=2:r=30",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-shortest",
        "-pix_fmt", "yuv420p", "-r", "30",
        str(legacy_chunk),
    ], check=True, capture_output=True)

    video = MagicMock()
    video.id = 42
    video.status = "rendering"
    video.render_parts = [{
        "idx": 0, "status": "completed",
        "file_path": str(legacy_chunk),
    }]

    db = MagicMock()
    db.get.return_value = video

    with patch("console.backend.database.SessionLocal", return_value=db), \
         patch("pipeline.youtube_ffmpeg.render_full_audio_track") as mock_audio, \
         patch("pipeline.concat.concat_video_and_mux_audio") as mock_mux:
        from console.backend.tasks.youtube_render_task import concat_youtube_chunks_task
        # Force run; expect failure.
        with pytest.raises(Exception) as exc_info:
            concat_youtube_chunks_task.apply(
                args=[[], 42], throw=True,
            ).get()

    msg = str(exc_info.value)
    assert "embedded audio" in msg or "still contain embedded" in msg, \
        f"expected explicit error about embedded audio, got: {msg!r}"
    mock_audio.assert_not_called()
    mock_mux.assert_not_called()
