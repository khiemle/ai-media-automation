# Design: Manage Videos — Video Assets Tab + Upload Preview + Channel Bug Fix

**Date:** 2026-04-29  
**Status:** Approved

---

## Summary

Three scoped changes to the Management Console:

1. **Bug fix** — YouTube channels fail to load in the Uploads > Videos tab on first visit.
2. **Video Assets page** — New top-level nav tab for browsing, editing, and deleting video assets (Pexels downloads + Veo generations).
3. **Rendered video player** — Play-button per row in Uploads > Videos tab to preview the rendered mp4 before uploading.

---

## 1. Bug Fix — Channel Loading in Uploads Tab

### Problem

`UploadsPage` initializes `channels = []`. This state is populated only via the `onChannelsLoaded` callback that `ChannelsTab` fires after it fetches `/api/channels`. Because the default sub-tab is `videos`, `ChannelsTab` never mounts on first load, so `VideosTab` always receives an empty `channels` prop — `ChannelPicker` shows "No active channels".

### Fix

Add a `useEffect` in `UploadsPage` that fetches `GET /api/channels` directly on mount and writes into the `channels` state. Remove the dependency on the child callback as the source of truth; `ChannelsTab` can still call `onChannelsLoaded` after its own load for consistency, but the initial data no longer requires the child to mount first.

**Files changed:**
- `console/frontend/src/pages/UploadsPage.jsx` — add top-level `useEffect` fetch for channels

---

## 2. Video Assets Page

### Goal

Allow editors to browse the full video asset library (all Pexels + Veo + manual clips), preview any clip, edit metadata (description, keywords, niche tags, quality score), and delete assets. Mirrors the existing Music page pattern.

### Navigation

New entry in `ALL_TABS` in `App.jsx`:

```js
{ id: 'assets', label: 'Assets', Icon: Icons.Assets, roles: ['admin', 'editor'] }
```

Positioned between Music and Composer. Roles: admin + editor (same as Music).

### Frontend — `VideoAssetsPage.jsx`

**Stats row** (StatBox components):
- Total · Pexels · Veo · Manual

**Filter bar:**
- Keyword search (text input)
- Source dropdown: all / pexels / veo / manual
- Niche multi-select (fetched from `/api/niches`)
- Min duration input

**Asset table columns:**
| Column | Notes |
|--------|-------|
| Thumbnail | 64×64 `<img>` from `thumbnail_url`; fallback icon if none |
| Description | Truncated to 160 chars |
| Source | Badge: pexels / veo / manual |
| Duration | `{n}s` mono |
| Resolution | `1080x1920` mono |
| Niche tags | Pill chips, max 3 shown |
| Score | Numeric 0–100 |
| Uses | `usage_count` |
| Actions | ▶ Preview · ✎ Edit · ✕ Delete |

**Preview modal** — opens on ▶:
- Centered modal (`max-w-xs`, 9:16 aspect ratio container)
- `<video controls autoPlay src="/api/production/assets/{id}/stream" />`
- Title / description above the player
- Close button

**Edit modal** — opens on ✎:
- Description (textarea)
- Keywords (comma-separated text input, stored as array)
- Niche (multi-select pill group, options from `/api/niches`)
- Quality Score (number input 0–100)
- Save / Cancel buttons

**Delete** — ✕ button with confirmation; removes DB row (file stays on disk).

### Backend — additions to production router

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/production/assets` | Already exists — search/list (add `niche` array filter if missing) |
| `GET` | `/api/production/assets/{id}` | Already exists |
| `GET` | `/api/production/assets/{id}/stream` | **New** — `FileResponse` of the mp4 file |
| `PUT` | `/api/production/assets/{id}` | **New** — update description, keywords, niche, quality_score |
| `DELETE` | `/api/production/assets/{id}` | **New** — delete DB row |

**`stream` endpoint** mirrors music's `/{id}/stream`: fetch asset row, check `file_path` exists on disk, return `FileResponse(path, media_type="video/mp4")`.

**`PUT` request body:**
```json
{
  "description": "string",
  "keywords": ["array", "of", "strings"],
  "niche": ["array", "of", "niche", "names"],
  "quality_score": 85
}
```

**`DELETE`** removes the DB row only; does not delete the file (pipeline manages files).

**`ProductionService` additions:**
- `update_asset(asset_id, **fields) -> dict`
- `delete_asset(asset_id) -> None`

**`client.js` additions:**
```js
export const assetsApi = {
  list: (params) => fetchApi(`/api/production/assets?${q}`),
  get: (id) => fetchApi(`/api/production/assets/${id}`),
  update: (id, body) => fetchApi(`/api/production/assets/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) => fetchApi(`/api/production/assets/${id}`, { method: 'DELETE' }),
  streamUrl: (id) => `/api/production/assets/${id}/stream`,
}
```

---

## 3. Rendered Video Player in Uploads

### Goal

Editors can watch the final rendered mp4 directly in the Uploads > Videos tab before deciding to upload.

### Frontend — `UploadsPage.jsx` (VideosTab)

- Add ▶ button in the Actions column for each video row.
- Button is enabled only when `v.has_video === true` (new field from API).
- Clicking opens a `VideoPreviewModal` component (defined in the same file):
  - Centered modal, `max-w-sm`
  - `<video controls autoPlay src="/api/uploads/videos/{id}/stream" />`
  - Video title above the player
  - Close button

### Backend — additions to uploads router

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/uploads/videos/{id}/stream` | **New** — stream the rendered mp4 |

**`stream` endpoint:**
1. Look up `GeneratedScript` by `id` (the `video_id` in the upload list is the script id).
2. Check `script.output_path` is set and the file exists on disk.
3. Return `FileResponse(output_path, media_type="video/mp4")`.
4. 404 if not found or path missing.

**`list_videos` response extended:**  
Add `has_video: bool` to each item — `True` when `output_path` is set and the file exists.

**`UploadService.list_videos` change:**  
For each script row, add `has_video: os.path.isfile(script.output_path or "")`.

---

## Files Changed (complete list)

### Frontend
| File | Change |
|------|--------|
| `src/App.jsx` | Add `assets` entry to `ALL_TABS`; import `VideoAssetsPage`; add `case 'assets'` to `renderPage` |
| `src/pages/VideoAssetsPage.jsx` | **New** — full assets management page |
| `src/pages/UploadsPage.jsx` | Fix channel loading bug; add `VideoPreviewModal`; add `has_video` check + ▶ button |
| `src/api/client.js` | Add `assetsApi` |

### Backend
| File | Change |
|------|--------|
| `console/backend/routers/production.py` | Add `stream`, `update`, `delete` asset endpoints |
| `console/backend/services/production_service.py` | Add `update_asset`, `delete_asset`, `stream_asset_path` methods |
| `console/backend/routers/uploads.py` | Add `stream` endpoint for rendered video |
| `console/backend/services/upload_service.py` | Add `has_video` to `list_videos` output; add `stream_video_path` method |
