# YouTube Pipeline Fixes & SFX Redesign — Design Spec

**Date:** 2026-05-01  
**Scope:** Bug fixes across YouTube Videos, Uploads, Pipeline pages + SFX audio in render + SFX Library UI redesign

---

## Overview

Six issues to address across the Management Console:

1. YouTube video Preview button never shows (wrong status check)
2. YouTube Long videos not appearing in Uploads tab
3. Uploads format filter collapses when "YouTube Long" selected
4. Visual asset list empty in YouTube video CreationPanel
5. SFX audio not applied in YouTube video render
6. SFX Library page UI redesign (grid layout)

---

## Issue 1 — Preview button never shows (YouTubeVideosPage)

**Root cause:** `YouTubeVideosPage.jsx` shows the Preview button when `v.status === 'ready'`, but the YouTube video render pipeline sets status to `'done'` on completion, not `'ready'`.

**Fix:** Change the Preview button condition from `v.status === 'ready'` to `v.status === 'done'`.

**File:** `console/frontend/src/pages/YouTubeVideosPage.jsx`

---

## Issue 2 — YouTube Long videos not appearing in Uploads tab

**Design:** Add a second list section — **"YouTube Long Videos"** — inside the existing Videos tab in `UploadsPage.jsx`, below the current Production Videos list. The two sections are visually separated by a section header with a divider.

**Data source:** Queries `/api/youtube-videos?status=done` directly. No new backend endpoint needed — the existing list endpoint already supports status filtering.

**Each item shows:**
- Title
- Duration (formatted as hours)
- Created date
- Status badge (`done` / `published`)
- Channel picker (YouTube channels only, same component as short-form)
- Upload button — calls `POST /api/youtube-videos/{id}/upload` with `{ channel_id }`, which dispatches an `upload_to_channel_task` using the video's `output_path` as the source file

**New backend endpoint required:** `POST /api/youtube-videos/{id}/upload` in `console/backend/routers/youtube_videos.py`. Accepts `channel_id`, validates the video is in `done` status, and enqueues `upload_to_channel_task(youtube_video_id=id, channel_id=channel_id)`. Updates video status to `published` on task completion.

**Relationship to short-form flow:** Completely separate. YouTube Long videos are never mixed into the Production Videos list. No shared state between the two sections.

---

## Issue 3 — Format filter collapses when "YouTube Long" selected

**Root cause:** The Production Videos format filter includes a `youtube_long` option, but youtube_long videos do not exist in the uploads table — selecting it returns an empty list and a CSS layout collapse hides the filter bar.

**Fix:** Remove `youtube_long` from the Production Videos format filter. The filter keeps only `all` and `short`. YouTube Long videos are now surfaced via their own dedicated section (Issue 2).

**File:** `console/frontend/src/pages/UploadsPage.jsx`

---

## Issue 4 — Visual asset list empty in CreationPanel

**Root cause:** `YouTubeVideosPage.jsx` (Task 4 implementation) filters assets client-side using:
```js
const AI_SOURCES = ['midjourney', 'runway', 'veo']
filter(a => AI_SOURCES.includes(a.source))
```
The `source` values stored in the `video_assets` table likely use a different casing or naming convention (e.g. `'Midjourney'`, `'mid_journey'`).

**Fix:**
1. Query the actual `source` values in the DB: `SELECT DISTINCT source FROM video_assets WHERE asset_type = 'video_clip'`
2. Update `AI_SOURCES` to match the exact stored values (or normalise by lowercasing both sides during comparison)

**File:** `console/frontend/src/pages/YouTubeVideosPage.jsx`

---

## Issue 5 — SFX audio not applied in YouTube video render

**Root cause:** `youtube_render_task.py`'s `_render_video()` resolves music and visual assets but does not read `video.sfx_overrides` — the SFX configuration is stored in the DB but never passed to FFmpeg.

### Audio model

All four audio sources are individually optional:
- `music_track_id` — resolved via `MusicTrack` (existing)
- `sfx_overrides.foreground` — `{ asset_id, volume }`
- `sfx_overrides.midground` — `{ asset_id, volume }`
- `sfx_overrides.background` — `{ asset_id, volume }`

At least 1 selected → valid render with that audio. 0 selected → silence fallback (current behaviour, unchanged).

### New helper: `_resolve_sfx_layers(video, db)`

Reads `video.sfx_overrides` (JSONB). For each of the three named layers, looks up `SfxAsset` by `asset_id` and returns the `file_path` and `volume`. Returns a list of `(file_path, volume)` tuples for layers that have an `asset_id` set. Skips layers with no `asset_id` or missing file on disk.

### FFmpeg audio graph changes

The audio section of the FFmpeg command in `_render_video()` becomes dynamic:

1. Collect all audio inputs: music (if selected) + resolved SFX layers (0–3)
2. For each input, add `-i <path> -stream_loop -1` to loop for full video duration
3. Apply per-input volume filter: `[N:a]volume=X[aN]`
4. Merge all labelled streams: `amix=inputs=N:duration=first:normalize=0`
5. If no inputs → silence (existing `-f lavfi -i anullsrc` fallback)

No schema changes required — `sfx_overrides` is already JSONB on `YoutubeVideo`, already populated by the creation form.

**Files:**
- `console/backend/tasks/youtube_render_task.py` — add `_resolve_sfx_layers()`, update `_render_video()`

---

## Issue 6 — SFX Library UI redesign

**Current state:** Full-width list rows — hard to scan a large library.

### New layout: 3-column grid

Grid class: `grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4` — adapts to viewport; default sidebar layout shows 3 columns.

**Each card (~120px tall):**
- Top row: play/pause icon button (left) + sound type badge (right, muted `text-[#5a5a70]`)
- Middle: title — `text-sm font-medium text-[#e8e8f0]`, truncated to 2 lines
- Bottom: duration bar (`h-0.5 bg-[#7c6af7]`, same as current implementation) + duration label (`text-xs font-mono text-[#5a5a70]`)
- Hover state reveals a delete icon (top-right corner overlay, `text-[#f87171]`)

**Page chrome (unchanged in function):**
- Search input + sound type filter dropdown — top bar above the grid
- Import button — top-right page action, outside the grid

**Files:** `console/frontend/src/pages/SFXPage.jsx`

---

## File Map

| File | Change |
|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Fix Preview button status check; fix AI_SOURCES filter |
| `console/frontend/src/pages/UploadsPage.jsx` | Remove `youtube_long` from format filter; add YouTube Long Videos section |
| `console/frontend/src/pages/SFXPage.jsx` | Redesign to 3-column grid layout |
| `console/backend/tasks/youtube_render_task.py` | Add `_resolve_sfx_layers()`; update `_render_video()` for dynamic audio mix |
| `console/backend/routers/youtube_videos.py` | Add `POST /{id}/upload` endpoint |
