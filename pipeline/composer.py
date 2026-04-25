"""
Scene Composer — assembles per-scene assets into raw_video.mp4 using MoviePy.
Parallel per-scene processing (TTS + asset + overlay), then sequential assembly.
"""
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_PATH    = os.environ.get("OUTPUT_PATH", "./assets/output")
MUSIC_PATH     = os.environ.get("MUSIC_PATH",  "./assets/music")
MUSIC_VOLUME   = 0.08
MAX_WORKERS    = int(os.environ.get("COMPOSE_WORKERS", "4"))
TARGET_W, TARGET_H = 1080, 1920
TARGET_FPS     = 30


def compose_video(script_id: int) -> Path:
    """
    Full composition pipeline for a script:
    1. Load script from DB
    2. For each scene: TTS + asset resolver + overlay builder (parallel)
    3. MoviePy: composite scenes → concatenate → mix music
    4. Write raw_video.mp4

    Returns path to raw_video.mp4
    """
    from database.connection import get_session
    from database.models import GeneratedScript

    db = get_session()
    try:
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")
        script_json = script.script_json
    finally:
        db.close()

    meta   = script_json.get("meta", {})
    scenes = script_json.get("scenes", [])
    video  = script_json.get("video", {})

    # Output directory per script
    out_dir = Path(OUTPUT_PATH) / f"script_{script_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Parallel per-scene asset generation ──────────────────────────
    scene_assets: dict[int, dict] = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_process_scene, scene, meta, out_dir, i): i
            for i, scene in enumerate(scenes)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                scene_assets[idx] = future.result()
            except Exception as e:
                logger.error(f"[Composer] Scene {idx} failed: {e}")
                scene_assets[idx] = _fallback_scene_assets(scenes[idx], out_dir, idx)

    # ── Phase 2: MoviePy assembly ─────────────────────────────────────────────
    raw_video_path = out_dir / "raw_video.mp4"
    _assemble(scenes, scene_assets, meta, video, raw_video_path)

    # Update output_path in DB
    db = get_session()
    try:
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if script:
            script.output_path = str(raw_video_path)
            db.commit()
    finally:
        db.close()

    logger.info(f"[Composer] raw_video.mp4 → {raw_video_path}")
    return raw_video_path


def _process_scene(scene: dict, meta: dict, out_dir: Path, idx: int) -> dict:
    """Generate TTS audio, video clip, and text overlay for one scene."""
    scene_id = f"script_scene{idx}"
    duration = float(scene.get("duration", 5))

    # 1. TTS
    audio_path = out_dir / f"audio_{idx}.wav"
    try:
        from pipeline.tts_router import generate_tts
        generate_tts(
            text=scene.get("narration", ""),
            voice_id=meta.get("voice", "af_heart"),
            speed=float(meta.get("voice_speed", 1.1)),
            language=meta.get("language", "vietnamese"),
            output_path=str(audio_path),
        )
    except Exception as e:
        logger.warning(f"[Composer] Scene {idx} TTS failed: {e}")
        audio_path = None

    # 2. Video clip
    clip_path: Path | None = None
    try:
        from pipeline.asset_resolver import resolve
        clip_path = resolve(scene, meta)
    except Exception as e:
        logger.warning(f"[Composer] Scene {idx} asset resolver failed: {e}")

    # 3. Text overlay
    overlay_path = out_dir / f"overlay_{idx}.png"
    try:
        from pipeline.overlay_builder import build_overlay
        build_overlay(scene, output_path=str(overlay_path))
    except Exception as e:
        logger.warning(f"[Composer] Scene {idx} overlay failed: {e}")
        overlay_path = None

    return {
        "scene":        scene,
        "duration":     duration,
        "audio_path":   str(audio_path) if audio_path and audio_path.exists() else None,
        "clip_path":    str(clip_path)  if clip_path and clip_path.exists() else None,
        "overlay_path": str(overlay_path) if overlay_path and overlay_path.exists() else None,
    }


def _assemble(
    scenes:       list[dict],
    scene_assets: dict[int, dict],
    meta:         dict,
    video_cfg:    dict,
    output_path:  Path,
):
    """Assemble all scene clips into raw_video.mp4 using MoviePy."""
    try:
        from moviepy import (
            VideoFileClip, AudioFileClip, ImageClip,
            ColorClip, concatenate_videoclips, CompositeVideoClip,
        )
    except ImportError:
        logger.error("moviepy not installed. Run: pip install moviepy")
        raise

    composed_clips = []

    for idx in range(len(scenes)):
        assets   = scene_assets.get(idx, {})
        duration = assets.get("duration", 5)

        # Base video clip
        if assets.get("clip_path") and Path(assets["clip_path"]).exists():
            try:
                clip = VideoFileClip(assets["clip_path"]).with_subclip(0, duration)
                # Ensure correct size
                if clip.w != TARGET_W or clip.h != TARGET_H:
                    clip = clip.resized((TARGET_W, TARGET_H))
            except Exception as e:
                logger.warning(f"[Composer] Scene {idx} clip load failed: {e}")
                clip = ColorClip((TARGET_W, TARGET_H), color=(0, 0, 0), duration=duration)
        else:
            clip = ColorClip((TARGET_W, TARGET_H), color=(10, 10, 15), duration=duration)

        clip = clip.with_duration(duration)

        # Layer overlay PNG
        layers = [clip]
        if assets.get("overlay_path") and Path(assets["overlay_path"]).exists():
            try:
                overlay = ImageClip(assets["overlay_path"]).with_duration(duration)
                layers.append(overlay)
            except Exception as e:
                logger.debug(f"[Composer] Scene {idx} overlay layer failed: {e}")

        scene_clip = CompositeVideoClip(layers, size=(TARGET_W, TARGET_H)).with_duration(duration)

        # Set narration audio
        if assets.get("audio_path") and Path(assets["audio_path"]).exists():
            try:
                audio = AudioFileClip(assets["audio_path"])
                # Trim or pad audio to match scene duration
                if audio.duration > duration:
                    audio = audio.with_subclip(0, duration)
                scene_clip = scene_clip.with_audio(audio)
            except Exception as e:
                logger.warning(f"[Composer] Scene {idx} audio failed: {e}")

        # Apply transition
        transition = scenes[idx].get("transition", "cut")
        if transition == "fade" and idx > 0:
            scene_clip = scene_clip.with_effects([])  # MoviePy 2.x transitions handled at concat

        composed_clips.append(scene_clip)

    if not composed_clips:
        raise ValueError("No scenes could be composed")

    # Concatenate all scenes
    final = concatenate_videoclips(composed_clips, method="chain")

    # Mix background music (if available)
    music_track = _select_music(meta.get("mood", "uplifting"), meta.get("niche", "lifestyle"), final.duration)
    if music_track:
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
            music = AudioFileClip(music_track).with_volume_scaled(MUSIC_VOLUME)
            if music.duration < final.duration:
                # Loop music
                import math
                loops = math.ceil(final.duration / music.duration)
                from moviepy import concatenate_audioclips
                music = concatenate_audioclips([music] * loops).with_subclip(0, final.duration)
            else:
                music = music.with_subclip(0, final.duration)

            if final.audio:
                mixed = CompositeAudioClip([final.audio, music])
                final = final.with_audio(mixed)
            else:
                final = final.with_audio(music)
        except Exception as e:
            logger.warning(f"[Composer] Music mix failed: {e}")

    # Write raw video (libx264 fast, will be re-encoded by renderer)
    final.write_videofile(
        str(output_path),
        fps=TARGET_FPS,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        logger=None,
    )


def _select_music(mood: str, niche: str, duration: float) -> str | None:
    """Find a background music track from the local Suno library."""
    MOOD_MAP = {
        "uplifting":  ["uplifting", "positive"],
        "calm_focus": ["calm", "focus", "ambient"],
        "energetic":  ["energetic", "dynamic"],
        "trust":      ["trust", "calm", "professional"],
    }
    search_terms = MOOD_MAP.get(mood, ["uplifting"])

    music_dir = Path(MUSIC_PATH)
    if not music_dir.exists():
        return None

    for term in search_terms:
        for f in music_dir.glob(f"*{term}*.mp3"):
            return str(f)
    # Fallback: any mp3
    mp3s = list(music_dir.glob("*.mp3"))
    return str(mp3s[0]) if mp3s else None


def _fallback_scene_assets(scene: dict, out_dir: Path, idx: int) -> dict:
    """Return minimal assets dict for a scene that failed processing."""
    return {
        "scene":        scene,
        "duration":     float(scene.get("duration", 5)),
        "audio_path":   None,
        "clip_path":    None,
        "overlay_path": None,
    }
