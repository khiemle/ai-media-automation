"""TikTok browser scraper with Playwright first and Selenium fallback."""
import asyncio
import logging
import random
import time

from scraper.base_scraper import BaseScraper, ScrapedVideo
from scraper.tiktok_browser_common import (
    GLOBAL_STATE_EXPRESSIONS,
    TRENDING_URLS,
    USER_AGENTS,
    dedupe_scraped_videos,
    derive_niche_from_url,
    extract_candidate_items,
    extract_items_from_html,
    load_browser_scraper_settings,
    looks_like_block_page,
    parse_tiktok_item,
)

logger = logging.getLogger(__name__)


async def _scrape_page(url: str, settings, headless: bool) -> list[dict]:
    """Open a TikTok page and extract item payloads from XHR, globals, and page state."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
        return []

    results: list[dict] = []
    async with async_playwright() as p:
        launch_kwargs = {
            "headless": headless,
            "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        }
        if settings.browser_channel:
            launch_kwargs["channel"] = settings.browser_channel
        if settings.chrome_binary_path:
            launch_kwargs["executable_path"] = settings.chrome_binary_path

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 900},
            locale="vi-VN",
        )
        page = await context.new_page()

        video_data_from_xhr: list[dict] = []

        async def handle_response(response):
            response_url = response.url.lower()
            if "tiktok.com" not in response_url or "/api/" not in response_url:
                return
            if not any(token in response_url for token in ("item", "recommend", "explore", "search", "feed", "related")):
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type and "javascript" not in content_type:
                return
            try:
                body = await response.json()
            except Exception:
                return
            try:
                video_data_from_xhr.extend(extract_candidate_items(body))
            except Exception:
                return

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
            await page.wait_for_timeout(random.randint(1800, 3200))
            for _ in range(max(1, settings.scroll_count)):
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                except Exception:
                    pass
                await page.wait_for_timeout(max(1000, settings.scroll_delay_ms))

            for expression in GLOBAL_STATE_EXPRESSIONS:
                try:
                    payload = await page.evaluate(f"() => {expression}")
                except Exception:
                    payload = None
                if payload:
                    results.extend(extract_candidate_items(payload))

            html = await page.content()
            results.extend(extract_items_from_html(html))
            if not results and looks_like_block_page(html):
                logger.warning("[Playwright] %s looks blocked by TikTok", url)
        except Exception as e:
            logger.warning(f"Playwright page load error {url}: {e}")
        finally:
            await context.close()
            await browser.close()

    results.extend(video_data_from_xhr)
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in results:
        item_id = str(item.get("id", "")).strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(item)
    return deduped


class TikTokPlaywright(BaseScraper):
    def __init__(self, urls: list[str] | None = None, settings=None, source_label: str = "tiktok_playwright"):
        self.urls = urls or TRENDING_URLS
        self.settings = settings or load_browser_scraper_settings()
        self.source_label = source_label

    def _fetch_playwright_once(self, headless: bool) -> list[ScrapedVideo]:
        results: list[ScrapedVideo] = []
        for url in self.urls:
            niche = derive_niche_from_url(url)

            try:
                items = asyncio.run(_scrape_page(url, self.settings, headless=headless))
                for item in items:
                    scraped = parse_tiktok_item(item, self.source_label, default_niche=niche)
                    if scraped and scraped.video_id:
                        results.append(scraped)
                logger.info("[Playwright/%s] %s → %s items", "headless" if headless else "headful", url, len(items))
            except Exception as e:
                logger.error(f"[Playwright] error scraping {url}: {e}")

            time.sleep(2)

        return dedupe_scraped_videos(results)

    def fetch(self) -> list[ScrapedVideo]:
        if self.settings.engine_preference == "selenium":
            from scraper.tiktok_selenium import TikTokSelenium

            return TikTokSelenium(urls=self.urls, settings=self.settings).fetch()

        results = self._fetch_playwright_once(headless=self.settings.headless)
        if results:
            return results

        if self.settings.headless and self.settings.headful_retry_on_empty:
            logger.info("[Playwright] retrying in headful mode after empty headless scrape")
            results = self._fetch_playwright_once(headless=False)
            if results:
                return results

        if self.settings.selenium_fallback and self.settings.engine_preference == "auto":
            logger.info("[Playwright] falling back to Selenium after empty Playwright scrape")
            from scraper.tiktok_selenium import TikTokSelenium

            return TikTokSelenium(urls=self.urls, settings=self.settings).fetch()

        return []


_instance: TikTokPlaywright | None = None


def scrape() -> list[int]:
    global _instance
    if _instance is None:
        _instance = TikTokPlaywright()
    return _instance.scrape()
