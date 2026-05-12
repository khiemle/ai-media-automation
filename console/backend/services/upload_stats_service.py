"""Live YouTube stats fetcher for uploaded videos. No DB persistence.

Calls YouTube Data API v3 statistics for views/likes/comments and the
YouTube Analytics API v2 for estimatedMinutesWatched. Each API call is
independent; a failure on one does not block the other.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from console.backend.config import settings

logger = logging.getLogger(__name__)


def _decrypt(value: str | None) -> str | None:
    if not value:
        return None
    return Fernet(settings.FERNET_KEY.encode()).decrypt(value.encode()).decode()


def _get_credentials_for_channel(channel_id: int, db: Session) -> Credentials:
    """Build google Credentials from the channel's stored OAuth tokens.

    Mirrors the pattern used in console/backend/tasks/youtube_upload_task.py:
    look up the Channel row, then its PlatformCredential, and decrypt the
    stored access/refresh tokens with Fernet.
    """
    from console.backend.models.channel import Channel
    from console.backend.models.credentials import PlatformCredential

    channel = db.get(Channel, channel_id)
    if channel is None:
        raise ValueError(f"Channel {channel_id} not found")
    cred = db.get(PlatformCredential, channel.credential_id) if channel.credential_id else None
    if cred is None:
        raise ValueError(f"Credential not found for channel {channel_id}")

    return Credentials(
        token=_decrypt(cred.access_token),
        refresh_token=_decrypt(cred.refresh_token),
        client_id=cred.client_id,
        client_secret=_decrypt(cred.client_secret),
        token_uri="https://oauth2.googleapis.com/token",
    )


def _fetch_data_api_stats(creds: Credentials, platform_id: str) -> dict:
    """Call YouTube Data API v3 videos().list and parse the statistics block."""
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    response = youtube.videos().list(id=platform_id, part="statistics").execute()
    items = response.get("items") or []
    if not items:
        return {"view_count": None, "like_count": None, "comment_count": None}
    stats = items[0].get("statistics") or {}

    def _as_int(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "view_count":    _as_int(stats.get("viewCount")),
        "like_count":    _as_int(stats.get("likeCount")),
        "comment_count": _as_int(stats.get("commentCount")),
    }


def _fetch_analytics_watch_time(creds: Credentials, platform_id: str, start_date) -> int | None:
    """Call YouTube Analytics API v2 for estimatedMinutesWatched.

    start_date: the upload's date object (or string YYYY-MM-DD).
    Returns the integer minutes or 0 when the report has no rows yet.
    Raises on API error — caller decides how to surface.
    """
    analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    end_date = datetime.now(timezone.utc).date().isoformat()
    response = analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
        endDate=end_date,
        metrics="estimatedMinutesWatched",
        filters=f"video=={platform_id}",
    ).execute()
    rows = response.get("rows") or []
    if not rows or not rows[0]:
        return 0  # report returned no data yet (e.g., brand-new video)
    try:
        return int(rows[0][0])
    except (TypeError, ValueError):
        return None


def fetch_stats(upload_id: int, db: Session) -> dict:
    """Fetch live YouTube stats for one upload. Synchronous; no DB writes.

    Returns:
        {
            "view_count":           int | None,
            "like_count":           int | None,
            "comment_count":        int | None,
            "watch_time_minutes":   int | None,
            "fetched_at":           datetime,
            "watch_time_available": bool,
        }

    Raises:
        ValueError("YoutubeVideoUpload {id} not found") when upload doesn't exist.
        ValueError("upload not ready for stats") when status != 'done' or platform_id is missing.
    """
    from console.backend.models.youtube_video_upload import YoutubeVideoUpload

    upload = db.get(YoutubeVideoUpload, upload_id)
    if upload is None:
        raise ValueError(f"YoutubeVideoUpload {upload_id} not found")
    if upload.status != "done" or not upload.platform_id:
        raise ValueError("upload not ready for stats")

    creds = _get_credentials_for_channel(upload.channel_id, db)

    data_stats = _fetch_data_api_stats(creds, upload.platform_id)

    watch_time_minutes: int | None = None
    watch_time_available = False
    try:
        start_date = (upload.uploaded_at or upload.created_at).date()
        watch_time_minutes = _fetch_analytics_watch_time(creds, upload.platform_id, start_date)
        watch_time_available = True
    except Exception as exc:  # noqa: BLE001 — analytics fail-soft by design
        logger.warning(
            "YouTube Analytics fetch failed for upload %s (platform_id=%s): %s",
            upload_id, upload.platform_id, exc,
        )

    return {
        "view_count":           data_stats["view_count"],
        "like_count":           data_stats["like_count"],
        "comment_count":        data_stats["comment_count"],
        "watch_time_minutes":   watch_time_minutes,
        "fetched_at":           datetime.now(timezone.utc),
        "watch_time_available": watch_time_available,
    }
