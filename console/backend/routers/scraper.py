from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.schemas.scraper import (
    ScraperSourceResponse,
    ScraperSourceStatusUpdate,
    ScrapedVideoResponse,
    TriggerScrapeRequest,
    IndexVideosRequest,
)
from console.backend.schemas.common import PaginatedResponse
from console.backend.services.scraper_service import ScraperService

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.get("/sources", response_model=list[ScraperSourceResponse])
def list_sources(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ScraperService(db).list_sources()


@router.patch("/sources/{source_id}/status", response_model=ScraperSourceResponse)
def update_source_status(
    source_id: str,
    body: ScraperSourceStatusUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ScraperService(db).update_source_status(source_id, body.status)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run")
def trigger_scrape(
    body: TriggerScrapeRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        task_id = ScraperService(db).trigger_scrape(body.source_id)
        return {"task_id": task_id, "status": "queued"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/videos", response_model=PaginatedResponse[ScrapedVideoResponse])
def list_videos(
    source: str | None = None,
    niche: str | None = None,
    region: str | None = None,
    sort_by: str = "play_count",
    sort_dir: str = "desc",
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ScraperService(db).list_videos(
        source=source,
        niche=niche,
        region=region,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        per_page=per_page,
    )


@router.post("/videos/index")
def index_videos(
    body: IndexVideosRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        count = ScraperService(db).index_to_chromadb(body.video_ids)
        return {"indexed": count}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
