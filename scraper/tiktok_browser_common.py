import json
import os
import re
from dataclasses import dataclass
from html import unescape

from scraper.base_scraper import ScrapedVideo

TRENDING_URLS = [
    "https://www.tiktok.com/explore",
    "https://www.tiktok.com/tag/suckhoe",
    "https://www.tiktok.com/tag/fitness",
    "https://www.tiktok.com/tag/lifestyle",
    "https://www.tiktok.com/tag/taichinhcanhan",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

NICHE_TAG_MAP = {
    "suckhoe": "health",
    "suckhoetotday": "health",
    "health": "health",
    "wellness": "health",
    "fitness": "fitness",
    "gymlife": "fitness",
    "workout": "fitness",
    "thehinh": "fitness",
    "lifestyle": "lifestyle",
    "cuocsong": "lifestyle",
    "dailyvlog": "lifestyle",
    "taichinhcanhan": "finance",
    "dautu": "finance",
    "finance": "finance",
    "money": "finance",
    "amthuc": "food",
    "monan": "food",
    "food": "food",
    "cooking": "food",
}

GLOBAL_STATE_EXPRESSIONS = [
    "window['SIGI_STATE'] || null",
    "window['__NEXT_DATA__'] || null",
    "window['__UNIVERSAL_DATA_FOR_REHYDRATION__'] || null",
    "window['__INITIAL_STATE__'] || null",
]

BLOCK_HINTS = (
    "verify to continue",
    "captcha",
    "login",
    "log in",
    "suspicious activity",
    "something went wrong",
)


@dataclass(frozen=True)
class BrowserScraperSettings:
    engine_preference: str = "auto"
    headless: bool = True
    headful_retry_on_empty: bool = True
    selenium_fallback: bool = True
    timeout_ms: int = 30000
    scroll_count: int = 4
    scroll_delay_ms: int = 1800
    browser_channel: str = ""
    chrome_binary_path: str = ""


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def load_browser_scraper_settings() -> BrowserScraperSettings:
    return BrowserScraperSettings(
        engine_preference=os.environ.get("TIKTOK_SCRAPER_ENGINE", "auto").strip().lower() or "auto",
        headless=_env_bool("TIKTOK_BROWSER_HEADLESS", True),
        headful_retry_on_empty=_env_bool("TIKTOK_BROWSER_HEADFUL_RETRY_ON_EMPTY", True),
        selenium_fallback=_env_bool("TIKTOK_SELENIUM_FALLBACK", True),
        timeout_ms=_env_int("TIKTOK_BROWSER_TIMEOUT_MS", 30000),
        scroll_count=_env_int("TIKTOK_BROWSER_SCROLL_COUNT", 4),
        scroll_delay_ms=_env_int("TIKTOK_BROWSER_SCROLL_DELAY_MS", 1800),
        browser_channel=os.environ.get("TIKTOK_BROWSER_CHANNEL", "").strip(),
        chrome_binary_path=os.environ.get("TIKTOK_CHROME_BINARY", "").strip(),
    )


def derive_niche_from_url(url: str) -> str:
    tag = url.split("/tag/")[-1] if "/tag/" in url else "lifestyle"
    return NICHE_TAG_MAP.get(tag.lower(), "lifestyle")


def looks_like_block_page(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in BLOCK_HINTS)


def dedupe_raw_items(items: list[dict]) -> list[dict]:
    unique: list[dict] = []
    seen: set[str] = set()
    for item in items:
        item_id = str(item.get("id", "")).strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        unique.append(item)
    return unique


def dedupe_scraped_videos(videos: list[ScrapedVideo]) -> list[ScrapedVideo]:
    unique: list[ScrapedVideo] = []
    seen: set[str] = set()
    for video in videos:
        if not video.video_id or video.video_id in seen:
            continue
        seen.add(video.video_id)
        unique.append(video)
    return unique


def parse_tiktok_item(item: dict, source_label: str, default_niche: str = "lifestyle") -> ScrapedVideo | None:
    try:
        video_info = item.get("video", {})
        stats = item.get("stats", {}) or item.get("statistics", {})
        author = item.get("author", {}) or item.get("authorInfo", {}) or item.get("author_info", {})
        description = item.get("desc") or item.get("video_description") or ""
        challenges = item.get("challenges") or item.get("hashtag_info") or []

        tags: list[str] = []
        for challenge in challenges:
            if not isinstance(challenge, dict):
                continue
            tag = challenge.get("title") or challenge.get("hashtag_name") or challenge.get("name")
            if tag:
                tags.append(str(tag))

        niche = default_niche
        for tag in tags:
            mapped = NICHE_TAG_MAP.get(tag.lower())
            if mapped:
                niche = mapped
                break

        return ScrapedVideo(
            video_id=str(item.get("id", "")),
            source=source_label,
            author=author.get("uniqueId", "") or author.get("unique_id", "") or author.get("nickname", ""),
            hook_text=description.split("\n")[0][:150],
            play_count=stats.get("playCount", 0) or stats.get("play_count", 0),
            like_count=stats.get("diggCount", 0) or stats.get("like_count", 0),
            share_count=stats.get("shareCount", 0) or stats.get("share_count", 0),
            comment_count=stats.get("commentCount", 0) or stats.get("comment_count", 0),
            duration_s=float(video_info.get("duration", 0) or item.get("duration", 0) or 0),
            niche=niche,
            region="vn",
            tags=tags,
            thumbnail_url=video_info.get("cover", "") or video_info.get("cover_image_url", ""),
            video_url=item.get("shareUrl", "") or item.get("video_url", ""),
            raw=item,
        )
    except Exception:
        return None


def _looks_like_tiktok_item(node: dict) -> bool:
    if not isinstance(node, dict):
        return False
    item_id = node.get("id")
    if item_id in (None, ""):
        return False
    return any(key in node for key in ("video", "stats", "statistics", "desc", "author", "authorInfo", "video_description"))


def _walk_payload(node: object, found: list[dict]) -> None:
    if isinstance(node, dict):
        if _looks_like_tiktok_item(node):
            found.append(node)

        for key, value in node.items():
            if key in {"itemModule", "ItemModule"} and isinstance(value, dict):
                for item in value.values():
                    if isinstance(item, dict):
                        found.append(item)
                continue
            if key in {"itemList", "items"} and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        found.append(item)
            _walk_payload(value, found)
        return

    if isinstance(node, list):
        for item in node:
            _walk_payload(item, found)


def extract_candidate_items(payload: object) -> list[dict]:
    found: list[dict] = []
    _walk_payload(payload, found)
    return dedupe_raw_items(found)


def _parse_script_body(body: str) -> object | None:
    cleaned = unescape(body).strip()
    if not cleaned:
        return None
    if cleaned.startswith("{") or cleaned.startswith("["):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None
    return None


def extract_items_from_html(html: str) -> list[dict]:
    items: list[dict] = []
    for match in re.finditer(r"<script[^>]*?(?:id=['\"](?P<id>[^'\"]+)['\"])?[^>]*>(?P<body>.*?)</script>", html, re.IGNORECASE | re.DOTALL):
        script_id = (match.group("id") or "").strip()
        if script_id and script_id not in {"SIGI_STATE", "__UNIVERSAL_DATA_FOR_REHYDRATION__", "__NEXT_DATA__"}:
            continue
        payload = _parse_script_body(match.group("body"))
        if payload is None:
            continue
        items.extend(extract_candidate_items(payload))
    return dedupe_raw_items(items)