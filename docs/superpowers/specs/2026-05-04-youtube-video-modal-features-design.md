# YouTube Video Modal — Feature Additions

**Date:** 2026-05-04
**Status:** Design approved, awaiting plan
**Scope:** Five additions to the Create / Edit YouTube Video modal in the Management Console

---

## 1. Goals

Five additions to the YouTube Videos page (`console/frontend/src/pages/YouTubeVideosPage.jsx` and adjacent components):

1. **Edit existing video** — open the same form prefilled; on save reset status to `draft` and discard orphaned preview / output artifacts. Allowed only from `draft`, `failed`, `audio_preview_ready`, `video_preview_ready`. `done` and `published` are immutable; no clone path.
2. **Modal-style SFX layer pickers** — replace the three plain `<select>` dropdowns in **④ SFX LAYERS** (Foreground / Midground / Background) with the same modal picker pattern as **④b RANDOM SFX POOL**. Each layer remains single-select.
3. **Listen-before-select** — small ▶ button per row in every SFX/music modal, with single-track-at-a-time semantics. Applies to ④b SFX pool picker, the new ④ SFX layer picker, and the existing music playlist's "Add Track" modal.
4. **Visual picker becomes a playlist editor** — replace the visual `<select>` with an inline `VisualPlaylistEditor` mirroring `MusicPlaylistEditor` (reorder ↑↓, remove ×, per-clip duration field). **+ Add Visual** opens a single-select modal with thumbnail grid + click-to-play preview.
5. **Multi-visual loop on render** — videos play in playlist order. User picks one of two loop modes:
   - **Concat-then-loop** *(default)*: each item plays its native length once, sequence repeats until target duration is reached. Stills use the per-clip duration field.
   - **Per-clip duration**: every item plays for its configured duration; videos shorter than their slot loop within the slot, longer ones are trimmed; sequence repeats to fill target duration.
   - Mixed lists (videos + stills) allowed. Default per-clip duration for stills: **3.0s**.

**Out of scope.** No clone-on-edit. The non-ASMR single-track music dropdown (`<Select>` for `music_track_id`) is *not* converted to a modal; only the existing playlist modal gains the play button.

---

## 2. Architectural choices

**Picker reuse.** Extract a tiny shared `PreviewPlayer` primitive and reuse it inside the existing `SfxPoolEditor` modal, the existing `MusicPlaylistEditor` modal, and the two new picker modals (`SfxPickerModal`, `VisualPickerModal`). No big unifying `MediaPicker`; each picker keeps its own domain logic and only the preview chrome is shared.

**Edit form.** Reuse `CreationPanel` with a new `mode: 'create' | 'edit'` prop and an optional `existingVideo` prop. The two existing mode-sensitive behaviours (the **✦ AI Autofill** button and the theme→SEO autofill `useEffect`) get `mode === 'create'` guards. In edit mode the submit button calls `youtubeVideosApi.update(id, …)` and is labelled **Save changes →**.

---

## 3. Data model

One Alembic migration: `014_youtube_video_visual_playlist.py` — adds three columns to `youtube_videos`:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `visual_asset_ids` | `INTEGER[]` | `'{}'` | Ordered playlist of visual assets. |
| `visual_clip_durations_s` | `FLOAT[]` | `'{}'` | Parallel array; per-clip display duration in seconds. In `concat_loop` mode, `0` for a video item means "use native length"; stills always require `> 0` (default 3.0). In `per_clip` mode, every item must be `> 0`. |
| `visual_loop_mode` | `VARCHAR(20)` | `'concat_loop'` | One of `'concat_loop'` \| `'per_clip'`. |

The migration is purely additive; no data backfill is needed.

**Backwards compatibility.** Existing `visual_asset_id` (singular) column is kept. The renderer treats `visual_asset_ids` as the source of truth when non-empty; otherwise it falls back to `visual_asset_id`. Historical rows continue to render unchanged. New videos created via the playlist editor write to `visual_asset_ids` (even when the playlist contains exactly one item, so the read path stays uniform) and leave `visual_asset_id` `NULL`.

No schema changes required for the SFX layer pickers (already serialised into the existing `sfx_overrides` JSONB column) or for the edit feature (existing `PUT /youtube-videos/{id}` already covers it).

---

## 4. UI components

### 4.1 New components

| Component | File | Purpose |
|---|---|---|
| `PreviewPlayer` | `console/frontend/src/components/PreviewPlayer.jsx` | Shared primitive: takes `{ src, kind: 'audio' \| 'video' \| 'image' }`, renders a small ▶/⏸ button (or thumbnail with overlay-play for image/video). Subscribes to a single module-level `currentlyPlaying` ref so starting one preview stops any other. Stops on click-outside / unmount. |
| `SfxPickerModal` | `console/frontend/src/components/SfxPickerModal.jsx` | Single-select modal for one SFX (used by ④ FG / MG / BG layer cards). Search by title / sound_type. Grid of cards each embedding `<PreviewPlayer kind="audio" />`. Confirm returns `{ asset_id }`. |
| `VisualPlaylistEditor` | `console/frontend/src/components/VisualPlaylistEditor.jsx` | Inline list mirroring `MusicPlaylistEditor`: each row shows thumbnail + title + duration field + `↑ ↓ ×`. Per-row duration field is always visible. In `concat_loop` mode, video rows show `[native]` placeholder (blank = use native length) and still rows require a number. In `per_clip` mode, every row's duration is required. |
| `VisualPickerModal` | `console/frontend/src/components/VisualPickerModal.jsx` | Single-select picker invoked by **+ Add Visual**. Reuses the `AssetBrowser` thumbnail-grid pattern but each tile embeds `<PreviewPlayer />` (videos play inline in the tile on click; images just enlarge). Filters: source (Midjourney / Runway / Veo / manual / pexels / stock), keywords, `asset_type`. |

### 4.2 Modified components

- **`SfxPoolEditor`** — inside the existing "Pick SFX" modal grid, swap each plain title cell for one that includes `<PreviewPlayer kind="audio" />`. Also add a tiny ▶ button to each already-selected pool row.
- **`MusicPlaylistEditor`** — same: add `<PreviewPlayer kind="audio" />` to each row in the modal *and* to each row in the selected list.
- **`YouTubeVideosPage.jsx` — `CreationPanel`**:
  - Accept `mode: 'create' | 'edit'` (default `'create'`) and an optional `existingVideo` prop. Prefill all form state from `existingVideo` when `mode === 'edit'`.
  - Hide the **✦ AI Autofill** button when `mode === 'edit'`.
  - Skip the theme → SEO autofill `useEffect` when `mode === 'edit'` (don't clobber the editor's edits).
  - `handleSubmit` calls `youtubeVideosApi.update(id, …)` instead of `.create(…)` when in edit mode; submit label changes to **Save changes →**.
  - Replace the three `<select>`s in section ④ SFX LAYERS with three `<SfxPickerModal>` triggers (a chip showing the picked SFX with a ▶ and an ✕, or a **+ Pick SFX** button when empty).
  - Replace section ③ VISUAL's `<Select>` with a segmented loop-mode toggle (Concat-then-loop | Per-clip duration) + `<VisualPlaylistEditor>`.
- **`YouTubeVideosPage.jsx` — list rows** — add a small **✎ Edit** button alongside the existing actions, *only* when `v.status` is in `{draft, failed, audio_preview_ready, video_preview_ready}`. Click sets `editingVideo = v` and opens `<CreationPanel mode="edit" existingVideo={v} …/>`.
- **`api/client.js` — `youtubeVideosApi`** — add `update(id, body) → PUT /api/youtube-videos/{id}`. (Endpoint already exists server-side; only the client wrapper is missing.)

The existing `PreviewApprovalGate` and `RenderStatePanel` are untouched.

### 4.3 Section layout sketches

**③ VISUAL**

```
③ VISUAL
  [ Concat-then-loop  |  Per-clip duration ]   ← segmented toggle
  + Add Visual
  ┌───────────────────────────────────────────────┐
  │ 1  [thumb]  rainy_window.mp4   [native] ↑↓×   │
  │ 2  [thumb]  fire_close.mp4     [12s   ] ↑↓×   │
  │ 3  [thumb]  candle.jpg         [3s    ] ↑↓×   │
  └───────────────────────────────────────────────┘
```

**④ SFX LAYERS — one card per layer**

```
Foreground                    template default: rain_window
[  ▶  Light Rain Patter  ✕  ]    ← chip; click body opens SfxPickerModal
Volume ▭▭▭▭▭▭───────  60%
```

Empty state shows **+ Pick SFX** button instead of the chip.

---

## 5. Backend changes

### 5.1 Routers — `console/backend/routers/youtube_videos.py`

Both `YoutubeVideoCreate` and `YoutubeVideoUpdate` schemas gain three optional fields:

```python
visual_asset_ids:        list[int] | None = None
visual_clip_durations_s: list[float] | None = None
visual_loop_mode:        Literal['concat_loop', 'per_clip'] | None = None
```

No new endpoints. `PUT /youtube-videos/{id}` already exists and is what the edit UI calls.

### 5.2 Service — `console/backend/services/youtube_video_service.py`

`update_video(video_id, fields, user_id)` — extend with edit-reset logic:

1. Reject if `video.status` is not in `{'draft', 'failed', 'audio_preview_ready', 'video_preview_ready'}` — raises `ValueError`, router maps to HTTP 400. `done` and `published` are explicitly rejected.
2. Validate the visual playlist if `visual_asset_ids` is provided:
   - All IDs exist in `video_assets`.
   - `visual_clip_durations_s`, if provided, is the same length as `visual_asset_ids` (or empty — treated as all-zeros).
   - `visual_loop_mode` must be one of the two literals.
   - **Per-mode duration rules** (applied after the array-length check):
     - `concat_loop`: still-image rows must have `> 0` (auto-fill `3.0` if `0`/missing); video rows may be `0` (= use native length).
     - `per_clip`: every row — video or still — must have `> 0`; the service auto-fills `3.0` for stills if `0`/missing and rejects with `ValueError` if any video row is `0`/missing.
3. Apply the field updates.
4. Force `status = 'draft'`.
5. Discard orphaned artifacts: delete files at `audio_preview_path`, `video_preview_path`, and `output_path` if present; null those columns and `celery_task_id`.
6. Audit-log entry: `action='video_edit_reset'`, `meta={changed_fields: [...], discarded_artifacts: [...]}`.

`create_video(...)` — accept the same three new fields and persist them. If only legacy `visual_asset_id` is provided, store as-is (no auto-promotion to array).

`dispatch_render(video_id)` and the preview-render starts already read the model row, so they automatically pick up the new array fields once the renderer respects them. No changes there.

### 5.3 Renderer — `pipeline/youtube_ffmpeg.py`

Loop strategies are handled at the visual-track-build step:

- **`concat_loop`** — build a single concatenated visual segment from `visual_asset_ids` in order. Videos use native length; stills use `visual_clip_durations_s[i]` (default 3.0s). Loop the resulting concat segment with ffmpeg `-stream_loop -1` until `target_duration_h` is reached, then trim to exact length.
- **`per_clip`** — build the segment using `visual_clip_durations_s[i]` for *every* item. Videos shorter than their slot loop within the slot; longer videos are trimmed. Loop the whole sequence to fill the target duration.

**Backwards-compat fallback.** If `visual_asset_ids` is empty, behave exactly as today using `visual_asset_id` (loop the single asset).

The audio side (music, SFX layers, SFX pool) is unchanged — this section only touches visual track assembly.

---

## 6. Wiring details

### 6.1 Edit round-trip

1. User clicks **✎ Edit** on a list row → `setEditingVideo(v)` → `<CreationPanel mode="edit" existingVideo={v} …/>` opens, prefilled.
2. User changes fields and clicks **Save changes →** → `youtubeVideosApi.update(id, body)` → `PUT /api/youtube-videos/{id}`.
3. Server runs the edit-reset path described in §5.2: validates, writes fields, sets `status='draft'`, deletes preview/output files, audit-logs.
4. Response: the updated video row. Frontend reloads the list (`load()`) and closes the panel.
5. Video reappears in the list as `draft` with the standard **Render →** button available.

### 6.2 Migration / rollout order

1. Alembic migration `014_youtube_video_visual_playlist` (additive — safe).
2. Backend service + schema updates (§5.1, §5.2). Deployable independently; old frontend keeps working because new fields are all optional.
3. Renderer (`pipeline/youtube_ffmpeg.py`) loop modes. **Must precede the visual-playlist UI** — otherwise a user could save a multi-visual video before the renderer can build it, and rendering would fail (legacy `visual_asset_id` would be `NULL`).
4. Build `PreviewPlayer` primitive (no UI consumers yet).
5. Add preview buttons to existing `SfxPoolEditor` and `MusicPlaylistEditor` modals.
6. Build `SfxPickerModal` and swap into `CreationPanel` ④ SFX LAYERS.
7. Build `VisualPickerModal` + `VisualPlaylistEditor` and swap into `CreationPanel` ③ VISUAL.
8. Add `mode='edit'` support and the ✎ Edit button in list rows.

### 6.3 Test plan

- Pytest: `update_video` rejects from each forbidden status; permits each allowed status; cleans up artifacts; validates parallel-array length; rejects unknown asset IDs.
- Pytest: `create_video` round-trips the three new fields.
- Manual: render a 10-min ASMR video with three mixed visuals (1 video, 1 still, 1 video) in both loop modes; verify total duration matches target.
- Manual: edit a `video_preview_ready` video; confirm preview file is gone from disk and status is `draft`.
- Manual: SFX layer picker — open, search, ▶ on three rows in sequence, confirm only one plays at a time, select, confirm chip shows in the layer card.
- Manual: music playlist's add modal — confirm ▶ behaviour matches SFX picker.

---

## 7. Open questions

None — all six clarifying questions resolved during brainstorm.
