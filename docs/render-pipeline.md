# Long-Form YouTube Render Pipeline

> How a 3-hour 4K ambient-relax video is actually rendered, from "user clicks
> render" to the final muxed MP4. Covers chunked orchestration, audio layering,
> blackout, the music-loop bug we hit in v1.2.x, and the trade-offs of the
> current architecture.

---

## 1. The two render paths

There are **two** render strategies in the pipeline. They share the same low-level
helpers (`render_landscape`, music/SFX builders) but differ in how they slice
the work.

| Path | Entry task | When it's used |
|------|-----------|----------------|
| **Single-pass** | `render_youtube_video_task` | Non-ASMR/soundscape templates (one ffmpeg, video + audio together, no chunks) |
| **Chunked** | `render_youtube_chunked_orchestrator_task` | ASMR / soundscape with `skip_previews=True`, or anything dispatched via `start_chunked_render` after preview approval |

The chunked path is where everything interesting happens, and where every
"glitch every 5 min" bug we've fought lives. The rest of this document is
about that path.

Routing decision (`console/backend/services/youtube_video_service.py:716-744`):

```
asmr/soundscape + skip_previews=False → audio_preview → video_preview → start_chunked_render
asmr/soundscape + skip_previews=True  → chunked orchestrator directly
portrait_short                        → short render
everything else                       → render_youtube_video_task (single-pass)
```

---

## 2. The chunked orchestrator

`render_youtube_chunked_orchestrator_task` (`console/backend/tasks/youtube_render_task.py:533+`)
plans the chunks, persists state in the DB, and dispatches a Celery **chord**:

```
chord(
  group([
    render_youtube_chunk_task(video_id, idx=0,  start_s=0,    end_s=300),
    render_youtube_chunk_task(video_id, idx=1,  start_s=300,  end_s=600),
    render_youtube_chunk_task(video_id, idx=2,  start_s=600,  end_s=900),
    ...
    render_youtube_chunk_task(video_id, idx=35, start_s=10500, end_s=10800),
  ])
)(concat_youtube_chunks_task(video_id))
```

### Chunk size

Hard-coded at **300 s (5 min)**. For a 3-hour video that's exactly 36 chunks.
The number isn't magic — it's a balance between:

- **Smaller chunks** → finer-grained resume / cancel, smaller individual files.
- **Larger chunks** → less ffmpeg startup overhead, fewer DB writes.

```python
full_dur = int((video.target_duration_h or 3.0) * 3600)
n_chunks = max(1, math.ceil(full_dur / 300))
chunk_size = math.ceil(full_dur / n_chunks)
```

### `render_parts` JSONB column

Each chunk's state lives in `youtube_videos.render_parts` (Postgres JSONB array).
One element per chunk:

```jsonc
{
  "idx": 5,
  "start_s": 1500,
  "end_s": 1800,
  "status": "pending" | "running" | "completed" | "failed",
  "file_path": "/app/assets/output/youtube_42/chunk_5/chunk.video.mp4",
  "task_id": "celery-uuid-here",
  "started_at": "2026-05-20T13:00:00+00:00",
  "completed_at": "2026-05-20T13:04:55+00:00"
}
```

The atomic update helper (`_update_chunk_status`) writes via `jsonb_set` so
parallel chunk workers don't trample each other:

```sql
UPDATE youtube_videos
SET render_parts = jsonb_set(
  COALESCE(render_parts, '[]'::jsonb),
  ARRAY[CAST(:idx_str AS text)],
  COALESCE(render_parts->CAST(:idx_int AS int), '{}'::jsonb) || CAST(:patch AS jsonb),
  true
)
WHERE id = :video_id
```

### Resume semantics

When the orchestrator runs (start, retry, or resume), it walks the existing
`render_parts` and preserves entries that are still safe to reuse:

```python
prev_path = prev.get("file_path") or ""
is_post_v121_chunk = prev_path.endswith(".video.mp4")
if prev["status"] == "completed" and prev_path and is_post_v121_chunk:
    new_parts.append(prev)        # preserve
else:
    new_parts.append({...status: "pending"...})  # re-render
```

The `.video.mp4` suffix check exists specifically to **invalidate legacy
chunks** rendered before v1.2.1 — those had embedded AAC audio (`chunk.mp4`)
that's now incompatible with the mux pipeline (see §5).

---

## 3. Per-chunk video rendering

Each chunk runs `render_landscape(video, chunk_path, db, start_s, end_s, include_audio=False)`
in `pipeline/youtube_ffmpeg.py`.

**The chunk is VIDEO ONLY.** No audio stream. `-an` flag. Filename suffix
`chunk.video.mp4`. This is the key architectural decision behind v1.2.1.

### Why video-only chunks?

Because the alternative — independently AAC-encoding audio per chunk and then
`-c copy` concatenating — bakes a ~46 ms AAC priming gap into the output at
every chunk seam. MP4's `edts/elst` edit list, which normally trims that
priming on playback, only applies to the FIRST chunk's encode after a
stream-copy concat. Every subsequent seam becomes an audible click for tonal
music (and gets masked by broadband audio like rain or stream sounds — which
is why the bug was content-dependent).

### Encoder params

Encoder settings are **identical across chunks**, keyed off the FULL video
duration, not the chunk size. This matters for stream-copy concat:

```python
# Preset is "ultrafast" if full_duration_s > 600 (any long video),
# never per-chunk — otherwise a 500 s tail chunk would pick "slow"
# while earlier chunks used "ultrafast", breaking -c copy concat.

_maxrate, _bufsize = ("35M", "70M") if scale == "3840:2160" else ("8M", "16M")
if _nvenc_available():
    cmd += ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr", "-cq", "23", ...]
else:
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "23", ...]
```

### Visual handling per chunk

The visual input is positioned to absolute time `start_s`:

- **Visual playlist** (multiple clips/images): pre-rendered to a `vseg_concat.mp4`
  for the target window, then optionally looped to `target_dur`.
- **Single video asset**: `-stream_loop -1` + `-ss` to seek to `start_s % vid_dur`
  so each chunk picks up where playback would be at that moment.
- **Single image**: `-loop 1 -i image.jpg`.
- **All-black chunks** (when `start_s >= black_from_s`): skip visual entirely,
  feed `lavfi color=c=black` directly.

---

## 4. Audio rendering — one continuous pass

After all video chunks complete, `concat_youtube_chunks_task` runs
**one** ffmpeg pass to produce the full-duration audio:

```python
render_full_audio_track(video, audio_path, db)
```

This function (`pipeline/youtube_ffmpeg.py:1194+`):

1. Builds `music_playlist.wav` for the full duration (see §5).
2. Builds `sound_layers.wav` for the full duration (see §6).
3. Mixes them together with `amix`.
4. Encodes ONCE as AAC `192k`, 44.1 kHz stereo → `audio_full.m4a`.

The output has exactly ONE AAC encode → zero priming gaps anywhere → no per-N-min clicks
from the audio side.

---

## 5. Music playlist — seamless loop crossfade

`_build_music_playlist_wav` (`pipeline/youtube_ffmpeg.py:301+`).

### The bug (before v1.2.3)

```python
# OLD — broken for non-loopable music
if len(paths) == 1:
    parts.append("[v0]aloop=loop=-1:size=2147483647[looped]")
else:
    # crossfade between tracks, but loop boundary is still hard
    ...
    parts.append("[joined]aloop=loop=-1:size=2147483647[looped]")
```

`aloop` repeats the audio buffer **byte-for-byte**. The last sample of one
iteration butts up against the first sample of the next. Almost no music
naturally starts and ends at matching zero crossings, so this creates an
audible click at every loop boundary.

If the music track is 5 min long, the click lands every 5 min. **That was
the actual root cause** of the "glitch every 5 min" the user kept hearing,
not the chunk concat that v1.2.1 fixed.

You suspected this might come from moving from one music file → multiple:
half-right. The multi-track path crossfaded *between* tracks correctly, but
the `[joined]` block still hit `aloop` — so the boundary between iterations
of the JOINED playlist was still a hard cut. Single-track and multi-track
both had the bug, just with different loop periods.

### The fix (v1.2.3)

Probe each track's duration, compute how many iterations are needed to
overshoot the target by ≥ one crossfade, then replicate the playlist
that many times as **separate ffmpeg inputs** and crossfade every consecutive
pair — within and across iteration boundaries:

```
Track sequence:  T1 → T2 → T3 → T1 → T2 → T3 → ... (N iterations)
                  ↘  ↘  ↘  ↘  ↘  ↘
                acrossfade=1.5s between every adjacent pair
```

```python
n_iters = 1 + math.ceil((target_end - one_iter_natural) / (one_iter_natural - CROSSFADE)) + 1

seq = paths * n_iters  # e.g. 37 copies of a single 300 s track for a 3-h render

# pairwise acrossfade
prev = "v0"
for i in range(1, len(seq)):
    parts.append(f"[{prev}][v{i}]acrossfade=d=1.5:c1=tri:c2=tri[x{i}]")
    prev = f"x{i}"

# atrim to exactly target_duration_s
parts.append(f"[looped]atrim=start={start_s}:end={start_s+target_duration_s},asetpts=PTS-STARTPTS[out]")
```

If ffprobe can't determine a track's duration, falls back to the legacy
`aloop` path so we still produce *some* output rather than failing.

---

## 6. Sound layers — background loop + 3 scheduled layers

`_build_sound_layers_wav` (`pipeline/youtube_ffmpeg.py:463+`).

`video.sound_layers` is a JSON spec with **four** layers, each optional:

```jsonc
{
  "background": {                       // continuous, looped
    "asset_id": 1001,
    "volume": 0.4
  },
  "midground": {                        // scheduled events, medium gap
    "pool": [2001, 2002, 2003],
    "volume": 0.8,
    "interval_min_s": 15,
    "interval_max_s": 30
  },
  "foreground": {                       // scheduled events, longer gap
    "pool": [3001, 3002],
    "volume": 1.0,
    "interval_min_s": 30,
    "interval_max_s": 60
  },
  "random_sfx": {                       // sparse rare events
    "pool": [4001, 4002, 4003, 4004],
    "volume": 0.6,
    "interval_min_s": 60,
    "interval_max_s": 180
  }
}
```

### The background layer

ONE looping SFX file. Added as one ffmpeg input with `-stream_loop -1`, and
`-ss seek_s` if `start_s > 0` (so the loop phase is consistent across renders
that resume mid-way):

```python
seek = (start_s % asset_dur) if asset_dur > 0.5 and start_s > 0 else 0.0
cmd += ["-ss", str(seek), "-stream_loop", "-1", "-i", path]
```

⚠️ The background loop has the **same hard-loop boundary problem** as the
old music path (§5). For broadband background (rain, stream, white noise)
it's inaudible because the noise masks the seam. For tonal background it
would be audible. Today this is fine in practice because backgrounds are
always broadband ambience; if that ever changes, this layer needs the same
seamless-crossfade treatment as the music playlist.

### Scheduled layers (midground / foreground / random_sfx)

Each one uses `schedule_sfx_layer` (`pipeline/sfx_scheduler.py:42+`):

```python
def schedule_sfx_layer(pool_ids, interval_min_s, interval_max_s, seed, start_s, end_s):
    rng = random.Random(seed)
    # Burn one number per second of start_s so chunks at different offsets
    # still draw from the seeded stream consistently.
    for _ in range(int(start_s)):
        rng.random()
    schedule = []
    t = start_s
    while t < end_s:
        gap = rng.uniform(interval_min_s, interval_max_s)
        t += gap
        if t >= end_s:
            break
        sfx_id = rng.choice(pool_ids)
        schedule.append((round(t, 3), sfx_id))
    return schedule
```

**Determinism is critical.** Same `(seed, pool, interval_min, interval_max,
start_s, end_s)` always produces the same schedule. This is how we render
the *full* audio in one pass yet still match what a per-chunk render would
have placed.

Each layer uses its own seed offset so layers don't collide on the same RNG
stream:

```python
LAYER_SEED_OFFSETS = {
    "midground":  0,
    "foreground": 100003,
    "random_sfx": 200003,
}
```

### Mixing all layers

Each scheduled event becomes an ffmpeg input with `adelay=ts_ms|ts_ms` to
position it on the timeline; everything goes into `amix`:

```
[0:a]volume=0.4[bg0];                                        # background
[1:a]volume=0.8,adelay=18342|18342[ev0];                     # midground event @ 18.342 s
[2:a]volume=0.8,adelay=37105|37105[ev1];                     # midground event @ 37.105 s
[3:a]volume=1.0,adelay=42891|42891[ev2];                     # foreground event
[4:a]volume=0.6,adelay=88204|88204[ev3];                     # random_sfx event
... (potentially hundreds of events for a 3-h render)
[bg0][ev0][ev1][ev2]...[evN]amix=inputs=N+1:duration=longest:normalize=0[mixed]
[mixed]apad=whole_dur=10800[out]
```

The `apad=whole_dur=10800` ensures the output is exactly the target duration
even if all SFX events finish before the end. Then encoded as PCM s16le WAV.

For a 3-hour render with three active scheduled layers, that's typically
~1500–2000 ffmpeg inputs in this single filter graph. ffmpeg handles this
fine but the command line gets long; it's the practical upper bound today.

---

## 7. Blackout overlay

`video.black_from_seconds` (optional). When set, the visual fades to black
at that absolute time and stays black for the rest of the video. Common for
"X hours then fade to black sleep" renders.

Per-chunk handling:

```python
black_from_s = getattr(video, "black_from_seconds", None)
# Chunks entirely within the black period need no visual — skip the
# expensive visual-segment build and go straight to a lavfi black source.
chunk_is_all_black = black_from_s is not None and start_s >= black_from_s
```

For chunks that straddle the blackout boundary, `_blackout_filter_chain`
adds a fading-in black overlay at the correct local timestamp:

```
[v_main][bkf]overlay=enable='gte(t,{local_start})':shortest=0[vout]
```

For chunks fully past `black_from_s`, the entire chunk's video input
becomes `lavfi color=c=black` — no expensive visual decode, just black
frames at the target fps.

---

## 8. Concat + mux (final step)

`concat_youtube_chunks_task` (`console/backend/tasks/youtube_render_task.py:370+`)
runs after every chunk completes (Celery chord callback). It does:

### Step 1 — safety net

`ffprobe` every chunk and refuse to mux if any chunk has an audio stream:

```python
for p in parts:
    res = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        p["file_path"],
    ], ...)
    if res.stdout.strip():
        bad_chunks.append(p["idx"])
if bad_chunks:
    raise RuntimeError(f"Refusing to concat: chunks {bad_chunks} still contain embedded audio")
```

This catches the corner case where a legacy chunk somehow slipped past the
orchestrator's `.video.mp4` filter.

### Step 2 — render full audio

`render_full_audio_track(video, audio_path, db)` (see §4–§6).

### Step 3 — concat + mux

`concat_video_and_mux_audio` (`pipeline/concat.py:76+`):

```bash
ffmpeg -y \
  -f concat -safe 0 -i list.txt \   # stream-copy concat the video-only chunks
  -i audio_full.m4a \                # the single continuous audio
  -map 0:v:0 -map 1:a:0 \            # video from concat, audio from .m4a
  -c copy \                          # NO re-encoding
  -shortest \                        # trim to shorter stream (defensive)
  final.mp4
```

`-shortest` defends against minor cumulative drift in the concatenated video
duration vs the exact audio duration (see §10).

---

## 9. Cancel / resume / error handling

### Cancel

`cancel_chunked_render` revokes **every** in-flight Celery task ID:

```python
for part in (video.render_parts or []):
    task_id = part.get("task_id")
    if task_id:
        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
if video.celery_task_id:  # concat callback
    celery_app.control.revoke(video.celery_task_id, terminate=True, signal="SIGTERM")
```

This is why the orchestrator persists each chunk's `task_id` to `render_parts`
*before* dispatching the chord — so cancel can find them immediately.

### Resume

`resume_chunked_render` walks `render_parts`, resets `failed`/`running`
entries to `pending`, then re-runs the orchestrator. Completed `.video.mp4`
entries are preserved.

### Failure modes

| Stage fails | What happens |
|-------------|--------------|
| One chunk | Chunk marks `failed`. After 2 retries, video marks `failed`. User can `resume` to re-run pending. |
| `render_full_audio_track` | Concat task fails, video marks `failed`. Chunks are preserved — `resume` skips them and re-tries audio + mux. |
| `concat_video_and_mux_audio` | Same as above. |
| Legacy chunk detected | Concat task raises clear error. User restarts; orchestrator invalidates and re-renders as video-only. |

---

## 10. Trade-offs and known issues

### Cumulative A/V drift in the chunked path

Each chunk is encoded with `-t 300`. ffmpeg targets 300 s but the actual
container duration can vary by a frame or two (~33 ms at 30 fps) depending
on GOP placement. Over 36 chunks: maybe ~1 s cumulative video-vs-audio
mismatch. The `-shortest` flag handles it cleanly by trimming the longer
stream.

For ambient/relax content where visuals are loops and SFX events are
positionally random, drift doesn't matter. For content where audio events
must hit specific video frames, prefer the single-pass path.

### Why we don't render the WHOLE video in one ffmpeg pass

We could. Pros: zero drift, dead simple, no chunk-boundary anything.
Cons: a 3-hour render becomes one 1.5–3 hour ffmpeg process with no resume.
If the worker restarts mid-render, you lose everything.

The chunked path trades a bounded amount of A/V drift for crash resilience.
Whether that's the right call depends on how stable the render worker is
in production.

### Background SFX still uses `aloop`

The seamless-crossfade fix (§5) was applied to the music playlist only.
The background sound layer (§6) still uses `-stream_loop -1` and would
have the same loop-boundary click for tonal content. In practice all
backgrounds are broadband ambience, so the click is masked. If this
assumption ever breaks, give `background` the same crossfade treatment
as music.

### SFX count scaling

A 3-hour render with all three scheduled SFX layers active produces
~1500–2000 ffmpeg inputs in `_build_sound_layers_wav`. This works today
but the command line is long and ffmpeg startup is non-trivial. For
significantly longer renders (8+ hours), consider building the SFX layer
in batches and concatenating the WAVs.

---

## 11. Version history (relevant fixes)

| Version | Fix |
|---------|-----|
| v1.2.0 | Baseline chunked render (had AAC priming glitch every 5 min) |
| v1.2.1 | Video-only chunks + `render_full_audio_track` + `concat_video_and_mux_audio` — eliminates AAC priming at chunk seams |
| v1.2.2 | Chunk filename suffix `.video.mp4` + orchestrator invalidates legacy `.mp4` chunks on resume; ffprobe safety net in concat task |
| v1.2.3 | Music playlist seamless loop via N-copy acrossfade (eliminates per-track-length click) |

---

## 12. File map

| File | Purpose |
|------|---------|
| `console/backend/services/youtube_video_service.py` | `dispatch_render` (path routing), `start_chunked_render`, `resume_chunked_render`, `cancel_chunked_render` |
| `console/backend/tasks/youtube_render_task.py` | `render_youtube_chunked_orchestrator_task`, `render_youtube_chunk_task`, `concat_youtube_chunks_task`, `_update_chunk_status` |
| `pipeline/youtube_ffmpeg.py` | `render_landscape` (per-chunk video), `_build_music_playlist_wav` (§5), `_build_sound_layers_wav` (§6), `_blackout_filter_chain` (§7), `render_full_audio_track` (§4) |
| `pipeline/concat.py` | `concat_parts` (legacy AAC concat), `concat_video_and_mux_audio` (current mux pipeline) |
| `pipeline/sfx_scheduler.py` | `schedule_sfx_layer` — deterministic event timing per layer/seed |
| `docs/render-pipeline-visualization.html` | Interactive timeline + flowchart visualization of this pipeline |
