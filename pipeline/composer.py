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
        music_track_id = getattr(script, "music_track_id", None)
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
            executor.submit(_process_scene, scene, meta, video, out_dir, i): i
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
    _assemble(scenes, scene_assets, meta, video, raw_video_path, music_track_id=music_track_id)

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


def _process_scene(scene: dict, meta: dict, video_cfg: dict, out_dir: Path, idx: int) -> dict:
    """Generate TTS audio, video clip, and text overlay for one scene."""
    scene_id = f"script_scene{idx}"
    duration = float(scene.get("duration", 5))

    # 1. TTS
    audio_path = out_dir / f"audio_{idx}.wav"
    word_timing: list[dict] | None = None
    subtitle_style = video_cfg.get("subtitle_style") or ""
    try:
        if subtitle_style:
            from pipeline.tts_router import generate_tts_with_timing
            audio_path, word_timing = generate_tts_with_timing(
                text=scene.get("narration", ""),
                voice_id=video_cfg.get("voice", ""),
                speed=float(video_cfg.get("voice_speed", 1.1)),
                language=meta.get("language", "vietnamese"),
                output_path=str(audio_path),
                tts_service=video_cfg.get("tts_service", ""),
            )
        else:
            from pipeline.tts_router import generate_tts
            generate_tts(
                text=scene.get("narration", ""),
                voice_id=video_cfg.get("voice", ""),
                speed=float(video_cfg.get("voice_speed", 1.1)),
                language=meta.get("language", "vietnamese"),
                output_path=str(audio_path),
                tts_service=video_cfg.get("tts_service", ""),
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
        "word_timing":  word_timing,
    }


def _build_subtitle_clips(
    scene_word_timings: list[tuple[float, list[dict]]],
    subtitle_style: str,
) -> list:
    """
    Build MoviePy TextClip overlays from per-scene word timing data.
    Returns a list of positioned, timed TextClip objects ready for compositing.
    No libass or ffmpeg subtitle filter needed.
    """
    try:
        from moviepy import TextClip
        from pipeline.subtitle_builder import SUBTITLE_STYLES, _ass_color_to_rgb
    except ImportError as exc:
        logger.warning(f"[Composer] Subtitle clips unavailable: {exc}")
        return []

    style = SUBTITLE_STYLES.get(subtitle_style, SUBTITLE_STYLES["bold_center"])
    wpe           = style.get("words_per_entry", 1)
    font          = style.get("font", "Arial")
    font_size     = style.get("font_size", 80)
    primary_rgb   = _ass_color_to_rgb(style.get("primary_color", "&H00FFFFFF"))
    outline_rgb   = _ass_color_to_rgb(style.get("outline_color", "&H00000000"))
    outline_width = style.get("outline_width", 0)
    uppercase     = style.get("uppercase", False)
    margin_v      = style.get("margin_v", 200)

    # Relative vertical position: fraction from top (0=top, 1=bottom)
    y_pos = max(0.0, min(0.95, 1.0 - (margin_v + font_size * 1.2) / TARGET_H))

    clips = []
    for scene_offset, word_list in scene_word_timings:
        if not word_list:
            continue
        for i in range(0, len(word_list), wpe):
            chunk = word_list[i:i + wpe]
            if not chunk:
                continue
            text = " ".join(w["word"] for w in chunk)
            if uppercase:
                text = text.upper()
            if not text.strip():
                continue
            abs_start = max(0.0, scene_offset + chunk[0]["start"])
            abs_end   = scene_offset + chunk[-1]["end"]
            if abs_end <= abs_start:
                continue
            try:
                txt = TextClip(
                    text=text,
                    font=font,
                    font_size=font_size,
                    color=primary_rgb,
                    stroke_color=outline_rgb if outline_width > 0 else None,
                    stroke_width=outline_width if outline_width > 0 else 0,
                ).with_start(abs_start).with_end(abs_end).with_position(
                    ("center", y_pos), relative=True
                )
                clips.append(txt)
            except Exception as exc:
                logger.warning(f"[Composer] TextClip error for '{text}': {exc}")

    return clips


def _assemble(
    scenes:         list[dict],
    scene_assets:   dict[int, dict],
    meta:           dict,
    video_cfg:      dict,
    output_path:    Path,
    music_track_id: int | None = None,
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
                raw_clip = VideoFileClip(assets["clip_path"])
                clip_end = min(duration, raw_clip.duration)
                if raw_clip.duration < duration - 0.1:
                    logger.warning(
                        f"[Composer] Scene {idx} clip is {raw_clip.duration:.1f}s, "
                        f"scene needs {duration:.1f}s — clamping to clip length"
                    )
                clip = raw_clip.subclipped(0, clip_end)
                # Ensure correct size
                if clip.w != TARGET_W or clip.h != TARGET_H:
                    clip = clip.resized((TARGET_W, TARGET_H))
            except Exception as e:
                logger.warning(f"[Composer] Scene {idx} clip load failed ({assets['clip_path']}): {e}")
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
        # Strip any alpha mask inherited from the overlay — without this, the mask
        # (nearly 0 = transparent) would cause concatenate_videoclips to render black frames.
        scene_clip = scene_clip.with_opacity(1.0)
        scene_clip.mask = None

        # Set narration audio
        if assets.get("audio_path") and Path(assets["audio_path"]).exists():
            try:
                audio = AudioFileClip(assets["audio_path"])
                # Trim or pad audio to match scene duration
                if audio.duration > duration:
                    audio = audio.subclipped(0, duration)
                scene_clip = scene_clip.with_audio(audio)
            except Exception as e:
                logger.warning(f"[Composer] Scene {idx} audio failed: {e}")

        composed_clips.append(scene_clip)

    if not composed_clips:
        raise ValueError("No scenes could be composed")

    # Concatenate all scenes
    final = concatenate_videoclips(composed_clips, method="compose")

    # Mix background music (if available)
    _assigned_track = None
    _track_volume = MUSIC_VOLUME
    if music_track_id:
        try:
            from database.connection import get_session as _gs
            from database.models import MusicTrack
            _db2 = _gs()
            try:
                _t = _db2.query(MusicTrack).filter(MusicTrack.id == music_track_id, MusicTrack.generation_status == "ready").first()
                if _t and _t.file_path and Path(_t.file_path).exists():
                    _assigned_track = _t.file_path
                    _track_volume = float(_t.volume or MUSIC_VOLUME)
            finally:
                _db2.close()
        except Exception as _e:
            logger.warning(f"[Composer] Could not load assigned music track {music_track_id}: {_e}")

    music_disabled = video_cfg.get("music_disabled", False) if video_cfg else False
    music_track_path = None
    if not music_disabled:
        music_track_path = _assigned_track or _select_music(
            meta.get("mood", "uplifting"), meta.get("niche", "lifestyle"), final.duration
        )
    if music_track_path:
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
            music = AudioFileClip(music_track_path).with_volume_scaled(_track_volume)
            if music.duration < final.duration:
                # Loop music
                import math
                loops = math.ceil(final.duration / music.duration)
                from moviepy import concatenate_audioclips
                music = concatenate_audioclips([music] * loops).subclipped(0, final.duration)
            else:
                music = music.subclipped(0, final.duration)

            if final.audio:
                mixed = CompositeAudioClip([final.audio, music])
                final = final.with_audio(mixed)
            else:
                final = final.with_audio(music)

            # Increment usage count for DB-tracked tracks
            if music_track_id and _assigned_track:
                try:
                    from database.connection import get_session as _gs3
                    from database.models import MusicTrack
                    _db3 = _gs3()
                    try:
                        _mt = _db3.query(MusicTrack).filter(MusicTrack.id == music_track_id).first()
                        if _mt:
                            _mt.usage_count = (_mt.usage_count or 0) + 1
                            _db3.commit()
                    finally:
                        _db3.close()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[Composer] Music mix failed: {e}")

    # Burn-in subtitles via MoviePy TextClip (no libass required)
    subtitle_style = (video_cfg.get("subtitle_style") or "") if video_cfg else ""
    if subtitle_style:
        scene_offsets = []
        offset = 0.0
        for idx in range(len(scenes)):
            scene_offsets.append(offset)
            offset += scene_assets.get(idx, {}).get("duration", 5)
        scene_word_timings = [
            (scene_offsets[idx], scene_assets.get(idx, {}).get("word_timing") or [])
            for idx in range(len(scenes))
        ]
        subtitle_clips = _build_subtitle_clips(scene_word_timings, subtitle_style)
        if subtitle_clips:
            logger.info(f"[Composer] Compositing {len(subtitle_clips)} subtitle entries via MoviePy")
            audio = final.audio
            final = CompositeVideoClip([final] + subtitle_clips)
            if audio:
                final = final.with_audio(audio)
        else:
            logger.info("[Composer] No word timing data available; subtitles skipped")

    # Write raw video (libx264 fast, will be re-encoded by renderer)
    final.write_videofile(
        str(output_path),
        fps=TARGET_FPS,
        codec="libx264",
        audio_codec="aac",
        audio_fps=44100,
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
        "word_timing":  None,
    }
