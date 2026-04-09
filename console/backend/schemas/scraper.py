from datetime import datetime
from pydantic import BaseModel


class ScraperSourceResponse(BaseModel):
    id: str
    name: str
    type: str
    module: str | None
    function: str | None
    status: str  # active | standby | planned


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


class IndexVideosRequest(BaseModel):
    video_ids: list[str]


class GenerateScriptRequest(BaseModel):
    topic: str
    niche: str
    template: str
    source_video_ids: list[str] | None = None
