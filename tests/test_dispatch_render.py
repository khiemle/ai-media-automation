import pytest
from unittest.mock import MagicMock, patch


def _setup_db(output_format: str):
    """Return a mock db that returns a video and template with the given output_format."""
    video = MagicMock()
    video.id = 1
    video.template_id = 10
    video.celery_task_id = None

    template = MagicMock()
    template.output_format = output_format

    db = MagicMock()

    def _get(cls, _id):
        name = cls.__name__ if hasattr(cls, "__name__") else str(cls)
        return video if "YoutubeVideo" in name else template

    db.get.side_effect = _get
    return db, video, template


def test_dispatch_render_routes_landscape_long_to_landscape_task():
    db, video, _ = _setup_db("landscape_long")

    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="task-landscape")

    with patch(
        "console.backend.tasks.youtube_render_task.render_youtube_video_task",
        mock_task,
    ):
        from console.backend.services.youtube_video_service import YoutubeVideoService
        svc = YoutubeVideoService(db)
        task_id = svc.dispatch_render(1)

    mock_task.delay.assert_called_once_with(1)
    assert task_id == "task-landscape"


def test_dispatch_render_routes_portrait_short_to_short_task():
    db, video, _ = _setup_db("portrait_short")

    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="task-short")

    with patch(
        "console.backend.tasks.youtube_short_render_task.render_youtube_short_task",
        mock_task,
    ):
        from console.backend.services.youtube_video_service import YoutubeVideoService
        svc = YoutubeVideoService(db)
        task_id = svc.dispatch_render(1)

    mock_task.delay.assert_called_once_with(1)
    assert task_id == "task-short"


def test_dispatch_render_raises_when_video_not_found():
    db = MagicMock()
    db.get.return_value = None

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(KeyError, match="not found"):
        svc.dispatch_render(999)


def test_dispatch_render_raises_when_template_not_found():
    video = MagicMock()
    video.id = 1
    video.template_id = 10

    db = MagicMock()
    call_count = {"n": 0}

    def _get(cls, _id):
        call_count["n"] += 1
        return video if call_count["n"] == 1 else None

    db.get.side_effect = _get

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="not found"):
        svc.dispatch_render(1)
