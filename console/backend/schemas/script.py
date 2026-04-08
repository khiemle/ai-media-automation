from datetime import datetime
from pydantic import BaseModel


class ScriptListItem(BaseModel):
    id: int
    topic: str | None = None
    niche: str | None = None
    template: str | None = None
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
    source_video_ids: list[str] | None = None


class SceneRegenerateRequest(BaseModel):
    scene_index: int
