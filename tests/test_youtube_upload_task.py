from unittest.mock import MagicMock, patch


def _make_db():
    video = MagicMock()
    video.output_path = "/renders/out.mp4"
    video.seo_title = "My Video"
    video.seo_description = "desc"
    video.seo_tags = []
    video.title = "My Video"
    video.thumbnail_path = None

    channel = MagicMock()
    channel.default_language = "en"
    channel.credential_id = 5

    cred = MagicMock()
    cred.client_id = "cid"
    cred.client_secret = None
    cred.access_token = None
    cred.refresh_token = None

    upload = MagicMock()
    upload.id = 99
    upload.status = "queued"

    db = MagicMock()

    def _get(cls, _id):
        name = getattr(cls, "__name__", str(cls))
        if "YoutubeVideo" in name and "Upload" not in name:
            return video
        if "Channel" in name:
            return channel
        if "PlatformCredential" in name:
            return cred
        if "YoutubeVideoUpload" in name:
            return upload
        return MagicMock()

    db.get.side_effect = _get
    return db, video, channel, cred, upload


def test_upload_task_sets_uploading_then_done():
    db, video, channel, cred, upload = _make_db()

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", return_value="yt_xyz"):
        mock_settings.FERNET_KEY = "a" * 44  # valid base64 length for Fernet
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
        result = upload_youtube_video_task.run(1, 3, 99)

    assert upload.status == "done"
    assert upload.platform_id == "yt_xyz"
    assert upload.uploaded_at is not None
    assert result["platform_id"] == "yt_xyz"


def test_upload_task_sets_failed_on_error():
    db, video, channel, cred, upload = _make_db()

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", side_effect=RuntimeError("API error")):
        mock_settings.FERNET_KEY = "a" * 44
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task

        # Patch self.retry to raise to simulate Celery retry behavior
        with patch.object(upload_youtube_video_task, "retry", side_effect=RuntimeError("retrying")):
            try:
                upload_youtube_video_task.run(1, 3, 99)
            except RuntimeError:
                pass

    assert upload.status == "failed"
    assert "API error" in (upload.error or "")


def test_upload_task_calls_set_thumbnail_when_path_set():
    db, video, channel, cred, upload = _make_db()
    video.thumbnail_path = "/assets/thumbnails/generated/yt_1.png"

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", return_value="yt_xyz"), \
         patch("console.backend.tasks.youtube_upload_task.set_thumbnail") as mock_set_thumb:
        mock_settings.FERNET_KEY = "a" * 44
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
        upload_youtube_video_task.run(1, 3, 99)

    args = mock_set_thumb.call_args[0]
    assert args[0] == "yt_xyz"
    assert args[1] == "/assets/thumbnails/generated/yt_1.png"
    assert isinstance(args[2], dict)


def test_upload_task_skips_set_thumbnail_when_no_path():
    db, video, channel, cred, upload = _make_db()
    video.thumbnail_path = None

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", return_value="yt_xyz"), \
         patch("console.backend.tasks.youtube_upload_task.set_thumbnail") as mock_set_thumb:
        mock_settings.FERNET_KEY = "a" * 44
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
        upload_youtube_video_task.run(1, 3, 99)

    mock_set_thumb.assert_not_called()


def test_upload_task_thumbnail_failure_does_not_fail_upload():
    db, video, channel, cred, upload = _make_db()
    video.thumbnail_path = "/assets/thumbnails/generated/yt_1.png"

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", return_value="yt_xyz"), \
         patch("console.backend.tasks.youtube_upload_task.set_thumbnail", side_effect=RuntimeError("API error")):
        mock_settings.FERNET_KEY = "a" * 44
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
        result = upload_youtube_video_task.run(1, 3, 99)

    assert upload.status == "done"
    assert result["platform_id"] == "yt_xyz"
