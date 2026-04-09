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


class TikTokSelenium(BaseScraper):
    def __init__(self, urls: list[str] | None = None, settings=None, source_label: str = "tiktok_selenium"):
        self.urls = urls or TRENDING_URLS
        self.settings = settings or load_browser_scraper_settings()
        self.source_label = source_label

    def _build_driver(self, headless: bool):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            logger.error("selenium not installed. Run: pip install -r requirements.pipeline.txt")
            return None

        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
        options.add_argument("--window-size=1280,900")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if self.settings.chrome_binary_path:
            options.binary_location = self.settings.chrome_binary_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(max(10, self.settings.timeout_ms // 1000))
        return driver

    def _scrape_page(self, url: str, headless: bool) -> list[dict]:
        driver = self._build_driver(headless)
        if driver is None:
            return []

        items: list[dict] = []
        try:
            driver.get(url)
            time.sleep(max(1.0, self.settings.scroll_delay_ms / 1000))

            for _ in range(max(1, self.settings.scroll_count)):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(max(1.0, self.settings.scroll_delay_ms / 1000))

            for expression in GLOBAL_STATE_EXPRESSIONS:
                try:
                    payload = driver.execute_script(f"return {expression};")
                except Exception:
                    payload = None
                if payload:
                    items.extend(extract_candidate_items(payload))

            page_source = driver.page_source or ""
            items.extend(extract_items_from_html(page_source))

            if not items and looks_like_block_page(page_source):
                logger.warning("[Selenium] %s looks blocked by TikTok", url)
        except Exception as exc:
            logger.warning("[Selenium] page load error %s: %s", url, exc)
        finally:
            driver.quit()

        return items

    def _fetch_once(self, headless: bool) -> list[ScrapedVideo]:
        results: list[ScrapedVideo] = []
        for url in self.urls:
            niche = derive_niche_from_url(url)
            items = self._scrape_page(url, headless=headless)
            for item in items:
                scraped = parse_tiktok_item(item, self.source_label, default_niche=niche)
                if scraped and scraped.video_id:
                    results.append(scraped)
            logger.info("[Selenium/%s] %s → %s items", "headless" if headless else "headful", url, len(items))
            time.sleep(2)
        return dedupe_scraped_videos(results)

    def fetch(self) -> list[ScrapedVideo]:
        results = self._fetch_once(headless=self.settings.headless)
        if results or not self.settings.headless or not self.settings.headful_retry_on_empty:
            return results
        logger.info("[Selenium] retrying in headful mode after empty headless scrape")
        return self._fetch_once(headless=False)


_instance: TikTokSelenium | None = None


def scrape() -> list[int]:
    global _instance
    if _instance is None:
        _instance = TikTokSelenium()
    return _instance.scrape()