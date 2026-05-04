# console/backend/services/youtube_video_service.py
"""Service for managing YouTube long-form video projects."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from console.backend.models.audit_log import AuditLog
from console.backend.models.channel import Channel
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.models.youtube_video_upload import YoutubeVideoUpload
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


def _video_to_dict(
    v: YoutubeVideo,
    template_label: str | None = None,
    uploads: list | None = None,
) -> dict[str, Any]:
    return {
        "id": v.id,
        "title": v.title,
        "template_id": v.template_id,
        "template_label": template_label,
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
        "music_track_ids":     list(v.music_track_ids or []),
        "sfx_pool":            v.sfx_pool or [],
        "sfx_density_seconds": v.sfx_density_seconds,
        "sfx_seed":            v.sfx_seed,
        "black_from_seconds":  v.black_from_seconds,
        "skip_previews":       bool(v.skip_previews) if v.skip_previews is not None else True,
        "render_parts":        v.render_parts or [],
        "audio_preview_path":  v.audio_preview_path,
        "video_preview_path":  v.video_preview_path,
        "visual_asset_ids":        list(v.visual_asset_ids or []),
        "visual_clip_durations_s": list(v.visual_clip_durations_s or []),
        "visual_loop_mode":        v.visual_loop_mode or "concat_loop",
        "uploads": uploads if uploads is not None else [],
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


def _upload_to_dict(u, channel_name: str | None = None) -> dict[str, Any]:
    return {
        "id": u.id,
        "channel_id": u.channel_id,
        "channel_name": channel_name,
        "status": u.status,
        "platform_id": u.platform_id,
        "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
        "error": u.error,
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
    EDITABLE_STATUSES = {"draft", "failed", "audio_preview_ready", "video_preview_ready"}

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
        videos = q.order_by(YoutubeVideo.created_at.desc()).all()

        # batch-resolve template labels
        template_ids = {v.template_id for v in videos if v.template_id}
        templates = {
            t.id: t.label
            for t in self.db.query(VideoTemplate).filter(VideoTemplate.id.in_(template_ids)).all()
        } if template_ids else {}

        # batch-resolve upload records with channel names
        video_ids = [v.id for v in videos]
        upload_rows = (
            self.db.query(YoutubeVideoUpload, Channel.name)
            .outerjoin(Channel, YoutubeVideoUpload.channel_id == Channel.id)
            .filter(YoutubeVideoUpload.youtube_video_id.in_(video_ids))
            .all()
        ) if video_ids else []

        uploads_by_video: dict[int, list] = {}
        for upload, channel_name in upload_rows:
            uploads_by_video.setdefault(upload.youtube_video_id, []).append(
                _upload_to_dict(upload, channel_name)
            )

        return [
            _video_to_dict(
                v,
                template_label=templates.get(v.template_id),
                uploads=uploads_by_video.get(v.id, []),
            )
            for v in videos
        ]

    def get_video(self, video_id: int) -> dict | None:
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            return None

        template_label = None
        if v.template_id:
            t = self.db.query(VideoTemplate).filter(VideoTemplate.id == v.template_id).first()
            template_label = t.label if t else None

        upload_rows = (
            self.db.query(YoutubeVideoUpload, Channel.name)
            .outerjoin(Channel, YoutubeVideoUpload.channel_id == Channel.id)
            .filter(YoutubeVideoUpload.youtube_video_id == video_id)
            .all()
        )
        uploads = [_upload_to_dict(u, ch_name) for u, ch_name in upload_rows]

        return _video_to_dict(v, template_label=template_label, uploads=uploads)

    def create_video(self, data: dict, user_id: int | None = None) -> dict:
        """Create a new YouTube video project."""
        template_id = data.get("template_id")
        if not template_id:
            raise ValueError("template_id is required")
        template = self.db.get(VideoTemplate, template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Default skip_previews=False for asmr/soundscape templates (preview flow opt-in by default)
        skip_previews = data.get("skip_previews")
        if skip_previews is None:
            skip_previews = template.slug not in ("asmr", "soundscape")

        video = YoutubeVideo(
            title=data["title"],
            template_id=template_id,
            theme=data.get("theme"),
            music_track_id=data.get("music_track_id"),
            music_track_ids=data.get("music_track_ids") or [],
            visual_asset_id=data.get("visual_asset_id"),
            parent_youtube_video_id=data.get("parent_youtube_video_id"),
            sfx_overrides=data.get("sfx_overrides"),
            sfx_pool=data.get("sfx_pool") or [],
            sfx_density_seconds=data.get("sfx_density_seconds"),
            black_from_seconds=data.get("black_from_seconds"),
            skip_previews=skip_previews,
            target_duration_h=data.get("target_duration_h"),
            output_quality=data.get("output_quality", "1080p"),
            seo_title=data.get("seo_title"),
            seo_description=data.get("seo_description"),
            seo_tags=data.get("seo_tags"),
            visual_asset_ids=data.get("visual_asset_ids") or [],
            visual_clip_durations_s=data.get("visual_clip_durations_s") or [],
            visual_loop_mode=data.get("visual_loop_mode") or "concat_loop",
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

    def _validate_visual_playlist(self, data: dict) -> list[float] | None:
        """Validate visual playlist fields. Returns the normalized durations array if rewritten, else None.

        Raises ValueError on invalid combinations.
        """
        if "visual_asset_ids" not in data:
            return None
        asset_ids = data.get("visual_asset_ids") or []
        if not asset_ids:
            return None

        from console.backend.models.video_asset import VideoAsset
        rows = self.db.query(VideoAsset).filter(VideoAsset.id.in_(asset_ids)).all()
        rows_by_id = {r.id: r for r in rows}
        for aid in asset_ids:
            if aid not in rows_by_id:
                raise ValueError(f"visual_asset_ids includes unknown asset {aid}")

        durations = list(data.get("visual_clip_durations_s") or [])
        if durations and len(durations) != len(asset_ids):
            raise ValueError(
                f"visual_clip_durations_s length ({len(durations)}) "
                f"must match visual_asset_ids length ({len(asset_ids)})"
            )
        if not durations:
            durations = [0.0] * len(asset_ids)

        loop_mode = data.get("visual_loop_mode") or "concat_loop"
        if loop_mode not in ("concat_loop", "per_clip"):
            raise ValueError(f"visual_loop_mode must be 'concat_loop' or 'per_clip', got {loop_mode!r}")

        # Per-mode duration rules
        for i, aid in enumerate(asset_ids):
            asset = rows_by_id[aid]
            is_still = asset.asset_type == "still_image"
            if loop_mode == "concat_loop":
                if is_still and durations[i] <= 0:
                    durations[i] = 3.0
            else:  # per_clip
                if is_still and durations[i] <= 0:
                    durations[i] = 3.0
                elif not is_still and durations[i] <= 0:
                    raise ValueError(
                        f"per_clip mode requires duration > 0 for video at index {i} (asset {aid})"
                    )
        return durations

    def _discard_render_artifacts(self, v: YoutubeVideo) -> list[str]:
        """Delete preview + output files from disk; null the path columns. Return list of discarded paths."""
        from pathlib import Path

        discarded: list[str] = []
        for attr in ("audio_preview_path", "video_preview_path", "output_path"):
            path_str = getattr(v, attr, None)
            if path_str:
                p = Path(path_str)
                if p.is_file():
                    try:
                        p.unlink()
                        discarded.append(path_str)
                    except OSError:
                        pass  # best-effort; we still null the column
                setattr(v, attr, None)
        return discarded

    def update_video(self, video_id: int, data: dict, user_id: int | None = None) -> dict:
        """Edit fields on a YouTube video and reset to draft, discarding any preview/output artifacts."""
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")
        if v.status not in self.EDITABLE_STATUSES:
            raise ValueError(
                f"Video in status {v.status!r} cannot be edited "
                f"(allowed: {sorted(self.EDITABLE_STATUSES)})"
            )

        # Validate visual playlist BEFORE any writes
        playlist_validation = self._validate_visual_playlist(data)

        editable_fields = [
            "title", "theme", "music_track_id", "music_track_ids", "visual_asset_id",
            "sfx_overrides", "sfx_pool", "sfx_density_seconds", "black_from_seconds",
            "skip_previews", "target_duration_h", "output_quality",
            "seo_title", "seo_description", "seo_tags",
            "visual_asset_ids", "visual_clip_durations_s", "visual_loop_mode",
        ]
        changed = {f: data[f] for f in editable_fields if f in data}

        # Apply normalized durations array if validation rewrote it
        if playlist_validation is not None:
            changed["visual_clip_durations_s"] = playlist_validation

        for field, value in changed.items():
            setattr(v, field, value)

        # Reset to draft + discard orphaned artifacts
        discarded = self._discard_render_artifacts(v)
        v.status = "draft"
        v.celery_task_id = None

        try:
            _audit(
                self.db,
                user_id,
                "video_edit_reset",
                "youtube_video",
                str(video_id),
                {"changed_fields": sorted(changed.keys()), "discarded_artifacts": discarded},
            )
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
        """Queue the correct render task based on template + skip_previews. Returns Celery task_id."""
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")

        template = self.db.get(VideoTemplate, v.template_id)
        if not template:
            raise ValueError(f"VideoTemplate {v.template_id} not found")

        # Route asmr/soundscape with previews enabled → audio preview gate
        if template.slug in ("asmr", "soundscape") and not v.skip_previews:
            from console.backend.tasks.youtube_render_task import render_youtube_audio_preview_task
            task = render_youtube_audio_preview_task.delay(video_id)
        elif template.output_format == "portrait_short":
            from console.backend.tasks.youtube_short_render_task import render_youtube_short_task
            task = render_youtube_short_task.delay(video_id)
        else:
            # asmr/soundscape with skip_previews=True → chunked orchestrator (still gets chunked render benefit)
            if template.slug in ("asmr", "soundscape"):
                from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
                task = render_youtube_chunked_orchestrator_task.delay(video_id)
            else:
                from console.backend.tasks.youtube_render_task import render_youtube_video_task
                task = render_youtube_video_task.delay(video_id)

        v.celery_task_id = task.id
        self.db.commit()
        return task.id

    def queue_upload(self, video_id: int, channel_id: int) -> dict:
        """Create a YoutubeVideoUpload record and dispatch the upload Celery task."""
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")
        if v.status != "done":
            raise ValueError(f"Video must be 'done' to upload (current: '{v.status}')")

        existing = (
            self.db.query(YoutubeVideoUpload)
            .filter(
                YoutubeVideoUpload.youtube_video_id == video_id,
                YoutubeVideoUpload.channel_id == channel_id,
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"Upload already exists for video {video_id} → channel {channel_id} "
                f"(status: {existing.status})"
            )

        upload = YoutubeVideoUpload(
            youtube_video_id=video_id,
            channel_id=channel_id,
            status="queued",
        )
        self.db.add(upload)
        try:
            self.db.flush()
            from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
            task = upload_youtube_video_task.delay(video_id, channel_id, upload.id)
            upload.celery_task_id = task.id
            self.db.commit()
            self.db.refresh(upload)
        except Exception:
            self.db.rollback()
            raise

        return {"task_id": task.id, "upload_id": upload.id, "status": "queued"}

    # ── ASMR / Soundscape render lifecycle ───────────────────────────────────

    def _load_video_or_404(self, video_id: int) -> YoutubeVideo:
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")
        return v

    def _revoke_active_render_jobs(self, video_id: int) -> None:
        """Revoke any in-flight Celery render task for this video."""
        from console.backend.celery_app import celery_app
        v = self.db.get(YoutubeVideo, video_id)
        if v and v.celery_task_id:
            try:
                celery_app.control.revoke(v.celery_task_id, terminate=True)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to revoke task %s: %s", v.celery_task_id, e)

    def start_audio_preview(self, video_id: int, user_id: int | None = None) -> str:
        from console.backend.tasks.youtube_render_task import render_youtube_audio_preview_task
        v = self._load_video_or_404(video_id)
        if v.status not in ("draft", "queued", "audio_preview_ready", "video_preview_ready"):
            raise ValueError(f"Cannot start audio preview from status '{v.status}'")
        v.status = "audio_preview_rendering"
        _audit(self.db, user_id, "start_audio_preview", "youtube_video", str(video_id))
        self.db.commit()
        task = render_youtube_audio_preview_task.delay(video_id)
        v.celery_task_id = task.id
        self.db.commit()
        return task.id

    def approve_audio_preview(self, video_id: int, user_id: int | None = None) -> dict:
        v = self._load_video_or_404(video_id)
        if v.status != "audio_preview_ready":
            raise ValueError(f"Cannot approve from status '{v.status}'")
        _audit(self.db, user_id, "approve_audio_preview", "youtube_video", str(video_id))
        self.db.commit()
        return {"status": v.status}

    def reject_audio_preview(self, video_id: int, user_id: int | None = None) -> dict:
        v = self._load_video_or_404(video_id)
        if v.status != "audio_preview_ready":
            raise ValueError(f"Cannot reject from status '{v.status}'")
        v.status = "queued"
        v.audio_preview_path = None
        _audit(self.db, user_id, "reject_audio_preview", "youtube_video", str(video_id))
        self.db.commit()
        return {"status": v.status}

    def start_video_preview(self, video_id: int, user_id: int | None = None) -> str:
        from console.backend.tasks.youtube_render_task import render_youtube_video_preview_task
        v = self._load_video_or_404(video_id)
        if v.status not in ("audio_preview_ready", "video_preview_ready"):
            raise ValueError(f"Cannot start video preview from status '{v.status}'")
        v.status = "video_preview_rendering"
        _audit(self.db, user_id, "start_video_preview", "youtube_video", str(video_id))
        self.db.commit()
        task = render_youtube_video_preview_task.delay(video_id)
        v.celery_task_id = task.id
        self.db.commit()
        return task.id

    def approve_video_preview(self, video_id: int, user_id: int | None = None) -> dict:
        v = self._load_video_or_404(video_id)
        if v.status != "video_preview_ready":
            raise ValueError(f"Cannot approve from status '{v.status}'")
        _audit(self.db, user_id, "approve_video_preview", "youtube_video", str(video_id))
        self.db.commit()
        return {"status": v.status}

    def reject_video_preview(self, video_id: int, user_id: int | None = None) -> dict:
        v = self._load_video_or_404(video_id)
        if v.status != "video_preview_ready":
            raise ValueError(f"Cannot reject from status '{v.status}'")
        v.status = "audio_preview_ready"
        v.video_preview_path = None
        _audit(self.db, user_id, "reject_video_preview", "youtube_video", str(video_id))
        self.db.commit()
        return {"status": v.status}

    def start_chunked_render(self, video_id: int, user_id: int | None = None) -> str:
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        v = self._load_video_or_404(video_id)
        valid_from = ("video_preview_ready", "queued", "draft") if v.skip_previews else ("video_preview_ready",)
        if v.status not in valid_from:
            raise ValueError(f"Cannot start final render from status '{v.status}'")
        v.status = "rendering"
        _audit(self.db, user_id, "start_chunked_render", "youtube_video", str(video_id))
        self.db.commit()
        task = render_youtube_chunked_orchestrator_task.delay(video_id)
        v.celery_task_id = task.id
        self.db.commit()
        return task.id

    def resume_chunked_render(self, video_id: int, user_id: int | None = None) -> str:
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        from sqlalchemy.orm.attributes import flag_modified
        v = self._load_video_or_404(video_id)
        if not v.render_parts:
            raise ValueError("No prior render to resume")
        # Revoke in-flight tasks before re-dispatching
        self._revoke_active_render_jobs(video_id)
        # Reset failed/running parts to pending
        parts = list(v.render_parts)
        for p in parts:
            if p.get("status") in ("failed", "running"):
                p["status"] = "pending"
                p["error"] = None
        v.render_parts = parts
        flag_modified(v, "render_parts")
        v.status = "rendering"
        _audit(self.db, user_id, "resume_chunked_render", "youtube_video", str(video_id))
        self.db.commit()
        task = render_youtube_chunked_orchestrator_task.delay(video_id)
        v.celery_task_id = task.id
        self.db.commit()
        return task.id

    def cancel_chunked_render(self, video_id: int, user_id: int | None = None) -> dict:
        v = self._load_video_or_404(video_id)
        self._revoke_active_render_jobs(video_id)
        v.status = "video_preview_ready" if v.video_preview_path else "queued"
        _audit(self.db, user_id, "cancel_chunked_render", "youtube_video", str(video_id))
        self.db.commit()
        return {"status": v.status}

    def get_render_state(self, video_id: int) -> dict:
        from console.backend.services.youtube_render_state import get_render_state
        return get_render_state(self.db, video_id)
