"""Channels router — CRUD for channels and template defaults."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_admin, require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.channel_service import ChannelService

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelBody(BaseModel):
    name: str
    platform: str
    credential_id: int | None = None
    account_email: str | None = None
    category: str | None = None
    default_language: str = "vi"
    monetized: bool = False
    status: str = "active"
    subscriber_count: int = 0
    video_count: int = 0


class ChannelUpdateBody(BaseModel):
    name: str | None = None
    platform: str | None = None
    credential_id: int | None = None
    account_email: str | None = None
    category: str | None = None
    default_language: str | None = None
    monetized: bool | None = None
    status: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None


class DefaultsBody(BaseModel):
    channel_ids: list[int]


@router.get("")
def list_channels(
    platform: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ChannelService(db).list_channels(platform=platform, status=status)


@router.post("")
def create_channel(
    body: ChannelBody,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    if body.platform not in ("youtube", "tiktok", "instagram"):
        raise HTTPException(status_code=400, detail="Platform must be youtube, tiktok, or instagram")
    return ChannelService(db).create_channel(body.model_dump())


@router.get("/defaults")
def list_all_defaults(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return ChannelService(db).list_all_defaults()


@router.get("/defaults/{template}")
def get_defaults(
    template: str,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return {"template": template, "channel_ids": ChannelService(db).get_defaults(template)}


@router.put("/defaults/{template}")
def set_defaults(
    template: str,
    body: DefaultsBody,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    return {"template": template, "channel_ids": ChannelService(db).set_defaults(template, body.channel_ids)}


@router.get("/{channel_id}")
def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ChannelService(db).get_channel(channel_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{channel_id}")
def update_channel(
    channel_id: int,
    body: ChannelUpdateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    try:
        return ChannelService(db).update_channel(channel_id, body.model_dump(exclude_none=True))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    try:
        ChannelService(db).delete_channel(channel_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
