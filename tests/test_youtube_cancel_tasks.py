"""Tests for cancel-all-tasks: revoke all chunk + concat Celery task IDs on cancel/delete."""
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
