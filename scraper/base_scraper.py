"""
Abstract base class for all scraper adapters.
Each adapter must implement `scrape() → list[ScrapedVideo]`.
News adapters must implement `fetch_homepage()` and `fetch_article()`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ScrapedVideo:
    """Normalized video data returned by any scraper adapter."""
    video_id:      str
    source:        str                      # tiktok_research | tiktok_playwright | apify
    author:        str = ""
    hook_text:     str = ""                 # first caption line / first 3s text
    play_count:    int = 0
    like_count:    int = 0
    share_count:   int = 0
    comment_count: int = 0
    duration_s:    float = 0.0
    niche:         str = ""
    region:        str = "vn"
    tags:          list[str] = field(default_factory=list)
    thumbnail_url: str = ""
    video_url:     str = ""
    raw:           dict = field(default_factory=dict)   # original platform response

    @property
    def engagement_rate(self) -> float:
        if not self.play_count:
            return 0.0
        interactions = self.like_count + self.comment_count + self.share_count
        return round(interactions / self.play_count * 100, 2)


@dataclass
class ScrapedArticle:
    """Normalized news article data returned by any news scraper adapter."""
    article_id:    str            # sha256(url)[:16]
    source:        str            # vnexpress | tinhte | cnn
    url:           str
    title:         str
    main_content:  str
    language:      str            # vietnamese | english
    author:        str = ""
    published_at:  Optional[datetime] = None
    niche:         str = ""
    tags:          list[str] = field(default_factory=list)
    thumbnail_url: str = ""
    raw:           dict = field(default_factory=dict)


def _article_to_row(article: "ScrapedArticle"):
    """Convert a ScrapedArticle dataclass to a NewsArticle ORM row."""
    from database.models import NewsArticle
    return NewsArticle(
        article_id=article.article_id,
        source=article.source,
        url=article.url,
        title=article.title,
        main_content=article.main_content,
        language=article.language,
        author=article.author,
        published_at=article.published_at,
        niche=article.niche,
        tags=article.tags,
        thumbnail_url=article.thumbnail_url,
    )


class NewsBaseScraper(ABC):
    """
    Adapter interface for news scrapers.
    Implement `fetch_homepage()` to return articles from the front page.
    Implement `fetch_article()` to return a single article by URL.
    """
    source_id: str
    language: str

    @abstractmethod
    def fetch_homepage(self) -> list[ScrapedArticle]:
        """Fetch all articles visible on the homepage."""
        ...

    @abstractmethod
    def fetch_article(self, url: str) -> Optional[ScrapedArticle]:
        """Fetch a single article by its URL."""
        ...

    def scrape_homepage(self) -> list[int]:
        """
        Public entry point called by Celery task via YAML config.
        1. Fetch articles from homepage
        2. Deduplicate against DB by URL
        3. Bulk insert new records
        4. Return list of inserted IDs
        """
        from database.connection import get_session
        from database.models import NewsArticle
        from sqlalchemy import select

        articles = self.fetch_homepage()
        if not articles:
            return []

        db = get_session()
        try:
            existing_urls = set(
                row[0] for row in db.execute(
                    select(NewsArticle.url).where(
                        NewsArticle.url.in_([a.url for a in articles])
                    )
                ).fetchall()
            )
            new_articles = [a for a in articles if a.url not in existing_urls]
            if not new_articles:
                return []

            rows = [_article_to_row(a) for a in new_articles]
            db.add_all(rows)
            db.commit()
            for r in rows:
                db.refresh(r)
            return [r.id for r in rows]
        finally:
            db.close()


class BaseScraper(ABC):
    """
    Adapter interface for scrapers.
    Implement `fetch()` to return raw platform videos.
    The base class handles dedup + DB insertion.
    """

    @abstractmethod
    def fetch(self) -> list[ScrapedVideo]:
        """Fetch videos from the platform. Must be implemented by each adapter."""
        ...

    def scrape(self) -> list[int]:
        """
        Public entry point called by Celery task via YAML config.
        1. Fetch videos from platform
        2. Deduplicate against DB
        3. Bulk insert new records
        4. Return list of inserted IDs
        """
        from database.connection import get_session
        from database.models import ViralVideo
        from sqlalchemy import select

        videos = self.fetch()
        if not videos:
            return []

        db = get_session()
        try:
            # Find which video_ids already exist
            existing_ids = set(
                row[0] for row in db.execute(
                    select(ViralVideo.video_id).where(
                        ViralVideo.video_id.in_([v.video_id for v in videos])
                    )
                ).fetchall()
            )

            new_videos = [v for v in videos if v.video_id not in existing_ids]
            if not new_videos:
                return []

            rows = [
                ViralVideo(
                    video_id=v.video_id,
                    source=v.source,
                    author=v.author,
                    hook_text=v.hook_text,
                    play_count=v.play_count,
                    like_count=v.like_count,
                    share_count=v.share_count,
                    comment_count=v.comment_count,
                    duration_s=v.duration_s,
                    niche=v.niche,
                    region=v.region,
                    tags=v.tags,
                    thumbnail_url=v.thumbnail_url,
                    video_url=v.video_url,
                )
                for v in new_videos
            ]
            db.add_all(rows)
            db.commit()
            for r in rows:
                db.refresh(r)
            return [r.id for r in rows]
        finally:
            db.close()
