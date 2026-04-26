from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.schemas.scraper import (
    ScraperSourceResponse,
    ScraperSourceStatusUpdate,
    ScrapedArticleResponse,
    ScrapeUrlRequest,
    TriggerScrapeRequest,
    ScraperTaskStatus,
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


@router.get("/tasks/{task_id}", response_model=ScraperTaskStatus)
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ScraperService(db).get_task_status(task_id)


@router.get("/articles", response_model=PaginatedResponse[ScrapedArticleResponse])
def list_articles(
    source: str | None = None,
    language: str | None = None,
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ScraperService(db).list_articles(source=source, language=language, page=page, per_page=per_page)


@router.post("/articles/from-url", response_model=ScrapedArticleResponse, status_code=201)
def scrape_article_from_url(
    body: ScrapeUrlRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ScraperService(db).scrape_article_from_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
