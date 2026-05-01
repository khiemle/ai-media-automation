# YouTube Portrait Short Render — Design Spec

**Date:** 2026-05-01  
**Status:** Approved

---

## Overview

When a user clicks "Make Short" on a long-form YouTube video, the system renders a new YouTube Short using the same source materials (visual asset + music track + SFX layers) in portrait 9:16 format (1080×1920), adds a CTA subtitle overlay in the last 10 seconds, and uploads it as a YouTube Short to the linked channel.

The frontend "Make Short" button and `MakeShortModal` already exist. The `portrait_short` output format and seed templates (`asmr_viral`, `soundscape_viral`) already exist. The gap is entirely in the render backend.

---

## Architecture

### New file: `pipeline/youtube_ffmpeg.py`

Shared ffmpeg helpers used by both the long-form and short render tasks. Eliminates duplication.

**Exports:**
- `resolve_visual(video, db) → str | None` — returns file path of linked visual asset
- `resolve_audio(video, db) → str | None` — returns file path of linked music track
- `resolve_sfx_layers(video, db) → list[tuple[str, float]]` — resolves SFX layer paths + volumes from `sfx_overrides`
- `render_landscape(video, output_path, db)` — current long-form ffmpeg render logic (moved from `youtube_render_task.py`)
- `render_portrait_short(video, template, output_path, db)` — new Short render logic (see below)

### Modified: `console/backend/tasks/youtube_render_task.py`

Becomes a thin wrapper around `render_landscape`:
- Removes the 4 resolver helpers and `_render_video()` (all moved to `pipeline/youtube_ffmpeg.py`)
- Task body calls `render_landscape(video, output_path, db)` from the shared module
- Only ever receives `landscape_long` videos — routing to the right task happens at the service layer (see below)

### New file: `console/backend/tasks/youtube_short_render_task.py`

Dedicated Celery task `tasks.render_youtube_short` on `render_q`:
- Status machine: `draft/queued → rendering → done/failed`
- Loads `YoutubeVideo` + its `VideoTemplate`
- Calls `render_portrait_short(video, template, output_path, db)` from shared module
- Output path: `renders/youtube/short_{id}_v{timestamp}.mp4`
- `max_retries=2`, `default_retry_delay=60`

### DB changes

**`VideoTemplate` model** — two new nullable columns:
- `short_cta_text` (Text, nullable) — default CTA overlay text for this template
- `short_duration_s` (Integer, nullable, default 58) — Short clip duration in seconds

**Migration:** `console/backend/alembic/versions/010_template_short_fields.py`

### Frontend: `MakeShortModal` in `YouTubeVideosPage.jsx`

- Pre-fill `ctaText` from `template.short_cta_text` (fallback to current generic string if null)
- Show duration from `template.short_duration_s` instead of hardcoded `58`
- No other UI changes needed

### Backend: queue-render service routing

`YoutubeVideoService.queue_render(video_id)` (called by the existing queue-render endpoint) loads the video's template and checks `template.output_format`:
- `landscape_long` → dispatch `youtube_render_task`
- `portrait_short` → dispatch `youtube_short_render_task`

This is the single routing point. Neither task needs to re-check the format.

---

## Portrait Short Render Logic (`render_portrait_short`)

### Resolution & crop

Center-crop landscape source to 9:16 portrait, then scale to 1080×1920:

```
crop=ih*9/16:ih:(iw-ih*9/16)/2:0, scale=1080:1920, fps=30
```

For a 1920×1080 input this extracts a ~607px-wide center strip and scales to full portrait. Works for any landscape input resolution.

### Duration

`template.short_duration_s` seconds (default 58). Passed directly to ffmpeg `-t`.

### CTA subtitle overlay

Text source: `video.sfx_overrides["cta"]["text"]`, falling back to `template.short_cta_text`, then a hardcoded default `"Watch the full video — link in description!"`.

ffmpeg `drawtext` filter properties:
- White text, semi-transparent black `box` background
- Horizontally centered (`x=(w-tw)/2`)
- Positioned at ~80% height (`y=h*0.80`)
- Font size: 52px
- Enabled only in last 10 seconds: `enable='between(t,{duration-10},{duration})'`

### Audio

Same audio-mixing logic as long-form: music track + SFX layers mixed via `amix`. Shared via `pipeline/youtube_ffmpeg.py`.

### Output codec

```
-c:v libx264 -preset slow -crf 18
-c:a aac -b:a 192k -ar 44100
-movflags +faststart
```

---

## Upload

No changes to `youtube_upload_task.py` or `youtube_uploader.py`. The uploader already:
- Adds `#Shorts` to tags and description
- YouTube auto-classifies 9:16 videos ≤60s as Shorts based on aspect ratio + duration

---

## Data Flow

```
Editor clicks "Make Short"
  → MakeShortModal pre-fills from template.short_cta_text + short_duration_s
  → Creates YoutubeVideo (output_format=portrait_short via template, sfx_overrides.cta.text set)
  → Editor clicks "Queue Render"
  → Backend: detect portrait_short → dispatch youtube_short_render_task
  → Task: render_portrait_short() → center crop + drawtext → renders/youtube/short_{id}.mp4
  → status="done"
  → Editor triggers upload → youtube_upload_task → YouTube Shorts
```

---

## Files Changed / Created

| File | Change |
|------|--------|
| `pipeline/youtube_ffmpeg.py` | **New** — shared ffmpeg helpers |
| `console/backend/tasks/youtube_render_task.py` | **Refactor** — thin dispatcher, remove helpers |
| `console/backend/tasks/youtube_short_render_task.py` | **New** — dedicated Short render task |
| `console/backend/models/video_template.py` | **Extend** — add `short_cta_text`, `short_duration_s` |
| `console/backend/alembic/versions/010_template_short_fields.py` | **New** — migration |
| `console/backend/services/youtube_video_service.py` | **Extend** — expose new template fields in response |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | **Update** — MakeShortModal pre-fill from template |

---

## Out of Scope

- Smart/subject-aware crop (center crop only)
- Custom timestamp selection for the short clip (always uses same visual asset, full loop)
- TikTok upload of Shorts
- Thumbnail generation for Shorts
