import logging
import os
from pathlib import Path

from console.backend.celery_app import celery_app
from console.backend.tasks.job_tracking import mark_job_completed, mark_job_failed, mark_job_progress
from console.backend.services.pipeline_service import emit_log

logger = logging.getLogger(__name__)


def _auto_generate_elevenlabs_music(db, script_id: int, niche: str, mood: str, duration_s: float) -> None:
    """Auto-generate ElevenLabs music track for a script if enabled in config and no library track exists."""
    import os
    import yaml
    from pathlib import Path
    from sqlalchemy import text

    cfg_path = Path(__file__).parents[3] / "config" / "pipeline_config.yaml"
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
    except Exception:
        return

    prod_cfg = cfg.get("production", {})
    if not prod_cfg.get("auto_music_elevenlabs", False):
        return

    output_format = prod_cfg.get("auto_music_elevenlabs_format", "mp3_44100_192")
    length_ms = prod_cfg.get("auto_music_elevenlabs_length_ms", 0) or int((duration_s or 60) * 1000)

    from console.backend.services.music_service import MusicService
    svc = MusicService(db)
    existing = svc.list_tracks(niche=niche, mood=mood, status="ready")
    if existing:
        track_id = existing[0]["id"]
        db.execute(
            text("UPDATE generated_scripts SET music_track_id = :tid WHERE id = :sid"),
            {"tid": track_id, "sid": script_id},
        )
        db.commit()
        return

    prompt = f"{mood or 'uplifting'} background music for a {niche or 'lifestyle'} video, {int(duration_s or 60)}s, instrumental"
    try:
        from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider, _ext_for_format
        provider = ElevenLabsProvider()
        plan = provider.create_plan(prompt, length_ms)
        audio_bytes = provider.compose(plan, output_format)

        MUSIC_DIR = Path(os.environ.get("MUSIC_PATH", "./assets/music"))
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)

        track = svc.create_pending(
            title=f"{niche or 'auto'} {mood or 'uplifting'} auto-generated",
            niches=[niche] if niche else [],
            moods=[mood] if mood else [],
            genres=[],
            is_vocal=False,
            volume=0.15,
            provider="elevenlabs",
            prompt=prompt,
        )
        track_id = track["id"]
        ext = _ext_for_format(output_format)
        dest = MUSIC_DIR / f"{track_id}{ext}"
        dest.write_bytes(audio_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready_with_plan(track_id, str(dest), duration, plan)

        db.execute(
            text("UPDATE generated_scripts SET music_track_id = :tid WHERE id = :sid"),
            {"tid": track_id, "sid": script_id},
        )
        db.commit()
        logger.info(f"[render] Auto-generated ElevenLabs track {track_id} for script {script_id}")
    except Exception as e:
        logger.warning(f"[render] Auto ElevenLabs music failed for script {script_id}: {e}")


@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.regenerate_tts_task", queue="render_q")
def regenerate_tts_task(self, script_id: int, scene_index: int):
    """Regenerate TTS audio for a specific scene."""
    from console.backend.database import SessionLocal

    self.update_state(state="PROGRESS", meta={"step": "tts", "scene": scene_index})
    db = SessionLocal()
    try:
        task_id = self.request.id
        job = mark_job_progress(
            db,
            task_id=task_id,
            job_type="tts",
            script_id=script_id,
            progress=20,
            details={"step": "tts", "scene_index": scene_index},
        )
        emit_log(job.id, "INFO", f"Regenerating TTS for scene {scene_index}...")

        from database.models import GeneratedScript
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        scenes = script.script_json.get("scenes", [])
        scene = scenes[scene_index]
        meta = script.script_json.get("meta", {})
        video_cfg = script.script_json.get("video", {})
        out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / str(script_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / f"audio_{scene_index}.wav"

        from pipeline.tts_router import generate_tts
        generate_tts(
            text=scene.get("narration", ""),
            voice_id=video_cfg.get("voice", "af_heart"),
            speed=float(video_cfg.get("voice_speed", 1.0)),
            language=meta.get("language", "vietnamese"),
            output_path=str(audio_path),
        )
        scene["audio_path"] = str(audio_path)
        scenes[scene_index] = scene
        script.script_json = {**script.script_json, "scenes": scenes}
        db.commit()
        emit_log(job.id, "INFO", f"TTS done → {audio_path}")
        mark_job_completed(
            db,
            task_id=task_id,
            job_type="tts",
            script_id=script_id,
            details={
                "step": "tts",
                "scene_index": scene_index,
                "audio_path": str(audio_path),
            },
        )
        return {"scene": scene_index, "audio_path": str(audio_path)}
    except Exception as exc:
        if 'job' in dir():
            emit_log(job.id, "ERROR", f"TTS failed: {exc}")
        mark_job_failed(
            db,
            task_id=self.request.id,
            job_type="tts",
            script_id=script_id,
            error=str(exc),
            details={"step": "tts", "scene_index": scene_index},
        )
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.render_video_task", queue="render_q")
def render_video_task(self, script_id: int):
    """Full production pipeline: compose → caption → render."""
    from console.backend.database import SessionLocal

    self.update_state(state="PROGRESS", meta={"step": "composing"})
    db = SessionLocal()
    try:
        task_id = self.request.id
        job = mark_job_progress(
            db,
            task_id=task_id,
            job_type="render",
            script_id=script_id,
            progress=10,
            details={"step": "composing"},
        )
        emit_log(job.id, "INFO", "Starting render pipeline: compose → captions → render")

        from database.models import GeneratedScript
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        script.status = "producing"
        db.commit()

        # Auto-generate ElevenLabs music if configured and no track assigned
        meta = (script.script_json or {}).get("meta", {})
        if not script.music_track_id:
            _auto_generate_elevenlabs_music(
                db=db,
                script_id=script_id,
                niche=meta.get("niche", ""),
                mood=meta.get("mood", "uplifting"),
                duration_s=meta.get("duration_s", 60.0),
            )
            db.refresh(script)

        # Step 1: Compose
        from pipeline.composer import compose_video
        self.update_state(state="PROGRESS", meta={"step": "composing"})
        raw_path, subtitles_burned = compose_video(script_id)
        emit_log(job.id, "INFO", f"Compose done → {raw_path}")
        mark_job_progress(
            db,
            task_id=task_id,
            job_type="render",
            script_id=script_id,
            progress=45,
            details={"step": "composing", "raw_path": str(raw_path)},
        )

        # Step 2: Captions
        # Skip if composer already burned subtitles into raw_video.
        # Run Whisper SRT if: (a) no subtitle_style set, or (b) subtitle_style set but
        # word timing was unavailable (e.g. ElevenLabs returned no alignment).
        subtitle_style = (script.script_json or {}).get("video", {}).get("subtitle_style")
        srt_path = None
        if not subtitles_burned:
            from pipeline.caption_gen import generate_captions
            self.update_state(state="PROGRESS", meta={"step": "captions"})
            srt_path = generate_captions(raw_path)
            emit_log(job.id, "INFO", f"Captions done → {srt_path}")
            mark_job_progress(
                db,
                task_id=task_id,
                job_type="render",
                script_id=script_id,
                progress=70,
                details={"step": "captions", "raw_path": str(raw_path), "srt_path": str(srt_path)},
            )
        else:
            emit_log(job.id, "INFO", f"Subtitle style '{subtitle_style}' burned in by composer — skipping Whisper")
            mark_job_progress(
                db,
                task_id=task_id,
                job_type="render",
                script_id=script_id,
                progress=70,
                details={"step": "captions_skipped", "subtitle_style": subtitle_style},
            )

        # Step 3: Render
        from pipeline.renderer import render_final
        self.update_state(state="PROGRESS", meta={"step": "rendering"})
        emit_log(job.id, "INFO", "Rendering final video...")
        final_path = render_final(raw_video_path=raw_path, srt_path=srt_path)

        script.output_path = str(final_path)
        script.status = "completed"
        db.commit()
        emit_log(job.id, "INFO", f"Render complete → {final_path}")
        mark_job_completed(
            db,
            task_id=task_id,
            job_type="render",
            script_id=script_id,
            details={
                "step": "rendering",
                "raw_path": str(raw_path),
                "srt_path": str(srt_path),
                "output_path": str(final_path),
            },
        )
        logger.info(f"Render complete: {final_path}")
        return {"script_id": script_id, "output": str(final_path), "srt_path": str(srt_path)}
    except Exception as e:
        db.rollback()
        if 'job' in dir():
            emit_log(job.id, "ERROR", f"Render failed: {e}")
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if script:
            script.status = "approved"  # Roll back to approved so editor can retry
            db.commit()
        mark_job_failed(
            db,
            task_id=self.request.id,
            job_type="render",
            script_id=script_id,
            error=str(e),
            details={"step": "rendering"},
        )
        raise
    finally:
        db.close()
