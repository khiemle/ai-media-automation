"""
CNN (edition.cnn.com) news scraper.
Scrapes article listings from CNN homepage and full article content.
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

HOMEPAGE = "https://edition.cnn.com"
SOURCE_ID = "cnn"
LANGUAGE = "english"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_TIMEOUT = 10


def _make_article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _is_article_url(url: str) -> bool:
    """
    CNN text article URLs follow two patterns:
      1. Date-prefixed:  /YYYY/MM/DD/<category>/<slug>   (no /video/ segment)
      2. Static slug:    /some/path/index.html
    Section hubs, videos, podcasts, games, and schedules are excluded.
    """
    import re
    parsed = urlparse(url)
    path = parsed.path

    if parsed.netloc not in ("", "edition.cnn.com", "www.cnn.com", "cnn.com"):
        return False

    # Hard exclusions
    excluded_prefixes = (
        "/videos/", "/video/", "/profiles/", "/search", "/audio/",
        "/games/", "/schedule", "/gallery/", "/interactive/",
    )
    if any(path.startswith(p) for p in excluded_prefixes):
        return False
    if "/video/" in path:
        return False

    # Pattern 1: date-prefixed article  e.g. /2026/04/09/politics/article-slug
    if re.match(r"^/20\d{2}/\d{2}/\d{2}/", path):
        return True

    # Pattern 2: ends with index.html  e.g. /politics/some-slug/index.html
    if path.endswith("/index.html") and path.count("/") >= 3:
        return True

    return False


class CNNScraper(NewsBaseScraper):
    source_id = SOURCE_ID
    language = LANGUAGE

    def fetch_homepage(self) -> list[ScrapedArticle]:
        """Scrape all articles visible on the CNN homepage."""
        try:
            resp = requests.get(HOMEPAGE, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[CNN] Homepage fetch failed: {e}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        article_urls: list[str] = []
        seen = set()

        # CNN uses data-link-type="article" on anchor tags, but also plain hrefs
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(HOMEPAGE, href).split("?")[0].split("#")[0]
            # Normalise www.cnn.com → edition.cnn.com
            full_url = full_url.replace("//www.cnn.com/", "//edition.cnn.com/")
            if full_url not in seen and _is_article_url(full_url):
                seen.add(full_url)
                article_urls.append(full_url)

        logger.info(f"[CNN] Found {len(article_urls)} article URLs on homepage")

        articles = []
        for url in article_urls[:50]:
            article = self.fetch_article(url)
            if article:
                articles.append(article)

        logger.info(f"[CNN] Scraped {len(articles)} articles")
        return articles

    def fetch_article(self, url: str) -> Optional[ScrapedArticle]:
        """Scrape a single CNN article by URL."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[CNN] Article fetch failed ({url}): {e}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # Title
        title_tag = (
            soup.find("h1", class_="headline__text")
            or soup.find("h1", class_="article__title")
            or soup.find("h1")
        )
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title:
            # Try og:title
            og_title = soup.find("meta", property="og:title")
            title = og_title["content"] if og_title and og_title.get("content") else ""
        if not title:
            return None

        # Main content
        content_tag = (
            soup.find("div", class_="article__content")
            or soup.find("div", class_="l-container")
            or soup.find("section", class_="zn-body__paragraph")
            or soup.find("div", {"data-module-name": "ArticleBody"})
        )
        if content_tag:
            paragraphs = content_tag.find_all("p")
            main_content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        else:
            # Fallback: collect all paragraph text
            paragraphs = soup.find_all("p", class_=lambda c: c and "paragraph" in c)
            main_content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Author
        author = ""
        author_tag = (
            soup.find("span", class_="byline__name")
            or soup.find("div", class_="byline__names")
        )
        if author_tag:
            author = author_tag.get_text(strip=True).lstrip("By").strip()

        # Published date
        published_at = None
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date and meta_date.get("content"):
            try:
                published_at = datetime.fromisoformat(meta_date["content"].replace("Z", "+00:00"))
            except Exception:
                pass
        if not published_at:
            time_tag = soup.find("div", class_="timestamp")
            if time_tag:
                # CNN renders "Updated 3:45 PM EDT, Tue April 8, 2026" — best effort
                pass

        # Thumbnail
        thumbnail_url = ""
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            thumbnail_url = og_image["content"]

        # Tags
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


# Module-level functions for Celery dynamic dispatch
def scrape_homepage() -> list[int]:
    return CNNScraper().scrape_homepage()


def scrape_article(url: str) -> Optional[ScrapedArticle]:
    return CNNScraper().fetch_article(url)
