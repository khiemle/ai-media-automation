import math
from pathlib import Path

import yaml
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from console.backend.schemas.common import PaginatedResponse
from console.backend.schemas.scraper import ScraperSourceResponse, ScrapedVideoResponse

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

    def trigger_scrape(self, source_id: str) -> str:
        """Dispatch a Celery scrape task and return its task ID."""
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
        # Import the existing core model dynamically (it lives in database/)
        try:
            from database.models import ViralVideo
        except ImportError:
            # Fallback: try lowercase module name
            from database.models import ViralVideo

        filters = []
        if niche:
            filters.append(ViralVideo.niche == niche)
        if region:
            filters.append(ViralVideo.region == region)
        if source:
            filters.append(ViralVideo.platform == source)

        query = self.db.query(ViralVideo)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()

        sort_col = {
            "play_count": ViralVideo.play_count,
            "engagement_rate": ViralVideo.engagement_rate,
            "likes": ViralVideo.play_count,  # fallback if no likes col
        }.get(sort_by, ViralVideo.play_count)

        if sort_dir == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        offset = (page - 1) * per_page
        rows = query.offset(offset).limit(per_page).all()

        return PaginatedResponse(
            items=[ScrapedVideoResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            pages=math.ceil(total / per_page) if per_page else 1,
            per_page=per_page,
        )

    # ── ChromaDB indexing ─────────────────────────────────────────────────────

    def index_to_chromadb(self, video_ids: list[str]) -> int:
        try:
            from database.models import ViralVideo
            from vector_db.indexer import index_videos

            index_videos(video_ids)
            self.db.query(ViralVideo).filter(
                ViralVideo.id.in_(video_ids)
            ).update({"is_indexed": True}, synchronize_session=False)
            self.db.commit()
            return len(video_ids)
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"ChromaDB indexing failed: {e}") from e
