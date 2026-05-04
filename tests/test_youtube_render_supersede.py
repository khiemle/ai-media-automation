"""Regression tests for the render-task supersede guard.

Without the guard, two ffmpeg processes could write to the same output file
simultaneously when a Celery retry overlapped a fresh user-initiated dispatch,
producing a corrupted MP4 with two `moov` atoms.
"""
from unittest.mock import MagicMock


def _make_self(task_id: str):
    """Mock the bound `self` argument of a Celery task with .request.id set."""
    s = MagicMock()
    s.request.id = task_id
    return s


def test_is_superseded_returns_true_when_celery_task_id_differs():
    from console.backend.tasks.youtube_render_task import _is_superseded
    video = MagicMock()
    video.id = 22
    video.celery_task_id = "newer-task-uuid"
    assert _is_superseded(_make_self("stale-task-uuid"), video) is True


def test_is_superseded_returns_false_when_ids_match():
    from console.backend.tasks.youtube_render_task import _is_superseded
    video = MagicMock()
    video.id = 22
    video.celery_task_id = "matching-uuid"
    assert _is_superseded(_make_self("matching-uuid"), video) is False


def test_is_superseded_returns_false_when_celery_task_id_is_none():
    """Backwards compat: legacy rows have no celery_task_id; never abort."""
    from console.backend.tasks.youtube_render_task import _is_superseded
    video = MagicMock()
    video.id = 22
    video.celery_task_id = None
    assert _is_superseded(_make_self("any-uuid"), video) is False


def test_dispatch_render_task_writes_celery_task_id_before_dispatch():
    """The service's _dispatch_render_task must write celery_task_id to the DB
    BEFORE calling apply_async, so the task can read it on startup. Otherwise
    the task could see a stale (or None) celery_task_id and falsely abort."""
    from console.backend.services.youtube_video_service import YoutubeVideoService

    video = MagicMock()
    video.celery_task_id = None

    db = MagicMock()
    svc = YoutubeVideoService(db)

    write_order = []
    def record_commit():
        write_order.append(("commit", video.celery_task_id))
    db.commit.side_effect = record_commit

    fake_task = MagicMock()
    def record_apply_async(args=None, task_id=None):
        write_order.append(("apply_async", task_id))
        return MagicMock()
    fake_task.apply_async.side_effect = record_apply_async

    returned_id = svc._dispatch_render_task(fake_task, video, [42])

    # The commit (with celery_task_id set) must come BEFORE apply_async
    assert write_order[0][0] == "commit", f"expected commit first, got: {write_order}"
    assert write_order[0][1] == returned_id, "celery_task_id must be set before commit"
    assert write_order[1][0] == "apply_async"
    assert write_order[1][1] == returned_id, "apply_async must use the same task_id"


def test_dispatch_render_task_passes_args_through():
    from console.backend.services.youtube_video_service import YoutubeVideoService

    video = MagicMock()
    video.celery_task_id = None
    db = MagicMock()
    fake_task = MagicMock()
    captured = {}
    def record(args=None, task_id=None):
        captured["args"] = args
        return MagicMock()
    fake_task.apply_async.side_effect = record

    svc = YoutubeVideoService(db)
    svc._dispatch_render_task(fake_task, video, [42, "extra"])
    assert captured["args"] == [42, "extra"]
