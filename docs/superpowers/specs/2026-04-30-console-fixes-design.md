# Console Fixes & Enhancements — Design Spec

**Date:** 2026-04-30

---

## Overview

Five targeted fixes and enhancements to the management console, addressing a confirmed bug, a UX regression, a nav restructure, and two new capabilities.

---

## Issue 1: SFX Import Appears to Fail (Bug Fix)

**Root cause:** `sfxApi.list` and `youtubeVideosApi.list` both use `new URLSearchParams(params)` without filtering out `undefined` values. JavaScript's `URLSearchParams` converts `undefined` to the string `"undefined"`, so a call like `sfxApi.list({ sound_type: undefined })` sends `GET /api/sfx?sound_type=undefined`. The backend filters by the literal string `"undefined"`, returns 0 results, and the page appears empty after a successful import.

**Fix:** In `client.js`, update `sfxApi.list` and `youtubeVideosApi.list` to strip `null`, `undefined`, and empty-string values before building the query string:

```js
const filtered = Object.fromEntries(
  Object.entries(params).filter(([, v]) => v != null && v !== '')
)
const qs = new URLSearchParams(filtered).toString()
```

**Scope:** `console/frontend/src/api/client.js` only — no backend changes.

---

## Issue 2: Nav Restructure — Uploads + Pipeline → Admin

**Change:** Move `uploads` and `pipeline` tabs from `section: 'shared'` to `section: 'admin'` in `App.jsx`. Both tabs retain `roles: ['admin', 'editor']` — this is purely a visual reorganization.

The `SECTION_LABELS.shared = null` entry and the `'shared'` section logic in `renderNavWithSections` can be removed.

**Scope:** `console/frontend/src/App.jsx` only.

---

## Issue 3: Assets Import — New Upload Endpoint + UI

### Backend

New endpoint: `POST /api/production/assets/upload`

- **Form fields:** `file` (UploadFile), `source` (str), `description` (str, optional), `keywords` (str, comma-separated, optional), `asset_type` (str, optional — auto-detected from extension if omitted)
- **Supported formats:**
  - Images: `.jpg`, `.jpeg`, `.png`, `.webp` → `asset_type = "still_image"`
  - Videos: `.mp4`, `.mov`, `.webm` → `asset_type = "video_clip"`
- **Storage:** Save to `./assets/video_db/manual/asset_{id}{ext}`
- **DB insert:** Creates a `VideoAsset` row with the given source, description, keywords, asset_type, and file_path
- **Returns:** Standard asset dict (matching `production_service._asset_to_dict`)
- **Auth:** `require_editor_or_admin`
- **Max size:** 500 MB

The `production_service.py` gets a new `import_asset()` method that handles the file save + DB insert.

### Frontend

**`assetsApi.upload(file, metadata)`** — raw `fetch` (multipart, like `musicApi.upload`).

**`VideoAssetsPage`** — "Import Asset" button in the page header opens an `ImportAssetModal`:
- File picker: accepts images + videos
- `asset_type` shown read-only, auto-detected from selected file extension
- Source dropdown: `manual` | `midjourney` | `runway` | `pexels` | `veo` | `stock` (default: `manual`)
- Description field (optional)
- Keywords field (comma-separated, optional)
- On submit: calls `assetsApi.upload()`, closes modal, calls `refetch()`

**Scope:** `production.py`, `production_service.py`, `client.js`, `VideoAssetsPage.jsx`

---

## Issue 4: Login Persistence — sessionStorage

**Problem:** The JWT is held in a module-level `_token` variable. A page reload clears it, forcing re-login.

**Fix:** Use `sessionStorage` as a backing store. `sessionStorage` is tab-scoped and clears when the browser tab closes — a good balance between convenience and security for an admin console.

### `client.js` changes

```js
export function setToken(token) {
  if (!token) return
  _token = token
  sessionStorage.setItem('console_token', token)
}

export function clearToken() {
  _token = null
  sessionStorage.removeItem('console_token')
}

export function restoreToken() {
  const t = sessionStorage.getItem('console_token')
  if (t) _token = t
  return t
}
```

### `App.jsx` changes

On mount, call `restoreToken()` + `authApi.me()`. If the token is valid, set the user and skip the login screen. If it fails (token expired or invalid), clear token and show login.

```js
useEffect(() => {
  const token = restoreToken()
  if (!token) return
  authApi.me()
    .then(userData => setUser(userData))
    .catch(() => clearToken())
}, [])
```

**Scope:** `client.js`, `App.jsx`

---

## Issue 5: YouTube Creation — Inline Upload

**Context:** The `CreationPanel` in `YouTubeVideosPage` currently shows dropdowns to select music/visual from existing libraries. Users need to upload new files without leaving the creation panel.

### Music section

Add an "Upload" toggle button next to "Select from library" label. When active, shows:
- Audio file picker (`.mp3`, `.wav`, `.m4a`, `.ogg`)
- Title field (pre-filled from filename)
- Submit button → calls `musicApi.upload(file, { title, niches: [], moods: [], genres: [], is_vocal: false, volume: 0.15, quality_score: 80 })`
- On success: appends new track to `musicList`, auto-selects it in the dropdown, collapses upload panel

### Visual section

Same pattern for visual assets:
- Image/video file picker (`.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4`, `.mov`, `.webm`)
- Description field (optional)
- Source dropdown: same list as issue 3 (default: `manual`)
- Submit button → calls `assetsApi.upload(file, { source, description, asset_type })`
- On success: appends new asset to `assetList`, auto-selects it in the dropdown, collapses upload panel

Both upload panels are inline (not modals) — they expand below the respective section header and collapse on success or cancel.

**Scope:** `YouTubeVideosPage.jsx`, `client.js` (assetsApi.upload already added by Issue 3)

---

## File Change Summary

| File | Change |
|------|--------|
| `console/frontend/src/api/client.js` | Fix URLSearchParams; add `restoreToken`; add `assetsApi.upload` |
| `console/frontend/src/App.jsx` | Nav section change; sessionStorage restore on mount |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | Import Asset button + modal |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Inline upload panels for music + visual |
| `console/backend/routers/production.py` | Add `POST /assets/upload` endpoint |
| `console/backend/services/production_service.py` | Add `import_asset()` method |
