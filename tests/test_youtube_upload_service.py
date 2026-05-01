import pytest
from unittest.mock import MagicMock, patch


def _make_video(id=1, title="My Video", template_id=10, status="done"):
    v = MagicMock()
    v.id = id
    v.title = title
    v.template_id = template_id
    v.theme = None
    v.status = status
    v.music_track_id = None
    v.visual_asset_id = None
    v.parent_youtube_video_id = None
    v.sfx_overrides = None
    v.target_duration_h = 3.0
    v.output_quality = "1080p"
    v.seo_title = None
    v.seo_description = None
    v.seo_tags = None
    v.celery_task_id = None
    v.output_path = "/renders/out.mp4"
    v.created_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
    v.updated_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
    return v


def _make_upload(id=1, video_id=1, channel_id=3, status="done", platform_id="yt_abc"):
    u = MagicMock()
    u.id = id
    u.youtube_video_id = video_id
    u.channel_id = channel_id
    u.status = status
    u.platform_id = platform_id
    u.error = None
    u.uploaded_at = MagicMock(isoformat=lambda: "2026-05-01T10:00:00")
    return u


# ── _video_to_dict enrichment ─────────────────────────────────────────────────

def test_video_to_dict_includes_template_label():
    from console.backend.services.youtube_video_service import _video_to_dict
    result = _video_to_dict(_make_video(), template_label="ASMR Viral")
    assert result["template_label"] == "ASMR Viral"


def test_video_to_dict_template_label_defaults_to_none():
    from console.backend.services.youtube_video_service import _video_to_dict
    result = _video_to_dict(_make_video())
    assert result["template_label"] is None


def test_video_to_dict_includes_uploads():
    from console.backend.services.youtube_video_service import _video_to_dict
    result = _video_to_dict(_make_video(), uploads=[{
        "id": 1, "channel_id": 3, "channel_name": "My Channel",
        "status": "done", "platform_id": "yt_abc",
        "uploaded_at": "2026-05-01T10:00:00", "error": None,
    }])
    assert len(result["uploads"]) == 1
    assert result["uploads"][0]["channel_name"] == "My Channel"
    assert result["uploads"][0]["status"] == "done"


def test_video_to_dict_uploads_defaults_to_empty_list():
    from console.backend.services.youtube_video_service import _video_to_dict
    result = _video_to_dict(_make_video())
    assert result["uploads"] == []


# ── queue_upload ──────────────────────────────────────────────────────────────

def test_queue_upload_creates_record_and_returns_task_id():
    video = _make_video(status="done")
    db = MagicMock()
    db.get.return_value = video
    db.query.return_value.filter.return_value.first.return_value = None  # no existing

    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="celery-abc")

    with patch("console.backend.tasks.youtube_upload_task.upload_youtube_video_task", mock_task):
        from console.backend.services.youtube_video_service import YoutubeVideoService
        svc = YoutubeVideoService(db)
        result = svc.queue_upload(1, channel_id=3)

    assert result["task_id"] == "celery-abc"
    assert result["status"] == "queued"
    assert "upload_id" in result


def test_queue_upload_raises_conflict_when_done_upload_exists():
    video = _make_video(status="done")
    db = MagicMock()
    db.get.return_value = video
    db.query.return_value.filter.return_value.first.return_value = _make_upload(status="done")

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="already exists"):
        svc.queue_upload(1, channel_id=3)


def test_queue_upload_raises_conflict_when_uploading():
    video = _make_video(status="done")
    db = MagicMock()
    db.get.return_value = video
    db.query.return_value.filter.return_value.first.return_value = _make_upload(status="uploading")

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="already exists"):
        svc.queue_upload(1, channel_id=3)


def test_queue_upload_raises_when_video_not_found():
    db = MagicMock()
    db.get.return_value = None

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(KeyError):
        svc.queue_upload(999, channel_id=3)


def test_queue_upload_raises_when_video_not_done():
    video = _make_video(status="rendering")
    db = MagicMock()
    db.get.return_value = video

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="done"):
        svc.queue_upload(1, channel_id=3)
