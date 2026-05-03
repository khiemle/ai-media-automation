# ASMR Features for YouTube Videos — Design Spec (Revision)

**Date:** 2026-05-03
**Status:** Draft — REVISES `2026-05-03-asmr-soundscape-design.md` (which targeted the wrong system)
**Predecessor:** `2026-05-03-asmr-soundscape-design.md` — design decisions stand; integration surface changed.

## Why revision

The previous spec extended `generated_scripts` (Scripts→ProductionPage flow). The actual product flow for ASMR/Soundscape videos is the **YouTube tab → "+ New Video" modal**, backed by `youtube_videos` table and rendered via `pipeline/youtube_ffmpeg.py` (NOT the script-based `pipeline/composer.py`). All previous implementation was on `feat/asmr-soundscape` — abandoned. Migration 013 has been downgraded.

## What ports forward

Design decisions from the original spec are unchanged:
- Random SFX: script-level pool, density slider with seed for reproducibility (Q3a-A, Q3b-A).
- Black-from-time: 2s fade, audio continues, null = no blackout (Q4).
- Multi-music: ordered list, loop list when exhausted, 1.5s crossfade, per-track volume (Q5).
- Chunked render: ~5min chunks on whole-second boundaries, ffmpeg stream-copy concat for seamless seams (Q6).
- Preview workflow: audio preview → approve → video preview (first 2 min) → approve → final, optional skip (Q7).
- Progress UI: progress bar + per-chunk pills + log tail + WebSocket push (Q8).

What's different: **the renderer is ffmpeg directly, not MoviePy**. The audio mixing path uses ffmpeg's `amix`+`adelay`+`acrossfade` filters; the blackout uses `overlay=enable=...`+`fade=alpha`; the chunk render uses `-ss N -t M` slices.

## What's reused from `feat/asmr-soundscape` salvage

Pure modules saved to `/tmp/asmr-salvage/`:
- `pipeline/sfx_scheduler.py` + tests — deterministic seeded scheduler. **Reused as-is.**
- `pipeline/concat.py` + tests — ffmpeg concat-demuxer wrapper. **Reused as-is.**
- Frontend: `MusicPlaylistEditor`, `SfxPoolEditor`, `RenderStatePanel`, `PreviewApprovalGate`, `useRenderWebSocket`. **Reused with imports/wiring adapted from `productionApi` → `youtubeVideosApi`.**
- Backend WS: `console/backend/ws/render_ws.py` + the per-script Redis pub/sub publish in `mark_job_progress` / `emit_log`. **Reused with channel renamed from `render:script:{id}` → `render:youtube:{id}` and state reader pointing at `youtube_videos`.**

## Data Layer

Migration `013_asmr_youtube_fields.py` extends `youtube_videos`:

| Column | Type | Notes |
|---|---|---|
| `music_track_ids` | ARRAY(integer) default `{}` | Ordered playlist. Replaces single `music_track_id` use in renderer (column kept for back-compat — migration backfills `music_track_ids = ARRAY[music_track_id]` where set). |
| `sfx_pool` | JSONB default `[]` | List of `{asset_id, volume}` objects. Note: NOT just IDs — per-SFX volume needed because YouTube SFX assets are mastered at varying levels. |
| `sfx_density_seconds` | integer null | Mean gap between random SFX firings; ±50% jitter. Null = no random layer. |
| `sfx_seed` | integer null | RNG seed for deterministic SFX. Auto-set on first preview. |
| `black_from_seconds` | integer null | When visual fades to black. Null = no blackout. |
| `skip_previews` | boolean default `true` | Set to `false` by service in `create_video` for asmr/soundscape templates. |
| `render_parts` | JSONB default `[]` | `[{idx, start_s, end_s, status, file_path, error, started_at, completed_at}]` |
| `audio_preview_path` | varchar(500) | |
| `video_preview_path` | varchar(500) | |

`sfx_overrides` (existing 3-fixed-layer column) is preserved — the new random SFX pool is **additive**, not a replacement. This means a video can have BOTH the existing 3 fixed layers (foreground/midground/background loops) AND the new random pool. Mix is straightforward at the audio filter level.

Status enum on `youtube_videos.status` extended:
```
draft → queued → rendering → done   (existing)
draft → queued → audio_preview_rendering → audio_preview_ready
       → video_preview_rendering → video_preview_ready
       → rendering (chunked) → done
draft ← failed                       (existing)
```

## Backend Files

| Path | Status | Responsibility |
|---|---|---|
| `console/backend/alembic/versions/013_asmr_youtube_fields.py` | NEW | Migration |
| `console/backend/models/youtube_video.py` | MODIFY | Add SQLAlchemy columns |
| `pipeline/sfx_scheduler.py` + test | NEW (salvaged) | |
| `pipeline/concat.py` + test | NEW (salvaged) | |
| `pipeline/youtube_ffmpeg.py` | MODIFY | Refactor `render_landscape` to support: (a) multi-music input list with concat+crossfade, (b) random SFX schedule pre-rendered to a temp WAV, (c) black-overlay filter, (d) `start_s/end_s` parameters for chunk rendering. |
| `pipeline/youtube_audio_only.py` | NEW | `render_audio_only(video, output_path, db, start_s, end_s)` — runs an ffmpeg pass with `-vn` producing the audio mix only. Reuses the music+SFX builders from youtube_ffmpeg. |
| `console/backend/tasks/youtube_render_task.py` | MODIFY | Add 4 new Celery tasks: `render_youtube_audio_preview_task`, `render_youtube_video_preview_task`, `render_youtube_chunk_task`, `concat_youtube_chunks_task`, `render_youtube_chunked_orchestrator_task`. Existing `render_youtube_video_task` becomes the legacy single-shot path for non-ASMR templates. |
| `console/backend/services/youtube_video_service.py` | MODIFY | Add 10 methods mirroring the previous design (start/approve/reject for each gate, start_chunked, resume, cancel, get_render_state). Update `dispatch_render` to route asmr/soundscape with `skip_previews=False` to audio preview. Update `create_video` to set `skip_previews=False` when template is asmr/soundscape. |
| `console/backend/services/youtube_render_state.py` | NEW | Same shape as the abandoned `render_state.py` but reads `youtube_videos.render_parts` and pipeline_jobs filtered by job_type='render' + script_id stored as the video id. |
| `console/backend/routers/youtube_videos.py` | MODIFY | Add 10 new endpoints under `/youtube-videos/{video_id}/render/...`. Add 2 preview-file routes (`/preview/audio`, `/preview/video`) following the auth-less precedent of `stream_asset` (browsers can't send Bearer to media element loads). |
| `console/backend/ws/render_ws.py` | NEW (salvaged + adapted) | WebSocket at `/ws/render/youtube/{video_id}`. Channel: `render:youtube:{video_id}`. |
| `console/backend/services/pipeline_service.py` | MODIFY (small) | `emit_log` and `mark_job_progress` already publish to `render:script:{id}`. Adapt: introduce a `channel_kind` parameter (default "script" for back-compat; "youtube" for new tasks) so the publish goes to the right channel. Or simpler: pass full channel name. |
| `console/backend/tasks/job_tracking.py` | MODIFY | Same — accept `channel_kind` for the publish. |

## Frontend Files

| Path | Status | Responsibility |
|---|---|---|
| `console/frontend/src/components/MusicPlaylistEditor.jsx` | NEW (salvaged) | |
| `console/frontend/src/components/SfxPoolEditor.jsx` | NEW (salvaged + adapted) | Now emits `[{asset_id, volume}]` objects, not bare IDs, to match `youtube_videos.sfx_pool` shape. Add per-row volume slider next to existing density slider. |
| `console/frontend/src/components/RenderStatePanel.jsx` | NEW (salvaged + adapted) | Use `youtubeVideosApi` actions instead of `productionApi`. |
| `console/frontend/src/components/PreviewApprovalGate.jsx` | NEW (salvaged + adapted) | Same swap. Preview URL: `/api/youtube-videos/{id}/preview/{kind}`. |
| `console/frontend/src/hooks/useRenderWebSocket.js` | NEW (salvaged + adapted) | Path: `/ws/render/youtube/${videoId}`. |
| `console/frontend/src/api/client.js` | MODIFY | Extend `youtubeVideosApi` with: `getRenderState`, `startAudioPreview`, `approveAudioPreview`, `rejectAudioPreview`, `startVideoPreview`, `approveVideoPreview`, `rejectVideoPreview`, `startFinal`, `resume`, `cancel` (all under `/api/youtube-videos/{id}/render/...`). |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | MODIFY | Inside the New Video modal:<br>(a) Replace `② MUSIC` single Select with `<MusicPlaylistEditor>` for asmr/soundscape templates (legacy single-track Select for non-asmr).<br>(b) Add NEW section `④b RANDOM SFX POOL` (between SFX LAYERS and RENDER) for asmr/soundscape templates only — `<SfxPoolEditor>` + density slider + skip-previews toggle + black-from-time input.<br>(c) On the video card list (after creation): add `<RenderStatePanel>` and `<PreviewApprovalGate>` driven by `useRenderWebSocket(videoId)` when status is one of the new preview/render states. |

## API Endpoints

```
POST   /api/youtube-videos/{id}/render/audio-preview
POST   /api/youtube-videos/{id}/render/audio-preview/approve
POST   /api/youtube-videos/{id}/render/audio-preview/reject
POST   /api/youtube-videos/{id}/render/video-preview
POST   /api/youtube-videos/{id}/render/video-preview/approve
POST   /api/youtube-videos/{id}/render/video-preview/reject
POST   /api/youtube-videos/{id}/render/final              ← chunked
POST   /api/youtube-videos/{id}/render/cancel
POST   /api/youtube-videos/{id}/render/resume
GET    /api/youtube-videos/{id}/render/state
GET    /api/youtube-videos/{id}/preview/audio             ← FileResponse, no auth (browser media loads)
GET    /api/youtube-videos/{id}/preview/video             ← FileResponse, no auth
WS     /ws/render/youtube/{id}
```

Existing `POST /youtube-videos/{id}/render` is preserved; updated to route asmr/soundscape with `skip_previews=False` into audio preview, otherwise falls through to legacy `dispatch_render`.

## ffmpeg Filter Recipes

**Multi-music with crossfade + loop:**
For N tracks, build `concat=n=N:v=0:a=1[concatenated]; [concatenated]aloop=loop=-1:size={target_samples}[looped]; [looped]atrim=duration={target}` chain. Per-track volume applied via `[i:a]volume={v}[a_i]` before concat. Crossfade between adjacent tracks via `acrossfade=d=1.5` (chained pairwise).

**Random SFX pool:**
Pre-render to a temp WAV (`pipeline/youtube_audio_only.py` style, but SFX-only):
- For each (timestamp, asset_id) from `schedule_sfx()`, build `[i:a]adelay={ts*1000}|{ts*1000}[d_i]`.
- Mix all `[d_i]` with `amix=inputs=N:duration=longest:normalize=0`.
- Output to `temp_sfx.wav`. Use as one input in the main render.

**Black-from-time:**
Add to video filter chain:
```
[0:v]<existing scale/pad/fps>[v]; color=c=black:s={w}x{h}:r=30:d={overlay_dur}[bk]; [bk]fade=t=in:d=2:alpha=1[bkf]; [v][bkf]overlay=enable='gte(t,{black_from})':shortest=0[vout]
```

**Chunked render:**
Run `render_landscape(video, output_path, db, start_s=N, end_s=M)` with `-ss N` after the looping inputs and `-t (M-N)` instead of `-t duration`. Each chunk uses identical encoder params so concat-demuxer with `-c copy` joins seamlessly.

## Out of Scope

Same as previous spec: per-pair crossfade configurability, real-time SFX schedule editor, automatic preview cleanup on edit, per-event SFX volume (we have per-pool-entry volume in the new sfx_pool shape, which is enough), backwards UI for old `music_track_id` (renderer falls back to it when `music_track_ids` is empty).

## Migration & Rollout

1. Apply migration 013 (extends youtube_videos).
2. New asmr/soundscape video creation defaults `skip_previews=False` so preview flow kicks in.
3. Non-asmr templates render via existing `render_landscape`/`render_portrait_short` — single-shot, no preview, unchanged.
4. First test: create a 10-min asmr video → verify 2-chunk render + concat → audio preview → video preview → final.
