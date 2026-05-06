"""Celery tasks for music generation — Suno (async polling) and Lyria (sync call)."""
import logging
import os
import time
from pathlib import Path

import requests

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(os.environ.get("MUSIC_PATH", "./assets/music"))
SUNO_POLL_INTERVAL = 15   # seconds between polls
SUNO_MAX_ATTEMPTS  = 20   # ~5 minutes total


@celery_app.task(bind=True, name="console.backend.tasks.music_tasks.generate_suno_music_task", queue="render_q")
def generate_suno_music_task(self, track_id: int):
    """Submit to Suno, poll until ready, download MP3, update DB."""
    from console.backend.database import SessionLocal
    from console.backend.services.music_service import MusicService
    from pipeline.music_providers.suno_provider import SunoProvider

    db = SessionLocal()
    try:
        svc = MusicService(db)
        track = svc.get_track(track_id)

        provider = SunoProvider()
        suno_task_id = provider.submit(
            prompt=track["generation_prompt"] or "",
            style=", ".join(track["genres"]) if track["genres"] else "pop",
            title=track["title"],
            instrumental=not track["is_vocal"],
        )
        svc.set_provider_task_id(track_id, suno_task_id)
        logger.info(f"[music_tasks] Suno task submitted: {suno_task_id}")

        # Poll loop
        audio_url = None
        for attempt in range(SUNO_MAX_ATTEMPTS):
            time.sleep(SUNO_POLL_INTERVAL)
            self.update_state(state="PROGRESS", meta={"attempt": attempt + 1, "suno_task_id": suno_task_id})
            try:
                audio_url = provider.poll(suno_task_id)
                if audio_url:
                    break
            except RuntimeError as e:
                logger.error(f"[music_tasks] Suno failed: {e}")
                svc.mark_failed(track_id)
                raise

        if not audio_url:
            logger.warning(f"[music_tasks] Suno timed out for track {track_id}")
            svc.mark_failed(track_id)
            return {"status": "failed", "track_id": track_id}

        # Download MP3
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        dest = MUSIC_DIR / f"{track_id}.mp3"
        resp = requests.get(audio_url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready(track_id, str(dest), duration)
        logger.info(f"[music_tasks] Suno track {track_id} ready: {dest}")
        return {"status": "ready", "track_id": track_id, "file_path": str(dest)}

    except Exception as exc:
        try:
            MusicService(db).mark_failed(track_id)
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="console.backend.tasks.music_tasks.generate_lyria_music_task", queue="render_q")
def generate_lyria_music_task(self, track_id: int):
    """Generate music via Lyria (synchronous API call), save to disk, update DB."""
    import subprocess
    import tempfile
    from console.backend.database import SessionLocal
    from console.backend.services.music_service import MusicService
    from pipeline.music_providers.lyria_provider import LyriaProvider, LYRIA_MODELS

    db = SessionLocal()
    try:
        svc = MusicService(db)
        track = svc.get_track(track_id)

        # provider is 'lyria-clip' or 'lyria-pro' — map to model string
        model_key = track["provider"]  # 'lyria-clip' or 'lyria-pro'
        model_name = LYRIA_MODELS.get(model_key, "lyria-3-clip-preview")

        provider = LyriaProvider()
        audio_bytes, mime_type = provider.generate(
            prompt=track["generation_prompt"] or "",
            model=model_name,
            is_vocal=track["is_vocal"],
        )

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        dest = MUSIC_DIR / f"{track_id}.mp3"

        # Lyria returns PCM/WAV audio — convert to MP3 via ffmpeg for browser compatibility
        is_pcm = "pcm" in mime_type.lower() or "L16" in mime_type
        is_wav = "wav" in mime_type.lower()

        if is_pcm and not is_wav:
            # Raw L16 PCM — need sample rate from mime type e.g. "audio/L16;rate=44100"
            rate = 44100
            for part in mime_type.split(";"):
                if "rate=" in part:
                    try:
                        rate = int(part.split("=")[1].strip())
                    except ValueError:
                        pass
            with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            subprocess.run(
                ["ffmpeg", "-y", "-f", "s16le", "-ar", str(rate), "-ac", "1",
                 "-i", tmp_path, str(dest)],
                check=True, capture_output=True,
            )
        elif is_wav or not dest.suffix:
            # WAV or unknown — let ffmpeg figure it out
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_path, str(dest)],
                check=True, capture_output=True,
            )
        else:
            # Already MP3 or other browser-compatible format
            dest.write_bytes(audio_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready(track_id, str(dest), duration)
        logger.info(f"[music_tasks] Lyria track {track_id} ready: {dest} ({duration:.1f}s)")
        return {"status": "ready", "track_id": track_id, "file_path": str(dest)}

    except Exception as exc:
        try:
            MusicService(db).mark_failed(track_id)
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="console.backend.tasks.music_tasks.generate_elevenlabs_music_task",
    queue="render_q",
)
def generate_elevenlabs_music_task(
    self,
    track_id: int,
    composition_plan: dict,
    output_format: str = "mp3_44100_192",
    respect_sections_durations: bool = True,
):
    """Generate music via ElevenLabs compose API, save to disk, update DB."""
    from console.backend.database import SessionLocal
    from console.backend.services.music_service import MusicService
    from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider, _ext_for_format

    db = SessionLocal()
    try:
        svc = MusicService(db)
        provider = ElevenLabsProvider()

        audio_bytes = provider.compose(
            plan=composition_plan,
            output_format=output_format,
            respect_sections_durations=respect_sections_durations,
        )

        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        ext = _ext_for_format(output_format)
        dest = MUSIC_DIR / f"{track_id}{ext}"
        dest.write_bytes(audio_bytes)

        from pipeline.music_providers import probe_audio_duration
        duration = probe_audio_duration(str(dest))
        svc.mark_ready_with_plan(track_id, str(dest), duration, composition_plan)
        logger.info(f"[music_tasks] ElevenLabs track {track_id} ready: {dest} ({duration:.1f}s)")
        return {"status": "ready", "track_id": track_id, "file_path": str(dest)}

    except Exception:
        try:
            MusicService(db).mark_failed(track_id)
        except Exception:
            pass
        raise
    finally:
        db.close()

