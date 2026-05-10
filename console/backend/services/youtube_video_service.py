# console/backend/services/youtube_video_service.py
"""Service for managing YouTube long-form video projects."""
from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from console.backend.models.audit_log import AuditLog
from console.backend.models.channel import Channel
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.models.youtube_video_upload import YoutubeVideoUpload
from console.backend.models.video_template import VideoTemplate
from database.models import MusicTrack

# Fields that are NOT NULL in the DB — explicit None in an update payload is an error
_MUSIC_NOT_NULL_FIELDS = (
    "track_transition",
    "track_transition_seconds",
    "spectrum_enabled",
    "spectrum_position",
    "spectrum_height_pct",
    "spectrum_color",
    "spectrum_opacity",
)

# Valid status transitions for the YoutubeVideo state machine
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"queued"},
    "queued": {"rendering", "failed", "draft"},
    "rendering": {"done", "failed"},
    "done": {"published", "draft"},
    "failed": {"draft"},
    "published": set(),
}


def _resolve_music_tracks(video, db) -> list[MusicTrack]:
    """Return ordered list of MusicTrack rows for video.music_track_ids.

    Preserves the user-specified order. Raises ValueError if any ID is missing.
    Falls back to single music_track_id when music_track_ids is empty.
    """
    track_ids = list(getattr(video, "music_track_ids", None) or [])
    if not track_ids and getattr(video, "music_track_id", None):
        track_ids = [video.music_track_id]
    if not track_ids:
        return []

    rows = db.query(MusicTrack).filter(MusicTrack.id.in_(track_ids)).all()
    by_id = {t.id: t for t in rows}
    missing = [tid for tid in track_ids if tid not in by_id]
    if missing:
        raise ValueError(f"music_track_ids not found: {missing}")
    return [by_id[tid] for tid in track_ids]


def _compute_music_total_duration(
    tracks, transition: str, transition_s: float
) -> tuple[float, list[float]]:
    """Return (total_seconds, per-track-start boundaries).

    Boundaries[i] is the start time of track i in the final timeline.
    Total is the timeline length after transition adjustments.
    """
    if not tracks:
        return 0.0, []

    boundaries: list[float] = [0.0]
    if transition == "gapless" or len(tracks) == 1:
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + float(t.duration_s))
        total = boundaries[-1] + float(tracks[-1].duration_s)
    elif transition == "crossfade":
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + float(t.duration_s) - transition_s)
        total = boundaries[-1] + float(tracks[-1].duration_s)
    elif transition == "gap":
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + float(t.duration_s) + transition_s)
        total = boundaries[-1] + float(tracks[-1].duration_s)
    else:
        raise ValueError(f"unknown transition mode: {transition}")
    return total, boundaries


def build_chapters_from_tracks(
    tracks, transition: str, transition_s: float
) -> list[dict] | None:
    """Pure function — chapter list or None.

    Returns None when fewer than 3 tracks (YouTube minimum). Falls back
    to "Track {i+1}" when a track title is empty/null, with WARNING log.
    """
    if len(tracks) < 3:
        return None
    _, boundaries = _compute_music_total_duration(tracks, transition, transition_s)
    chapters = []
    for i, t in enumerate(tracks):
        title = (t.title or "").strip()
        if not title:
            logger.warning(
                "Music track at index %d has empty title; falling back to 'Track %d'",
                i, i + 1,
            )
            title = f"Track {i + 1}"
        chapters.append({
            "seconds": int(round(boundaries[i])),
            "title": title,
        })
    return chapters


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
        "sound_layers":  v.sound_layers,
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
        "thumbnail_asset_id":      v.thumbnail_asset_id,
        "thumbnail_text":          v.thumbnail_text,
        "thumbnail_path":          v.thumbnail_path,
        # Music template fields
        "track_transition":         v.track_transition,
        "track_transition_seconds": v.track_transition_seconds,
        "playlist_overlay_style":   v.playlist_overlay_style,
        "spectrum_enabled":         bool(v.spectrum_enabled) if v.spectrum_enabled is not None else False,
        "spectrum_position":        v.spectrum_position,
        "spectrum_height_pct":      v.spectrum_height_pct,
        "spectrum_color":           v.spectrum_color,
        "spectrum_opacity":         v.spectrum_opacity,
        "total_duration_s":         None,
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
        "ui_features": list(t.ui_features) if t.ui_features else [],
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

        # Validate music-template-specific constraints before any writes
        data = self._validate_music_template(data, template)
        data.pop("_field_warnings", None)  # internal validator marker, don't pass to ORM

        # Default skip_previews=False for asmr/soundscape templates (preview flow opt-in by default)
        skip_previews = data.get("skip_previews")
        if skip_previews is None:
            skip_previews = template.slug not in ("asmr", "soundscape")

        # Validate visual playlist (if provided) — same rules as update_video
        playlist_validation = self._validate_visual_playlist(data)
        if playlist_validation is not None:
            data = {**data, "visual_clip_durations_s": playlist_validation}

        video = YoutubeVideo(
            title=data["title"],
            template_id=template_id,
            theme=data.get("theme"),
            music_track_id=data.get("music_track_id"),
            music_track_ids=data.get("music_track_ids") or [],
            visual_asset_id=data.get("visual_asset_id"),
            parent_youtube_video_id=data.get("parent_youtube_video_id"),
            sound_layers=data.get("sound_layers"),
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
            track_transition=data.get("track_transition", "gapless"),
            track_transition_seconds=data.get("track_transition_seconds", 2.0),
            playlist_overlay_style=data.get("playlist_overlay_style"),
            spectrum_enabled=data.get("spectrum_enabled", False),
            spectrum_position=data.get("spectrum_position", "bottom"),
            spectrum_height_pct=data.get("spectrum_height_pct", 0.12),
            spectrum_color=data.get("spectrum_color", "#ffffff"),
            spectrum_opacity=data.get("spectrum_opacity", 0.6),
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

    def _validate_music_template(self, data: dict, template) -> dict:
        """Reject music-template-incompatible fields, normalize single-track overlay.

        Returns the (possibly mutated) data dict. May add `_field_warnings` key
        listing soft warnings that the response will surface.
        """
        if template.slug != "music":
            return data
        warnings: list[str] = []

        if data.get("target_duration_h") is not None:
            raise ValueError(
                "music template derives duration from tracks; remove target_duration_h"
            )
        if data.get("black_from_seconds") is not None:
            raise ValueError("music template does not support blackout")
        for field in ("sound_layers", "sfx_overrides", "sfx_pool"):
            if data.get(field):
                raise ValueError("music template does not support SFX layers")

        track_ids = data.get("music_track_ids") or []
        if not track_ids and not data.get("music_track_id"):
            raise ValueError("music template requires at least 1 music track")

        # Single-track → null the overlay style silently, with warning
        effective_count = len(track_ids) if track_ids else 1
        if effective_count < 2 and data.get("playlist_overlay_style"):
            warnings.append("overlay hidden for single-track playlists")
            data = {**data, "playlist_overlay_style": None}

        # Crossfade safety: must be < half the shortest track
        if data.get("track_transition") == "crossfade" and track_ids:
            rows = self.db.query(MusicTrack).filter(MusicTrack.id.in_(track_ids)).all()
            durations = [r.duration_s for r in rows if r.duration_s]
            if durations:
                shortest = min(durations)
                xfade = float(data.get("track_transition_seconds") or 2.0)
                if xfade > shortest / 2:
                    raise ValueError(
                        f"crossfade ({xfade}s) exceeds half the shortest "
                        f"track duration ({shortest}s)"
                    )

        if warnings:
            data = {**data, "_field_warnings": warnings}
        return data

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

        # Validate music-template-specific constraints BEFORE any writes
        template = self.db.get(VideoTemplate, v.template_id)
        if template and template.slug == "music":
            # For partial updates, merge update data with existing video state so that
            # single-track-overlay and crossfade checks can see the effective track list.
            effective_data = {
                "music_track_ids": list(v.music_track_ids or []),
                "music_track_id": v.music_track_id,
                "track_transition": v.track_transition,
                "track_transition_seconds": v.track_transition_seconds,
                "playlist_overlay_style": v.playlist_overlay_style,
            }
            effective_data.update(data)
            validated = self._validate_music_template(effective_data, template)
            validated.pop("_field_warnings", None)  # internal validator marker, don't pass to ORM
            # If overlay was silently nulled, propagate that into the update payload
            if validated.get("playlist_overlay_style") != effective_data.get("playlist_overlay_style"):
                data = {**data, "playlist_overlay_style": validated["playlist_overlay_style"]}

        # Validate visual playlist BEFORE any writes
        playlist_validation = self._validate_visual_playlist(data)

        editable_fields = [
            "title", "theme", "music_track_id", "music_track_ids", "visual_asset_id",
            "sound_layers", "sfx_overrides", "sfx_pool", "sfx_density_seconds",
            "black_from_seconds", "skip_previews", "target_duration_h", "output_quality",
            "seo_title", "seo_description", "seo_tags",
            "visual_asset_ids", "visual_clip_durations_s", "visual_loop_mode",
            "track_transition", "track_transition_seconds", "playlist_overlay_style",
            "spectrum_enabled", "spectrum_position", "spectrum_height_pct",
            "spectrum_color", "spectrum_opacity",
        ]
        changed = {f: data[f] for f in editable_fields if f in data}

        # Guard: NOT NULL music fields must not be set to None via partial update
        for f in _MUSIC_NOT_NULL_FIELDS:
            if f in changed and changed[f] is None:
                raise ValueError(f"{f} cannot be null")

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
        self._revoke_all_render_jobs(v)
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

    def _dispatch_render_task(self, task, v: YoutubeVideo, args: list) -> str:
        """Stamp celery_task_id on the video BEFORE dispatching, so the task can verify
        at start time that it hasn't been superseded by a newer dispatch.

        Without this, the worker could pick up a stale retried task while a fresh
        user-initiated task is also in flight, and both would write to the same
        output file simultaneously — producing a corrupted MP4.
        """
        new_task_id = str(uuid.uuid4())
        v.celery_task_id = new_task_id
        self.db.commit()
        task.apply_async(args=args, task_id=new_task_id)
        return new_task_id

    def _revoke_all_render_jobs(self, video: YoutubeVideo) -> None:
        """Revoke all chunk task IDs stored in render_parts, plus the concat callback."""
        from console.backend.celery_app import celery_app
        for part in (video.render_parts or []):
            task_id = part.get("task_id")
            if task_id:
                try:
                    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
                except Exception as e:
                    logger.warning("Failed to revoke chunk task %s: %s", task_id, e)
        if video.celery_task_id:
            try:
                celery_app.control.revoke(video.celery_task_id, terminate=True, signal="SIGTERM")
            except Exception as e:
                logger.warning("Failed to revoke concat task %s: %s", video.celery_task_id, e)

    def start_audio_preview(self, video_id: int, user_id: int | None = None) -> str:
        from console.backend.tasks.youtube_render_task import render_youtube_audio_preview_task
        v = self._load_video_or_404(video_id)
        if v.status not in ("draft", "queued", "audio_preview_ready", "video_preview_ready"):
            raise ValueError(f"Cannot start audio preview from status '{v.status}'")
        v.status = "audio_preview_rendering"
        _audit(self.db, user_id, "start_audio_preview", "youtube_video", str(video_id))
        return self._dispatch_render_task(render_youtube_audio_preview_task, v, [video_id])

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
        return self._dispatch_render_task(render_youtube_video_preview_task, v, [video_id])

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
        return self._dispatch_render_task(render_youtube_chunked_orchestrator_task, v, [video_id])

    def resume_chunked_render(self, video_id: int, user_id: int | None = None) -> str:
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        from sqlalchemy.orm.attributes import flag_modified
        v = self._load_video_or_404(video_id)
        if not v.render_parts:
            raise ValueError("No prior render to resume")
        # Revoke in-flight tasks before re-dispatching
        self._revoke_all_render_jobs(v)
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
        return self._dispatch_render_task(render_youtube_chunked_orchestrator_task, v, [video_id])

    def cancel_chunked_render(self, video_id: int, user_id: int | None = None) -> dict:
        from sqlalchemy.orm.attributes import flag_modified
        v = self._load_video_or_404(video_id)
        self._revoke_all_render_jobs(v)
        v.status = "failed"
        parts = list(v.render_parts or [])
        for p in parts:
            if p.get("status") != "completed":
                p["status"] = "cancelled"
        v.render_parts = parts
        flag_modified(v, "render_parts")
        v.celery_task_id = None
        _audit(self.db, user_id, "cancel_chunked_render", "youtube_video", str(video_id))
        self.db.commit()
        return {"status": v.status}

    def get_render_state(self, video_id: int) -> dict:
        from console.backend.services.youtube_render_state import get_render_state
        return get_render_state(self.db, video_id)

    def build_chapters(self, video) -> list[dict] | None:
        """Service wrapper: builds chapters for a YoutubeVideo (music template only)."""
        if video.template.slug != "music":
            return None
        tracks = _resolve_music_tracks(video, self.db)
        return build_chapters_from_tracks(
            tracks, video.track_transition, video.track_transition_seconds
        )
