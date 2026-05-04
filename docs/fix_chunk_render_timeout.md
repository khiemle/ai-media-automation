# Fix: YouTube Chunk Render Timeout

**Symptom:** Every chunk of `YoutubeVideo 42` fails with `RuntimeError: ffmpeg timed out after 600s` and retries indefinitely. Later chunks (position > 2h) fail within seconds of starting their retry, never completing.

**Discovered:** 2026-05-04 via `docker compose logs celery-render`

---

## Root Cause

`render_landscape()` in `pipeline/youtube_ffmpeg.py` places `-ss start_s` **after** the filter graph — an output-side seek. This forces ffmpeg to:

1. Loop-decode the background video from t=0
2. Run the entire filter graph for every frame from 0 → `start_s`
3. Encode all of it to `/dev/null`
4. Only then start writing actual output

For a 5-minute chunk at position 8100 s (chunk 27 of video 42), ffmpeg must encode and discard **2.25 hours** of 1080p30 video before writing a single output frame. At ~40–60 fps with `libx264 ultrafast` on this CPU, that is ~135–200 s of overhead per chunk — before adding the 300 s of actual encoding. Total well exceeds the 600 s timeout.

Each subsequent chunk is worse: chunk 33 seeks to t=9900 (2.75 h = ~165 s overhead + 300 s encode ≈ 465 s, still under the timeout but shrinking margin fast, and the 60 s retry delay stacks).

Relevant lines (container version of `pipeline/youtube_ffmpeg.py`):

```python
# line 391-393  — THE BUG
# Window: -ss after inputs (output-side seek to apply to filter graph output)
if start_s > 0:
    cmd += ["-ss", str(int(start_s))]   # encodes + discards start_s seconds!
cmd += ["-t", str(target_dur)]
# ...
_run_ffmpeg(cmd, target_dur * 2)        # timeout ignores start_s overhead
```

---

## Fix Plan

### 1. Add `_probe_duration()` helper

Uses `ffprobe` (already present everywhere ffmpeg is) to get the duration of a file in seconds. Returns 0.0 on failure (caller must handle gracefully).

```python
def _probe_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, timeout=15,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0
```

### 2. Replace output-side seek with input-side seek

For a looped video (`-stream_loop -1`), the loop is conceptually infinite. ffmpeg's input-side `-ss` seeks within the underlying file. To land at the correct point in the loop, compute the modulo of `start_s` against the file's actual duration.

**Before (broken):**
```python
# Visual input — no seek here
cmd += ["-stream_loop", "-1", "-i", visual_path]

# ... filter graph, map args ...

# Output-side seek  ← BUG
if start_s > 0:
    cmd += ["-ss", str(int(start_s))]
cmd += ["-t", str(target_dur)]
_run_ffmpeg(cmd, target_dur * 2)
```

**After (fixed):**
```python
# Visual input — input-side seek for chunked windows
if start_s > 0:
    vid_dur = _probe_duration(visual_path)
    effective_seek = (start_s % vid_dur) if vid_dur > 1.0 else 0.0
    if effective_seek > 0.5:
        cmd += ["-stream_loop", "-1", "-ss", str(int(effective_seek)), "-i", visual_path]
    else:
        cmd += ["-stream_loop", "-1", "-i", visual_path]
else:
    cmd += ["-stream_loop", "-1", "-i", visual_path]

# ... filter graph, map args (unchanged) ...

# No output-side -ss; input already seeked  ← REMOVED
cmd += ["-t", str(target_dur)]
_run_ffmpeg(cmd, max(120, target_dur * 2))
```

**Why modulo?** `asset_5.mp4` might be 60 s long. Chunk 27 starts at 8100 s — that is loop iteration 135, position 0 s into the file. Without modulo, `-ss 8100` on a 60 s file would seek past EOF, and ffmpeg would either error or start from 0 anyway but non-deterministically.

**Why threshold `0.5`?** Avoids a pointless `-ss 0` for tiny float residuals.

**Why not `-ss` on images?** Images use `-loop 1` (single static frame), which has no duration to modulo against. No change needed.

**Why not `-ss` on music/sfx WAVs?** `music_wav` and `sfx_wav` are pre-rendered to exactly `target_dur` seconds for the chunk. They start at t=0 by design. `sfx_layers` (3-layer overrides) are looped ambient tracks with no positional meaning — correct as-is.

### 3. Upgrade to GPU encoder (`h264_nvenc`)

The celery-render container already has the NVIDIA driver reservation (`nvidia`, count=1) for the GTX 1660S. `libx264` is pure CPU; `h264_nvenc` offloads encoding to the GPU and is 5–15× faster at equivalent quality.

Add an encoder-selection helper:

```python
def _nvenc_available() -> bool:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True, text=True, timeout=10,
    )
    return "h264_nvenc" in (result.stdout or "")
```

Replace the encoder block in `render_landscape`:

```python
if _nvenc_available():
    # h264_nvenc: p1=fastest preset, vbr+cq≈crf, no tune:stillimage needed
    cmd += ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "23"]
else:
    preset = "ultrafast" if full_duration_s > 600 else "slow"
    if is_image:
        cmd += ["-c:v", "libx264", "-preset", preset, "-tune", "stillimage", "-crf", "23"]
    else:
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "23"]
```

> **Note:** All chunks of the same video must use identical codec/preset. Since `_nvenc_available()` is a process-level constant (driver either works or it doesn't), this is consistent across the chord.

### 4. Update timeout calculation

After the input-side seek fix, the timeout for `render_landscape` is simply the time needed to encode `target_dur` seconds. Keep the existing `target_dur * 2` factor (2× realtime headroom). With nvenc, actual encode should be well under 1× realtime.

```python
_run_ffmpeg(cmd, max(120, target_dur * 2))
```

No further change needed.

---

## Files to Change

| File | Change |
|---|---|
| `pipeline/youtube_ffmpeg.py` | Add `_probe_duration()`, add `_nvenc_available()`, replace output-side seek in `render_landscape` with input-side seek, update encoder block |

No task or schema changes needed. The fix is self-contained to the ffmpeg helper.

---

## Testing on Dev Machine

1. Pick a video with `target_duration_h >= 2` and a video (non-image) visual asset.
2. Dispatch a `render_youtube_chunk` task for chunk index 10+ (start_s ≥ 3000) via the API or directly via Celery.
3. Confirm the ffmpeg command logged no longer contains `-ss` after `-map` — it should appear before `-i visual_path`.
4. Confirm the chunk finishes in < 2× `target_dur` wall-clock seconds.
5. After all chunks complete, run `concat_youtube_chunks_task` and verify the concat is seamless (no A/V desync at chunk boundaries).

### Quick sanity check (no full render needed)

```bash
# Verify nvenc is available in the render container
docker exec ai-media-automation-celery-render-1 ffmpeg -hide_banner -encoders 2>/dev/null | grep nvenc

# Probe asset_5.mp4 duration (used for modulo seek)
docker exec ai-media-automation-celery-render-1 ffprobe -v quiet \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  /app/assets/video_db/manual/asset_5.mp4
```

---

## Why Chunks at Position 0 Still Work

Chunk 0 (`start_s=0`) never triggers the `-ss` output seek, so the existing code works for the first chunk. This is why video 42 made it through chunks 0–26 before failing — the accumulated overhead for chunks at position < ~7200 s was still under the 600 s timeout.

---

## Rollback

If the input-side seek causes a visible loop-boundary glitch (unlikely for ambient video), fall back to output-side seek but raise the timeout:

```python
_run_ffmpeg(cmd, int(start_s * 0.5) + target_dur * 2 + 120)
```

This is a band-aid, not a fix — it lets chunks finish but render time grows linearly with position.
