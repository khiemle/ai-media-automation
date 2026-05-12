import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch


def _seed_upload(db, *, platform_id="vid_endpoint", status="done"):
    from console.backend.models.channel import Channel
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.youtube_video_upload import YoutubeVideoUpload

    template = VideoTemplate(
        slug=f"stats-ep-{uuid.uuid4().hex[:6]}",
        label="x",
        output_format="landscape_long",
    )
    db.add(template); db.flush()
    video = YoutubeVideo(title="x", template_id=template.id)
    db.add(video); db.flush()
    channel = Channel(platform="youtube", name="Test")
    db.add(channel); db.flush()
    upload = YoutubeVideoUpload(
        youtube_video_id=video.id,
        channel_id=channel.id,
        platform_id=platform_id,
        status=status,
        uploaded_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(upload); db.flush()
    return upload


def test_get_upload_stats_returns_json(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    upload = _seed_upload(db)
    db.commit()

    def _get_db_override():
        yield db
    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()

    fake_result = {
        "view_count": 100, "like_count": 5, "comment_count": 1,
        "watch_time_minutes": 25, "fetched_at": datetime.now(timezone.utc),
        "watch_time_available": True,
    }
    try:
        with patch("console.backend.routers.youtube_videos.fetch_upload_stats",
                   return_value=fake_result) as mock_fn:
            with TestClient(app) as client:
                resp = client.get(f"/api/youtube-videos/uploads/{upload.id}/stats")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["view_count"] == 100
        assert body["watch_time_minutes"] == 25
        assert body["watch_time_available"] is True
        assert "fetched_at" in body
        mock_fn.assert_called_once_with(upload.id, db)
    finally:
        app.dependency_overrides.clear()


def test_get_upload_stats_404_when_missing(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    def _get_db_override():
        yield db
    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with patch(
            "console.backend.routers.youtube_videos.fetch_upload_stats",
            side_effect=ValueError("YoutubeVideoUpload 999 not found"),
        ):
            with TestClient(app) as client:
                resp = client.get("/api/youtube-videos/uploads/999/stats")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_upload_stats_400_when_not_ready(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    upload = _seed_upload(db, status="queued", platform_id=None)
    db.commit()

    def _get_db_override():
        yield db
    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with patch(
            "console.backend.routers.youtube_videos.fetch_upload_stats",
            side_effect=ValueError("upload not ready for stats"),
        ):
            with TestClient(app) as client:
                resp = client.get(f"/api/youtube-videos/uploads/{upload.id}/stats")
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()
