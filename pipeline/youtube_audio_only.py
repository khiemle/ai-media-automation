"""Audio-only preview rendering for YouTube videos — fast, no video encoding."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def render_audio_preview(video, output_path: Path, db, start_s: float = 0.0, end_s: float | None = None) -> None:
    """Render audio-only preview WAV for [start_s, end_s) of the video.

    Same mix as the final render — multi-music playlist + random SFX pool +
    existing 3-layer SFX overrides. No video encoding.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    from pipeline.youtube_ffmpeg import (
        _build_music_playlist_wav,
        _build_sfx_pool_wav,
        resolve_sfx_layers,
        _run_ffmpeg,
    )

    full_duration_s = int((video.target_duration_h or 3.0) * 3600)
    if end_s is None:
        end_s = full_duration_s
    target_dur = int(end_s - start_s)
    if target_dur <= 0:
        raise ValueError(f"Window has non-positive duration: [{start_s}, {end_s})")

    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-render music + SFX (these are exact-duration WAVs)
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir)
    sfx_wav   = _build_sfx_pool_wav(video, db, target_dur, start_s, output_dir)

    # Existing 3-layer SFX (looped at runtime)
    sfx_layers = resolve_sfx_layers(video, db)

    audio_inputs: list[tuple[str, float, bool]] = []  # (path, volume, needs_loop)
    if music_wav:
        audio_inputs.append((music_wav, 1.0, False))
    if sfx_wav:
        audio_inputs.append((sfx_wav, 1.0, False))
    for path, vol in sfx_layers:
        audio_inputs.append((path, vol, True))

    if not audio_inputs:
        raise RuntimeError("No audio content to compose (no music, no SFX)")

    cmd = ["ffmpeg", "-y"]
    for path, _vol, needs_loop in audio_inputs:
        if needs_loop:
            cmd += ["-stream_loop", "-1", "-i", path]
        else:
            cmd += ["-i", path]

    parts = []
    for i, (_p, vol, _) in enumerate(audio_inputs):
        parts.append(f"[{i}:a]volume={vol}[a{i}]")
    if len(audio_inputs) == 1:
        audio_map = "[a0]"
    else:
        labels = "".join(f"[a{i}]" for i in range(len(audio_inputs)))
        parts.append(f"{labels}amix=inputs={len(audio_inputs)}:duration=first:normalize=0[aout]")
        audio_map = "[aout]"

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", audio_map,
        "-t", str(target_dur),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        "-vn",
        str(output_path),
    ]

    logger.info("ffmpeg audio-only cmd (window [%s,%s)): %s", start_s, end_s, " ".join(cmd))
    _run_ffmpeg(cmd, max(120, target_dur + 60))
