import math
from datetime import datetime, timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session

from console.backend.models.audit_log import AuditLog
from console.backend.schemas.common import PaginatedResponse
from console.backend.schemas.script import ScriptListItem, ScriptDetail

# Valid script status transitions
VALID_TRANSITIONS = {
    "draft": ["pending_review", "approved"],
    "pending_review": ["approved", "draft"],   # draft = rejected
    "approved": ["editing", "producing"],
    "editing": ["approved"],
    "producing": ["completed"],
    "rejected": ["draft"],
    "completed": [],
}


def _audit(db: Session, user_id: int, action: str, target_type: str, target_id: str, details: dict = None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        details=details or {},
    )
    db.add(log)


class ScriptService:
    def __init__(self, db: Session):
        self.db = db

    def _get_model(self):
        """Import the existing GeneratedScript model from the core pipeline."""
        try:
            from database.models import GeneratedScript
            return GeneratedScript
        except ImportError as e:
            raise RuntimeError(f"Cannot import GeneratedScript model: {e}")

    # ── List ──────────────────────────────────────────────────────────────────

    def list_scripts(
        self,
        status: str | None = None,
        niche: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse[ScriptListItem]:
        Script = self._get_model()
        filters = []
        if status:
            filters.append(Script.status == status)
        if niche:
            filters.append(Script.niche == niche)

        query = self.db.query(Script)
        if filters:
            query = query.filter(and_(*filters))

        total = query.count()
        rows = query.order_by(Script.id.desc()).offset((page - 1) * per_page).limit(per_page).all()

        return PaginatedResponse(
            items=[ScriptListItem.model_validate(r) for r in rows],
            total=total,
            page=page,
            pages=math.ceil(total / per_page) if per_page else 1,
            per_page=per_page,
        )

    # ── Get ───────────────────────────────────────────────────────────────────

    def get_script(self, script_id: int) -> ScriptDetail:
        Script = self._get_model()
        row = self.db.query(Script).filter(Script.id == script_id).first()
        if not row:
            raise KeyError(f"Script {script_id} not found")
        return ScriptDetail.model_validate(row)

    # ── Update ────────────────────────────────────────────────────────────────

    def update_script(self, script_id: int, script_json: dict, editor_notes: str | None, user_id: int, language: str | None = None) -> ScriptDetail:
        Script = self._get_model()
        row = self.db.query(Script).filter(Script.id == script_id).first()
        if not row:
            raise KeyError(f"Script {script_id} not found")

        # Validate required keys
        required = {"meta", "video", "scenes"}
        missing = required - set(script_json.keys())
        if missing:
            raise ValueError(f"script_json missing required keys: {missing}")

        # Recalculate total_duration from scenes
        scenes = script_json.get("scenes", [])
        total_duration = sum(s.get("duration", 0) for s in scenes)
        if "video" in script_json:
            script_json["video"]["total_duration"] = total_duration

        row.script_json = script_json
        # Sync music_track_id DB column from script_json.video so composer picks it up
        video_section = script_json.get("video", {})
        if "music_track_id" in video_section:
            row.music_track_id = video_section.get("music_track_id")  # None = auto, int = explicit
        if editor_notes is not None:
            row.editor_notes = editor_notes
        row.edited_by = user_id
        if language is not None:
            row.language = language

        # Move approved scripts back to editing
        if row.status == "approved":
            row.status = "editing"

        _audit(self.db, user_id, "update_script", "script", script_id)
        self.db.commit()
        self.db.refresh(row)
        return ScriptDetail.model_validate(row)

    # ── Approve ───────────────────────────────────────────────────────────────

    def approve_script(self, script_id: int, user_id: int) -> ScriptDetail:
        Script = self._get_model()
        row = self.db.query(Script).filter(Script.id == script_id).first()
        if not row:
            raise KeyError(f"Script {script_id} not found")
        if row.status not in ("draft", "pending_review", "editing"):
            raise ValueError(f"Cannot approve a script with status '{row.status}'")

        row.status = "approved"
        row.approved_at = datetime.now(timezone.utc)
        _audit(self.db, user_id, "approve_script", "script", script_id)
        self.db.commit()
        self.db.refresh(row)
        return ScriptDetail.model_validate(row)

    # ── Reject ────────────────────────────────────────────────────────────────

    def reject_script(self, script_id: int, user_id: int) -> ScriptDetail:
        Script = self._get_model()
        row = self.db.query(Script).filter(Script.id == script_id).first()
        if not row:
            raise KeyError(f"Script {script_id} not found")

        rejectable = {"pending_review", "draft", "editing"}
        if row.status not in rejectable:
            raise ValueError(f"Cannot reject a script with status '{row.status}'")

        row.status = "draft"
        _audit(self.db, user_id, "reject_script", "script", script_id)
        self.db.commit()
        self.db.refresh(row)
        return ScriptDetail.model_validate(row)

    # ── Generate ──────────────────────────────────────────────────────────────

    def generate_script(
        self,
        topic: str,
        niche: str,
        template: str,
        source_video_ids: list[str] | None,
        user_id: int,
        language: str = "vietnamese",
        source_article_id: int | None = None,
        raw_content: str | None = None,
    ) -> ScriptDetail:
        Script = self._get_model()

        # Optionally fetch RAG context videos
        context_videos = []
        if source_video_ids:
            try:
                from database.models import ViralVideo
                context_videos = (
                    self.db.query(ViralVideo)
                    .filter(ViralVideo.id.in_(source_video_ids))
                    .all()
                )
            except Exception:
                pass

        # Fetch article content for rewrite mode — raw_content (Composer) wins when provided
        article_content: str | None = None
        if raw_content:
            article_content = raw_content
        elif source_article_id:
            try:
                from database.models import NewsArticle
                article = self.db.query(NewsArticle).filter(NewsArticle.id == source_article_id).first()
                if article and article.main_content:
                    article_content = article.main_content
                    # Use article language if caller didn't explicitly set one
                    if language == "vietnamese" and article.language:
                        language = article.language
            except Exception:
                pass

        # Call the core script writer
        from rag.script_writer import generate_script as _generate
        script_json = _generate(
            topic=topic,
            niche=niche,
            template=template,
            language=language,
            article_content=article_content,
            context_videos=context_videos if context_videos else None,
        )

        row = Script(
            topic=topic,
            niche=niche,
            template=template,
            language=language,
            script_json=script_json,
            status="draft",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        # Auto-assign music track for the niche (best ready track, or none)
        try:
            from console.backend.services.music_service import MusicService
            track_id = MusicService(self.db).best_track_for_niche(niche or "")
            if track_id:
                row.music_track_id = track_id
                self.db.commit()
                self.db.refresh(row)
        except Exception:
            pass  # never block script creation

        _audit(self.db, user_id, "generate_script", "script", row.id, {
            "topic": topic,
            "source_article_id": source_article_id,
            "from_composer": bool(raw_content),
        })
        self.db.commit()
        return ScriptDetail.model_validate(row)

    # ── Regenerate full script ────────────────────────────────────────────────

    def regenerate_script(self, script_id: int) -> ScriptDetail:
        Script = self._get_model()
        row = self.db.query(Script).filter(Script.id == script_id).first()
        if not row:
            raise KeyError(f"Script {script_id} not found")

        from rag.script_writer import generate_script as _generate
        script_json = _generate(
            topic=row.topic, niche=row.niche, template=row.template,
            language=getattr(row, "language", "vietnamese"),
        )
        row.script_json = script_json
        row.status = "draft"
        self.db.commit()
        self.db.refresh(row)
        return ScriptDetail.model_validate(row)

    # ── Regenerate single scene ───────────────────────────────────────────────

    def regenerate_scene(self, script_id: int, scene_index: int) -> ScriptDetail:
        Script = self._get_model()
        row = self.db.query(Script).filter(Script.id == script_id).first()
        if not row:
            raise KeyError(f"Script {script_id} not found")

        script_json = row.script_json or {}
        scenes = script_json.get("scenes", [])
        if scene_index >= len(scenes):
            raise ValueError(f"Scene index {scene_index} out of range (script has {len(scenes)} scenes)")

        scene = scenes[scene_index]
        meta = script_json.get("meta", {})

        try:
            from rag.llm_router import get_router
            router_instance = get_router()
            prompt = (
                f"Rewrite only this scene for a {meta.get('template','tiktok_viral')} video "
                f"about '{meta.get('topic','')}' in niche '{meta.get('niche','')}'. "
                f"Return JSON with keys: narration, visual_hint. "
                f"Current scene type: {scene.get('type','body')}. "
                f"Keep duration: {scene.get('duration', 5)}s."
            )
            result = router_instance.generate(prompt)
            if isinstance(result, dict):
                scene["narration"] = result.get("narration", scene.get("narration"))
                scene["visual_hint"] = result.get("visual_hint", scene.get("visual_hint"))
        except Exception:
            pass  # Scene regeneration is best-effort

        scenes[scene_index] = scene
        script_json["scenes"] = scenes
        row.script_json = script_json
        self.db.commit()
        self.db.refresh(row)
        return ScriptDetail.model_validate(row)
