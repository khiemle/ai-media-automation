import logging
from console.backend.celery_app import celery_app
from console.backend.database import SessionLocal
from console.backend.services.script_service import ScriptService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="console.backend.tasks.script_tasks.generate_script_task", queue="script_q")
def generate_script_task(self, topic: str, niche: str, template: str, context_video_ids: list = None, language: str = "vietnamese"):
    """Generate a script via the RAG pipeline and store it in the DB."""
    self.update_state(state="PROGRESS", meta={"step": "generating"})

    db = SessionLocal()
    try:
        svc = ScriptService(db)
        script = svc.generate_script(
            topic=topic,
            niche=niche,
            template=template,
            source_video_ids=context_video_ids,
            user_id=0,  # system user
            language=language,
        )
        return {"script_id": script.id, "status": "draft"}
    finally:
        db.close()
