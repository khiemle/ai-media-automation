"""
TikTok Research API scraper adapter.
Docs: https://developers.tiktok.com/doc/research-api-get-videos
Requires: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET in env.
"""
import logging
import os
import time
from datetime import datetime, timedelta

import httpx

from scraper.base_scraper import BaseScraper, ScrapedVideo

logger = logging.getLogger(__name__)

TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_QUERY_URL = "https://open.tiktokapis.com/v2/research/video/query/"

NICHE_HASHTAG_MAP = {
    "health":      ["suckhoe", "suckhoetotday", "health", "wellness"],
    "fitness":     ["fitness", "gymlife", "workout", "thehinh"],
    "lifestyle":   ["lifestyle", "cuocsong", "dailyvlog"],
    "finance":     ["taichinhcanhan", "dautu", "finance", "money"],
    "food":        ["amthuc", "monan", "food", "cooking"],
}


class TikTokResearchAPI(BaseScraper):
    def __init__(self, niches: list[str] | None = None, max_count: int = 100):
        self.client_key    = os.environ.get("TIKTOK_CLIENT_KEY", "")
        self.client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
        self.niches        = niches or list(NICHE_HASHTAG_MAP.keys())
        self.max_count     = max_count
        self._token: str | None = None
        self._token_expires: float = 0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        resp = httpx.post(
            TIKTOK_TOKEN_URL,
            data={
                "client_key":    self.client_key,
                "client_secret": self.client_secret,
                "grant_type":    "client_credentials",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 7200)
        return self._token

    def _query_videos(self, hashtag: str, niche: str) -> list[ScrapedVideo]:
        token = self._get_token()
        end_date   = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        payload = {
            "query": {
                "and": [
                    {"operation": "IN", "field_name": "hashtag_name", "field_values": [hashtag]},
                    {"operation": "GT", "field_name": "video_duration", "field_values": ["5"]},
                ]
            },
            "start_date": start_date.strftime("%Y%m%d"),
            "end_date":   end_date.strftime("%Y%m%d"),
            "max_count":  self.max_count,
            "fields":     "id,create_time,author_info,video_info,statistics,hashtag_info",
        }

        resp = httpx.post(
            TIKTOK_QUERY_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.warning(f"TikTok Research API error {resp.status_code}: {resp.text[:200]}")
            return []

        videos = resp.json().get("data", {}).get("videos", [])
        results = []
        for v in videos:
            stats = v.get("statistics", {})
            vinfo = v.get("video_info", {})
            author = v.get("author_info", {})
            tags = [h.get("hashtag_name", "") for h in v.get("hashtag_info", [])]
            # Extract hook: first line of description
            desc = vinfo.get("video_description", "")
            hook = desc.split("\n")[0][:150] if desc else ""

            results.append(ScrapedVideo(
                video_id=str(v.get("id", "")),
                source="tiktok_research",
                author=author.get("unique_id", ""),
                hook_text=hook,
                play_count=stats.get("play_count", 0),
                like_count=stats.get("like_count", 0),
                share_count=stats.get("share_count", 0),
                comment_count=stats.get("comment_count", 0),
                duration_s=float(vinfo.get("duration", 0)),
                niche=niche,
                region="vn",
                tags=tags,
                thumbnail_url=vinfo.get("cover_image_url", ""),
                raw=v,
            ))
        return results

    def fetch(self) -> list[ScrapedVideo]:
        if not self.client_key or not self.client_secret:
            logger.warning("TikTok Research API: TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET not set")
            return []

        all_videos: list[ScrapedVideo] = []
        for niche in self.niches:
            for hashtag in NICHE_HASHTAG_MAP.get(niche, [niche]):
                try:
                    videos = self._query_videos(hashtag, niche)
                    all_videos.extend(videos)
                    logger.info(f"[TikTok Research] niche={niche} hashtag={hashtag} → {len(videos)} videos")
                    time.sleep(1)   # rate limit
                except Exception as e:
                    logger.error(f"[TikTok Research] hashtag={hashtag} error: {e}")

        # Deduplicate within this batch by video_id
        seen: set[str] = set()
        unique = []
        for v in all_videos:
            if v.video_id not in seen:
                seen.add(v.video_id)
                unique.append(v)
        return unique


# Entry point for Celery task (called via YAML module/function config)
_instance: TikTokResearchAPI | None = None


def scrape() -> list[int]:
    global _instance
    if _instance is None:
        _instance = TikTokResearchAPI()
    return _instance.scrape()
