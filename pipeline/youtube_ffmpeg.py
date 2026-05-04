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


def resolve_visual_playlist(video, db):
    """Return the ordered list of VideoAsset rows whose files exist on disk.

    Empty list means "use legacy single-asset path" (caller falls back to resolve_visual).
    """
    ids = list(getattr(video, "visual_asset_ids", None) or [])
    if not ids:
        return []
    from console.backend.models.video_asset import VideoAsset

    rows = db.query(VideoAsset).filter(VideoAsset.id.in_(ids)).all()
    by_id = {r.id: r for r in rows}
    out = []
    for aid in ids:
        a = by_id.get(aid)
        if a and a.file_path and Path(a.file_path).is_file():
            out.append(a)
        else:
            logger.warning("Visual asset %s missing or file not on disk; skipping in playlist", aid)
    return out


def _build_visual_segment(
    playlist,
    durations: list[float],
    loop_mode: str,
    w: int,
    h: int,
    target_dur_s: int,
    output_dir: Path,
) -> Path | None:
    """Render the visual playlist to a single concatenated MP4 (no audio), then loop to target_dur_s.

    Returns the file path of the looped concat, or None if playlist was empty.
    """
    if not playlist:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: render each item to a normalized clip (same scale, fps, codec, no audio)
    item_paths: list[Path] = []
    for i, asset in enumerate(playlist):
        is_image = asset.asset_type == "still_image"
        # Resolve per-item duration: 0 in concat_loop+video means "native length"
        item_dur = durations[i] if i < len(durations) else 0.0
        out = output_dir / f"vseg_{i}.mp4"

        cmd = ["ffmpeg", "-y"]
        if is_image:
            cmd += ["-loop", "1", "-t", str(item_dur or 3.0), "-i", asset.file_path]
        elif loop_mode == "per_clip" and item_dur > 0:
            # Loop the video so it fills the slot; -t bounds it
            cmd += ["-stream_loop", "-1", "-t", str(item_dur), "-i", asset.file_path]
        elif loop_mode == "concat_loop" and item_dur > 0:
            # Trim to user-specified duration
            cmd += ["-t", str(item_dur), "-i", asset.file_path]
        else:
            # concat_loop + video + duration=0 → native length
            cmd += ["-i", asset.file_path]

        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
        )
        cmd += ["-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-pix_fmt", "yuv420p", str(out)]
        _run_ffmpeg(cmd, max(120, int(item_dur or 60) * 4))
        item_paths.append(out)

    # Step 2: concat the items with the concat demuxer
    # ffmpeg resolves paths in the list file relative to the LIST FILE's directory,
    # not the cwd. The items live alongside the list file, so use bare basenames —
    # using the full path would double the prefix (e.g., 'foo/bar/foo/bar/x.mp4').
    list_file = output_dir / "vseg_list.txt"
    list_file.write_text("\n".join(f"file '{p.name}'" for p in item_paths))
    concat_path = output_dir / "vseg_concat.mp4"
    _run_ffmpeg(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(concat_path)],
        timeout=300,
    )

    # Step 3: loop the concat segment to target_dur_s (using -stream_loop on the demuxer side)
    looped_path = output_dir / "vseg_looped.mp4"
    _run_ffmpeg(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(concat_path),
         "-t", str(target_dur_s), "-c", "copy", str(looped_path)],
        timeout=max(300, target_dur_s + 60),
    )
    return looped_path


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


def _probe_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             path],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except (ValueError, AttributeError, subprocess.TimeoutExpired):
        return 0.0


def _build_music_playlist_wav(video, db, target_duration_s: int, output_dir: Path) -> str | None:
    """Render the multi-track music playlist to a single temp WAV, with crossfade and loop.

    Falls back to single ``music_track_id`` when ``music_track_ids`` is empty.
    Returns path to the temp WAV, or None if no music is configured / files missing.
    """
    from database.models import MusicTrack

    track_ids_attr = getattr(video, "music_track_ids", None) or []
    try:
        track_ids = list(track_ids_attr)
    except TypeError:
        track_ids = []
    if not track_ids and getattr(video, "music_track_id", None):
        track_ids = [video.music_track_id]
    if not track_ids:
        return None

    # Load tracks, preserving user-specified order, only those with files on disk
    tracks_by_id = {
        t.id: t
        for t in db.query(MusicTrack).filter(MusicTrack.id.in_(track_ids)).all()
    }
    paths: list[tuple[str, float]] = []
    for tid in track_ids:
        t = tracks_by_id.get(tid)
        if t and t.file_path and Path(t.file_path).is_file():
            paths.append((t.file_path, float(t.volume or 1.0)))
    if not paths:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "music_playlist.wav"

    CROSSFADE = 1.5

    cmd = ["ffmpeg", "-y"]
    for path, _vol in paths:
        cmd += ["-i", path]

    # Per-track volume, then chain via acrossfade pairwise
    parts: list[str] = []
    for i, (_p, vol) in enumerate(paths):
        parts.append(f"[{i}:a]volume={vol}[v{i}]")

    if len(paths) == 1:
        parts.append("[v0]aloop=loop=-1:size=2147483647[looped]")
    else:
        prev = "v0"
        for i in range(1, len(paths)):
            label = f"x{i}" if i < len(paths) - 1 else "joined"
            parts.append(f"[{prev}][v{i}]acrossfade=d={CROSSFADE}:c1=tri:c2=tri[{label}]")
            prev = label
        parts.append("[joined]aloop=loop=-1:size=2147483647[looped]")

    parts.append(f"[looped]atrim=duration={target_duration_s}[out]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[out]",
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(out_path),
    ]
    _run_ffmpeg(cmd, max(120, target_duration_s + 60))
    return str(out_path)


def _build_sfx_pool_wav(
    video, db, target_duration_s: int, start_s: float, output_dir: Path
) -> str | None:
    """Render the random SFX pool to a single temp WAV with each SFX positioned at its scheduled time.

    ``sfx_pool`` is a list of ``{asset_id, volume}`` dicts (per spec).
    ``schedule_sfx()`` determines timestamps. Returns path to temp WAV, or None
    if no SFX configured / no files load.
    """
    from console.backend.models.sfx_asset import SfxAsset
    from pipeline.sfx_scheduler import schedule_sfx

    pool = getattr(video, "sfx_pool", None) or []
    density = getattr(video, "sfx_density_seconds", None)
    seed_attr = getattr(video, "sfx_seed", None)
    seed = seed_attr if seed_attr is not None else 0

    if not pool or not density:
        return None

    pool_ids: list[int] = []
    volumes_by_id: dict[int, float] = {}
    for entry in pool:
        if not isinstance(entry, dict):
            continue
        aid = entry.get("asset_id")
        if aid is None:
            continue
        try:
            aid_int = int(aid)
        except (TypeError, ValueError):
            continue
        pool_ids.append(aid_int)
        volumes_by_id[aid_int] = float(entry.get("volume", 1.0))
    if not pool_ids:
        return None

    end_s = start_s + target_duration_s
    schedule = schedule_sfx(pool_ids, density, seed, start_s, end_s)
    if not schedule:
        return None

    sfx_by_id = {
        s.id: s
        for s in db.query(SfxAsset).filter(SfxAsset.id.in_(pool_ids)).all()
    }
    events: list[tuple[str, float, float]] = []  # (file_path, volume, local_ts)
    for ts, sfx_id in schedule:
        sfx = sfx_by_id.get(sfx_id)
        if not sfx or not sfx.file_path or not Path(sfx.file_path).is_file():
            continue
        local_ts = max(0.0, ts - start_s)  # rebase to chunk-local time
        events.append((sfx.file_path, volumes_by_id.get(sfx_id, 1.0), local_ts))
    if not events:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "sfx_pool.wav"

    cmd = ["ffmpeg", "-y"]
    for path, _vol, _ts in events:
        cmd += ["-i", path]

    parts: list[str] = []
    for i, (_p, vol, ts) in enumerate(events):
        ts_ms = int(ts * 1000)
        parts.append(f"[{i}:a]volume={vol},adelay={ts_ms}|{ts_ms}[d{i}]")

    mix_in = "".join(f"[d{i}]" for i in range(len(events)))
    parts.append(
        f"{mix_in}amix=inputs={len(events)}:duration=longest:normalize=0[mixed]"
    )
    parts.append(f"[mixed]apad=whole_dur={target_duration_s}[out]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[out]",
        "-t", str(target_duration_s),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(out_path),
    ]
    _run_ffmpeg(cmd, max(120, target_duration_s + 60))
    return str(out_path)


def _blackout_filter_chain(
    black_from_s: int | None, w: int, h: int, start_s: float, target_dur: int
) -> str:
    """Return a filter chain segment that overlays a fading-in black layer at black_from_s.

    Returns empty string if no blackout configured or blackout falls outside this window.
    The returned chain assumes the upstream video label is ``[v_main]`` and produces ``[vout]``.
    Caller is responsible for chaining this AFTER their existing video filter.
    """
    if black_from_s is None:
        return ""
    local_start = max(0.0, black_from_s - start_s)
    if local_start >= target_dur:
        return ""
    overlay_dur = target_dur - local_start
    return (
        f";color=c=black:s={w}x{h}:r=30:d={overlay_dur}[bk];"
        f"[bk]fade=t=in:d=2:alpha=1[bkf];"
        f"[v_main][bkf]overlay=enable='gte(t,{local_start})':shortest=0[vout]"
    )


def render_landscape(
    video,
    output_path: Path,
    db,
    start_s: float = 0.0,
    end_s: float | None = None,
) -> None:
    """Render a landscape long-form YouTube video.

    For chunked render: pass ``start_s`` and ``end_s``. Each chunk uses identical encoder
    params so concat-demuxer with ``-c copy`` joins seamlessly.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    full_duration_s = int((video.target_duration_h or 3.0) * 3600)
    if end_s is None:
        end_s = full_duration_s
    target_dur = int(end_s - start_s)
    if target_dur <= 0:
        raise ValueError(f"Window has non-positive duration: [{start_s}, {end_s})")

    scale = QUALITY_SCALE.get(getattr(video, "output_quality", None) or "1080p", DEFAULT_SCALE)
    w_str, h_str = scale.split(":")
    w, h = int(w_str), int(h_str)

    output_dir = output_path.parent

    # Try the new playlist path first; fall back to legacy single-asset
    playlist = resolve_visual_playlist(video, db)
    playlist_segment_path: Path | None = None
    if playlist:
        playlist_segment_path = _build_visual_segment(
            playlist=playlist,
            durations=list(getattr(video, "visual_clip_durations_s", None) or []),
            loop_mode=getattr(video, "visual_loop_mode", None) or "concat_loop",
            w=w, h=h, target_dur_s=target_dur,
            output_dir=output_dir,
        )

    if playlist_segment_path is not None:
        visual_path = str(playlist_segment_path)
        is_image = False  # the segment is always an mp4
    else:
        visual_path = resolve_visual(video, db)
        is_image = visual_path is not None and Path(visual_path).suffix.lower() in IMAGE_EXTS

    # Pre-render music playlist + SFX pool to temp WAVs (separate ffmpeg passes)
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir)
    sfx_wav = _build_sfx_pool_wav(video, db, target_dur, start_s, output_dir)

    # Existing 3-layer SFX overrides remain additive
    sfx_layers = resolve_sfx_layers(video, db)

    audio_inputs: list[tuple[str, float]] = []
    if music_wav:
        audio_inputs.append((music_wav, 1.0))  # already volume-scaled internally
    if sfx_wav:
        audio_inputs.append((sfx_wav, 1.0))
    audio_inputs.extend(sfx_layers)

    base_vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
    )

    blackout = _blackout_filter_chain(
        getattr(video, "black_from_seconds", None), w, h, start_s, target_dur
    )

    cmd = ["ffmpeg", "-y"]

    # Visual input
    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        elif playlist_segment_path is not None:
            # Pre-rendered playlist segment: exact duration, no looping needed
            cmd += ["-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    # Audio inputs
    if audio_inputs:
        for path, _ in audio_inputs:
            # music_wav and sfx_wav are exact-duration WAVs — don't loop them
            if path in (music_wav, sfx_wav):
                cmd += ["-i", path]
            else:
                cmd += ["-stream_loop", "-1", "-i", path]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

    # Build filter graph
    if audio_inputs:
        audio_parts: list[str] = []
        audio_labels: list[str] = []
        for i, (_, vol) in enumerate(audio_inputs):
            audio_parts.append(f"[{i + 1}:a]volume={vol}[a{i}]")
            audio_labels.append(f"[a{i}]")
        if len(audio_inputs) == 1:
            audio_map = "[a0]"
        else:
            audio_parts.append(
                f"{''.join(audio_labels)}amix=inputs={len(audio_inputs)}:duration=first:normalize=0[aout]"
            )
            audio_map = "[aout]"

        if blackout:
            video_chain = f"[0:v]{base_vf}[v_main]{blackout}"
        else:
            video_chain = f"[0:v]{base_vf}[vout]"
        video_map = "[vout]"

        cmd += [
            "-filter_complex", ";".join(audio_parts) + ";" + video_chain,
            "-map", video_map, "-map", audio_map,
        ]
    else:
        if blackout:
            # Need filter_complex for the overlay even with silence
            cmd += [
                "-filter_complex", f"[0:v]{base_vf}[v_main]{blackout}",
                "-map", "[vout]", "-map", "1:a",
            ]
        else:
            cmd += ["-vf", base_vf]

    # Window: -ss only for single-asset looping path; playlist segments are already pre-cut
    # to target_dur, so applying -ss would seek past their end and produce empty output.
    # NOTE: this means each chunk's playlist starts from item 0 (not continuous across
    # chunks) — acceptable for ambient/loop content. To restore continuity across chunks
    # would require passing start_s into _build_visual_segment and using input-side seek
    # on the looped concat.
    if start_s > 0 and playlist_segment_path is None:
        cmd += ["-ss", str(int(start_s))]
    cmd += ["-t", str(target_dur)]

    # Encoder — IDENTICAL across chunks for stream-copy concat to work.
    # Preset is keyed off FULL video duration (not chunk size) so all chunks of
    # the same video share encoder params. Otherwise a 500s tail chunk would
    # pick "slow" while earlier chunks used "ultrafast", breaking -c copy concat.
    preset = "ultrafast" if full_duration_s > 600 else "slow"
    if is_image:
        cmd += ["-c:v", "libx264", "-preset", preset, "-tune", "stillimage", "-crf", "23"]
    else:
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "23"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart",
            str(output_path)]

    logger.info("ffmpeg landscape cmd (window [%s,%s)): %s", start_s, end_s, " ".join(cmd))
    _run_ffmpeg(cmd, target_dur * 2)


def render_portrait_short(video, template, output_path: Path, db) -> None:
    """Render a portrait 9:16 YouTube Short with CTA drawtext overlay in the last 10 seconds."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    duration_s = template.short_duration_s or 58

    visual_path = resolve_visual(video, db)
    music_path = resolve_audio(video, db)
    sfx_layers = resolve_sfx_layers(video, db)
    is_image = visual_path is not None and Path(visual_path).suffix.lower() in IMAGE_EXTS

    audio_inputs: list[tuple[str, float]] = []
    if music_path and Path(music_path).is_file():
        audio_inputs.append((music_path, 1.0))
    audio_inputs.extend(sfx_layers)

    cta_text = _get_cta_text(video, template)
    cta_start = max(0, duration_s - 10)
    escaped = _escape_drawtext(cta_text)
    drawtext = (
        f"drawtext=text='{escaped}'"
        f":fontcolor=white:fontsize=52"
        f":x=(w-tw)/2:y=h*0.80"
        f":box=1:boxcolor=black@0.5:boxborderw=10"
        f":enable='between(t,{cta_start},{duration_s})'"
    )

    portrait_crop = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,fps=30"
    vf_chain = f"{portrait_crop},{drawtext}"

    cmd = ["ffmpeg", "-y"]

    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30"]

    if audio_inputs:
        for path, _ in audio_inputs:
            cmd += ["-stream_loop", "-1", "-i", path]
        parts, map_args = _build_audio_filter(audio_inputs, vf_chain)
        cmd += ["-filter_complex", ";".join(parts)] + map_args
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-vf", vf_chain]

    cmd += ["-t", str(duration_s)]

    if is_image:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "18"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]

    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart",
            str(output_path)]

    logger.info("ffmpeg portrait short cmd: %s", " ".join(cmd))
    _run_ffmpeg(cmd, max(duration_s * 4, 120))


def _get_cta_text(video, template) -> str:
    overrides = video.sfx_overrides or {}
    cta = overrides.get("cta") or {}
    return (
        cta.get("text")
        or getattr(template, "short_cta_text", None)
        or "Watch the full video — link in description!"
    )
