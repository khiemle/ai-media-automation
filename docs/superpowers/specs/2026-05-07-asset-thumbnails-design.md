# Asset Thumbnail Support — Design Spec

**Date:** 2026-05-07  
**Status:** Approved

---

## Overview

Add thumbnail preview support to the asset library. Images serve themselves as thumbnails; videos get a JPEG frame extracted at the 1-second mark via ffmpeg. Thumbnails are generated at upload time for new assets and lazily on first request for existing assets. The AssetBrowser (scene picker) shows thumbnails only if already available — it never triggers generation.

---

## Requirements

| Context | Behaviour |
|---------|-----------|
| Assets Library (VideoAssetsPage) | Show thumbnail for every asset. If not yet generated, generate lazily on first load. |
| Upload new video asset | Generate thumbnail synchronously before returning the upload response. |
| Upload new image asset | No generation needed — the image file is its own thumbnail. |
| AssetBrowser (scene picker) | Show thumbnail if already available. Never trigger generation. |
| Already-uploaded videos (no thumbnail) | Generate lazily on first `/thumbnail` request from VideoAssetsPage. |

---

## Backend

### 1. Thumbnail Utility

New helper inside `production_service.py` (or `thumbnail_utils.py`):

```python
def generate_video_thumbnail(video_path: str) -> str | None:
```

- Calls ffmpeg: `ffmpeg -ss 1 -i <video_path> -frames:v 1 -q:v 2 <thumb_path> -y`
- Output path: `{same_directory}/{stem}_thumb.jpg`
- Returns the thumbnail path on success, `None` on any failure (ffmpeg missing, video too short, etc.)
- Videos shorter than 1 second: ffmpeg seeks to the nearest available frame automatically

### 2. Upload Flow (`import_asset()` in `production_service.py`)

After saving the uploaded file to disk:

- `still_image` → `thumbnail_path = file_path` (image is its own thumbnail)
- `video_clip` → call `generate_video_thumbnail(file_path)`, set `thumbnail_path` from result (may be `None` if ffmpeg fails — upload still succeeds)

### 3. New Endpoint

```
GET /api/production/assets/{asset_id}/thumbnail?generate=false
```

Behaviour:

1. Fetch asset from DB
2. If `thumbnail_path` is set and file exists → `FileResponse(thumbnail_path)`
3. If no `thumbnail_path` and `?generate=false` → 404
4. If no `thumbnail_path`, asset is `video_clip`, and `generate` not false:
   - Call `generate_video_thumbnail(file_path)`
   - If successful: persist `thumbnail_path` to DB, serve file
   - If failed: 404
5. If no `thumbnail_path` and asset is `still_image`:
   - Set `thumbnail_path = file_path`, persist to DB, serve file
6. If file missing: 404

Race condition guard: after lazy generation, re-check `thumbnail_path` before writing to DB — only update if still null.

---

## Frontend

### `client.js`

Update `thumbnailUrl()` to accept options:

```js
thumbnailUrl(id, { generate = true } = {})
// generate=true  → /api/production/assets/{id}/thumbnail
// generate=false → /api/production/assets/{id}/thumbnail?generate=false
```

### `VideoAssetsPage.jsx`

Replace placeholder emoji in the Thumbnail column with:

```jsx
<img
  src={assetsApi.thumbnailUrl(asset.id)}
  onError={e => { e.target.style.display = 'none' }}
  className="w-16 h-10 object-cover rounded"
/>
```

Hitting the URL triggers lazy generation for old video assets that have no thumbnail yet.

### `AssetBrowser.jsx`

Same `<img>` pattern but opts out of generation:

```jsx
<img
  src={assetsApi.thumbnailUrl(asset.id, { generate: false })}
  onError={e => { e.target.style.display = 'none' }}
  className="w-full h-full object-cover"
/>
```

Shows thumbnail if already available; silently hides if not. No generation triggered.

---

## Edge Cases

| Case | Handling |
|------|----------|
| ffmpeg not installed | `generate_video_thumbnail()` returns `None`; upload succeeds; thumbnail stays null |
| Video shorter than 1 second | ffmpeg seeks to nearest available frame — handled automatically |
| Thumbnail file deleted from disk | Endpoint returns 404; frontend `onError` hides the `<img>` silently |
| Concurrent lazy generation requests | Re-check `thumbnail_path` after generation; only write to DB if still null |
| Unsupported formats | Not in scope — accepted extensions are jpg/jpeg/png/webp/mp4/mov/webm only |

---

## Files Touched

| File | Change |
|------|--------|
| `console/backend/routers/production.py` | Add `GET /api/production/assets/{id}/thumbnail` endpoint |
| `console/backend/services/production_service.py` | Add `generate_video_thumbnail()`, update `import_asset()`, add lazy generation logic |
| `console/frontend/src/api/client.js` | Update `thumbnailUrl()` to accept `{ generate }` option |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | Replace placeholder with `<img>` using `thumbnailUrl(id)` |
| `console/frontend/src/components/AssetBrowser.jsx` | Replace placeholder with `<img>` using `thumbnailUrl(id, { generate: false })` |

---

## Out of Scope

- Batch backfill script to pre-generate thumbnails for all existing video assets
- Thumbnail size/resolution constraints (ffmpeg default JPEG output)
- Animated GIF support
- WebSocket notification when lazy thumbnail becomes ready
