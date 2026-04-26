"""
VnExpress news scraper.
Scrapes article listings from vnexpress.net homepage and full article content.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scraper.base_scraper import NewsBaseScraper, ScrapedArticle

logger = logging.getLogger(__name__)

HOMEPAGE = "https://vnexpress.net"
SOURCE_ID = "vnexpress"
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
    """VnExpress article URLs contain a numeric ID at the end, e.g. /article-slug-1234567.html"""
    parsed = urlparse(url)
    path = parsed.path
    return (
        parsed.netloc in ("", "vnexpress.net", "www.vnexpress.net")
        and path.endswith(".html")
        and any(c.isdigit() for c in path)
        and path.count("/") >= 1
    )


class VnExpressScraper(NewsBaseScraper):
    source_id = SOURCE_ID
    language = LANGUAGE

    def fetch_homepage(self) -> list[ScrapedArticle]:
        """Scrape all articles visible on the VnExpress homepage."""
        try:
            resp = requests.get(HOMEPAGE, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[VnExpress] Homepage fetch failed: {e}")
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

        logger.info(f"[VnExpress] Found {len(article_urls)} article URLs on homepage")

        articles = []
        for url in article_urls[:50]:  # cap at 50 to avoid overloading
            article = self.fetch_article(url)
            if article:
                articles.append(article)

        logger.info(f"[VnExpress] Scraped {len(articles)} articles")
        return articles

    def fetch_article(self, url: str) -> Optional[ScrapedArticle]:
        """Scrape a single VnExpress article by URL."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[VnExpress] Article fetch failed ({url}): {e}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # Title
        title_tag = soup.find("h1", class_="title-detail") or soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title:
            return None

        # Main content — VnExpress uses article.fck or .sidebar-1
        content_tag = soup.find("article", class_="fck_detail") or soup.find("div", class_="fck_detail")
        if not content_tag:
            content_tag = soup.find("article")
        paragraphs = content_tag.find_all("p") if content_tag else []
        main_content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Author
        author_tag = soup.find("p", class_="author_mail") or soup.find("span", class_="author")
        if not author_tag:
            author_tag = soup.find("strong", class_="author")
        author = author_tag.get_text(strip=True) if author_tag else ""

        # Published date
        published_at = None
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

        # Tags (keywords from meta)
        tags: list[str] = []
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


# Module-level functions for Celery dynamic dispatch (YAML: function: scrape_homepage)
def scrape_homepage() -> list[int]:
    return VnExpressScraper().scrape_homepage()


def scrape_article(url: str) -> Optional[ScrapedArticle]:
    return VnExpressScraper().fetch_article(url)
