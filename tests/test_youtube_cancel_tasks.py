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
