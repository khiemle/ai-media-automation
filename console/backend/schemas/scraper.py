from datetime import datetime
from pydantic import BaseModel


class ScraperSourceResponse(BaseModel):
    id: str
    name: str
    type: str
    module: str | None
    function: str | None
    status: str  # active | standby | planned
    language: str | None = None

    model_config = {"extra": "ignore"}


class ScraperSourceStatusUpdate(BaseModel):
    status: str


class ScrapedVideoResponse(BaseModel):
    id: str
    platform: str | None = None
    region: str | None = None
    niche: str | None = None
    play_count: int | None = None
    engagement_rate: float | None = None
    hook_text: str | None = None
    script_text: str | None = None
    is_indexed: bool = False
    scraped_at: datetime | None = None

    model_config = {"from_attributes": True}


class TriggerScrapeRequest(BaseModel):
    source_id: str | None = None


class ScrapedArticleResponse(BaseModel):
    id: int
    source: str
    url: str
    title: str
    language: str
    author: str | None = None
    published_at: datetime | None = None
    niche: str | None = None
    tags: list[str] = []
    is_indexed: bool = False
    scraped_at: datetime | None = None
    main_content: str | None = None

    model_config = {"from_attributes": True}


class ScrapeUrlRequest(BaseModel):
    url: str


class ScraperTaskStatus(BaseModel):
    task_id: str
    state: str          # PENDING | PROGRESS | SUCCESS | FAILURE
    step: str | None = None
    source_id: str | None = None
    count: int | None = None
    error: str | None = None
    logs: list[dict] = []


class GenerateScriptRequest(BaseModel):
    topic: str
    niche: str
    template: str
    source_video_ids: list[str] | None = None
