# /youtube page bug fixes & recreate-video — Design

**Date:** 2026-05-12
**Scope:** Four independent fixes/improvements on the `/youtube` console page, bundled because they touch the same surface but ship and review independently.

---

## Fix 1 — Thumbnail: bold the first N words (default 1)

### Problem

The user reports that thumbnail text renders entirely in one style — the "first words" are not visually bold. Two underlying causes:

1. **Font collision.** `pipeline/youtube_thumbnail.py:40-41` resolves both `DEFAULT_REGULAR_FONT` and `DEFAULT_BOLD_FONT` via `_resolve_font()`, which falls back to the **same** system font file (`SFNS.ttf` on macOS, `LiberationSans-Regular.ttf` on Linux) unless `THUMBNAIL_BOLD_FONT_PATH` is set. The `set_variation_by_name("Bold")` call at line 65-73 silently no-ops on most systems (the `except` swallows `AttributeError/OSError/ValueError`). Regular and bold therefore render identically.
2. **Bold granularity.** Even if the fonts differed, only the literal first **line** (which today equals the first word for ≥4-word inputs, per `split_text` at line 44-50) is treated as bold (line 92). The desired behavior is "bold the first N words" as a continuous span, where N is user-controllable.

### Solution

**Backend — fonts**

- Bundle two real OFL-licensed font files in `assets/fonts/`:
  - `assets/fonts/Inter-Black.ttf` (bold)
  - `assets/fonts/Inter-Regular.ttf` (regular)
- Update `pipeline/youtube_thumbnail.py`:
  - `_find_system_font()` becomes `_default_regular_font()` and prefers the bundled `Inter-Regular.ttf` before falling back to system fonts.
  - Add `_default_bold_font()` that prefers bundled `Inter-Black.ttf`.
  - Remove the `set_variation_by_name` hack — distinct files do the work.
  - Keep `THUMBNAIL_FONT_PATH` / `THUMBNAIL_BOLD_FONT_PATH` env overrides for power users.

**Backend — bold-N-words rendering**

- Replace `split_text(text: str) -> list[str]` with a function that returns a flat **wrap plan**: `list[list[(word: str, is_bold: bool)]]` — a list of lines, each a list of `(word, is_bold)` segments. The first N words are tagged `is_bold=True` in reading order.
- Wrap policy (preserve current "≤3 words → one per line; ≥4 words → word1 / word2 / rest" shape):
  - 1 word: one line `[(w, True if N≥1 else False)]`
  - 2 words: two lines, one word each
  - 3 words: three lines, one word each
  - ≥4 words: three lines — `[w1]`, `[w2]`, `[w3..wN]`
- Update `measure_lines` to measure each line as a sequence of word boxes (regular vs bold font picked per word) and return per-line word metadata.
- Update the draw loop in `generate_thumbnail` to render each word at its measured x-offset within the line, using the per-word font, stroke, and fill.

**Backend — persistence**

- Migration: add column `thumbnail_bold_word_count INTEGER NOT NULL DEFAULT 1` to `youtube_videos`.
- `generate_thumbnail()` signature: replace `bold_first_word: bool = True` with `bold_word_count: int = 1`.
- Router `POST /youtube-videos/{video_id}/thumbnail-generate` (`routers/youtube_videos.py:526`):
  - `ThumbnailGenerateRequest` adds `bold_word_count: int | None = None`.
  - On request, persist the value to `youtube_videos.thumbnail_bold_word_count` (when not `None`).
  - Always pass the stored `video.thumbnail_bold_word_count` into `generate_thumbnail()`.

**Frontend**

- `RegenerateThumbnailModal` (`YouTubeVideosPage.jsx:1931`):
  - Add a small number input "Bold first __ words" next to (or below) the text field. Default to `video.thumbnail_bold_word_count ?? 1`. Min 0, max = current word count of the input text.
  - Pass through to the API call at line 1956.
  - Word count chip shows e.g. `bold 1/3` to make the relationship clear.

### Defaults

- `thumbnail_bold_word_count` = **1** (DB default, UI default).
- N=0 → entire text regular. N ≥ total word count → entire text bold.

### Out of scope

- New thumbnail layouts, colors, positions.
- Mixed-style **within** a word (e.g. partial-word bolding).
- Italic / underline styling.

---

## Fix 2 — Short video renders black with no audio

### Problem

When a user creates a YouTube Short from an existing long video via `MakeShortModal` (`YouTubeVideosPage.jsx:1844`), the resulting render is a black 9:16 canvas with silent audio.

**Root cause:** `MakeShortModal` copies the parent's `music_track_id` and `visual_asset_id` (singular) at lines 1866-1867. For videos built from playlist-based templates (ASMR/soundscape — common case), those singular columns are `NULL` because all content lives in `visual_asset_ids` / `music_track_ids` (plural arrays added in migrations 013 and 015).

The short pipeline (`pipeline/youtube_ffmpeg.py:1015-1087`) calls `resolve_visual` (line 56-67) and `resolve_audio` (line 163-174), both of which **only** check the singular columns. Lines 1054 and 1062 then fall back to a black `lavfi color` source and a silent `anullsrc` source — producing exactly what the user sees.

### Solution (two layers — both)

**Frontend — `MakeShortModal` smart copy**

In the `handleSubmit` payload (`YouTubeVideosPage.jsx:1861-1870`), select the first valid plural-array entry when the singular is null:

```js
music_track_id: form.sameMusic
  ? (video.music_track_id ?? video.music_track_ids?.[0] ?? null)
  : null,
visual_asset_id: form.sameVisual
  ? (video.visual_asset_id ?? video.visual_asset_ids?.[0] ?? null)
  : null,
```

This keeps the short single-asset by design (58 s — one clip is enough) and produces a working short for every parent video.

**Backend — defensive fallback in `resolve_visual` / `resolve_audio`**

Update `pipeline/youtube_ffmpeg.py`:

- `resolve_visual(video, db)` — if `video.visual_asset_id` is None, try `video.visual_asset_ids[0]` before returning None.
- `resolve_audio(video, db)` — same pattern with `music_track_ids`.

This protects future callers (e.g., MCP server, scripted runs) from the same trap and matches the user's mental model of "the visual / music of this video".

### Schema

No DB change. Both fixes are code-only.

### Out of scope

- Multi-clip playlists inside the short renderer (the short stays single-clip).
- Re-using the parent's already-rendered output as the short's source (this design keeps it a fresh render from the same materials).

---

## Fix 3 — "Altered or synthetic content" always sent as True

### Problem

`uploader/youtube_uploader.py:103-105` already places `"selfDeclaration": { "hasSyntheticOrAltered": True }` inside `body.status`. Yet the user reports the disclosure does not "tick" on the uploaded video. The most likely cause is that the field name / path is not a recognized field on the `videos.insert` `status` resource, so the YouTube Data API v3 silently ignores it (the upload succeeds but the flag is never applied).

### Solution

No DB. No UI. No request-body changes. The intent is: every upload always discloses synthetic/altered content.

**Backend only — `uploader/youtube_uploader.py`**

1. Verify the correct YouTube Data API v3 field. As of the current YouTube reference, the disclosure lives at `status.containsSyntheticMedia` (boolean) rather than nested under `selfDeclaration.hasSyntheticOrAltered`. The current code's path is unrecognized and ignored.
2. Update the body to set the correct, recognized field while keeping the value `True`:

   ```python
   body = {
       "snippet": {...},
       "status": {
           "privacyStatus": privacy_status,
           "selfDeclaredMadeForKids": False,
           "containsSyntheticMedia": True,
       },
   }
   ```

3. Keep `part="snippet,status"` on the `videos().insert` call so the field is actually written.
4. After the insert response returns, log the value of `response["status"].get("containsSyntheticMedia")` so we can confirm the field stuck. If YouTube strips it, that's a separate API-permissions issue surfaced in logs rather than silent failure.

### Verification

- Upload a test video to an unlisted channel. Open YouTube Studio → check the "Altered or synthetic content" disclosure is ticked.
- If still untickled, escalate: the field may require a separate `videos.update` call with `contentDetails` or may be gated by channel monetization status. Resolution lives outside this spec.

### Out of scope

- Adding a UI toggle (explicitly removed from the original draft per user direction).
- Persisting per-video preference.
- Bulk-set across many videos.
- YouTube's separate "Made for Kids" flag (`selfDeclaredMadeForKids`) — left unchanged.

---

## Fix 4 — Recreate a render-done video

### Problem

Currently there is no path to start a fresh render that reuses the configuration of a finished video. The user has to re-enter all of: template, theme, music tracks, visual assets, durations, SFX, SEO fields, target duration, thumbnail settings, etc.

### Solution

**Endpoint**

- `POST /api/youtube-videos/{video_id}/recreate` → returns `{ "id": <new_video_id> }`.
- Allowed for any source `status` (not just `done`) — recreate is a convenience clone, not a state machine transition. UI will surface the button only for `done` rows initially (see below), but the endpoint stays permissive.

**Service method** — `YoutubeVideoService.recreate(source_id) -> YoutubeVideo`

Copies *configuration* fields:

```
template_id, theme,
music_track_id, music_track_ids,
visual_asset_id, visual_asset_ids,
visual_clip_durations_s, visual_loop_mode,
sfx_overrides, sfx_pool, sfx_density_seconds, sfx_seed,
seo_title, seo_description, seo_tags,
target_duration_h, output_quality,
sound_layers,
track_transition, track_transition_seconds, playlist_overlay_style,
spectrum_enabled, spectrum_height_pct, spectrum_color, spectrum_opacity,
spectrum_style, spectrum_bar_width_px, spectrum_bar_count,
spectrum_align_horizontal, spectrum_align_vertical,
thumbnail_asset_id, thumbnail_text, thumbnail_bold_word_count,  // Fix 1
contains_synthetic_content,                                      // Fix 3
black_from_seconds, skip_previews
```

Sets title to `"{source.title} (recreate)"`.

Resets *runtime* fields:

```
status            = "draft"
output_path       = None
audio_preview_path= None
video_preview_path= None
celery_task_id    = None
thumbnail_path    = None        // regenerate to pick up any param changes
render_parts      = []
parent_youtube_video_id = None  // a recreate is not a child of the source
created_at / updated_at = now (DB defaults)
```

Writes an `AuditLog` entry (`action="recreate_youtube_video"`, `target_id=new.id`, `details={"source_id": source.id}`).

**Frontend**

- `YouTubeVideosPage.jsx` — add a "Recreate" button in the action group for rows with `status="done"` (alongside preview / thumbnail / upload).
- On click → POST `/recreate` → toast "New draft created" → refresh the video list. The new draft appears at the top (sorted by created_at desc).
- No automatic re-render: the user can edit settings (e.g., swap a music track) before queueing.

### Out of scope

- Bulk recreate (single-row only).
- Auto-queue-render on recreate.
- Copying the rendered output file (recreate means re-render).
- Linking the new video back to the source (no `recreated_from_id` field — keep schema minimal; AuditLog has the trail).

---

## Cross-cutting

### Migration order

Only Fix 1 needs a schema change:

1. `xxx_add_thumbnail_bold_word_count.py` — adds `thumbnail_bold_word_count INTEGER NOT NULL DEFAULT 1`.

(No migration for Fix 2, Fix 3, or Fix 4.)

### Audit logging

- Fix 1: existing `generate_thumbnail` audit entry already covers thumbnail regen; extend its `details` to include `bold_word_count`.
- Fix 4: new `recreate_youtube_video` AuditLog entry.

### Suggested implementation order

1. **Fix 3** — one-line body field rename in the uploader, smallest change.
2. **Fix 2** — pure code, biggest user-visible win (shorts actually work).
3. **Fix 4** — adds one endpoint + button, no schema, unblocks workflow.
4. **Fix 1** — most surface area (font bundling, render-loop rewrite, column, UI). Bench last.

### Files touched (summary)

```
pipeline/youtube_thumbnail.py                       (Fix 1)
pipeline/youtube_ffmpeg.py                          (Fix 2)
uploader/youtube_uploader.py                        (Fix 3)
assets/fonts/Inter-Regular.ttf  (new)               (Fix 1)
assets/fonts/Inter-Black.ttf    (new)               (Fix 1)
console/backend/alembic/versions/*.py               (Fix 1)
console/backend/models/youtube_video.py             (Fix 1)
console/backend/routers/youtube_videos.py           (Fix 1, Fix 4)
console/backend/services/youtube_video_service.py   (Fix 4)
console/frontend/src/pages/YouTubeVideosPage.jsx    (Fix 1, Fix 2, Fix 4)
console/frontend/src/api/client.js                  (Fix 4 — new endpoint method)
```

### Testing notes

- **Fix 1**: render thumbnails for N=0, 1, 2, 5, and >word_count. Verify visual difference between bold and regular spans (eye-check; the font collision was the silent failure mode).
- **Fix 2**: create a short from (a) a soundscape parent using only playlist fields, (b) a legacy parent using only singular fields, (c) a parent with both. All three should produce a non-black, non-silent short.
- **Fix 3**: upload a test video and confirm in YouTube Studio that "Altered or synthetic content" is ticked. Inspect the `videos.insert` response logged by the uploader to confirm YouTube echoed back `containsSyntheticMedia: True`.
- **Fix 4**: recreate from a soundscape video (with playlists, SFX pool, thumbnail) and verify all listed fields match the source while runtime fields are reset. Render the new draft end-to-end to confirm the clone produces a valid render.
