# Design: YouTube Chunk Render Timeout + Smooth Concat Fix

**Date:** 2026-05-04  
**Status:** Approved  
**File changed:** `pipeline/youtube_ffmpeg.py` only

---

## Problem

Two related failures in chunked YouTube video rendering:

1. **Timeout:** Every chunk of `YoutubeVideo 42` (and any video with a non-image visual asset) fails with `RuntimeError: ffmpeg timed out after 600s` starting at chunk 9 (start_s=2700). Root cause: `-ss start_s` is placed after the filter graph — an output-side seek — forcing ffmpeg to encode and discard `start_s` seconds of video before writing a single output frame. At ~5× realtime on CPU, chunk 9 costs 93 s (encode) + 513 s (discard) = 606 s > 600 s limit.

2. **Glitchy concat:** Even on chunks that complete, the final concatenated video has audible/visual glitches every 300 s (every chunk boundary). Three root causes:
   - Visual loops restart from t=0 each chunk (same output-side seek bug, even when under the timeout)
   - Music WAV is rendered from t=0 of the playlist for every chunk — music resets at each boundary
   - SFX override layers (foreground/midground/background) restart from t=0 each chunk

**Not in scope (deferred):** GPU encoder selection (`h264_nvenc`). Tracked separately.

---

## Approach

Fix all three continuity layers in one change:

- Input-side seek with modulo for the visual asset
- `start_s`-aware music WAV pre-render
- Input-side seek with modulo for SFX override layers
- Timeout floor

---

## Design

### 1. New helper: `_probe_duration(path) -> float`

Added after `_run_ffmpeg`. Uses `ffprobe` to get the duration of a file in seconds. Returns `0.0` on any failure — callers treat this as "no seek, start from beginning," which is safe.

```python
def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         path],
        capture_output=True, text=True, timeout=15,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0
```

**Call count per chunk:** max 4 (1 visual + up to 3 SFX layers). Each call ~100 ms. Total overhead <0.5 s per chunk — negligible against a 300 s render.

---

### 2. Visual: input-side seek with modulo

**Why modulo?** The visual file (e.g., `asset_5.mp4`) may be 60 s long. Chunk 27 starts at `start_s=8100` — that is loop iteration 135, position 0 s into the file. Without modulo, `-ss 8100` on a 60 s file would seek past EOF non-deterministically. `effective_seek = start_s % file_dur` lands at the correct loop position.

**Why threshold 0.5?** Avoids a pointless `-ss 0` for small float residuals.

**Why not images?** Images use `-loop 1` (single static frame) with no file duration to modulo against. No change.

**Why not playlist segments?** `playlist_segment_path` is already pre-cut to `target_dur` by `_build_visual_segment`. Applying seek to it would produce empty output. No change.

**Change:** Remove output-side `-ss` lines 509–510. Move seek logic into the visual input block:

```python
else:
    # Single looped video — input-side seek so ffmpeg doesn't discard start_s frames
    if start_s > 0.5:
        vid_dur = _probe_duration(visual_path)
        effective_seek = (start_s % vid_dur) if vid_dur > 1.0 else 0.0
        if effective_seek > 0.5:
            cmd += ["-stream_loop", "-1", "-ss", str(int(effective_seek)), "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-stream_loop", "-1", "-i", visual_path]
```

---

### 3. Music WAV: `start_s`-aware pre-render

**Problem:** `_build_music_playlist_wav` always renders from t=0 of the looped playlist, regardless of `start_s`. After concat, music resets to the beginning of the playlist every chunk (every 5 minutes).

**Fix:** Add `start_s: float = 0.0` parameter. Change the final `atrim` filter from `duration=N` to `start=start_s:end=start_s+N`, followed by `asetpts=PTS-STARTPTS` to reset output timestamps to 0.

```python
# Before
parts.append(f"[looped]atrim=duration={target_duration_s}[out]")

# After
parts.append(
    f"[looped]atrim=start={start_s}:end={start_s + target_duration_s},"
    f"asetpts=PTS-STARTPTS[out]"
)
```

`asetpts=PTS-STARTPTS` is required — without it the output WAV's timestamps start at `start_s`, and the main ffmpeg command (which expects t=0) would produce silence or A/V desync.

**Call site** in `render_landscape`:
```python
music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir, start_s=start_s)
```

Default `start_s=0.0` keeps existing behaviour for non-chunked render and audio preview.

---

### 4. SFX override layers: input-side seek with modulo

**Problem:** SFX override layers (foreground/midground/background from `sfx_overrides`) are looped ambient tracks. Currently each chunk opens them with `-stream_loop -1` from t=0. They restart at each chunk boundary — audible as a sudden loop reset in the ambient bed.

**Fix:** Same `_probe_duration` + modulo pattern as the visual. Applied in the audio input loop, for any input that is not `music_wav` or `sfx_wav` (those are exact-duration pre-rendered WAVs with no seek needed):

```python
for path, _ in audio_inputs:
    if path in (music_wav, sfx_wav):
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
```

`sfx_pool` (the scheduled random SFX events) is **already correct** — `_build_sfx_pool_wav` already receives `start_s`/`end_s` and rebases events to chunk-local time. No change needed.

---

### 5. Timeout floor

```python
# Before
_run_ffmpeg(cmd, target_dur * 2)

# After
_run_ffmpeg(cmd, max(120, target_dur * 2))
```

Ensures very short tail chunks (e.g., a 30 s remainder) still get at least 2 minutes for encoder startup and muxing.

---

## Change Summary

| What | Location | Change |
|---|---|---|
| Add `_probe_duration()` | After `_run_ffmpeg` | New helper |
| Visual input-side seek | Visual input block in `render_landscape` | Move `-ss` before `-i`, add modulo |
| Remove output-side `-ss` | Lines 509–510 in `render_landscape` | Delete |
| Music WAV continuity | `_build_music_playlist_wav` | Add `start_s` param, update `atrim` + `asetpts` |
| SFX layer continuity | Audio input loop in `render_landscape` | Add modulo seek for non-WAV inputs |
| Timeout floor | Last line of `render_landscape` | `max(120, target_dur * 2)` |

**One file. Six focused edits. No schema changes. No task changes.**

---

## Testing

1. Dispatch `render_youtube_chunk` for chunk index 10+ (start_s ≥ 3000) on a video with a non-image visual asset and at least one music track.
2. Confirm the logged ffmpeg command has `-ss` before `-i visual_path` (not after `-map`).
3. Confirm the chunk completes in < `target_dur * 2` wall-clock seconds.
4. After all chunks complete, run `concat_youtube_chunks_task` and scrub through chunk boundaries — no visual loop reset, no music restart, no SFX ambient reset.

### Quick sanity checks

```bash
# Verify ffprobe is available in the render container
docker exec ai-media-automation-celery-render-1 ffprobe -version | head -1

# Probe visual asset duration (used for modulo seek)
docker exec ai-media-automation-celery-render-1 ffprobe -v quiet \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  /app/assets/video_db/manual/asset_5.mp4
```

---

## What is NOT changed

- `render_portrait_short` — no chunking, no `start_s`; untouched
- `_build_sfx_pool_wav` — already `start_s`-aware; untouched
- `_build_visual_segment` (playlist path) — already pre-cut to `target_dur`; untouched
- `concat.py`, `youtube_render_task.py`, all models/schemas — untouched
- GPU encoder (`h264_nvenc`) — deferred to a follow-up
