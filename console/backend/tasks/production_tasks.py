import logging
from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.regenerate_tts_task", queue="render_q")
def regenerate_tts_task(self, script_id: int, scene_index: int):
    """Regenerate TTS audio for a specific scene."""
    from console.backend.database import SessionLocal

    self.update_state(state="PROGRESS", meta={"step": "tts", "scene": scene_index})
    db = SessionLocal()
    try:
        from database.models import GeneratedScript
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        scenes = script.script_json.get("scenes", [])
        scene = scenes[scene_index]
        voice_cfg = script.script_json.get("video", {})

        from pipeline.tts_engine import generate_tts
        audio_path = generate_tts(
            text=scene.get("narration", ""),
            voice=voice_cfg.get("voice", "af_heart"),
            speed=voice_cfg.get("voice_speed", 1.0),
        )
        scene["audio_path"] = str(audio_path)
        scenes[scene_index] = scene
        script.script_json = {**script.script_json, "scenes": scenes}
        db.commit()
        return {"scene": scene_index, "audio_path": str(audio_path)}
    finally:
        db.close()


@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.render_video_task", queue="render_q")
def render_video_task(self, script_id: int):
    """Full production pipeline: compose → caption → render."""
    from console.backend.database import SessionLocal

    self.update_state(state="PROGRESS", meta={"step": "composing"})
    db = SessionLocal()
    try:
        from database.models import GeneratedScript
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        script.status = "producing"
        db.commit()

        # Step 1: Compose
        from pipeline.composer import compose_video
        self.update_state(state="PROGRESS", meta={"step": "composing"})
        raw_path = compose_video(script_id)

        # Step 2: Captions
        from pipeline.caption_gen import generate_captions
        self.update_state(state="PROGRESS", meta={"step": "captions"})
        generate_captions(raw_path)

        # Step 3: Render
        from pipeline.renderer import render_final
        self.update_state(state="PROGRESS", meta={"step": "rendering"})
        final_path = render_final(raw_path)

        script.status = "completed"
        db.commit()
        logger.info(f"Render complete: {final_path}")
        return {"script_id": script_id, "output": str(final_path)}
    except Exception as e:
        db.rollback()
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if script:
            script.status = "approved"  # Roll back to approved so editor can retry
            db.commit()
        raise
    finally:
        db.close()
