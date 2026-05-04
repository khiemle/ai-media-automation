"""Tests for cancel-all-tasks: revoke all chunk + concat Celery task IDs on cancel/delete."""
from unittest.mock import MagicMock, patch


def _make_video(parts=None, celery_task_id=None, status="rendering"):
    v = MagicMock()
    v.id = 42
    v.status = status
    v.celery_task_id = celery_task_id
    v.render_parts = parts or []
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
