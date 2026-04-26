from datetime import datetime
from pydantic import BaseModel


class ScriptListItem(BaseModel):
    id: int
    topic: str | None = None
    niche: str | None = None
    template: str | None = None
    language: str = "vietnamese"
    status: str = "draft"
    editor_notes: str | None = None
    approved_at: datetime | None = None
    performance_score: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScriptDetail(ScriptListItem):
    script_json: dict | None = None


class ScriptUpdate(BaseModel):
    script_json: dict
    editor_notes: str | None = None


class ScriptGenerateRequest(BaseModel):
    topic: str
    niche: str
    template: str
    language: str = "vietnamese"
    source_video_ids: list[str] | None = None
    source_article_id: int | None = None   # if set, script is rewritten from this article's content
    raw_content: str | None = None         # free-form text from Composer


class SceneRegenerateRequest(BaseModel):
    scene_index: int


class ExpandRequest(BaseModel):
    content: str


class ExpandResponse(BaseModel):
    expanded_outline: str
