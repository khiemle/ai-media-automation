"""MusicService — CRUD, Gemini prompt expansion, provider dispatch, usage tracking."""
import json
import os
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

MUSIC_DIR = Path(os.environ.get("MUSIC_PATH", "./assets/music"))


def _track_to_dict(t) -> dict:
    return {
        "id":               t.id,
        "title":            t.title,
        "file_path":        t.file_path,
        "duration_s":       t.duration_s,
        "niches":           t.niches or [],
        "moods":            t.moods or [],
        "genres":           t.genres or [],
        "is_vocal":         t.is_vocal,
        "is_favorite":      t.is_favorite,
        "volume":           t.volume,
        "usage_count":      t.usage_count,
        "quality_score":    t.quality_score,
        "provider":         t.provider,
        "provider_task_id": t.provider_task_id,
        "generation_status":t.generation_status,
        "generation_prompt":t.generation_prompt,
        "created_at":       t.created_at.isoformat() if t.created_at else None,
    }


class MusicService:
    def __init__(self, db: Session):
        self.db = db

    def _model(self):
        from database.models import MusicTrack
        return MusicTrack

    # ── List ──────────────────────────────────────────────────────────────────

    def list_tracks(
        self,
        niche: str | None = None,
        mood: str | None = None,
        genre: str | None = None,
        is_vocal: bool | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        MusicTrack = self._model()
        q = self.db.query(MusicTrack)
        if niche:
            q = q.filter(MusicTrack.niches.contains([niche]))
        if mood:
            q = q.filter(MusicTrack.moods.contains([mood]))
        if genre:
            q = q.filter(MusicTrack.genres.contains([genre]))
        if is_vocal is not None:
            q = q.filter(MusicTrack.is_vocal == is_vocal)
        if status:
            q = q.filter(MusicTrack.generation_status == status)
        if search:
            q = q.filter(MusicTrack.title.ilike(f"%{search}%"))
        tracks = q.order_by(MusicTrack.created_at.desc()).all()
        return [_track_to_dict(t) for t in tracks]

    # ── Get ───────────────────────────────────────────────────────────────────

    def get_track(self, track_id: int) -> dict:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if not t:
            raise KeyError(f"Music track {track_id} not found")
        return _track_to_dict(t)

    # ── Create pending row ────────────────────────────────────────────────────

    def create_pending(
        self,
        title: str,
        niches: list[str],
        moods: list[str],
        genres: list[str],
        is_vocal: bool,
        volume: float,
        provider: str,
        prompt: str,
        negative_tags: str = "",
    ) -> dict:
        MusicTrack = self._model()
        track = MusicTrack(
            title=title,
            niches=niches,
            moods=moods,
            genres=genres,
            is_vocal=is_vocal,
            volume=volume,
            provider=provider,
            generation_status="pending",
            generation_prompt=prompt,
        )
        self.db.add(track)
        self.db.commit()
        self.db.refresh(track)
        return _track_to_dict(track)

    # ── Mark ready / failed ───────────────────────────────────────────────────

    def mark_ready(self, track_id: int, file_path: str, duration_s: float) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.file_path = file_path
            t.duration_s = duration_s
            t.generation_status = "ready"
            self.db.commit()

    def mark_failed(self, track_id: int) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.generation_status = "failed"
            self.db.commit()

    def set_provider_task_id(self, track_id: int, provider_task_id: str) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.provider_task_id = provider_task_id
            self.db.commit()

    # ── Update metadata ───────────────────────────────────────────────────────

    def update_track(self, track_id: int, data: dict) -> dict:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if not t:
            raise KeyError(f"Music track {track_id} not found")
        for field in ("title", "niches", "moods", "genres", "is_vocal", "is_favorite", "volume", "quality_score"):
            if field in data:
                setattr(t, field, data[field])
        self.db.commit()
        self.db.refresh(t)
        return _track_to_dict(t)

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_track(self, track_id: int) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if not t:
            raise KeyError(f"Music track {track_id} not found")
        if t.file_path and Path(t.file_path).exists():
            Path(t.file_path).unlink(missing_ok=True)
        self.db.delete(t)
        self.db.commit()

    # ── Usage increment ───────────────────────────────────────────────────────

    def increment_usage(self, track_id: int) -> None:
        MusicTrack = self._model()
        t = self.db.query(MusicTrack).filter(MusicTrack.id == track_id).first()
        if t:
            t.usage_count = (t.usage_count or 0) + 1
            self.db.commit()

    # ── Gemini prompt expansion ───────────────────────────────────────────────

    def expand_prompt_with_gemini(
        self,
        idea: str,
        niches: list[str],
        moods: list[str],
        genres: list[str],
        is_vocal: bool,
    ) -> dict:
        """Call Gemini to produce a rich Suno/Lyria prompt + negative_tags."""
        from rag.llm_router import GeminiRouter

        vocal_style = "with vocals and sung lyrics" if is_vocal else "instrumental only, no vocals"
        system_prompt = f"""You are a music prompt engineer. Given a user idea and tags, produce a rich music generation prompt.

User idea: {idea}
Niches: {', '.join(niches) if niches else 'general'}
Moods: {', '.join(moods) if moods else 'neutral'}
Genres: {', '.join(genres) if genres else 'any'}
Vocal style: {vocal_style}

Return a JSON object with exactly two keys:
- "expanded_prompt": A vivid, descriptive music prompt (max 500 characters) suitable for Suno or Lyria. Include tempo, instrumentation, mood, and style details.
- "negative_tags": A short comma-separated string of styles to avoid (e.g. "aggressive, dissonant, minor key").

Respond with JSON only."""

        router = GeminiRouter()
        try:
            data = router.generate(system_prompt, expect_json=True)
            if not isinstance(data, dict):
                raise ValueError("Unexpected response type")
            return {
                "expanded_prompt": data.get("expanded_prompt", idea),
                "negative_tags":   data.get("negative_tags", ""),
            }
        except Exception:
            return {"expanded_prompt": idea, "negative_tags": ""}

    # ── Import (file upload) ──────────────────────────────────────────────────

    def import_track(
        self,
        file_bytes: bytes,
        extension: str,
        title: str,
        niches: list[str],
        moods: list[str],
        genres: list[str],
        is_vocal: bool,
        volume: float,
        quality_score: int,
    ) -> dict:
        MusicTrack = self._model()
        track = MusicTrack(
            title=title,
            niches=niches,
            moods=moods,
            genres=genres,
            is_vocal=is_vocal,
            volume=volume,
            quality_score=quality_score,
            provider="import",
            generation_status="ready",
        )
        self.db.add(track)
        self.db.flush()  # get track.id before writing file

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        dest = MUSIC_DIR / f"{track.id}{extension}"
        dest.write_bytes(file_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))

        track.file_path = str(dest)
        track.duration_s = duration
        self.db.commit()
        self.db.refresh(track)
        return _track_to_dict(track)

    # ── Auto-select for a niche ───────────────────────────────────────────────

    def best_track_for_niche(self, niche: str) -> int | None:
        """Return the best ready track id for a niche, or None."""
        MusicTrack = self._model()
        track = (
            self.db.query(MusicTrack)
            .filter(
                MusicTrack.generation_status == "ready",
                MusicTrack.niches.contains([niche]),
            )
            .order_by(MusicTrack.is_favorite.desc(), MusicTrack.quality_score.desc())
            .first()
        )
        return track.id if track else None
