"""Verify chapters are built and forwarded during the YouTube upload task."""
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_track(title: str, duration_s: float) -> MagicMock:
    t = MagicMock()
    t.title = title
    t.duration_s = duration_s
    return t


def _make_video(slug: str, track_count: int = 3, template_id: int = 1):
    """Return a MagicMock YoutubeVideo with the given template slug.

    Note: YoutubeVideo has no ``template`` ORM relationship — only
    ``template_id``.  ``_make_db_for(slug)`` pairs with this to supply
    a ``db.get`` mock that returns the right VideoTemplate.
    """
    video = MagicMock()
    video.template_id = template_id
    video.track_transition = "gapless"
    video.track_transition_seconds = 2.0
    video.music_track_ids = list(range(1, track_count + 1))
    video.music_track_id = None
    return video


def _make_db_for(slug: str, template_id: int = 1) -> MagicMock:
    """Return a MagicMock db whose .get() returns a fake VideoTemplate."""
    fake_template = MagicMock()
    fake_template.slug = slug
    db = MagicMock()
    db.get.return_value = fake_template
    return db


# ---------------------------------------------------------------------------
# Service-layer unit tests (no real DB needed)
# ---------------------------------------------------------------------------

def test_build_chapters_returns_list_for_music_template():
    """Service.build_chapters returns one entry per track for a music video."""
    from console.backend.services.youtube_video_service import YoutubeVideoService

    tracks = [_make_track(f"Track {i}", 60.0) for i in range(1, 4)]
    db = _make_db_for("music")
    video = _make_video("music", track_count=3)

    with patch(
        "console.backend.services.youtube_video_service._resolve_music_tracks",
        return_value=tracks,
    ):
        chapters = YoutubeVideoService(db).build_chapters(video)

    assert chapters is not None
    assert len(chapters) == 3
    assert chapters[0] == {"seconds": 0, "title": "Track 1"}
    assert chapters[1] == {"seconds": 60, "title": "Track 2"}
    assert chapters[2] == {"seconds": 120, "title": "Track 3"}


def test_build_chapters_returns_none_for_non_music_template():
    """Service.build_chapters returns None for templates that are not 'music'."""
    from console.backend.services.youtube_video_service import YoutubeVideoService

    db = _make_db_for("asmr")
    video = _make_video("asmr")

    chapters = YoutubeVideoService(db).build_chapters(video)
    assert chapters is None


def test_build_chapters_returns_none_for_fewer_than_3_tracks():
    """Service.build_chapters returns None when a music video has < 3 tracks."""
    from console.backend.services.youtube_video_service import YoutubeVideoService

    tracks = [_make_track("A", 60.0), _make_track("B", 60.0)]
    db = _make_db_for("music")
    video = _make_video("music", track_count=2)

    with patch(
        "console.backend.services.youtube_video_service._resolve_music_tracks",
        return_value=tracks,
    ):
        chapters = YoutubeVideoService(db).build_chapters(video)

    assert chapters is None


# ---------------------------------------------------------------------------
# Task wiring test — verifies chapters= is forwarded to the uploader
# ---------------------------------------------------------------------------

def test_upload_task_passes_chapters_to_uploader():
    """upload_youtube_video_task calls _youtube_upload with chapters= kwarg.

    We exercise the task body via ``__wrapped__`` (the undecorated function)
    so that we can pass a fake ``self`` without fighting Celery's proxy object.
    """
    fake_chapters = [
        {"seconds": 0,  "title": "Track 1"},
        {"seconds": 60, "title": "Track 2"},
        {"seconds": 120, "title": "Track 3"},
    ]

    # Minimal fake YoutubeVideo
    fake_video = MagicMock()
    fake_video.output_path = "/tmp/out.mp4"
    fake_video.seo_title = "Test"
    fake_video.seo_description = ""
    fake_video.seo_tags = []
    fake_video.thumbnail_path = None

    # Minimal fake channel + credential
    fake_channel = MagicMock()
    fake_channel.default_language = "en"
    fake_channel.credential_id = 1

    fake_cred = MagicMock()
    fake_cred.client_id = "client"
    fake_cred.client_secret = None
    fake_cred.access_token = None
    fake_cred.refresh_token = None

    fake_upload = MagicMock()

    fake_db = MagicMock()

    def _db_get(model, pk):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        return {
            "YoutubeVideo": fake_video,
            "YoutubeVideoUpload": fake_upload,
            "Channel": fake_channel,
            "PlatformCredential": fake_cred,
        }.get(name)

    fake_db.get.side_effect = _db_get

    mock_upload_fn = MagicMock(return_value="yt-abc123")
    mock_build_chapters = MagicMock(return_value=fake_chapters)

    # Fake Celery ``self`` for a bind=True task
    fake_self = MagicMock()
    fake_self.retry.side_effect = Exception("retry")

    with (
        patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=fake_db),
        patch("console.backend.tasks.youtube_upload_task._youtube_upload", mock_upload_fn),
        patch(
            "console.backend.services.youtube_video_service.YoutubeVideoService.build_chapters",
            mock_build_chapters,
        ),
    ):
        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task

        # __wrapped__ is the raw Python function before Celery's @task decorator.
        # Celery's bind=True attaches ``self`` separately; __wrapped__ only
        # needs the three user-visible positional arguments.
        result = upload_youtube_video_task.__wrapped__(1, 2, 3)

    # The uploader must have been called with chapters= keyword
    mock_upload_fn.assert_called_once()
    _, kwargs = mock_upload_fn.call_args
    assert "chapters" in kwargs, "chapters kwarg missing from _youtube_upload call"
    assert kwargs["chapters"] == fake_chapters
    assert result["platform_id"] == "yt-abc123"
