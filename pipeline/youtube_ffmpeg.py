"""Shared ffmpeg helpers for YouTube long-form and portrait-short rendering."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from pipeline.spectrum_bars import render_spectrum_bars_video

logger = logging.getLogger(__name__)

QUALITY_SCALE = {
    "4K":    "3840:2160",
    "1080p": "1920:1080",
}
DEFAULT_SCALE = "1920:1080"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def build_spectrum_filter(
    enabled: bool,
    position: str,
    height_pct: float,
    color: str,
    opacity: float,
    canvas_w: int,
    canvas_h: int,
    audio_input_label: str = "[1:a]",
    base_label: str = "[base]",
    out_label: str = "[v_with_spec]",
) -> tuple[str, list[str]]:
    """Return (filter_chain_fragment, extra_ffmpeg_inputs).

    Returns ('', []) when disabled. Caller splices the chain into the
    larger filtergraph and labels the inputs.
    """
    if not enabled:
        return ("", [])

    height_px = int(canvas_h * height_pct)
    y = canvas_h - height_px if position == "bottom" else (canvas_h - height_px) // 2

    hex_no_alpha = color[:7]

    chain = (
        f"{audio_input_label}showfreqs=mode=bar:ascale=log:fscale=log:"
        f"cmode=combined:win_size=2048:colors={hex_no_alpha}:"
        f"size={canvas_w}x{height_px}[spec_raw];"
        f"[spec_raw]format=rgba,colorchannelmixer=aa={opacity}[spec];"
        f"{base_label}[spec]overlay=0:{y}{out_label}"
    )
    return (chain, [])


def resolve_visual(video, db) -> str | None:
    """Return the file path of the linked visual asset, or None.

    Prefers the singular `visual_asset_id`; falls back to the first entry in
    `visual_asset_ids` so videos built from playlist-only templates still work.
    """
    try:
        from console.backend.models.video_asset import VideoAsset
    except Exception:  # pragma: no cover
        return None

    asset_id = video.visual_asset_id
    if not asset_id:
        plural = list(getattr(video, "visual_asset_ids", None) or [])
        if plural:
            asset_id = plural[0]
    if not asset_id:
        return None
    try:
        asset = db.get(VideoAsset, asset_id)
        if asset and asset.file_path:
            return asset.file_path
    except Exception as exc:
        logger.warning("Could not load visual asset %s: %s", asset_id, exc)
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
    """Return the file path of the linked music track, or None.

    Prefers the singular `music_track_id`; falls back to the first entry in
    `music_track_ids` so videos built from playlist-only templates still work.
    """
    try:
        from database.models import MusicTrack
    except Exception:  # pragma: no cover
        return None

    track_id = video.music_track_id
    if not track_id:
        plural = list(getattr(video, "music_track_ids", None) or [])
        if plural:
            track_id = plural[0]
    if not track_id:
        return None
    try:
        track = db.get(MusicTrack, track_id)
        if track and track.file_path:
            return track.file_path
    except Exception as exc:
        logger.warning("Could not load music track %s: %s", track_id, exc)
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
    except (ValueError, subprocess.TimeoutExpired):
        return 0.0


def _nvenc_available() -> bool:
    """Return True only if h264_nvenc can actually encode (not just listed).

    ffmpeg lists h264_nvenc even when libnvidia-encode.so.1 is missing (common
    on Docker Desktop / WSL2 where NVML works but NVENC does not). A real encode
    attempt is the only reliable check; ffmpeg exits 0 regardless with -f null,
    so we inspect stderr for the library-load error instead.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "nullsrc=s=256x256:r=30",
                "-frames:v", "1", "-c:v", "h264_nvenc", "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=15,
        )
        # ffmpeg exits 0 even on init failure with -f null; check stderr instead.
        # "Cannot load libnvidia" = library missing (Docker Desktop runc runtime).
        # Any other stderr = unexpected failure, treat as unavailable.
        return result.returncode == 0 and not (result.stderr or "").strip()
    except Exception:
        return False


def _build_music_playlist_wav(video, db, target_duration_s: int, output_dir: Path, start_s: float = 0.0) -> str | None:
    """Render the multi-track music playlist to a single temp WAV, with seamless loop.

    Falls back to single ``music_track_id`` when ``music_track_ids`` is empty.
    Returns path to the temp WAV, or None if no music is configured / files missing.

    Loop boundaries are crossfaded — not hard-cut. ``aloop`` (the previous
    approach) repeats the audio buffer verbatim, so the last sample of one
    iteration butts up against the first sample of the next. For music that
    doesn't start and end at matching zero crossings (i.e. almost any track
    that wasn't authored as a "loop"), this creates an audible click /
    discontinuity every M seconds, where M is the track length. Broadband /
    ambient content masks the click acoustically; tonal / melodic music
    exposes it as a "weird sound" every loop period — the symptom users
    report for 3-hour renders where the music track happens to be ~5 min.

    Implementation: probe each track's duration, replicate the sequence N
    times (with N chosen so the natural sum overshoots target by ≥ one
    crossfade), pairwise ``acrossfade`` every consecutive pair (within and
    between iterations), then atrim to the requested window. When a track's
    duration cannot be probed, falls back to the legacy ``aloop`` path.
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

    # Probe each unique track once.
    durations_by_path: dict[str, float] = {}
    for path, _vol in paths:
        if path not in durations_by_path:
            durations_by_path[path] = _probe_duration(path)
    can_seamless_loop = all(d > CROSSFADE * 2 for d in durations_by_path.values())

    if not can_seamless_loop:
        # Fallback: probe failed or a track is shorter than the crossfade.
        # Use the legacy aloop path (may glitch at loop boundary for tonal music,
        # but at least it produces output).
        logger.warning(
            "[MusicPlaylist] could not probe all track durations; "
            "falling back to legacy aloop (may click at loop boundary)"
        )
        cmd = ["ffmpeg", "-y"]
        for path, _vol in paths:
            cmd += ["-i", path]

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

        parts.append(
            f"[looped]atrim=start={start_s}:end={start_s + target_duration_s},"
            f"asetpts=PTS-STARTPTS[out]"
        )

        cmd += [
            "-filter_complex", ";".join(parts),
            "-map", "[out]",
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
            str(out_path),
        ]
        _run_ffmpeg(cmd, max(120, target_duration_s + 60))
        return str(out_path)

    # Seamless loop path: replicate the playlist N times with acrossfade
    # between every consecutive pair (within and at loop boundaries).
    target_end = start_s + target_duration_s
    n_tracks = len(paths)
    one_iter_natural = sum(durations_by_path[p] for p, _v in paths) - (n_tracks - 1) * CROSSFADE

    if one_iter_natural <= 0:
        # Pathological — fall back to legacy.
        return _build_music_playlist_wav_legacy_fallback(
            paths, target_duration_s, output_dir, start_s, CROSSFADE,
        )

    # How many full iterations are needed so the cumulative natural length
    # exceeds target_end? Add one extra to give atrim room for the final
    # crossfade tail.
    if one_iter_natural >= target_end:
        n_iters = 1
    else:
        # Each extra iteration adds (one_iter_natural - CROSSFADE) usable seconds
        # because the boundary between iterations consumes another crossfade.
        usable_per_extra = one_iter_natural - CROSSFADE
        if usable_per_extra <= 0:
            return _build_music_playlist_wav_legacy_fallback(
                paths, target_duration_s, output_dir, start_s, CROSSFADE,
            )
        extra_needed = target_end - one_iter_natural
        import math as _math
        n_iters = 1 + _math.ceil(extra_needed / usable_per_extra) + 1  # +1 safety

    # Flatten paths × n_iters into the sequence of inputs.
    seq: list[tuple[str, float]] = []
    for _ in range(n_iters):
        seq.extend(paths)

    cmd = ["ffmpeg", "-y"]
    for path, _vol in seq:
        cmd += ["-i", path]

    parts: list[str] = []
    for i, (_p, vol) in enumerate(seq):
        parts.append(f"[{i}:a]volume={vol}[v{i}]")

    if len(seq) == 1:
        parts.append("[v0]anull[looped]")
    else:
        prev = "v0"
        for i in range(1, len(seq)):
            label = f"x{i}" if i < len(seq) - 1 else "looped"
            parts.append(f"[{prev}][v{i}]acrossfade=d={CROSSFADE}:c1=tri:c2=tri[{label}]")
            prev = label

    parts.append(
        f"[looped]atrim=start={start_s}:end={start_s + target_duration_s},"
        f"asetpts=PTS-STARTPTS[out]"
    )

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[out]",
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(out_path),
    ]
    logger.info(
        "[MusicPlaylist] %s tracks × %s iters (one-iter natural=%.1fs) → %ss target",
        n_tracks, n_iters, one_iter_natural, target_duration_s,
    )
    _run_ffmpeg(cmd, max(120, target_duration_s + 60))
    return str(out_path)


def _build_music_playlist_wav_legacy_fallback(
    paths: list[tuple[str, float]],
    target_duration_s: int,
    output_dir: Path,
    start_s: float,
    crossfade: float,
) -> str:
    """Legacy aloop path — used only when seamless-loop math degenerates.

    May produce an audible click at each loop boundary for non-loopable music;
    kept as a backstop to ensure we always produce *some* output.
    """
    out_path = output_dir / "music_playlist.wav"
    cmd = ["ffmpeg", "-y"]
    for path, _vol in paths:
        cmd += ["-i", path]

    parts: list[str] = []
    for i, (_p, vol) in enumerate(paths):
        parts.append(f"[{i}:a]volume={vol}[v{i}]")

    if len(paths) == 1:
        parts.append("[v0]aloop=loop=-1:size=2147483647[looped]")
    else:
        prev = "v0"
        for i in range(1, len(paths)):
            label = f"x{i}" if i < len(paths) - 1 else "joined"
            parts.append(f"[{prev}][v{i}]acrossfade=d={crossfade}:c1=tri:c2=tri[{label}]")
            prev = label
        parts.append("[joined]aloop=loop=-1:size=2147483647[looped]")

    parts.append(
        f"[looped]atrim=start={start_s}:end={start_s + target_duration_s},"
        f"asetpts=PTS-STARTPTS[out]"
    )

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


LAYER_SEED_OFFSETS = {
    "midground":  0,
    "foreground": 100003,
    "random_sfx": 200003,
}


def _build_sound_layers_wav(
    video,
    db,
    target_duration_s: int,
    start_s: float,
    output_dir: Path,
) -> str | None:
    """Render background loop + 3 scheduled SFX layers to a single temp WAV.

    Replaces both _build_sfx_pool_wav and resolve_sfx_layers for the new
    sound_layers config. Returns None if sound_layers is absent or all layers
    resolve to nothing.
    """
    from console.backend.models.sfx_asset import SfxAsset
    from pipeline.sfx_scheduler import schedule_sfx_layer

    sound_layers = getattr(video, "sound_layers", None) or {}
    if not sound_layers:
        return None

    sfx_seed = getattr(video, "sfx_seed", None) or 0
    end_s = start_s + target_duration_s

    # Collect all referenced asset IDs to load in one query
    all_asset_ids: set[int] = set()
    bg_config = sound_layers.get("background") or {}
    if bg_config.get("asset_id") is not None:
        all_asset_ids.add(int(bg_config["asset_id"]))
    for layer_name in LAYER_SEED_OFFSETS:
        for aid in (sound_layers.get(layer_name) or {}).get("pool", []):
            all_asset_ids.add(int(aid))

    if not all_asset_ids:
        return None

    sfx_by_id = {
        s.id: s
        for s in db.query(SfxAsset).filter(SfxAsset.id.in_(list(all_asset_ids))).all()
    }

    # ── Background layer ─────────────────────────────────────────────────────
    # (path, volume, seek_s)  — seek_s is the ffmpeg -ss value for loop phase
    bg_inputs: list[tuple[str, float, float]] = []
    if bg_config:
        asset_id = bg_config.get("asset_id")
        volume = float(bg_config.get("volume", 1.0))
        if asset_id is not None:
            sfx = sfx_by_id.get(int(asset_id))
            if sfx and sfx.file_path and Path(sfx.file_path).is_file():
                asset_dur = _probe_duration(sfx.file_path)
                seek = (start_s % asset_dur) if asset_dur > 0.5 and start_s > 0 else 0.0
                bg_inputs.append((sfx.file_path, volume, seek))
            else:
                logger.warning(
                    "[SoundLayers] background asset %s not found or missing file", asset_id
                )

    # ── Scheduled layers ─────────────────────────────────────────────────────
    # (path, volume, local_ts_ms)
    scheduled: list[tuple[str, float, int]] = []
    for layer_name, seed_offset in LAYER_SEED_OFFSETS.items():
        layer = sound_layers.get(layer_name) or {}
        if not layer:
            continue
        pool_ids = [int(x) for x in layer.get("pool", [])]
        if not pool_ids:
            continue
        volume = float(layer.get("volume", 1.0))
        interval_min = float(layer.get("interval_min_s", 10))
        interval_max = float(layer.get("interval_max_s", 25))
        layer_seed = sfx_seed + seed_offset

        events = schedule_sfx_layer(pool_ids, interval_min, interval_max, layer_seed, start_s, end_s)
        for ts, sfx_id in events:
            sfx = sfx_by_id.get(sfx_id)
            if sfx and sfx.file_path and Path(sfx.file_path).is_file():
                local_ts_ms = max(0, int((ts - start_s) * 1000))
                scheduled.append((sfx.file_path, volume, local_ts_ms))

    if not bg_inputs and not scheduled:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "sound_layers.wav"

    cmd = ["ffmpeg", "-y"]

    # Inputs: background (looped) then scheduled events
    for path, _vol, seek in bg_inputs:
        if seek > 0.5:
            cmd += ["-ss", str(seek)]
        cmd += ["-stream_loop", "-1", "-i", path]

    for path, _vol, _ts_ms in scheduled:
        cmd += ["-i", path]

    # Filter complex
    parts: list[str] = []
    labels: list[str] = []
    fi = 0

    for i, (_, vol, _) in enumerate(bg_inputs):
        parts.append(f"[{fi}:a]volume={vol}[bg{i}]")
        labels.append(f"[bg{i}]")
        fi += 1

    for i, (_, vol, ts_ms) in enumerate(scheduled):
        parts.append(f"[{fi}:a]volume={vol},adelay={ts_ms}|{ts_ms}[ev{i}]")
        labels.append(f"[ev{i}]")
        fi += 1

    n = len(labels)
    if n == 1:
        parts.append(f"{labels[0]}apad=whole_dur={target_duration_s}[out]")
    else:
        mix_in = "".join(labels)
        parts.append(f"{mix_in}amix=inputs={n}:duration=longest:normalize=0[mixed]")
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


def _render_landscape_music(
    video,
    output_path: Path,
    db,
    start_s: float,
    end_s: float | None,
    include_audio: bool = True,
) -> None:
    """Music-template branch of render_landscape.

    Total duration comes from the natural sum of track durations (no looping).
    No SFX layers, no blackout overlay. Spectrum visualiser and now-playing
    PNG overlays are optional and applied as filtergraph stages.

    When ``include_audio`` is False, the audio stream is omitted (``-an``).
    The caller is responsible for muxing in a full-duration audio track
    later (see ``render_full_audio_track`` and the chunked render path) —
    this avoids AAC priming/concat artifacts at chunk seams.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    # Lazy imports — avoids circular dependency on console.backend.services
    from console.backend.services.youtube_video_service import (
        _resolve_music_tracks,
        _compute_music_total_duration,
    )
    from pipeline.music_audio import build_music_playlist_wav_with_transitions
    from pipeline.music_overlay import build_now_playing_overlay

    music_tracks = _resolve_music_tracks(video, db)
    if not music_tracks:
        raise RuntimeError("Music template requires at least one music track")

    total_dur_s, boundaries = _compute_music_total_duration(
        music_tracks,
        video.track_transition,
        video.track_transition_seconds,
    )
    full_duration_s = int(round(total_dur_s))

    if end_s is None:
        end_s = full_duration_s
    target_dur = int(end_s - start_s)
    if target_dur <= 0:
        raise ValueError(f"Window has non-positive duration: [{start_s}, {end_s})")

    scale = QUALITY_SCALE.get(getattr(video, "output_quality", None) or "1080p", DEFAULT_SCALE)
    w_str, h_str = scale.split(":")
    w, h = int(w_str), int(h_str)

    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Visual (same playlist / single-asset logic as legacy path) ────────────
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
        is_image = False
    else:
        visual_path = resolve_visual(video, db)
        is_image = visual_path is not None and Path(visual_path).suffix.lower() in IMAGE_EXTS

    # ── Music WAV (exact-duration, no looping) ────────────────────────────────
    # We still need this WAV when include_audio=False if the spectrum
    # visualiser is enabled — the visualiser is video output but reads the
    # audio waveform as input. When neither audio nor spectrum is needed,
    # skip the build entirely to save I/O on each chunk.
    spectrum_enabled_early = bool(getattr(video, "spectrum_enabled", False))
    music_wav: str | None = None
    if include_audio or spectrum_enabled_early:
        music_wav = build_music_playlist_wav_with_transitions(
            tracks=music_tracks,
            total_duration_s=total_dur_s,
            transition=video.track_transition,
            transition_s=video.track_transition_seconds,
            output_dir=output_dir,
            start_s=start_s,
        )

    # ── Now-playing overlay segments ──────────────────────────────────────────
    overlay_segments = []
    if video.playlist_overlay_style and len(music_tracks) >= 2:
        overlay_segments = build_now_playing_overlay(
            video=video,
            tracks=music_tracks,
            boundaries=boundaries,
            total_duration_s=total_dur_s,
            output_dir=output_dir,
            canvas_w=w,
            canvas_h=h,
        )

    # ── Spectrum: classic uses inline showfreqs filter; bars pre-renders a separate video ──
    spectrum_style = getattr(video, "spectrum_style", "classic") or "classic"
    spectrum_enabled = bool(getattr(video, "spectrum_enabled", False))
    spectrum_video_path: Path | None = None
    spec_chain = ""

    if spectrum_enabled and spectrum_style == "bars":
        spectrum_video_path = render_spectrum_bars_video(
            music_wav=str(music_wav),
            out_path=output_dir / "spectrum.mov",
            total_duration_s=total_dur_s,
            canvas_w=w,
            canvas_h=h,
            height_pct=getattr(video, "spectrum_height_pct", 0.12),
            color_hex=getattr(video, "spectrum_color", "#ffffff"),
            bar_width_px=getattr(video, "spectrum_bar_width_px", 10.0),
            bar_count=getattr(video, "spectrum_bar_count", 50),
            align_horizontal=getattr(video, "spectrum_align_horizontal", "center"),
        )
    elif spectrum_enabled:  # classic
        # Classic showfreqs supports only bottom/center vertical placement.
        # Map align_vertical → position; 'top' falls back to 'center' since
        # the legacy filter has no native top mode.
        legacy_pos = getattr(video, "spectrum_align_vertical", "bottom")
        if legacy_pos == "top":
            legacy_pos = "center"
        # spec_chain is built below once music_input_idx is known.
        _classic_spec_pos = legacy_pos
    else:
        _classic_spec_pos = None

    # ── Build ffmpeg command ──────────────────────────────────────────────────
    cmd = ["ffmpeg", "-y"]

    # Input 0: visual
    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        elif playlist_segment_path is not None:
            cmd += ["-i", visual_path]
        else:
            if start_s > 0.5:
                vid_dur = _probe_duration(visual_path)
                effective_seek = (start_s % vid_dur) if vid_dur > 1.0 else 0.0
                if effective_seek > 0.5:
                    cmd += ["-stream_loop", "-1", "-ss", str(int(effective_seek)), "-i", visual_path]
                else:
                    cmd += ["-stream_loop", "-1", "-i", visual_path]
            else:
                cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    # Input 1: music WAV (exact duration — no loop flag).
    # Always added when music_wav exists (needed for classic spectrum's
    # inline [1:a] filter even when audio is omitted from output).
    next_input_idx = 1
    music_input_idx: int | None = None
    if music_wav is not None:
        cmd += ["-i", str(music_wav)]
        music_input_idx = next_input_idx
        next_input_idx += 1

    # Optional: bars spectrum input (only present when spectrum_style == 'bars' and enabled)
    if spectrum_video_path is not None:
        cmd += ["-i", str(spectrum_video_path)]
        bars_input_idx = next_input_idx
        next_input_idx += 1
    else:
        bars_input_idx = None
    overlay_input_start = next_input_idx

    # Inputs overlay_input_start+: overlay PNGs (one still per track)
    for seg in overlay_segments:
        cmd += ["-loop", "1", "-i", seg.png_path]

    # Build classic spec_chain now that we know the music input index.
    if _classic_spec_pos is not None and music_input_idx is not None:
        spec_chain, _ = build_spectrum_filter(
            enabled=True,
            position=_classic_spec_pos,
            height_pct=getattr(video, "spectrum_height_pct", 0.12),
            color=getattr(video, "spectrum_color", "#ffffff"),
            opacity=getattr(video, "spectrum_opacity", 0.6),
            canvas_w=w,
            canvas_h=h,
            audio_input_label=f"[{music_input_idx}:a]",
            base_label="[base]",
            out_label="[v_after_spec]",
        )

    # ── Filtergraph ───────────────────────────────────────────────────────────
    base_vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
    )

    parts: list[str] = []
    parts.append(f"[0:v]{base_vf}[base]")

    if spec_chain:
        # Classic spectrum: inline showfreqs filter
        parts.append(spec_chain)
        prev_label = "[v_after_spec]"
    elif bars_input_idx is not None:
        # Bars spectrum: pre-rendered MOV overlaid onto [base]
        strip_h = max(1, int(h * getattr(video, "spectrum_height_pct", 0.12)))
        align_v = getattr(video, "spectrum_align_vertical", "bottom")
        edge_margin = max(8, int(round(h * 0.02)))
        if align_v == "top":
            y_pos = edge_margin
        elif align_v == "bottom":
            y_pos = h - strip_h - edge_margin
        else:  # center
            y_pos = (h - strip_h) // 2
        y_pos = max(0, y_pos)
        opacity = getattr(video, "spectrum_opacity", 0.6)
        parts.append(
            f"[{bars_input_idx}:v]format=rgba,colorchannelmixer=aa={opacity:.3f}[spec_bars]"
        )
        parts.append(
            f"[base][spec_bars]overlay=0:{y_pos}[v_after_spec]"
        )
        prev_label = "[v_after_spec]"
    else:
        prev_label = "[base]"

    # Chain overlay PNGs: switch active PNG at each track boundary
    for idx, seg in enumerate(overlay_segments):
        input_idx = overlay_input_start + idx
        is_last = (idx == len(overlay_segments) - 1)
        next_label = "[vout]" if is_last else f"[v_o{idx}]"
        # Rebase enable times to chunk window
        enable_start = max(0.0, seg.start_s - start_s)
        enable_end = max(0.0, seg.end_s - start_s)
        parts.append(
            f"{prev_label}[{input_idx}:v]overlay=0:0:"
            f"enable='between(t,{enable_start:.3f},{enable_end:.3f})'{next_label}"
        )
        prev_label = next_label

    # If neither spectrum nor overlays added, chain ended at [base]; rename to [vout]
    if prev_label != "[vout]":
        parts.append(f"{prev_label}null[vout]")

    filter_complex = ";".join(parts)
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
    ]
    if include_audio and music_input_idx is not None:
        cmd += ["-map", f"{music_input_idx}:a"]

    cmd += ["-t", str(target_dur)]

    # Encoder — same params as legacy path (keyed off full duration for chunk-concat compat)
    _maxrate, _bufsize = ("35M", "70M") if scale == "3840:2160" else ("8M", "16M")
    if _nvenc_available():
        cmd += ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "23",
                "-maxrate", _maxrate, "-bufsize", _bufsize]
    else:
        preset = "ultrafast" if full_duration_s > 600 else "slow"
        if is_image:
            cmd += ["-c:v", "libx264", "-preset", preset, "-tune", "stillimage", "-crf", "23",
                    "-maxrate", _maxrate, "-bufsize", _bufsize]
        else:
            cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "23",
                    "-maxrate", _maxrate, "-bufsize", _bufsize]
    if include_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
    else:
        cmd += ["-an"]
    cmd += [
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info(
        "ffmpeg landscape music cmd (window [%s,%s), audio=%s): %s",
        start_s, end_s, include_audio, " ".join(cmd),
    )
    _run_ffmpeg(cmd, max(120, target_dur * 2))


def render_landscape(
    video,
    output_path: Path,
    db,
    start_s: float = 0.0,
    end_s: float | None = None,
    include_audio: bool = True,
) -> None:
    """Render a landscape long-form YouTube video.

    For chunked render: pass ``start_s`` and ``end_s``. Each chunk uses identical encoder
    params so concat-demuxer with ``-c copy`` joins seamlessly.

    When ``include_audio`` is False, the chunk is encoded video-only (``-an``).
    A full-duration audio track is built separately by
    ``render_full_audio_track`` and muxed in after the video chunks are
    concatenated — this eliminates AAC priming/concat artifacts that would
    otherwise produce audible glitches at every chunk seam (e.g. every 5
    minutes for the default 300s chunk size).

    When the video's template slug is ``"music"``, rendering is delegated to
    ``_render_landscape_music``, which derives total duration from the playlist
    rather than ``target_duration_h``, omits SFX layers and blackout, and
    optionally applies the spectrum visualiser and now-playing PNG overlays.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    # Detect music template — load by template_id (no ORM relationship on model)
    from console.backend.models.video_template import VideoTemplate
    _template = db.get(VideoTemplate, video.template_id) if video.template_id else None
    if _template and getattr(_template, "slug", None) == "music":
        return _render_landscape_music(video, output_path, db, start_s, end_s, include_audio=include_audio)

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

    black_from_s = getattr(video, "black_from_seconds", None)
    # Chunks entirely within the black period need no visual — skip the expensive
    # visual-segment build and go straight to a lavfi black source.
    chunk_is_all_black = black_from_s is not None and start_s >= black_from_s

    playlist_segment_path: Path | None = None
    visual_path: str | None = None
    is_image = False

    if not chunk_is_all_black:
        # Try the new playlist path first; fall back to legacy single-asset
        playlist = resolve_visual_playlist(video, db)
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

    # Pre-render music playlist + sound layers to temp WAVs (separate ffmpeg passes).
    # In include_audio=False mode (chunked render) we skip these entirely — audio
    # is built in one continuous pass and muxed in after concat to avoid AAC
    # priming/boundary artifacts at chunk seams.
    music_wav: str | None = None
    sound_layers_wav: str | None = None
    audio_inputs: list[tuple[str, float]] = []
    if include_audio:
        music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir, start_s=start_s)
        sound_layers_wav = _build_sound_layers_wav(video, db, target_dur, start_s, output_dir)
        if music_wav:
            audio_inputs.append((music_wav, 1.0))
        if sound_layers_wav:
            audio_inputs.append((sound_layers_wav, 1.0))

    base_vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
    )

    # No overlay needed when the whole chunk is already black
    blackout = "" if chunk_is_all_black else _blackout_filter_chain(
        black_from_s, w, h, start_s, target_dur
    )

    cmd = ["ffmpeg", "-y"]

    # Visual input — use lavfi black source directly for all-black chunks
    if chunk_is_all_black:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]
    elif visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        elif playlist_segment_path is not None:
            # Pre-rendered playlist segment: exact duration, no looping needed
            cmd += ["-i", visual_path]
        else:
            if start_s > 0.5:
                vid_dur = _probe_duration(visual_path)
                effective_seek = (start_s % vid_dur) if vid_dur > 1.0 else 0.0
                if effective_seek > 0.5:
                    cmd += ["-stream_loop", "-1", "-ss", str(int(effective_seek)), "-i", visual_path]
                else:
                    cmd += ["-stream_loop", "-1", "-i", visual_path]
            else:
                cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    # Audio inputs (only added when include_audio=True)
    if include_audio:
        if audio_inputs:
            for path, _ in audio_inputs:
                # music_wav and sound_layers_wav are exact-duration WAVs — don't loop them
                if path in (music_wav, sound_layers_wav):
                    cmd += ["-i", path]
                else:
                    if start_s > 0.5:
                        sfx_dur = _probe_duration(path)
                        effective_seek = (start_s % sfx_dur) if sfx_dur > 1.0 else 0.0
                        if effective_seek > 0.5:
                            cmd += ["-stream_loop", "-1", "-ss", str(int(effective_seek)), "-i", path]
                        else:
                            cmd += ["-stream_loop", "-1", "-i", path]
                    else:
                        cmd += ["-stream_loop", "-1", "-i", path]
        else:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

    # Build filter graph
    if include_audio and audio_inputs:
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
    elif include_audio:  # silence-only path
        if blackout:
            # Need filter_complex for the overlay even with silence
            cmd += [
                "-filter_complex", f"[0:v]{base_vf}[v_main]{blackout}",
                "-map", "[vout]", "-map", "1:a",
            ]
        else:
            cmd += ["-vf", base_vf]
    else:  # include_audio=False — video-only chunk
        if blackout:
            cmd += [
                "-filter_complex", f"[0:v]{base_vf}[v_main]{blackout}",
                "-map", "[vout]",
            ]
        else:
            cmd += ["-vf", base_vf]

    cmd += ["-t", str(target_dur)]

    # Encoder — IDENTICAL across chunks for stream-copy concat to work.
    # Preset is keyed off FULL video duration (not chunk size) so all chunks of
    # the same video share encoder params. Otherwise a 500s tail chunk would
    # pick "slow" while earlier chunks used "ultrafast", breaking -c copy concat.
    _maxrate, _bufsize = ("35M", "70M") if scale == "3840:2160" else ("8M", "16M")
    if _nvenc_available():
        cmd += ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "23",
                "-maxrate", _maxrate, "-bufsize", _bufsize]
    else:
        preset = "ultrafast" if full_duration_s > 600 else "slow"
        if is_image:
            cmd += ["-c:v", "libx264", "-preset", preset, "-tune", "stillimage", "-crf", "23",
                    "-maxrate", _maxrate, "-bufsize", _bufsize]
        else:
            cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "23",
                    "-maxrate", _maxrate, "-bufsize", _bufsize]
    if include_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(output_path)]

    logger.info(
        "ffmpeg landscape cmd (window [%s,%s), audio=%s): %s",
        start_s, end_s, include_audio, " ".join(cmd),
    )
    _run_ffmpeg(cmd, max(120, target_dur * 2))


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


def render_full_audio_track(video, output_path: Path, db) -> Path:
    """Render the full-duration audio mix as a single AAC-in-MP4 (.m4a) file.

    Used by the chunked render pipeline: after video chunks (encoded with
    ``include_audio=False``) are concat-copied together, this single
    continuous AAC encode is muxed in. Doing all audio in one encoder pass
    eliminates the AAC priming/concat artifacts that produce audible
    glitches at every chunk seam when each chunk is independently AAC
    encoded and then ``-c copy`` joined.

    Branches on template slug just like ``render_landscape`` does:
      * music template → music playlist with transitions, no SFX.
      * everything else → music playlist (looped) + sound_layers WAV mix.

    Returns the path to the rendered audio file.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from console.backend.models.video_template import VideoTemplate

    _template = db.get(VideoTemplate, video.template_id) if video.template_id else None
    is_music_template = bool(_template and getattr(_template, "slug", None) == "music")

    output_dir = output_path.parent

    if is_music_template:
        # Total duration is the natural playlist sum, not target_duration_h.
        from console.backend.services.youtube_video_service import (
            _resolve_music_tracks,
            _compute_music_total_duration,
        )
        from pipeline.music_audio import build_music_playlist_wav_with_transitions

        music_tracks = _resolve_music_tracks(video, db)
        if not music_tracks:
            raise RuntimeError("Music template requires at least one music track")

        total_dur_s, _boundaries = _compute_music_total_duration(
            music_tracks,
            video.track_transition,
            video.track_transition_seconds,
        )
        full_duration_s = int(round(total_dur_s))

        music_wav = build_music_playlist_wav_with_transitions(
            tracks=music_tracks,
            total_duration_s=total_dur_s,
            transition=video.track_transition,
            transition_s=video.track_transition_seconds,
            output_dir=output_dir,
            start_s=0.0,
        )
        audio_inputs = [(music_wav, 1.0)]
    else:
        full_duration_s = int((video.target_duration_h or 3.0) * 3600)
        music_wav = _build_music_playlist_wav(
            video, db, full_duration_s, output_dir, start_s=0.0
        )
        sound_layers_wav = _build_sound_layers_wav(
            video, db, full_duration_s, 0.0, output_dir
        )
        audio_inputs = []
        if music_wav:
            audio_inputs.append((music_wav, 1.0))
        if sound_layers_wav:
            audio_inputs.append((sound_layers_wav, 1.0))

    cmd = ["ffmpeg", "-y"]

    if audio_inputs:
        for path, _ in audio_inputs:
            cmd += ["-i", path]
        parts: list[str] = []
        labels: list[str] = []
        for i, (_p, vol) in enumerate(audio_inputs):
            parts.append(f"[{i}:a]volume={vol}[a{i}]")
            labels.append(f"[a{i}]")
        if len(audio_inputs) == 1:
            audio_map = "[a0]"
        else:
            parts.append(
                f"{''.join(labels)}amix=inputs={len(audio_inputs)}:duration=first:normalize=0[aout]"
            )
            audio_map = "[aout]"
        cmd += ["-filter_complex", ";".join(parts), "-map", audio_map]
    else:
        # No music or SFX configured — emit silence of full_duration_s.
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]

    cmd += [
        "-t", str(full_duration_s),
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-vn",
        str(output_path),
    ]

    logger.info(
        "ffmpeg full audio track (duration=%ss, music_template=%s): %s",
        full_duration_s, is_music_template, " ".join(cmd),
    )
    _run_ffmpeg(cmd, max(300, full_duration_s + 120))
    return output_path
