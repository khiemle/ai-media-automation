---
name: YouTube Thumbnail Support
description: Add Midjourney image upload + text overlay thumbnail generation to the YouTube video pipeline, with thumbnail set on YouTube at upload time
type: project
date: 2026-05-05
---

# YouTube Thumbnail Support — Design

## Overview

When creating or editing a YouTube video in the `/youtube` console page, users can optionally upload a Midjourney image and enter overlay text (≤5 words). On "Generate Preview", a 1280×720 thumbnail PNG is produced immediately and shown in the form. At upload time, the thumbnail is set on YouTube via `thumbnails().set()`. Video cards on the `/youtube` page show the thumbnail when available.

---

## Database

**Migration:** `console/backend/alembic/versions/016_youtube_thumbnail.py`

Three new nullable columns on `youtube_videos`:

| Column | Type | Notes |
|---|---|---|
| `thumbnail_asset_id` | `Integer FK → video_assets.id NULL` | Source Midjourney image asset |
| `thumbnail_text` | `Text NULL` | Optional overlay text (≤5 words) |
| `thumbnail_path` | `Text NULL` | Path to generated 1280×720 PNG |

The uploaded Midjourney image is also persisted as a `VideoAsset` row with `source="midjourney"`, `aspect_ratio="16:9"`, making it available in the existing asset library.

**Model update:** `console/backend/models/youtube_video.py` — add the three columns as `Mapped` fields.

---

## Thumbnail Utility

**New file:** `pipeline/youtube_thumbnail.py`

Extracts and exposes the generation logic from `make_youtube_thumbnail.py` as an importable function:

```python
def generate_thumbnail(
    source_path: Path | str,
    output_path: Path | str,
    text: str | None = None,
    font: Path = DEFAULT_REGULAR_FONT,
    bold_font: Path = DEFAULT_BOLD_FONT,
    bold_first_word: bool = True,
    preferred_font_size: int = 162,
    min_font_size: int = 48,
    margin_x: int = 58,
    margin_bottom: int = 48,
    fill: str = "#F7F2E8",
    stroke_fill: str = "#06100C",
) -> Path
```

- When `text` is `None` or empty: only cover-resizes the source image to 1280×720, no text overlay.
- When `text` is provided: full text overlay pipeline (split, fit, draw).

`make_youtube_thumbnail.py` becomes a thin CLI wrapper that imports and calls `generate_thumbnail`.

---

## API Endpoints

All four endpoints added to `console/backend/routers/youtube_videos.py`.

### `POST /youtube-videos/{id}/thumbnail-image`

Multipart form upload. Field name: `image` (accepts `image/*`).

1. Validate video exists and its status is not `published` (all other statuses allow thumbnail updates).
2. Save file to `assets/thumbnails/source/yt_{id}_{timestamp}{ext}`.
3. Create `VideoAsset` row: `source="midjourney"`, `aspect_ratio="16:9"`, `file_path=saved_path`. Nullable fields (`duration_s`, `keywords`, `niche`) left null — this is a still image, not a video clip.
4. Set `video.thumbnail_asset_id = asset.id` and commit.
5. Return `{ "asset_id": int, "source_url": "/youtube-videos/{id}/thumbnail-source" }`.

### `POST /youtube-videos/{id}/thumbnail-generate`

JSON body: `{ "text": str | None }`.

1. Load video; confirm `thumbnail_asset_id` is set. Validate `text` word count ≤5 server-side (400 if exceeded).
2. Resolve `VideoAsset.file_path` for the source image.
3. Call `generate_thumbnail(source_path, output_path="assets/thumbnails/generated/yt_{id}.png", text=text)`.
4. Set `video.thumbnail_path` and `video.thumbnail_text`, commit.
5. Return `{ "thumbnail_url": "/youtube-videos/{id}/thumbnail" }`.

### `GET /youtube-videos/{id}/thumbnail`

`FileResponse` serving `video.thumbnail_path`. Returns 404 if `thumbnail_path` is not set.

### `GET /youtube-videos/{id}/thumbnail-source`

`FileResponse` serving the original source image (`VideoAsset.file_path` via `thumbnail_asset_id`). Returns 404 if not set.

---

## Upload Task

`console/backend/tasks/youtube_upload_task.py` — after `upload_to_youtube()` returns `platform_id`, if `video.thumbnail_path` is set:

```python
from uploader.youtube_uploader import set_thumbnail
set_thumbnail(platform_id, video.thumbnail_path, credentials_dict)
```

### `set_thumbnail` in `uploader/youtube_uploader.py`

New function:

```python
def set_thumbnail(platform_video_id: str, thumbnail_path: str | Path, credentials: dict) -> None
```

Builds a `Credentials` object (same as `upload()`), calls `youtube.thumbnails().set(videoId=platform_video_id, media_body=MediaFileUpload(thumbnail_path, mimetype="image/png"))`. Logs success/failure but does not raise — a failed thumbnail set should not fail the upload.

---

## Service / Model Updates

`YoutubeVideoService._video_to_dict()` — include `thumbnail_path`, `thumbnail_text`, `thumbnail_asset_id` in the returned dict so the frontend receives these fields on `GET /youtube-videos` and `GET /youtube-videos/{id}`.

---

## Frontend

### Video create/edit form (`YouTubeVideosPage.jsx`)

New **Thumbnail** section below the SEO fields:

```
[ Drop or click to upload Midjourney image ]   ← <input type="file" accept="image/*">
[ Thumbnail text (optional)            2/5 ]   ← text input, word counter
[ Generate Preview ]                           ← button, disabled until image uploaded

┌─────────────────────────────────┐
│  1280×720 preview image         │  ← hidden until first generate
└─────────────────────────────────┘
```

**Create flow:**
1. User completes form and clicks Save.
2. `POST /youtube-videos` → receive `id`.
3. If image selected: `POST /youtube-videos/{id}/thumbnail-image` (multipart).
4. `POST /youtube-videos/{id}/thumbnail-generate` with current text value.
5. Update local video state with returned `thumbnail_url`.

Steps 3–5 run sequentially after create; any failure shows a non-blocking toast ("Thumbnail could not be generated — you can retry from the edit form.").

**Edit flow:**
- On form open, if `thumbnail_path` is set, show existing thumbnail preview via `GET /youtube-videos/{id}/thumbnail`.
- Replacing image re-runs steps 3–5 on "Generate Preview" click.
- Changing text only re-runs step 4.

**Validation:** Client-side word count ≤5 enforced on input change; input turns red and button disabled if exceeded.

### Video list cards (`YouTubeVideosPage.jsx`)

Each video card currently shows title + status badge. If `thumbnail_path` is set (non-null in the list response), render:

```jsx
<img src={`/api/youtube-videos/${video.id}/thumbnail`} … />
```

as the card's top image (fixed aspect ratio 16:9, `object-cover`). No thumbnail → retain current card layout unchanged.

---

## File Layout

```
pipeline/
  youtube_thumbnail.py          ← new: reusable generate_thumbnail()
make_youtube_thumbnail.py       ← updated: thin CLI wrapper
assets/
  thumbnails/
    source/                     ← uploaded Midjourney originals
    generated/                  ← generated 1280×720 PNGs
console/backend/
  alembic/versions/016_youtube_thumbnail.py
  models/youtube_video.py       ← 3 new columns
  routers/youtube_videos.py     ← 4 new endpoints
  services/youtube_video_service.py  ← _video_to_dict update
  tasks/youtube_upload_task.py  ← thumbnails().set() call
uploader/
  youtube_uploader.py           ← set_thumbnail() function
console/frontend/src/pages/
  YouTubeVideosPage.jsx         ← thumbnail section + card image
```

---

## Error Handling

- Missing source image asset → 400 from generate endpoint ("No thumbnail image uploaded yet").
- Text exceeds 5 words → 400 from generate endpoint.
- `generate_thumbnail` failure (font not found, Pillow error) → 500 with message; stored `thumbnail_path` cleared.
- `thumbnails().set()` failure at upload time → logged as warning, upload still marked `done` (thumbnail is non-critical).
- File too large (>10MB) → 413 from upload endpoint.

---

## Out of Scope

- Generating thumbnails via AI (no auto-generation from video frame or Veo).
- Thumbnail support for TikTok uploads.
- Storing multiple thumbnail variants per video.
