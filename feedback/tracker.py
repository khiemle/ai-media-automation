"""
Feedback Tracker — fetches real performance metrics from YouTube and TikTok.
Stores results to generated_scripts and viral_videos tables.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    platform:      str
    platform_id:   str
    views:         int = 0
    likes:         int = 0
    comments:      int = 0
    shares:        int = 0
    revenue_usd:   float = 0.0
    engagement_rate: float = 0.0
    fetched_at:    datetime | None = None


def fetch_all() -> list[Metrics]:
    """
    Fetch metrics for all uploaded videos (those with platform_video_id set).
    Returns list of Metrics objects.
    """
    from database.connection import get_session
    from database.models import GeneratedScript

    db = get_session()
    try:
        scripts = db.query(GeneratedScript).filter(
            GeneratedScript.platform_video_id.isnot(None),
            GeneratedScript.status == "completed",
        ).all()

        all_metrics = []
        for script in scripts:
            pid = script.platform_video_id
            if pid.startswith("YT_"):
                m = fetch_youtube(pid[3:])
            elif pid.startswith("TT_"):
                m = fetch_tiktok(pid[3:])
            else:
                m = fetch_youtube(pid)  # default to YouTube

            if m:
                all_metrics.append(m)
                # Update script quality_score
                from feedback.scorer import compute_score
                score = compute_score(m)
                script.quality_score = score
                logger.info(f"[Tracker] script={script.id} platform_id={pid} score={score:.1f}")

        db.commit()
        return all_metrics
    finally:
        db.close()


def fetch_youtube(video_id: str) -> Metrics | None:
    """Fetch YouTube video statistics via Data API v3."""
    try:
        import os
        api_key = os.environ.get("GEMINI_API_KEY", "")   # reuse Google API key or set YOUTUBE_API_KEY
        yt_key  = os.environ.get("YOUTUBE_API_KEY", api_key)
        if not yt_key:
            logger.warning("[Tracker] YOUTUBE_API_KEY not set")
            return None

        import httpx
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "key":  yt_key,
                "id":   video_id,
                "part": "statistics",
            },
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None

        stats = items[0].get("statistics", {})
        views    = int(stats.get("viewCount", 0))
        likes    = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        er = round((likes + comments) / max(views, 1) * 100, 2)

        return Metrics(
            platform="youtube",
            platform_id=video_id,
            views=views,
            likes=likes,
            comments=comments,
            engagement_rate=er,
            fetched_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"[Tracker] YouTube fetch failed for {video_id}: {e}")
        return None


def fetch_tiktok(video_id: str) -> Metrics | None:
    """Fetch TikTok video stats via Research API."""
    try:
        import os, httpx
        token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
        if not token:
            logger.warning("[Tracker] TIKTOK_ACCESS_TOKEN not set")
            return None

        resp = httpx.post(
            "https://open.tiktokapis.com/v2/research/video/query/",
            json={
                "query": {"and": [{"operation": "IN", "field_name": "id", "field_values": [video_id]}]},
                "fields": "statistics",
            },
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        videos = resp.json().get("data", {}).get("videos", [])
        if not videos:
            return None

        stats  = videos[0].get("statistics", {})
        views  = int(stats.get("play_count", 0))
        likes  = int(stats.get("like_count", 0))
        shares = int(stats.get("share_count", 0))
        cmts   = int(stats.get("comment_count", 0))
        er = round((likes + cmts + shares) / max(views, 1) * 100, 2)

        return Metrics(
            platform="tiktok",
            platform_id=video_id,
            views=views,
            likes=likes,
            comments=cmts,
            shares=shares,
            engagement_rate=er,
            fetched_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        logger.error(f"[Tracker] TikTok fetch failed for {video_id}: {e}")
        return None
