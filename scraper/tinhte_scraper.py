"""
Tinhte.vn news scraper.
Scrapes article listings from tinhte.vn homepage and full article content.
"""
import hashlib
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scraper.base_scraper import NewsBaseScraper, ScrapedArticle

logger = logging.getLogger(__name__)

HOMEPAGE = "https://tinhte.vn"
SOURCE_ID = "tinhte"
LANGUAGE = "vietnamese"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9",
}
REQUEST_TIMEOUT = 10


def _make_article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _is_article_url(url: str) -> bool:
    """Tinhte article URLs look like /post/article-slug-1234567 or /threads/..."""
    parsed = urlparse(url)
    path = parsed.path
    return (
        parsed.netloc in ("", "tinhte.vn", "www.tinhte.vn")
        and len(path) > 5
        and not path.startswith("/tag/")
        and not path.startswith("/category/")
        and not path.startswith("/user/")
        and not path == "/"
        and any(c.isdigit() for c in path)
    )


class TinhteScraper(NewsBaseScraper):
    source_id = SOURCE_ID
    language = LANGUAGE

    def fetch_homepage(self) -> list[ScrapedArticle]:
        """Scrape all articles visible on the Tinhte homepage."""
        try:
            resp = requests.get(HOMEPAGE, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[Tinhte] Homepage fetch failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        article_urls: list[str] = []
        seen = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(HOMEPAGE, href).split("?")[0].split("#")[0]
            if full_url not in seen and _is_article_url(full_url):
                seen.add(full_url)
                article_urls.append(full_url)

        logger.info(f"[Tinhte] Found {len(article_urls)} article URLs on homepage")

        articles = []
        for url in article_urls[:50]:
            article = self.fetch_article(url)
            if article:
                articles.append(article)

        logger.info(f"[Tinhte] Scraped {len(articles)} articles")
        return articles

    def fetch_article(self, url: str) -> Optional[ScrapedArticle]:
        """Scrape a single Tinhte article by URL."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[Tinhte] Article fetch failed ({url}): {e}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # Title
        title_tag = soup.find("h1") or soup.find("h2", class_="title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title:
            return None

        # Main content
        content_tag = (
            soup.find("div", class_="article-body")
            or soup.find("div", class_="messageText")
            or soup.find("div", class_="bbWrapper")
            or soup.find("article")
        )
        paragraphs = content_tag.find_all("p") if content_tag else []
        main_content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        # Fallback: use all block text if paragraphs found nothing
        if not main_content and content_tag:
            main_content = content_tag.get_text(separator="\n", strip=True)

        # Author
        author_tag = soup.find("span", class_="username") or soup.find("a", class_="username")
        author = author_tag.get_text(strip=True) if author_tag else ""

        # Published date
        published_at = None
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            try:
                published_at = datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
            except Exception:
                pass
        if not published_at:
            meta_date = soup.find("meta", property="article:published_time")
            if meta_date and meta_date.get("content"):
                try:
                    published_at = datetime.fromisoformat(meta_date["content"].replace("Z", "+00:00"))
                except Exception:
                    pass

        # Thumbnail
        thumbnail_url = ""
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            thumbnail_url = og_image["content"]

        # Tags
        tags: list[str] = []
        for tag_link in soup.find_all("a", class_="tag"):
            t = tag_link.get_text(strip=True)
            if t:
                tags.append(t)
        if not tags:
            meta_keywords = soup.find("meta", attrs={"name": "keywords"})
            if meta_keywords and meta_keywords.get("content"):
                tags = [t.strip() for t in meta_keywords["content"].split(",") if t.strip()]

        return ScrapedArticle(
            article_id=_make_article_id(url),
            source=SOURCE_ID,
            url=url,
            title=title,
            main_content=main_content,
            language=LANGUAGE,
            author=author,
            published_at=published_at,
            tags=tags,
            thumbnail_url=thumbnail_url,
        )


# Module-level functions for Celery dynamic dispatch
def scrape_homepage() -> list[int]:
    return TinhteScraper().scrape_homepage()


def scrape_article(url: str) -> Optional[ScrapedArticle]:
    return TinhteScraper().fetch_article(url)
