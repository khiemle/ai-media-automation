# YouTube Pipeline Improvements — Design Spec

**Date:** 2026-05-01  
**Scope:** 6 improvement areas across the Management Console

---

## 1. SFX Library — Bug Fix + UI Polish

### Bug: Silent audio playback

**Root cause:** `GET /api/sfx/{sfx_id}/stream` requires `_user=Depends(require_editor_or_admin)`. The frontend plays audio via `new Audio(url)` which is a plain browser HTTP request — no `Authorization` header is sent. The backend returns 401 and no audio plays.

**Fix:** Remove the auth dependency from `stream_sfx` in `console/backend/routers/sfx.py`. Precedent: `GET /api/music/{id}/stream` already omits auth by design to allow HTML5 audio tags.

### UI improvements (`console/frontend/src/pages/SFXPage.jsx`)

- **Duration bar:** Add a thin colored progress bar below the title, proportional to `sfx.duration_s` (capped visually at 60 s). Gives instant sense of length without playing.
- **Playback error handling:** Wrap `audioRef.current.play()` in a `.catch()` — if the file is missing on disk show a toast "Could not load audio" instead of silent failure.
- **Toast position fix:** The `<Toast>` inside the `ImportModal` already has `onClose`. No further change needed there.
- **Layout:** Keep flat-list rows. No structural change.

---

## 2. Pipeline Screen — YouTube Video Jobs

**File:** `console/frontend/src/pages/PipelinePage.jsx`

### Changes

- **Filter chip:** Add a "YouTube" chip in the controls row. When active, filter displayed jobs to `job_type === 'youtube_render'`.
- **Linked video label:** If a job has `parent_youtube_video_id`, show the video title (or ID if title unavailable) as a small secondary label beneath the task ID in the job row. Fetch the full video list once on mount using `youtubeVideosApi.list()` and build an `id → title` map client-side.

### No backend changes required

`PipelineJob.parent_youtube_video_id` already exists in the model.

---

## 3. Uploads Screen — YouTube Long Video

**File:** `console/frontend/src/pages/UploadsPage.jsx`

### Changes

- **Aspect ratio fix in `VideoPreviewModal`:** The current modal hardcodes `aspectRatio: '9/16'` (portrait). Derive it from the video's `video_format` field: `youtube_long` → `'16/9'`, all others → `'9/16'`.
- The format filter (`all / short / youtube_long`) and channel picker already exist and work correctly for youtube_long.

### No backend changes required

---

## 4. YouTube Videos Screen — Preview Rendered Video

### Backend (`console/backend/routers/youtube_videos.py`)

Add endpoint:

```
GET /api/youtube-videos/{video_id}/stream
```

- Reads `YoutubeVideo.output_path` from the DB.
- Returns `FileResponse(output_path, media_type="video/mp4")`.
- Returns 404 if `output_path` is null or the file does not exist on disk.
- **No auth required** on the stream — same pattern as music and SFX streams.

### Frontend (`console/frontend/src/pages/YouTubeVideosPage.jsx`)

- Add `VideoPreviewModal` component: fixed overlay, `<video controls autoPlay>` with `aspectRatio: '16/9'`, `src` pointing to `/api/youtube-videos/{id}/stream`.
- For cards where `status === 'ready'`, add a "▶ Preview" button next to the existing "+ Make Short" button. Clicking it sets `previewVideo` state to open the modal.
- Add `youtubeVideosApi.streamUrl = (id) => \`/api/youtube-videos/${id}/stream\`` to `console/frontend/src/api/client.js`.

---

## 5. CreationPanel Improvements

**File:** `console/frontend/src/pages/YouTubeVideosPage.jsx`

### Duration: add 10 min preset

Add `{ label: '10min', value: 10 / 60 }` to `DURATION_PRESETS` between `1h` and `Custom`:

```js
const DURATION_PRESETS = [
  { label: '10min', value: 10 / 60 },
  { label: '1h',    value: 1 },
  { label: '3h',    value: 3 },
  { label: '8h',    value: 8 },
  { label: '10h',   value: 10 },
  { label: 'Custom', value: null },
]
```

### Visual asset filter — AI sources only

After fetching `assetsApi.list({ asset_type: 'video_clip' })`, apply a client-side filter before setting state:

```js
const AI_SOURCES = ['midjourney', 'runway', 'veo']
setAssetList((d.items || d || []).filter(a => AI_SOURCES.includes(a.source)))
```

Add a helper label above the Visual Loop selector: `"Showing AI-generated clips (Midjourney · Runway · Veo)"`.

### Scroll fix

The `<Toast>` at line 196 renders inside the `overflow-y-auto` scroll container, which can cause layout height jumps. Move the toast to render just inside the panel wrapper div (above the scrollable content div, outside it) so it overlays without affecting scroll position.

---

## 6. Multi-Channel YouTube — In-App Setup Wizard

### Schema change

**File:** `console/backend/alembic/versions/` — new migration

- Drop the unique constraint on `platform_credentials.platform` (currently prevents more than one YouTube credential).
- Add nullable `name` column (`VARCHAR(120)`) to `platform_credentials` for human-readable labels like "Main Channel" or "Sleep Channel".
- Each `Channel` row already has `credential_id` FK — this is the per-channel link, no change needed there.

### Reused existing endpoints (`console/backend/routers/credentials.py`)

- `GET /api/credentials/youtube/oauth-url` — already builds the Google OAuth authorization URL
- `GET /api/credentials/youtube/callback` — already exchanges auth code, stores tokens, marks `connected`

No changes needed to these endpoints.

### New wizard endpoints (`console/backend/routers/credentials.py`)

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/credentials/youtube/setup/start` | editor/admin | Accepts `{ client_id, client_secret, name }`. Upserts a `PlatformCredential` row with `status = pending` and the given `name`. Returns `{ cred_id }`. Frontend then calls the existing `oauth-url` endpoint. |
| `GET /api/credentials/youtube/setup/status/{cred_id}` | editor/admin | Returns `{ status, connected_at }` — polled every 3 s by the wizard to detect when callback completes. |
| `POST /api/credentials/youtube/setup/verify/{cred_id}` | editor/admin | Calls YouTube Data API `channels.list(part=snippet,mine=true)`. Returns `{ channel_title, subscriber_count, channel_id }` on success; 400 with error detail on failure. |
| `POST /api/credentials/youtube/setup/create-channel/{cred_id}` | editor/admin | Creates a `Channel` row linked to the credential using the verified channel title as the name. Returns the new channel row. |

**Google API + OAuth type considerations:**
- The in-app wizard uses the backend as the OAuth callback (`/api/credentials/youtube/callback`). For this to work, the Google Cloud OAuth client must be type **Web Application** (not Desktop App) and must have `http://localhost:8080/api/credentials/youtube/callback` registered as an Authorized Redirect URI. The wizard shows this exact URI to copy in Step 3.
- The existing CLI script (`setup_youtube_oauth.py`) uses `http://localhost:8888/callback` and requires **Desktop App** type. Users who prefer CLI can create a separate Desktop App credential or add both URIs to the same Web App client.
- `channels.list` costs 1 quota unit (daily quota: 10,000 units). Safe to call during setup.
- While the OAuth app is in **Testing** mode, only accounts listed as Test Users can authorize. The wizard shows a warning for this.
- Token refresh uses the stored `refresh_token` — no user interaction needed after initial setup.

### Frontend wizard (`console/frontend/src/pages/UploadsPage.jsx` + new component)

**Trigger:** "+ Add YouTube Channel" button in the Credentials sub-tab (replaces or extends the current per-platform "Connect" button for YouTube).

**Wizard steps (modal, step-indicator at top):**

| Step | Label | In-app? | Detail |
|---|---|---|---|
| 1 | Create Google Cloud Project | Deep link only | Checkbox + link to `https://console.cloud.google.com/projectcreate` |
| 2 | Enable YouTube Data API v3 | Deep link only | Checkbox + link to `https://console.cloud.google.com/apis/library/youtube.googleapis.com` |
| 3 | Create OAuth 2.0 Credentials | Deep link only | Checkbox + link to `https://console.cloud.google.com/apis/credentials`; instruct: Application Type = **Web Application**, add Authorized Redirect URI = `http://localhost:8080/api/credentials/youtube/callback` (shown as a copy button in the wizard) |
| 4 | Enter Credentials | In-app form | Inputs for `Client ID`, `Client Secret`, `Channel nickname`; "Next" calls `POST /setup/start` |
| 5 | Authorize with Google | In-app + browser tab | "Open Google Authorization" button opens `oauth_url` in new tab; wizard polls `GET /setup/status/{cred_id}` every 3 s until `connected` |
| 6 | Verify Connection | In-app | Calls `POST /setup/verify/{cred_id}`; shows "Connected as: [Channel Title]" with subscriber count |
| 7 | Create Channel Entry | In-app | Calls `POST /setup/create-channel/{cred_id}`; shows success, closes wizard, refreshes Channels tab |

**CLI fallback block** (shown at Step 4): collapsible "Advanced: run via CLI" section showing the `setup_youtube_oauth.py` command with a copy button. This is the headless path for automation.

**Testing-mode warning:** At Step 5, show a yellow notice: "Your OAuth app may be in Testing mode. Only Google accounts listed as Test Users can authorize. Add your account at Google Cloud → OAuth consent screen → Test users."

### Updated guide file

- Rename `docs/guides/youtube-upload-setup.md` → `docs/guides/youtube-channel-setup.md`
- Update title: "YouTube Channel Setup Guide (Long-form + Shorts)"
- Note multi-account setup: run wizard once per Google account
- Reference the in-app wizard as the recommended path; keep CLI steps as the alternative
- Add note on Testing vs. Production OAuth app verification

---

## Files changed summary

| File | Change type |
|---|---|
| `console/backend/routers/sfx.py` | Remove auth from stream endpoint |
| `console/backend/routers/youtube_videos.py` | Add `/stream` endpoint |
| `console/backend/routers/credentials.py` | Add 4 wizard endpoints (reuses existing oauth-url + callback) |
| `console/backend/alembic/versions/XXX_multi_youtube_credential.py` | New migration |
| `console/frontend/src/pages/SFXPage.jsx` | Duration bar, error handling, toast fix |
| `console/frontend/src/pages/PipelinePage.jsx` | YouTube filter chip, video title label |
| `console/frontend/src/pages/UploadsPage.jsx` | Aspect ratio fix, Add Channel wizard trigger |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | 10min preset, asset filter, preview modal, scroll fix |
| `console/frontend/src/api/client.js` | Add `youtubeVideosApi.streamUrl` |
| `console/frontend/src/components/YouTubeSetupWizard.jsx` | New wizard component |
| `docs/guides/youtube-channel-setup.md` | Renamed + updated guide |
