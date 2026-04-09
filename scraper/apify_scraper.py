"""
Apify cloud scraper adapter — TikTok Scraper actor.
Docs: https://apify.com/clockworks/tiktok-scraper
Requires: APIFY_API_TOKEN in env.
"""
import logging
import os
import time

from scraper.base_scraper import BaseScraper, ScrapedVideo

logger = logging.getLogger(__name__)

ACTOR_ID = os.environ.get("APIFY_TIKTOK_ACTOR_ID", "GdWCkxBtKWOsKjdch")

NICHE_HASHTAGS = {
    "health":    ["suckhoe", "health", "wellness", "suckhoetotday"],
    "fitness":   ["fitness", "workout", "thehinh", "gymlife"],
    "lifestyle": ["lifestyle", "cuocsong", "dailyvlog"],
    "finance":   ["taichinhcanhan", "dautu", "finance"],
    "food":      ["amthuc", "monan", "food"],
}

HASHTAG_TO_NICHE = {h: n for n, hs in NICHE_HASHTAGS.items() for h in hs}


class ApifyScraper(BaseScraper):
    def __init__(self, niches: list[str] | None = None, results_per_hashtag: int = 50):
        self.api_token = os.environ.get("APIFY_API_TOKEN", "")
        self.niches    = niches or list(NICHE_HASHTAGS.keys())
        self.results_per_hashtag = results_per_hashtag

    def _run_actor(self, hashtags: list[str]) -> list[dict]:
        """Run the Apify TikTok Scraper actor and wait for results."""
        try:
            from apify_client import ApifyClient
        except ImportError:
            logger.error("apify-client not installed. Run: pip install apify-client")
            return []

        client = ApifyClient(self.api_token)
        run_input = {
            "hashtags":         hashtags,
            "resultsPerPage":   self.results_per_hashtag,
            "maxItems":         len(hashtags) * self.results_per_hashtag,
            "scrapeLastNDays":  7,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
        }

        try:
            run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=300)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            return items
        except Exception as e:
            logger.error(f"[Apify] actor run failed: {e}")
            return []

    def fetch(self) -> list[ScrapedVideo]:
        if not self.api_token:
            logger.warning("[Apify] APIFY_API_TOKEN not set — skipping")
            return []

        hashtags = []
        for niche in self.niches:
            hashtags.extend(NICHE_HASHTAGS.get(niche, []))

        items = self._run_actor(hashtags)
        results: list[ScrapedVideo] = []

        for item in items:
            try:
                tags  = [h.get("name", "") for h in item.get("hashtags", [])]
                niche = "lifestyle"
                for tag in tags:
                    if tag.lower() in HASHTAG_TO_NICHE:
                        niche = HASHTAG_TO_NICHE[tag.lower()]
                        break

                desc  = item.get("text", "") or ""
                hook  = desc.split("\n")[0][:150]

                results.append(ScrapedVideo(
                    video_id=str(item.get("id", "")),
                    source="apify",
                    author=item.get("authorMeta", {}).get("name", ""),
                    hook_text=hook,
                    play_count=item.get("playCount", 0),
                    like_count=item.get("diggCount", 0),
                    share_count=item.get("shareCount", 0),
                    comment_count=item.get("commentCount", 0),
                    duration_s=float(item.get("videoMeta", {}).get("duration", 0)),
                    niche=niche,
                    region="vn",
                    tags=tags,
                    thumbnail_url=item.get("covers", {}).get("default", ""),
                    raw=item,
                ))
            except Exception as e:
                logger.debug(f"[Apify] parse error: {e}")

        logger.info(f"[Apify] scraped {len(results)} videos across {len(hashtags)} hashtags")
        return results


_instance: ApifyScraper | None = None


def scrape() -> list[int]:
    global _instance
    if _instance is None:
        _instance = ApifyScraper()
    return _instance.scrape()
