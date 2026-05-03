# ASMR & Soundscape Video Pipeline — Design Spec

**Date:** 2026-05-03
**Status:** Draft (awaiting user review)

---

## Overview

Add a new `asmr` / `soundscape` template family to the rendering pipeline. These are typically long-form (10 min → multi-hour) ambient videos with minimal narration, heavy on layered music + random SFX, often consumed for sleep/relaxation.

Six new capabilities, **all scoped to the new template family** — existing templates render unchanged:

1. **Random SFX layer** — script-defined SFX pool plays at a configurable density during the video, seeded for reproducibility
2. **Black-from-time** — at a configurable timestamp, the visual fades to black while audio continues (sleep mode)
3. **Visible render progress** — surface the existing `PipelineJob.progress` + log tail in the UI via WebSocket
4. **Resumable chunked render** — split long videos into ~5min chunks; each chunk is its own Celery subtask; chunk state persisted so a crash only loses the in-flight chunk; final concat with stream-copy guarantees seamless joins
5. **Preview-and-approve workflow** — two new gates before final render: audio preview (audio only, ~2 min) → editor approves → video preview (first chunk = ~2 min with sound) → editor approves → final render (preview chunk reused as final chunk 1)
6. **Multi-music ordered playlist** — script holds an ordered list of music tracks; tracks play in order with crossfade, looping the list when exhausted

---

## 1. Data Layer

### Schema changes (one migration: `00X_asmr_soundscape.py`)

**Extend `generated_scripts`:**

| Column | Type | Notes |
|---|---|---|
| `music_track_ids` | ARRAY(integer) | ordered list of `music_tracks.id`. Replaces the single FK `music_track_id` (kept nullable for back-compat; migration backfills new column from old when present) |
| `sfx_pool_ids` | ARRAY(integer) | `sfx_assets.id` values eligible for random SFX. Empty = no SFX layer |
| `sfx_density_seconds` | integer | mean gap between SFX firings; jitter is ±50%. Null = no SFX. Default 60 |
| `sfx_seed` | integer | RNG seed for deterministic SFX schedule. Auto-set on first render |
| `black_from_seconds` | integer | timestamp (s from start) where visual fades to black; null = no blackout |
| `skip_previews` | boolean | when true, jumps straight from approved → final render. Default false for asmr/soundscape, true for other templates (acts as feature gate) |
| `render_parts` | JSONB | array of `{idx, start_s, end_s, status, file_path, started_at, completed_at, error}`; populated when render starts |
| `audio_preview_path` | varchar(500) | path to audio-only preview WAV |
| `video_preview_path` | varchar(500) | path to video preview MP4 (first chunk) |

**Extended `status` enum** (string column, no DB enum — already free-text):

```
draft → pending_review → approved
  → audio_preview_rendering → audio_preview_ready
  → video_preview_rendering → video_preview_ready
  → producing (chunked) → completed
  ↑ rejected / editing transitions back to approved as today
```

If `skip_previews=true`, transitions go `approved → producing → completed` as today.

**No changes to** `music_tracks`, `sfx_assets`, `pipeline_jobs`, `video_assets`. Existing tables already carry all the metadata we need.

---

## 2. Backend Architecture

### Modified / new files

| File | Change |
|---|---|
| `console/backend/models/generated_script.py` | Add new columns above |
| `console/backend/services/production_service.py` | New methods: `start_audio_preview`, `start_video_preview`, `approve_audio_preview`, `approve_video_preview`, `start_final_render` (chunked dispatch), `cancel_render`, `get_render_state` |
| `console/backend/tasks/production_tasks.py` | Replace single `render_video_task` with: `render_audio_preview_task`, `render_video_preview_task`, `render_chunk_task`, `concat_chunks_task`, plus orchestrator `render_chunked_task` that dispatches a Celery `chord(group(chunks), concat)` |
| `console/backend/routers/production.py` | New endpoints listed in §4 |
| `pipeline/composer.py` | (a) Refactor existing compose into `compose_window(script_id, start_s, end_s)` so chunks and previews share one path. (b) New `_build_sfx_layer(script, start_s, end_s, seed)` that schedules SFX deterministically. (c) New `_build_music_playlist(script, start_s, end_s)` for ordered multi-track music with crossfade. (d) New `_apply_blackout(video, black_from_s)` that fades video → black at the given offset, leaving audio untouched. |
| `pipeline/renderer.py` | Add `concat_parts(part_paths, output_path)` that runs `ffmpeg -f concat -safe 0 -i parts.txt -c copy output.mp4`. Enforce identical encoder params across chunks (already true since renderer uses fixed NVENC settings). |
| `console/backend/ws/render_ws.py` | New WebSocket endpoint `/ws/render/{script_id}` — broadcasts progress + log lines emitted via `mark_job_progress` / `emit_log` |
| `console/backend/services/render_state.py` | New helper module that reads `render_parts` JSON + `pipeline_jobs` rows and produces a unified state object the frontend consumes |

### SFX scheduling algorithm

```python
def schedule_sfx(pool_ids, density_s, seed, start_s, end_s):
    rng = random.Random(seed)
    schedule = []
    t = start_s
    while t < end_s:
        gap = density_s * rng.uniform(0.5, 1.5)  # ±50% jitter
        t += gap
        if t >= end_s: break
        sfx_id = rng.choice(pool_ids)
        schedule.append((t, sfx_id))
    return schedule
```

Same `(seed, pool, density)` always produces the same schedule, so the SFX in the 2-min preview match the SFX in the first 2 min of the final video. The seed is auto-generated on first preview render and saved on the script.

### Chunking policy

- `n_chunks = ceil(duration / 300)`; `chunk_size = ceil(duration / n_chunks)`. Last chunk may be slightly shorter if duration doesn't divide evenly.
  - 10 min → 2 chunks of 300s
  - 12 min → 3 chunks of 240s
  - 8 hours → 96 chunks of 300s
- Chunks split on **whole seconds only** (no frame-level boundaries that could differ across runs).
- Each `render_chunk_task(script_id, chunk_idx, start_s, end_s, seed)` calls `compose_window` with identical encoder params, writes `part_{idx}.mp4`, updates `render_parts[idx].status = completed`.
- Concat task waits for all chunks complete, runs ffmpeg concat demuxer with `-c copy` (no re-encode). Stream copy guarantees seamless join: same codec, same params, same GOP cadence.
- **Video preview is independent of chunks** (preview window is fixed at min(120, duration); chunk size is 240–300s). No preview-reuse — re-rendering 2 minutes at the start of a long final render is cheap relative to the rest, and avoids coupling preview length to chunk size.

### Resume semantics

- On Celery worker startup or manual retry, an orchestrator entry point scans `render_parts` and re-queues any chunk with status `pending` or `running` (the running ones were interrupted). Completed chunks are kept as-is.
- The concat task only fires once all chunks report `completed`.
- A single `render_id` (UUID stored on the `PipelineJob` row) groups all subtasks for cancellation.

---

## 3. Frontend Architecture

### Modified / new files

| File | Change |
|---|---|
| `console/frontend/src/pages/ProductionPage.jsx` | Detect `script.template in ['asmr','soundscape']` and render an alternate sidebar panel: ASMR controls instead of the per-scene editor. Existing per-scene editor still shows for non-ASMR scripts. Add a global render-state panel (progress bar + stage label + log tail) for all templates. |
| `console/frontend/src/components/AsmrControls.jsx` | New component: black-from time input, SFX pool picker (modal: pick from `sfx_assets` table), SFX density slider, music playlist editor (drag-to-reorder, per-track volume), skip-previews toggle |
| `console/frontend/src/components/MusicPlaylistEditor.jsx` | Drag-and-drop ordered list, "Add track" opens MusicLibrary modal in multi-select mode, per-row volume slider |
| `console/frontend/src/components/SfxPoolEditor.jsx` | Multi-select grid of SFX assets, density slider with audible preview |
| `console/frontend/src/components/RenderStatePanel.jsx` | Progress bar (0–100), current stage label ("Rendering chunk 3 of 12"), per-chunk pills (green=done, yellow=running, gray=pending, red=failed), tailing log panel (last 50 lines), Cancel button, Resume button if any chunk failed |
| `console/frontend/src/components/PreviewApprovalGate.jsx` | Shown when status is `audio_preview_ready` or `video_preview_ready`. Embedded `<audio>` or `<video>` player, Approve and Reject buttons. Reject returns status to `approved` |
| `console/frontend/src/hooks/useRenderWebSocket.js` | Subscribes to `/ws/render/{script_id}`, dispatches state into a local reducer, auto-reconnect with exponential backoff |

### Render flow UI states

| Script status | UI state |
|---|---|
| `approved` | Show "Render Audio Preview" button (or "Skip to Final Render" if `skip_previews=true`) |
| `audio_preview_rendering` | Progress panel only |
| `audio_preview_ready` | Approval gate with audio player |
| `video_preview_rendering` | Progress panel only |
| `video_preview_ready` | Approval gate with video player |
| `producing` | Progress panel with per-chunk pills + Cancel button |
| `completed` | Final video player + Upload button |

---

## 4. API Endpoints (new)

```
POST   /api/production/scripts/{id}/render/audio-preview    → enqueue audio preview
POST   /api/production/scripts/{id}/render/audio-preview/approve
POST   /api/production/scripts/{id}/render/audio-preview/reject
POST   /api/production/scripts/{id}/render/video-preview    → enqueue first-chunk video preview
POST   /api/production/scripts/{id}/render/video-preview/approve
POST   /api/production/scripts/{id}/render/video-preview/reject
POST   /api/production/scripts/{id}/render/final            → enqueue chunked final render
POST   /api/production/scripts/{id}/render/cancel
POST   /api/production/scripts/{id}/render/resume           → re-queue any pending/failed chunks
GET    /api/production/scripts/{id}/render/state            → unified state (progress, chunks, logs tail)
WS     /ws/render/{script_id}                                → live state push
```

Existing `POST /api/production/scripts/{id}/render` is kept and routes to the appropriate path based on `template` and `skip_previews`:
- ASMR/Soundscape with `skip_previews=false` → audio preview
- Anything else → existing render flow (single Celery task, no chunking, no previews)

---

## 5. Pipeline Behavior Details

### Multi-music with crossfade

Tracks play in `music_track_ids` order. When the last track ends, restart from index 0. Between adjacent tracks, a 1.5s linear crossfade. Implementation in MoviePy: load each `AudioFileClip`, `set_start` cumulatively (subtract crossfade), use `CompositeAudioClip` with `audio_fadeout` / `audio_fadein`. Per-track volumes pulled from `music_tracks.volume`.

If the playlist's total duration > video duration: truncate at video end. If shorter: loop the whole playlist as a unit.

### Black-from-time

When `black_from_seconds` is set, the visual track is wrapped in a `CompositeVideoClip` with a black `ColorClip` overlaid from `black_from_seconds` onward, with a 2-second fade-in on the overlay. Audio track is untouched. Subtitles (if any) are also hidden after the blackout point.

Black overlay also applies to chunks: any chunk whose window crosses `black_from_seconds` gets the overlay; chunks fully past the blackout render the visual layer as a static black frame (saves encoding time).

### Audio preview

`render_audio_preview_task` calls a new `compose_audio_only(script_id, start_s=0, end_s=min(120, duration))` that produces narration (if any) + multi-music + SFX layer, writes `audio_preview.wav` (44.1kHz stereo), updates status to `audio_preview_ready`, broadcasts via WebSocket. No video encoding — should complete in seconds even for long scripts.

### Video preview

`render_video_preview_task` calls `compose_window(script_id, 0, min(120, duration))` and the renderer with the same encoder params used for chunks. Writes `video_preview.mp4`. The preview is informational only — final render re-renders chunk 0 from scratch (cheap relative to the rest of a long render).

### Progress reporting

Existing `mark_job_progress` / `emit_log` are unchanged. New work:
- Each chunk task updates `render_parts[idx].status` and emits a log line on every state transition.
- Overall progress = `(completed_chunks + current_chunk_progress) / total_chunks * 100`.
- New WebSocket endpoint subscribes to a Redis pub/sub channel `render:{script_id}`. The `emit_log` helper is extended to also publish to that channel when a `script_id` is in scope.

---

## 6. Error Handling & Edge Cases

| Case | Behavior |
|---|---|
| Empty SFX pool but density set | Treat as no SFX layer; warn in render log |
| `black_from_seconds >= duration` | Reject at API layer with 400 |
| Music playlist empty | Render with no music (silence on music track); log warning |
| Chunk fails after retries (3) | Mark chunk `failed`, stop concat, surface error in UI with Resume button |
| Worker crashes mid-chunk | On next worker startup (or manual Resume), the in-flight chunk is re-queued. Partial chunk file is overwritten |
| Video shorter than 2-min preview window | Preview = full duration |
| Editor edits script after preview approval | Status returns to `approved`; previews invalidated (paths cleared); must re-preview |
| Concat fails due to codec mismatch | Should never happen since renderer enforces fixed params; if it does, fall back to re-encode concat (`-c:v copy` removed) and log critical error |
| User cancels mid-render | Revoke pending Celery tasks; mark in-flight chunks `cancelled`; status returns to last preview-approved state |

---

## 7. Testing Strategy

| Layer | Tests |
|---|---|
| SFX scheduler | Unit test: same seed produces identical schedule; different seeds differ; density honored within tolerance |
| Multi-music | Unit test: 3 tracks of 30s play in order across 2-min window; crossfade non-zero amplitude in transition region |
| Blackout | Unit test: frame at `black_from + 5s` is all-black; audio sample at same time matches non-blackout render |
| Chunk seam | Integration test: render a 60s video as 2×30s chunks; render same as 1×60s; FFprobe both for codec params; concat the chunked version; assert pixel-perfect equality of decoded frames at and around the seam (tolerance for codec rounding) |
| Resume | Integration test: render 4 chunks, kill worker after chunk 2 completes, restart, assert chunks 3+4 render and chunk 0+1 are not re-rendered |
| Preview reuse | Integration test: render video preview; trigger final render; assert `part_0.mp4` size + checksum matches `video_preview.mp4` |
| WebSocket | Integration test: trigger render, connect WS, receive progress events 0 → 100 in order |
| API status transitions | Unit test: each transition (approve/reject/cancel) lands on the documented state |

---

## 8. Out of Scope

- SFX volume per-event (all SFX play at the SFX asset's stored volume; no per-script SFX volume slider in v1)
- Crossfade length per-pair (single 1.5s value applies to all transitions)
- Per-chunk regeneration UI (Resume re-queues failed chunks; selectively re-rendering a completed chunk is a future feature)
- Real-time visual editor for the SFX schedule (deterministic seed is the contract; if the editor wants different timing, they re-render to get a new seed or override `sfx_seed` manually)
- ASMR-specific scraper / script-generation prompts — that's a separate spec; this doc covers only render + UI for already-existing ASMR scripts
- Backwards-migration UI for existing scripts that used `music_track_id`; the migration backfills automatically and the old column is left in place

---

## 9. Migration & Rollout

1. **Migration** adds new columns; backfills `music_track_ids = [music_track_id]` where the old column is non-null.
2. **Code deploy** ships chunked renderer behind a per-template gate. Non-ASMR templates use the existing single-task render path until proven stable.
3. **First test:** create an ASMR script with a 10-min duration → verify 2-chunk render + concat → verify seam is seamless via ffprobe + manual playback.
4. **Optional later:** flip `skip_previews` default to `false` for all templates once chunked render is proven, getting universal preview gates.
