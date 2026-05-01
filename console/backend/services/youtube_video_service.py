# console/backend/services/youtube_video_service.py
"""Service for managing YouTube long-form video projects."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from console.backend.models.audit_log import AuditLog
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.models.video_template import VideoTemplate

# Valid status transitions for the YoutubeVideo state machine
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"queued"},
    "queued": {"rendering", "failed", "draft"},
    "rendering": {"done", "failed"},
    "done": {"published", "draft"},
    "failed": {"draft"},
    "published": set(),
}


def _audit(
    db: Session,
    user_id: int | None,
    action: str,
    target_type: str,
    target_id: str,
    details: dict | None = None,
) -> None:
    if user_id is None:
        return
    log = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        details=details or {},
    )
    db.add(log)


def _video_to_dict(v: YoutubeVideo) -> dict[str, Any]:
    return {
        "id": v.id,
        "title": v.title,
        "template_id": v.template_id,
        "theme": v.theme,
        "status": v.status,
        "music_track_id": v.music_track_id,
        "visual_asset_id": v.visual_asset_id,
        "parent_youtube_video_id": v.parent_youtube_video_id,
        "sfx_overrides": v.sfx_overrides,
        "target_duration_h": v.target_duration_h,
        "output_quality": v.output_quality,
        "seo_title": v.seo_title,
        "seo_description": v.seo_description,
        "seo_tags": v.seo_tags,
        "celery_task_id": v.celery_task_id,
        "output_path": v.output_path,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


def _template_to_dict(t: VideoTemplate) -> dict[str, Any]:
    return {
        "id": t.id,
        "slug": t.slug,
        "label": t.label,
        "output_format": t.output_format,
        "target_duration_h": t.target_duration_h,
        "suno_extends_recommended": t.suno_extends_recommended,
        "sfx_pack": t.sfx_pack,
        "suno_prompt_template": t.suno_prompt_template,
        "midjourney_prompt_template": t.midjourney_prompt_template,
        "runway_prompt_template": t.runway_prompt_template,
        "sound_rules": t.sound_rules,
        "seo_title_formula": t.seo_title_formula,
        "seo_description_template": t.seo_description_template,
        "short_cta_text": t.short_cta_text,
        "short_duration_s": t.short_duration_s if t.short_duration_s is not None else 58,
    }


class YoutubeVideoService:
    def __init__(self, db: Session):
        self.db = db

    # ── Templates ──────────────────────────────────────────────────────────

    def list_templates(self) -> list[dict]:
        rows = self.db.query(VideoTemplate).order_by(VideoTemplate.id).all()
        return [_template_to_dict(t) for t in rows]

    def get_template(self, template_id: int) -> dict:
        t = self.db.get(VideoTemplate, template_id)
        if not t:
            raise KeyError(f"Template {template_id} not found")
        return _template_to_dict(t)

    # ── Videos ─────────────────────────────────────────────────────────────

    def list_videos(self, status: str | None = None, template_id: int | None = None) -> list[dict]:
        q = self.db.query(YoutubeVideo)
        if status:
            q = q.filter(YoutubeVideo.status == status)
        if template_id:
            q = q.filter(YoutubeVideo.template_id == template_id)
        return [_video_to_dict(v) for v in q.order_by(YoutubeVideo.created_at.desc()).all()]

    def get_video(self, video_id: int) -> dict:
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")
        return _video_to_dict(v)

    def create_video(self, data: dict, user_id: int | None = None) -> dict:
        """Create a new YouTube video project."""
        template_id = data.get("template_id")
        if not template_id:
            raise ValueError("template_id is required")
        template = self.db.get(VideoTemplate, template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        video = YoutubeVideo(
            title=data["title"],
            template_id=template_id,
            theme=data.get("theme"),
            music_track_id=data.get("music_track_id"),
            visual_asset_id=data.get("visual_asset_id"),
            parent_youtube_video_id=data.get("parent_youtube_video_id"),
            sfx_overrides=data.get("sfx_overrides"),
            target_duration_h=data.get("target_duration_h"),
            output_quality=data.get("output_quality", "1080p"),
            seo_title=data.get("seo_title"),
            seo_description=data.get("seo_description"),
            seo_tags=data.get("seo_tags"),
            status="draft",
        )
        self.db.add(video)
        try:
            self.db.flush()
            _audit(self.db, user_id, "create_video", "youtube_video", str(video.id), {"title": video.title})
            self.db.commit()
            self.db.refresh(video)
        except Exception:
            self.db.rollback()
            raise
        return _video_to_dict(video)

    def update_video(self, video_id: int, data: dict, user_id: int | None = None) -> dict:
        """Update editable fields on a YouTube video project."""
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")

        editable_fields = [
            "title", "theme", "music_track_id", "visual_asset_id",
            "sfx_overrides", "target_duration_h", "output_quality",
            "seo_title", "seo_description", "seo_tags",
        ]
        changed = {f: data[f] for f in editable_fields if f in data}
        for field, value in changed.items():
            setattr(v, field, value)

        try:
            _audit(self.db, user_id, "update_video", "youtube_video", str(video_id), changed)
            self.db.commit()
            self.db.refresh(v)
        except Exception:
            self.db.rollback()
            raise
        return _video_to_dict(v)

    def update_status(self, video_id: int, status: str, user_id: int | None = None) -> dict:
        """Transition video status following the allowed state machine."""
        valid_statuses = set(ALLOWED_TRANSITIONS.keys())
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status!r}")
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")
        allowed = ALLOWED_TRANSITIONS.get(v.status, set())
        if status not in allowed:
            raise ValueError(f"Cannot transition from {v.status!r} to {status!r}")
        prev = v.status
        v.status = status
        try:
            _audit(self.db, user_id, "update_status", "youtube_video", str(video_id),
                   {"from": prev, "to": status})
            self.db.commit()
            self.db.refresh(v)
        except Exception:
            self.db.rollback()
            raise
        return _video_to_dict(v)

    def delete_video(self, video_id: int, user_id: int | None = None) -> None:
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")
        # Revoke active Celery task if video is queued or rendering
        if v.celery_task_id and v.status in {"queued", "rendering"}:
            from console.backend.celery_app import celery_app
            celery_app.control.revoke(v.celery_task_id, terminate=True)
        try:
            _audit(self.db, user_id, "delete_video", "youtube_video", str(video_id),
                   {"title": v.title})
            self.db.delete(v)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def dispatch_render(self, video_id: int) -> str:
        """Queue the correct render task based on template.output_format. Returns Celery task_id."""
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")

        template = self.db.get(VideoTemplate, v.template_id)
        if not template:
            raise ValueError(f"VideoTemplate {v.template_id} not found")

        if template.output_format == "portrait_short":
            from console.backend.tasks.youtube_short_render_task import render_youtube_short_task
            task = render_youtube_short_task.delay(video_id)
        else:
            from console.backend.tasks.youtube_render_task import render_youtube_video_task
            task = render_youtube_video_task.delay(video_id)

        v.celery_task_id = task.id
        self.db.commit()
        return task.id
