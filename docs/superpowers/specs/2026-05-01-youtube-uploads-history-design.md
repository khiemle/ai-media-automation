# YouTube Long Videos — Upload History & Table Improvements Design Spec

**Date:** 2026-05-01  
**Status:** Approved

---

## Overview

Improve the YouTube Long Videos section of the Uploads page with four additions: a Template column, a Remove action, per-channel upload history tracking (supporting multiple channels per video), and auto-refreshing upload progress. Duration display is also normalized to the most readable unit.

---

## Data Layer

### New table: `youtube_video_uploads`

| Column | Type | Constraints |
|---|---|---|
| `id` | Integer | PK, autoincrement |
| `youtube_video_id` | Integer | FK → `youtube_videos.id` ON DELETE CASCADE |
| `channel_id` | Integer | FK → `channels.id` ON DELETE SET NULL, nullable |
| `platform_id` | Text | nullable — YouTube video ID set on success |
| `status` | String(20) | `queued` → `uploading` → `done` / `failed` |
| `celery_task_id` | Text | nullable |
| `error` | Text | nullable — set on failure |
| `uploaded_at` | DateTime(timezone) | nullable — set when `done` |

**Unique constraint:** `(youtube_video_id, channel_id)` — one upload record per video+channel pair. A second upload attempt to the same channel (while one is `done` or in progress) returns HTTP 409.

### `YoutubeVideo.status` change

`video.status` stays `done` after rendering and is **never advanced to `published`**. All upload state lives in `youtube_video_uploads`. The Uploads list queries `status = 'done'` only.

### Migration: `011_youtube_video_uploads.py`

`down_revision = "010"`

---

## Backend

### New model: `console/backend/models/youtube_video_upload.py`

SQLAlchemy mapped class `YoutubeVideoUpload` for the table above.

### New service method: `YoutubeVideoService.list_uploads_for_video(video_id) → list[dict]`

Returns all upload records for a video, each with `channel_name` resolved from the `channels` table.

### Updated: `_video_to_dict`

Adds two fields:
- `template_label` — resolved by joining `video_templates` on `template_id`
- `uploads` — list of upload dicts: `{ id, channel_id, channel_name, status, platform_id, uploaded_at, error }`

### Updated: `POST /api/youtube-videos/{id}/upload`

1. Checks for an existing `YoutubeVideoUpload` for `(video_id, channel_id)` with `status IN ('queued', 'uploading', 'done')` → returns **409** if found.
2. Creates a new `YoutubeVideoUpload` with `status = 'queued'`, stores `celery_task_id`.
3. Returns `{ task_id, upload_id, status: "queued" }`.

### Updated: `youtube_upload_task.py`

Replaces `video.status = "published"` logic with:
- **Start:** set `upload.status = 'uploading'`
- **Success:** set `upload.status = 'done'`, `upload.platform_id = platform_id`, `upload.uploaded_at = now()`
- **Failure:** set `upload.status = 'failed'`, `upload.error = str(exc)`, then `raise self.retry(exc=exc)`

---

## Frontend

### `_video_to_dict` response shape (relevant fields)

```json
{
  "id": 12,
  "title": "My ASMR Video",
  "template_label": "ASMR Viral",
  "target_duration_h": 0.75,
  "status": "done",
  "output_path": "/renders/youtube/...",
  "uploads": [
    { "channel_id": 3, "channel_name": "My Channel", "status": "done", "uploaded_at": "2026-05-01T10:00:00Z" },
    { "channel_id": 7, "channel_name": "Second Channel", "status": "uploading", "uploaded_at": null }
  ]
}
```

### Duration helper

```js
function formatDuration(hours) {
  if (!hours) return '—'
  const s = Math.round(hours * 3600)
  if (s < 60)   return `${s}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  return `${+(hours.toFixed(1))}h`
}
```

### Table columns

| Column | Source | Notes |
|---|---|---|
| Title | `v.title` | truncated, existing |
| Template | `v.template_label` | muted text |
| Duration | `formatDuration(v.target_duration_h)` | replaces raw `Xh` display |
| Created | `v.created_at` | existing |
| Uploaded To | `v.uploads` | badges (see below) |
| Channel | ChannelPicker | existing, disabled if channel already `done` |
| Actions | play ▶ · Upload · 🗑 | |

### Uploaded To badges

- `done` upload → green badge with channel name
- `queued` or `uploading` → yellow badge with channel name + spinner
- `failed` → red badge with channel name
- No uploads yet → `—`

### Upload button state

- Disabled when no channel selected in the picker
- Disabled when the selected channel already has a `done` upload for this video
- Shows a small spinner while any upload for this video is `queued` or `uploading`

### Remove action

- Trash icon button in Actions column
- Hidden (not just disabled) while any upload is `queued` or `uploading`
- Clicking shows an inline confirm: "Delete this video?" with Confirm / Cancel
- On confirm: calls `DELETE /api/youtube-videos/{id}`, removes row from local state

### Auto-refresh polling

- After any upload is queued, the list polls `GET /api/youtube-videos?status=done` every **4 seconds**
- Polling stops when no video in the list has an upload in `queued` or `uploading` state
- Implemented with `useEffect` + `useRef` interval — cleared on unmount

---

## Files Changed / Created

| File | Change |
|---|---|
| `console/backend/models/youtube_video_upload.py` | **New** — `YoutubeVideoUpload` model |
| `console/backend/alembic/versions/011_youtube_video_uploads.py` | **New** — migration |
| `console/backend/services/youtube_video_service.py` | **Extend** — `_video_to_dict` with `template_label` + `uploads`; update `queue_upload` to create upload record + 409 guard |
| `console/backend/routers/youtube_videos.py` | **Update** — `start_upload` uses new service method |
| `console/backend/tasks/youtube_upload_task.py` | **Update** — track status on `YoutubeVideoUpload` instead of `video.status` |
| `console/frontend/src/pages/UploadsPage.jsx` | **Update** — `YouTubeLongSection`: new columns, badges, polling, remove action |

---

## Out of Scope

- Upload retry UI (failed uploads must be re-triggered by creating a new upload record)
- WebSocket real-time push (polling every 4s is sufficient)
- Pagination of the video list
- Showing `platform_id` / YouTube URL in the UI
