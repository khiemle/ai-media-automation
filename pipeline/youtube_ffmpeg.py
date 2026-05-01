"""Shared ffmpeg helpers for YouTube long-form and portrait-short rendering."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

QUALITY_SCALE = {
    "4K":    "3840:2160",
    "1080p": "1920:1080",
}
DEFAULT_SCALE = "1920:1080"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def resolve_visual(video, db) -> str | None:
    """Return the file path of the linked visual asset, or None."""
    if not video.visual_asset_id:
        return None
    try:
        from console.backend.models.video_asset import VideoAsset
        asset = db.get(VideoAsset, video.visual_asset_id)
        if asset and asset.file_path:
            return asset.file_path
    except Exception as exc:
        logger.warning("Could not load visual asset %s: %s", video.visual_asset_id, exc)
    return None


def resolve_audio(video, db) -> str | None:
    """Return the file path of the linked music track, or None."""
    if not video.music_track_id:
        return None
    try:
        from database.models import MusicTrack
        track = db.get(MusicTrack, video.music_track_id)
        if track and track.file_path:
            return track.file_path
    except Exception as exc:
        logger.warning("Could not load music track %s: %s", video.music_track_id, exc)
    return None


def resolve_sfx_layers(video, db) -> list[tuple[str, float]]:
    """Resolve SFX layer file paths from sfx_overrides (foreground/midground/background keys)."""
    from console.backend.models.sfx_asset import SfxAsset

    overrides = video.sfx_overrides or {}
    results = []
    for layer_name in ("foreground", "midground", "background"):
        layer = overrides.get(layer_name)
        if not layer:
            continue
        asset_id = layer.get("asset_id")
        volume = float(layer.get("volume", 0.5))
        if not asset_id:
            continue
        try:
            asset = db.get(SfxAsset, int(asset_id))
            if asset and asset.file_path and Path(asset.file_path).is_file():
                results.append((asset.file_path, volume))
            else:
                logger.warning("SFX asset %s not found or missing file on disk", asset_id)
        except Exception as exc:
            logger.warning("Could not resolve SFX asset %s: %s", asset_id, exc)
    return results


def _escape_drawtext(text: str) -> str:
    """Escape text for use in an ffmpeg drawtext filter value."""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _build_audio_filter(audio_inputs: list[tuple[str, float]], vf: str) -> tuple[list[str], list[str]]:
    """Return (filter_complex_parts, map_args) for the given audio inputs and video filter chain."""
    parts: list[str] = []
    audio_labels: list[str] = []
    for i, (_, vol) in enumerate(audio_inputs):
        parts.append(f"[{i + 1}:a]volume={vol}[a{i}]")
        audio_labels.append(f"[a{i}]")
    parts.append(f"[0:v]{vf}[vout]")

    if len(audio_inputs) == 1:
        return parts, ["-map", "[vout]", "-map", "[a0]"]

    mix_in = "".join(audio_labels)
    parts.append(
        f"{mix_in}amix=inputs={len(audio_inputs)}:duration=first:normalize=0[aout]"
    )
    return parts, ["-map", "[vout]", "-map", "[aout]"]


def _run_ffmpeg(cmd: list[str], timeout: float) -> None:
    timeout = max(timeout, 120)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(result.stderr or '')[-800:]}")


def render_landscape(video, output_path: Path, db) -> None:
    """Render a landscape long-form YouTube video."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    duration_s = int((video.target_duration_h or 3.0) * 3600)
    scale = QUALITY_SCALE.get(getattr(video, "output_quality", None) or "1080p", DEFAULT_SCALE)
    w, h = scale.split(":")

    visual_path = resolve_visual(video, db)
    music_path = resolve_audio(video, db)
    sfx_layers = resolve_sfx_layers(video, db)
    is_image = visual_path is not None and Path(visual_path).suffix.lower() in IMAGE_EXTS

    audio_inputs: list[tuple[str, float]] = []
    if music_path and Path(music_path).is_file():
        audio_inputs.append((music_path, 1.0))
    audio_inputs.extend(sfx_layers)

    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
    )

    cmd = ["ffmpeg", "-y"]

    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    if audio_inputs:
        for path, _ in audio_inputs:
            cmd += ["-stream_loop", "-1", "-i", path]
        parts, map_args = _build_audio_filter(audio_inputs, vf)
        cmd += ["-filter_complex", ";".join(parts)] + map_args
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-vf", vf]

    cmd += ["-t", str(duration_s)]

    if is_image:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "18"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]

    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart",
            str(output_path)]

    logger.info("ffmpeg landscape cmd: %s", " ".join(cmd))
    _run_ffmpeg(cmd, duration_s * 4)
