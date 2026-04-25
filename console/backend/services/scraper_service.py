import hashlib
import importlib
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml
from sqlalchemy import and_
from sqlalchemy.orm import Session

from console.backend.schemas.common import PaginatedResponse
from console.backend.schemas.scraper import (
    ScraperSourceResponse,
    ScrapedVideoResponse,
    ScrapedArticleResponse,
)

# Path to scraper_sources.yaml relative to the project root
SOURCES_YAML = Path(__file__).parent.parent.parent.parent / "config" / "scraper_sources.yaml"


def _load_sources() -> list[dict]:
    with open(SOURCES_YAML, "r") as f:
        data = yaml.safe_load(f)
    return data.get("sources", [])


def _save_sources(sources: list[dict]):
    with open(SOURCES_YAML, "w") as f:
        yaml.dump({"sources": sources}, f, default_flow_style=False, allow_unicode=True)


class ScraperService:
    def __init__(self, db: Session):
        self.db = db

    # ── Sources ───────────────────────────────────────────────────────────────

    def list_sources(self) -> list[ScraperSourceResponse]:
        return [ScraperSourceResponse(**s) for s in _load_sources()]

    def update_source_status(self, source_id: str, status: str) -> ScraperSourceResponse:
        valid = ("active", "standby", "planned")
        if status not in valid:
            raise ValueError(f"Status must be one of {valid}")
        sources = _load_sources()
        for s in sources:
            if s["id"] == source_id:
                s["status"] = status
                _save_sources(sources)
                return ScraperSourceResponse(**s)
        raise KeyError(f"Source '{source_id}' not found")

    def get_task_status(self, task_id: str) -> dict:
        """Return the current state + accumulated logs of a Celery scrape task."""
        from celery.result import AsyncResult
        from console.backend.celery_app import celery_app

        result = AsyncResult(task_id, app=celery_app)
        state = result.state

        out: dict = {
            "task_id": task_id,
            "state": state,
            "step": None,
            "source_id": None,
            "count": None,
            "error": None,
            "logs": [],
        }

        if state == "PROGRESS":
            meta = result.info or {}
            out["step"] = meta.get("step")
            out["source_id"] = meta.get("source")
            out["logs"] = meta.get("logs", [])
            out["count"] = meta.get("count")
        elif state == "SUCCESS":
            info = result.result or {}
            out["step"] = "done"
            out["source_id"] = info.get("source_id")
            out["count"] = info.get("count")
            out["logs"] = info.get("logs", [])
        elif state == "FAILURE":
            out["step"] = "error"
            out["error"] = str(result.result)

        return out

    def trigger_scrape(self, source_id: str | None = None) -> str:
        """Dispatch a Celery scrape task and return its task ID."""
        if not source_id:
            active_source = next((s for s in _load_sources() if s.get("status") == "active" and s.get("module") and s.get("function")), None)
            if not active_source:
                raise ValueError("No active scraper source is configured")
            source_id = active_source["id"]

        from console.backend.tasks.scraper_tasks import run_scrape_task
        task = run_scrape_task.delay(source_id)
        return task.id

    # ── Videos ────────────────────────────────────────────────────────────────

    def list_videos(
        self,
        source: str | None = None,
        niche: str | None = None,
        region: str | None = None,
        sort_by: str = "play_count",
        sort_dir: str = "desc",
        page: int = 1,
        per_page: int = 50,
    ) -> PaginatedResponse[ScrapedVideoResponse]:
        try:
            from database.models import ViralVideo
        except ImportError:
            # Core pipeline not present — return empty results
            return PaginatedResponse(items=[], total=0, page=page, pages=0, per_page=per_page)

        filters = []
        if niche:
            filters.append(ViralVideo.niche == niche)
        if region:
            filters.append(ViralVideo.region == region)
        if source:
            filters.append(ViralVideo.source == source)

        query = self.db.query(ViralVideo)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()

        sort_col = {
            "play_count":      ViralVideo.play_count,
            "engagement_rate": ViralVideo.engagement_rate,
            "likes":           ViralVideo.play_count,
        }.get(sort_by, ViralVideo.play_count)

        if sort_dir == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        offset = (page - 1) * per_page
        rows = query.offset(offset).limit(per_page).all()

        items = [
            ScrapedVideoResponse.model_validate({
                "id": str(r.id),
                "platform": r.source,
                "region": r.region,
                "niche": r.niche,
                "play_count": r.play_count,
                "engagement_rate": r.engagement_rate,
                "hook_text": r.hook_text,
                "script_text": None,
                "is_indexed": bool(r.indexed_at),
                "scraped_at": r.scraped_at,
            })
            for r in rows
        ]

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            pages=math.ceil(total / per_page) if per_page else 1,
            per_page=per_page,
        )

    # ── Articles ──────────────────────────────────────────────────────────────

    def list_articles(
        self,
        source: str | None = None,
        language: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> PaginatedResponse[ScrapedArticleResponse]:
        try:
            from database.models import NewsArticle
        except ImportError:
            return PaginatedResponse(items=[], total=0, page=page, pages=0, per_page=per_page)

        filters = []
        if source:
            filters.append(NewsArticle.source == source)
        if language:
            filters.append(NewsArticle.language == language)

        query = self.db.query(NewsArticle)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()
        rows = query.order_by(NewsArticle.scraped_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

        items = [
            ScrapedArticleResponse.model_validate({
                "id": r.id,
                "source": r.source,
                "url": r.url,
                "title": r.title,
                "language": r.language,
                "author": r.author,
                "published_at": r.published_at,
                "niche": r.niche,
                "tags": r.tags or [],
                "is_indexed": bool(r.indexed_at),
                "scraped_at": r.scraped_at,
                "main_content": r.main_content,
            })
            for r in rows
        ]

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            pages=math.ceil(total / per_page) if per_page else 1,
            per_page=per_page,
        )

    def scrape_article_from_url(self, url: str) -> ScrapedArticleResponse:
        """Detect source from domain, scrape synchronously, upsert to DB."""
        from database.models import NewsArticle

        domain = urlparse(url).netloc.replace("www.", "")
        scraper_map = {
            "vnexpress.net":   ("scraper.vnexpress_scraper", "scrape_article"),
            "tinhte.vn":       ("scraper.tinhte_scraper",    "scrape_article"),
            "edition.cnn.com": ("scraper.cnn_scraper",       "scrape_article"),
            "cnn.com":         ("scraper.cnn_scraper",        "scrape_article"),
        }
        entry = scraper_map.get(domain)
        if not entry:
            raise ValueError(f"Unsupported news source domain: {domain}")

        mod = importlib.import_module(entry[0])
        fn = getattr(mod, entry[1])
        article = fn(url)
        if not article:
            raise RuntimeError(f"Failed to scrape article from {url}")

        # Upsert by URL
        existing = self.db.query(NewsArticle).filter(NewsArticle.url == url).first()
        if existing:
            existing.title = article.title
            existing.main_content = article.main_content
            self.db.commit()
            self.db.refresh(existing)
            return ScrapedArticleResponse.model_validate({
                "id": existing.id, "source": existing.source, "url": existing.url,
                "title": existing.title, "language": existing.language,
                "author": existing.author, "published_at": existing.published_at,
                "niche": existing.niche, "tags": existing.tags or [],
                "is_indexed": bool(existing.indexed_at), "scraped_at": existing.scraped_at,
                "main_content": existing.main_content,
            })

        row = NewsArticle(
            article_id=hashlib.sha256(url.encode()).hexdigest()[:16],
            source=article.source,
            url=url,
            title=article.title,
            main_content=article.main_content,
            language=article.language,
            author=article.author,
            published_at=article.published_at,
            niche=article.niche,
            tags=article.tags,
            thumbnail_url=article.thumbnail_url,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return ScrapedArticleResponse.model_validate({
            "id": row.id, "source": row.source, "url": row.url,
            "title": row.title, "language": row.language,
            "author": row.author, "published_at": row.published_at,
            "niche": row.niche, "tags": row.tags or [],
            "is_indexed": False, "scraped_at": row.scraped_at,
            "main_content": row.main_content,
        })


