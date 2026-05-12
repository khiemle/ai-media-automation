# Uploaded YouTube Video Management — Design

**Date:** 2026-05-13
**Scope:** Three post-upload management features on `UploadsPage` → `YouTubeLongSection`, each row of which represents a `YoutubeVideoUpload` row.

---

## F1 — Open YouTube link in a new tab

### Problem

After a successful upload, the row shows status `done` but offers no direct way to view the live video on YouTube. The video ID is already persisted as `YoutubeVideoUpload.platform_id` (`tasks/youtube_upload_task.py:89`); the UI just doesn't surface a link.

### Solution

Frontend-only. No backend, no schema.

- Add a small helper in `console/frontend/src/api/client.js` (or a sibling `utils.js`):
  ```js
  export const youtubeWatchUrl = (platformId) =>
    `https://www.youtube.com/watch?v=${platformId}`
  ```
- In `console/frontend/src/pages/UploadsPage.jsx` `YouTubeLongSection`, add a per-row "↗ Watch on YouTube" button (or a `↗` icon with tooltip), shown only when `upload.status === 'done' && upload.platform_id`. On click:
  ```js
  window.open(youtubeWatchUrl(upload.platform_id), '_blank', 'noopener,noreferrer')
  ```

### Out of scope

- Embedding the video inside the console.
- Copy-to-clipboard helper for the URL.
- Channel-page deeplinks.

---

## F2 — Fetch YouTube stats on demand (live, no persistence)

### Problem

Editors want to see how an uploaded video is performing (views, watch time, likes, comments) without leaving the console. There is no current integration in the upload-management UI; `feedback/tracker.py` has a Data API v3 statistics fetcher but it's not wired to the console.

### Constraint (per user)

**Do not persist stats in the database.** Every fetch is live. The UI shows whatever was returned by the last successful click.

### Solution

**Backend service:** `console/backend/services/upload_stats_service.py`

```python
def fetch_stats(upload_id: int, db: Session) -> dict:
    """Fetch live YouTube stats for an upload. No DB writes.

    Returns:
        {
            "view_count":       int | None,
            "like_count":       int | None,
            "comment_count":    int | None,
            "watch_time_minutes": int | None,
            "fetched_at":       datetime,   # server time of this fetch
            "watch_time_available": bool,   # False if Analytics call failed (e.g. scope missing)
        }
    """
```

Behavior:
1. Load the `YoutubeVideoUpload` row and verify `status == 'done'` and `platform_id` is set; raise `ValueError("upload not ready for stats")` otherwise.
2. Resolve OAuth credentials for `upload.channel_id` via the existing `CredentialService`.
3. Call YouTube Data API v3 `videos().list(id=platform_id, part="statistics")`. Parse `viewCount`, `likeCount`, `commentCount` into integers; any of them may be missing on the response and stays `None`.
4. Call YouTube Analytics API `reports().query(ids=f"channel=={channel.platform_id}", startDate=upload_date, endDate=today, metrics="estimatedMinutesWatched", filters=f"video=={platform_id}")`. Parse the single returned row into `watch_time_minutes` (int). On any exception (missing scope `yt-analytics.readonly`, quota, etc.), log the reason and set `watch_time_minutes=None`, `watch_time_available=False`.
5. Return the dict; do not write to the DB.

**OAuth scope expansion:** add `https://www.googleapis.com/auth/yt-analytics.readonly` to `YOUTUBE_SCOPES` in `console/backend/services/credential_service.py:19-22`. Existing tokens lack this scope and the Analytics call will fail until the channel is re-authenticated. The fail-soft path keeps the rest of the stats working without forcing re-auth.

**Router:** `GET /api/youtube-videos/uploads/{upload_id}/stats` in `console/backend/routers/youtube_videos.py`:
- Thin wrapper: calls `upload_stats_service.fetch_stats(upload_id, db)`.
- Returns the dict as JSON (FastAPI serializes datetime as ISO 8601).
- Synchronous; expect ~0.5–1.5 s for the two API calls combined.
- Maps `ValueError` from the service to `HTTPException(400)`. Requires `editor_or_admin`.

**Frontend:** in `console/frontend/src/pages/UploadsPage.jsx` `YouTubeLongSection`:
- Per-row state `statsByUpload: { [uploadId]: { loading, data, error } }`.
- A `↻ Fetch stats` button on each done upload row (alongside F1's watch button). On click: set `loading`, GET the endpoint, store the result in `statsByUpload[id].data`.
- When data is present, render a small strip after the button:
  - Format: `2.3K views · 14m watched · 42 likes · 5 comments`
  - `view_count` formatted with `1234567 → "1.2M"` (existing utility if present, else inline).
  - `watch_time_minutes` rendered as `${m}m` for <60, `${Math.floor(m/60)}h ${m%60}m` otherwise.
  - When `watch_time_minutes === null && watch_time_available === false`, replace that field with a small inline link: "Re-auth channel for watch time" → opens the credentials tab. Other fields still render.
  - When a Data-API field is null (e.g. `like_count`), omit that segment from the strip.
- On error: toast `${error.message}`; do not render a partial strip.
- Stats are session-scoped only. No localStorage, no auto-fetch on row mount, no auto-refresh.

**Frontend API client:** add to `youtubeVideosApi` in `console/frontend/src/api/client.js`:
```js
fetchUploadStats: (uploadId) =>
  fetchApi(`/api/youtube-videos/uploads/${uploadId}/stats`, { method: 'GET' }),
```

### Out of scope

- DB persistence of any kind (explicitly rejected by the user).
- Background polling / Celery beat / "last fetched at" surface.
- Server- or client-side caching (TTL, memoization). Each click hits YouTube.
- Auto-fetch on mount (could burn quota with many rows visible).
- Page-level "Refresh all stats" bulk button.
- Avg view duration, CTR, impressions, subscribers-gained.

---

## F3 — Make Short from an uploaded video, with link to the original in the description

### Problem

Today, "+ Make Short" is only reachable from a done `YoutubeVideo` row on `YouTubeVideosPage` (`YouTubeVideosPage.jsx:2352`). For a video that's already uploaded, the user has to navigate back to YouTube Videos, find the source video, click Make Short — and even then, the resulting short doesn't reference the original.

### Solution

Surface "+ Make Short" on each done upload row in `UploadsPage`. Reuse the existing `MakeShortModal` (`YouTubeVideosPage.jsx:1844-1936`); add one optional prop.

**Frontend — UploadsPage row:**
- "+ Make Short" button on rows where `upload.status === 'done'` AND a corresponding parent `YoutubeVideo` is present in the page's already-loaded list (the page calls `youtubeVideosApi.list({ status: 'done' })`).
- Lookup: `const parent = videos.find(v => v.id === upload.youtube_video_id)`. Hide the button if `parent` is undefined (parent deleted or filtered out).
- On click, render `MakeShortModal` passing `video={parent}` and the new prop `originalUploadUrl={youtubeWatchUrl(upload.platform_id)}`.

**MakeShortModal — change:**
- Accept new optional prop `originalUploadUrl: string | null`.
- In `handleSubmit`, when computing the new short's payload, if `originalUploadUrl` is provided, prefix `seo_description`:
  ```js
  const baseDesc = video.seo_description ?? ''
  const seo_description = originalUploadUrl
    ? `Watch the full video → ${originalUploadUrl}\n\n${baseDesc}`.trimEnd()
    : baseDesc
  ```
  Pass this as `seo_description` in the create payload, replacing the existing `seo_description: video.seo_description ?? null` line (added in commit `7b95a97`). Other SEO fields (`seo_title`, `seo_tags`) keep the parent's values verbatim.

**Backend changes:** none. The existing `POST /api/youtube-videos` accepts `seo_description` and treats it as plain text.

### Out of scope

- Persisting the original-link relationship on the short's DB row (no new `parent_upload_id` column). The link lives in the SEO description text only.
- Bulk "Make Short for all my uploads" action.
- Automatically uploading the resulting short to the same channel as the parent (manual upload after render, as today).

---

## Cross-cutting

### Suggested implementation order

1. **F1** — frontend only, 1 helper + 1 button. Smallest blast radius.
2. **F3** — frontend only, reuses `MakeShortModal` with one new optional prop.
3. **F2** — biggest: scope expansion, service, router endpoint, UI strip. Ships last because it requires per-channel re-auth for watch time and that's the only surface that benefits from being tested independently.

### Files touched

```
console/frontend/src/api/client.js                      (F1 helper, F2 fetch method)
console/frontend/src/pages/UploadsPage.jsx              (F1 button, F2 button + strip, F3 button + modal wiring)
console/frontend/src/pages/YouTubeVideosPage.jsx        (F3 — MakeShortModal new prop + description prefix)
console/backend/services/upload_stats_service.py  (NEW) (F2)
console/backend/services/credential_service.py          (F2 — add yt-analytics.readonly scope)
console/backend/routers/youtube_videos.py               (F2 — new GET stats endpoint)
```

### No DB migration

Confirmed by the user: F2 is live-fetch only.

### Testing

- F1: manual smoke. No automated test needed for a button that opens a window.
- F2: pytest unit test for `upload_stats_service.fetch_stats` with mocked `googleapiclient.discovery.build`. Cover: both APIs succeed; Analytics 403 (scope missing); Data API returns missing fields; upload status != done raises ValueError.
- F3: pytest test that the short's `seo_description` carries the link prefix when `originalUploadUrl` is passed, plain prefix-less description otherwise. (Frontend logic can also be lightly smoke-tested by a Vitest spec if the project picks one up — none today.)

### Verification

- F1: click the button → opens `youtube.com/watch?v=<id>` in a new tab.
- F2: click "Fetch stats" on a done upload → strip renders within ~1.5 s with non-null views/likes/comments. If channel hasn't been re-authed with the new scope, watch time slot says "Re-auth channel for watch time"; other fields still populate.
- F3: click "+ Make Short" on a done upload row → modal opens with the parent video preselected. After Queue Render, the new short's row on `YouTubeVideosPage` opens to show `seo_description` starting with "Watch the full video → https://...".
