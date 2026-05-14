import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from console.backend.models.channel import Channel
from console.backend.models.credentials import PlatformCredential
from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.models.youtube_video_upload import YoutubeVideoUpload


def _seed_upload(db, *, status="done", platform_id="vid123",
                 uploaded_at=None) -> YoutubeVideoUpload:
    slug = f"stats-{uuid.uuid4().hex[:6]}"
    template = VideoTemplate(slug=slug, label="x", output_format="landscape_long")
    db.add(template); db.flush()

    video = YoutubeVideo(title="x", template_id=template.id)
    db.add(video); db.flush()

    channel = Channel(
        platform="youtube",
        name="Test Channel",
    )
    db.add(channel); db.flush()

    upload = YoutubeVideoUpload(
        youtube_video_id=video.id,
        channel_id=channel.id,
        platform_id=platform_id,
        status=status,
        uploaded_at=uploaded_at or datetime.now(timezone.utc) - timedelta(days=3),
    )
    db.add(upload); db.flush()
    return upload


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_happy_path_returns_all_metrics(mock_build, mock_creds, db):
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {
            "viewCount": "1234",
            "likeCount": "42",
            "commentCount": "5",
        }}],
    }
    analytics = MagicMock()
    analytics.reports().query().execute.return_value = {
        "rows": [[789]],  # estimatedMinutesWatched
        "columnHeaders": [{"name": "estimatedMinutesWatched"}],
    }

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)

    assert result["view_count"] == 1234
    assert result["like_count"] == 42
    assert result["comment_count"] == 5
    assert result["watch_time_minutes"] == 789
    assert result["watch_time_available"] is True
    assert isinstance(result["fetched_at"], datetime)


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_analytics_fails_soft(mock_build, mock_creds, db):
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {"viewCount": "10"}}],
    }
    analytics = MagicMock()
    analytics.reports().query().execute.side_effect = RuntimeError("scope missing")

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)

    assert result["view_count"] == 10
    assert result["like_count"] is None
    assert result["comment_count"] is None
    assert result["watch_time_minutes"] is None
    assert result["watch_time_available"] is False
    assert result["watch_time_scope_missing"] is False, \
        "RuntimeError isn't an HttpError — must not be classified as scope-missing"


def test_fetch_stats_rejects_non_done_upload(db):
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db, status="queued", platform_id=None)
    with pytest.raises(ValueError, match="not ready"):
        fetch_stats(upload.id, db)


def test_fetch_stats_rejects_missing_upload(db):
    from console.backend.services.upload_stats_service import fetch_stats
    with pytest.raises(ValueError, match="not found"):
        fetch_stats(999999, db)


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_handles_missing_data_api_fields(mock_build, mock_creds, db):
    """Data API may return only some statistics fields (e.g. comments disabled)."""
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {"viewCount": "100"}}],  # no like/comment
    }
    analytics = MagicMock()
    analytics.reports().query().execute.return_value = {"rows": [[50]]}

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)
    assert result["view_count"] == 100
    assert result["like_count"] is None
    assert result["comment_count"] is None
    assert result["watch_time_minutes"] == 50


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_classifies_scope_missing_on_http_403_forbidden(mock_build, mock_creds, db):
    """A real HttpError(403) with 'Insufficient Permission' should flag scope_missing=True."""
    from console.backend.services.upload_stats_service import fetch_stats
    from googleapiclient.errors import HttpError

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {"viewCount": "10"}}],
    }
    analytics = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status = 403
    fake_resp.reason = "Forbidden"
    analytics.reports().query().execute.side_effect = HttpError(
        resp=fake_resp,
        content=b'{"error":{"code":403,"message":"Insufficient Permission","errors":[{"message":"Insufficient Permission","domain":"global","reason":"insufficientPermissions"}]}}',
    )

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)

    assert result["watch_time_available"] is False
    assert result["watch_time_scope_missing"] is True
    assert result["view_count"] == 10  # Data API still works


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_does_not_flag_scope_missing_on_http_500(mock_build, mock_creds, db):
    """A 500-level Analytics error is not a scope problem; UI must not show re-auth link."""
    from console.backend.services.upload_stats_service import fetch_stats
    from googleapiclient.errors import HttpError

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {"viewCount": "10"}}],
    }
    analytics = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status = 500
    analytics.reports().query().execute.side_effect = HttpError(
        resp=fake_resp,
        content=b"Internal Server Error",
    )

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)

    assert result["watch_time_available"] is False
    assert result["watch_time_scope_missing"] is False


def test_get_credentials_refreshes_when_expired(db, monkeypatch):
    """If the stored access token is expired, _get_credentials_for_channel must
    proactively call creds.refresh(Request()) before returning. This mirrors
    the uploader's behavior; without it, an expired token shows up as an
    Analytics failure (mis-classified as a scope problem)."""
    from cryptography.fernet import Fernet
    from console.backend.models.channel import Channel
    from console.backend.models.credentials import PlatformCredential
    import console.backend.services.upload_stats_service as svc_mod

    fernet = Fernet(svc_mod.settings.FERNET_KEY.encode())

    cred = PlatformCredential(
        platform="youtube",
        name="Test Credential",
        client_id="cid",
        client_secret=fernet.encrypt(b"sec").decode(),
        access_token=fernet.encrypt(b"old_access").decode(),
        refresh_token=fernet.encrypt(b"refresh_tok").decode(),
    )
    db.add(cred); db.flush()

    channel = Channel(platform="youtube", name="Test", credential_id=cred.id)
    db.add(channel); db.flush()

    fake_creds = MagicMock()
    fake_creds.expired = True
    fake_creds.refresh_token = "refresh_tok"
    monkeypatch.setattr(svc_mod, "Credentials", lambda **kw: fake_creds)

    result = svc_mod._get_credentials_for_channel(channel.id, db)

    fake_creds.refresh.assert_called_once()
    assert result is fake_creds
