# YouTube Pipeline Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the silent SFX playback bug, polish the SFX library UI, add YouTube video preview, improve the CreationPanel, fix Uploads aspect ratio, surface YouTube jobs in Pipeline, and add a 7-step in-app wizard to connect multiple YouTube channels.

**Architecture:** Bug fixes and UI tweaks land directly in existing files. The YouTube preview adds one backend endpoint and one frontend modal. The multi-channel wizard adds 5 backend endpoints + 4 service methods to `credential_service.py` + a new `YouTubeSetupWizard.jsx` component wired into `UploadsPage.jsx`.

**Tech Stack:** FastAPI (Python 3.11), React 18 + Vite + Tailwind CSS, SQLAlchemy, httpx, Fernet encryption, YouTube Data API v3

---

## File Map

| File | Action | What changes |
|---|---|---|
| `console/backend/routers/sfx.py` | Modify | Remove auth guard from stream endpoint |
| `console/backend/routers/youtube_videos.py` | Modify | Add `GET /{video_id}/stream` endpoint |
| `console/backend/routers/credentials.py` | Modify | Add 4 wizard endpoints + modify callback to route by state |
| `console/backend/services/credential_service.py` | Modify | Add 5 new methods for wizard |
| `console/frontend/src/pages/SFXPage.jsx` | Modify | Duration bar, play error handling, toast outside scroll area |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Modify | 10min preset, AI asset filter, scroll fix, preview modal |
| `console/frontend/src/pages/UploadsPage.jsx` | Modify | Fix aspect ratio in VideoPreviewModal, add wizard trigger |
| `console/frontend/src/pages/PipelinePage.jsx` | Modify | Fetch YouTube video titles, show in job rows |
| `console/frontend/src/api/client.js` | Modify | Add `youtubeVideosApi.streamUrl` |
| `console/frontend/src/components/YouTubeSetupWizard.jsx` | Create | 7-step wizard component |
| `docs/guides/youtube-channel-setup.md` | Create | Updated + renamed guide |

---

## Task 1: Fix SFX silent playback (auth bug)

**Files:**
- Modify: `console/backend/routers/sfx.py:72-83`

The `/api/sfx/{id}/stream` endpoint currently requires `_user=Depends(require_editor_or_admin)`. The browser's `new Audio(url)` sends no Authorization header, so it gets a 401 and plays nothing. The music stream endpoint already omits auth by design — apply the same pattern.

- [ ] **Step 1: Remove the auth dependency from the stream endpoint**

Replace lines 72-83 in `console/backend/routers/sfx.py`:

```python
@router.get("/{sfx_id}/stream")
def stream_sfx(sfx_id: int, db: Session = Depends(get_db)):
    from console.backend.models.sfx_asset import SfxAsset
    row = db.get(SfxAsset, sfx_id)
    if not row:
        raise HTTPException(status_code=404, detail="SFX not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    ext = path.suffix.lower()
    media_type = MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(str(path), media_type=media_type)
```

- [ ] **Step 2: Verify the backend starts cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
uvicorn console.backend.main:app --port 8080 --reload
```

Expected: server starts, no import errors.

- [ ] **Step 3: Smoke-test the stream endpoint**

```bash
# Get an SFX id from the DB (replace 1 with a real id)
curl -s http://localhost:8080/api/sfx/1/stream -I
```

Expected: `HTTP/1.1 200 OK` with `content-type: audio/mpeg` (or wav). Previously returned `401 Unauthorized`.

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/sfx.py
git commit -m "fix: remove auth guard from sfx stream endpoint to allow HTML5 Audio playback"
```

---

## Task 2: SFX duration bar + playback error handling

**Files:**
- Modify: `console/frontend/src/pages/SFXPage.jsx:154-167, 209-247`

- [ ] **Step 1: Add play error handling and the duration bar**

Replace the `handlePlay` function (lines 154-168) and the card render block (lines 209-247) in `SFXPage.jsx`:

```jsx
  const handlePlay = (sfx) => {
    if (playing === sfx.id) {
      audioRef.current?.pause()
      setPlaying(null)
    } else {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.onended = null
      }
      const audio = new Audio(sfxApi.streamUrl(sfx.id))
      audioRef.current = audio
      audio.play().catch(() => {
        setPlaying(null)
        // show inline error — no toast state in this scope, use alert as fallback
        alert(`Could not load audio for "${sfx.title}". Check that the file exists on disk.`)
      })
      audio.onended = () => setPlaying(null)
      setPlaying(sfx.id)
    }
  }
```

Then update the card content inside the `.map()` (replace the `<div className="flex-1 min-w-0">` block):

```jsx
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-[#e8e8f0] truncate">{sfx.title}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-[#9090a8] font-mono">{sfx.sound_type}</span>
                  {sfx.duration_s && (
                    <span className="text-xs text-[#5a5a70]">{sfx.duration_s.toFixed(0)}s</span>
                  )}
                </div>
                {sfx.duration_s && (
                  <div className="mt-1.5 h-0.5 rounded-full bg-[#2a2a32] w-full max-w-[200px]">
                    <div
                      className="h-0.5 rounded-full bg-[#7c6af7]"
                      style={{ width: `${Math.min(100, (sfx.duration_s / 60) * 100)}%` }}
                    />
                  </div>
                )}
              </div>
```

- [ ] **Step 2: Manual test**

Open http://localhost:5173, navigate to SFX Library. Click a play button — audio should play. The colored bar below each title should reflect duration proportional to 60 s.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/SFXPage.jsx
git commit -m "feat: sfx duration bar and play error handling"
```

---

## Task 3: Uploads — fix VideoPreviewModal aspect ratio for YouTube Long

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx:53`

- [ ] **Step 1: Derive aspect ratio from video_format**

In `UploadsPage.jsx`, find the `VideoPreviewModal` component (around line 32–58). Replace the hardcoded `aspectRatio: '9/16'` on line 53:

```jsx
        <video
          controls
          autoPlay
          src={`/api/uploads/videos/${video.id}/stream`}
          className="w-full rounded-lg bg-black"
          style={{
            aspectRatio: video.video_format === 'youtube_long' ? '16/9' : '9/16',
            maxHeight: '60vh',
            objectFit: 'contain',
          }}
        />
```

- [ ] **Step 2: Manual test**

In Uploads → Videos tab, change format filter to "YouTube Long", find a completed video, click Preview. Video should render in 16:9 landscape. Switch to "Short", preview should be 9:16 portrait.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/UploadsPage.jsx
git commit -m "fix: derive video preview aspect ratio from video_format (16/9 for youtube_long)"
```

---

## Task 4: CreationPanel — 10min preset, AI asset filter, scroll fix

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx:13-19, 115-127, 185-197`

- [ ] **Step 1: Add 10min preset**

Replace the `DURATION_PRESETS` constant (lines 13–19):

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

- [ ] **Step 2: Filter visual assets to AI sources only**

In the `useEffect` at lines 115–127, replace the `assetsApi.list` call:

```js
  useEffect(() => {
    let mounted = true
    musicApi.list({ status: 'ready' })
      .then(d => { if (mounted) setMusicList(d.items || d || []) })
      .catch(() => {})
    const AI_SOURCES = ['midjourney', 'runway', 'veo']
    assetsApi.list({ asset_type: 'video_clip' })
      .then(d => {
        if (mounted) setAssetList((d.items || d || []).filter(a => AI_SOURCES.includes(a.source)))
      })
      .catch(() => {})
    sfxApi.list()
      .then(d => { if (mounted) setSfxList(d.items || d || []) })
      .catch(() => {})
    return () => { mounted = false }
  }, [])
```

- [ ] **Step 3: Fix toast scroll interference**

In the `CreationPanel` return (line 185 onwards), the `<Toast>` currently renders inside the `overflow-y-auto` div (line 196). Move it outside that div so it doesn't affect scroll layout.

Find this structure:

```jsx
      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">
          {toast && <Toast message={toast.msg} type={toast.type} />}
```

Change to (Toast moves above the scroll container, inside the panel wrapper):

```jsx
        {/* Toast — outside scroll area so it doesn't shift layout */}
        {toast && (
          <div className="absolute top-16 left-0 right-0 z-10 px-6">
            <Toast message={toast.msg} type={toast.type} />
          </div>
        )}
        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">
```

Also add a helper label above the Visual Loop selector. Find the `<Select label="Visual Loop"` block (around line 362) and add before it:

```jsx
              <p className="text-xs text-[#5a5a70]">Showing AI-generated clips only (Midjourney · Runway · Veo)</p>
              <Select
                label="Visual Loop"
```

- [ ] **Step 4: Manual test**

Open YouTube Videos → New video. Verify:
- Duration presets show 10min, 1h, 3h, 8h, 10h, Custom
- Visual Loop dropdown only shows midjourney/runway/veo assets
- Panel scrolls smoothly to the bottom (SFX Layers and Render sections visible)

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: creation panel — 10min preset, AI asset filter, toast scroll fix"
```

---

## Task 5: Pipeline — show linked YouTube video title in job rows

**Files:**
- Modify: `console/frontend/src/pages/PipelinePage.jsx:1-5, 113-162, 59-110`

- [ ] **Step 1: Import youtubeVideosApi and fetch video map on mount**

Add the import at the top of `PipelinePage.jsx` (after line 4):

```js
import { youtubeVideosApi } from '../api/client.js'
```

Add a `videoMap` state and fetch it once on mount. Inside `PipelinePage`, after the existing state declarations (around line 121):

```js
  const [videoMap, setVideoMap] = useState({})  // { id: title }

  useEffect(() => {
    youtubeVideosApi.list()
      .then(res => {
        const m = {}
        for (const v of res.items || res || []) m[v.id] = v.title
        setVideoMap(m)
      })
      .catch(() => {})
  }, [])
```

- [ ] **Step 2: Pass videoMap to JobRow and display the title**

In the `filtered.map(job => ...)` render (around line 256–258), pass `videoMap`:

```jsx
            {filtered.map(job => (
              <JobRow key={job.id} job={job} videoMap={videoMap} onRetry={handleRetry} onCancel={handleCancel} onError={(msg) => showToast(msg, 'error')} />
            ))}
```

In the `JobRow` component signature (line 35), add `videoMap`:

```jsx
function JobRow({ job, videoMap = {}, onRetry, onCancel, onError }) {
```

In the expanded details section of `JobRow` (around line 87, after the `job.celery_task_id` line), add:

```jsx
          {job.parent_youtube_video_id && (
            <div>
              YouTube Video:{' '}
              <span className="text-[#e8e8f0]">
                {videoMap[job.parent_youtube_video_id]
                  ? `${videoMap[job.parent_youtube_video_id]} (#${job.parent_youtube_video_id})`
                  : `#${job.parent_youtube_video_id}`}
              </span>
            </div>
          )}
```

- [ ] **Step 3: Manual test**

Open Pipeline page, expand a job that has a `parent_youtube_video_id`. The "YouTube Video:" line should show the video title.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/PipelinePage.jsx
git commit -m "feat: pipeline — show linked youtube video title in job detail row"
```

---

## Task 6: YouTube Videos — stream endpoint (backend)

**Files:**
- Modify: `console/backend/routers/youtube_videos.py`

- [ ] **Step 1: Add the stream endpoint**

Add at the end of `console/backend/routers/youtube_videos.py` (after line 179):

```python
@router.get("/{video_id}/stream")
def stream_video(video_id: int, db: Session = Depends(get_db)):
    """Stream the rendered output file. No auth — same pattern as music/sfx streams."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    from console.backend.models.youtube_video import YoutubeVideo

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not video.output_path:
        raise HTTPException(status_code=404, detail="Video has no rendered output yet")
    path = Path(video.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Render file not found on disk")
    return FileResponse(str(path), media_type="video/mp4")
```

- [ ] **Step 2: Verify endpoint is registered**

```bash
curl -s http://localhost:8080/api/youtube-videos/999/stream -I
```

Expected: `HTTP/1.1 404 Not Found` with `{"detail":"Video not found"}` — confirms endpoint exists and routes correctly.

- [ ] **Step 3: Commit**

```bash
git add console/backend/routers/youtube_videos.py
git commit -m "feat: add GET /api/youtube-videos/{id}/stream endpoint for rendered output"
```

---

## Task 7: YouTube Videos — preview modal (frontend)

**Files:**
- Modify: `console/frontend/src/api/client.js:207-233`
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx:1-10, 593-763`

- [ ] **Step 1: Add streamUrl to youtubeVideosApi in client.js**

In `console/frontend/src/api/client.js`, inside the `youtubeVideosApi` object (after the `render` line, around line 232):

```js
  render: (id) => fetchApi(`/api/youtube-videos/${id}/render`, { method: 'POST' }),
  streamUrl: (id) => `/api/youtube-videos/${id}/stream`,
}
```

- [ ] **Step 2: Add VideoPreviewModal component to YouTubeVideosPage.jsx**

Add this component before `function CreationPanel` (after the imports, around line 11):

```jsx
function VideoPreviewModal({ video, onClose }) {
  if (!video) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-[#1c1c22] border border-[#2a2a32] rounded-xl p-4 flex flex-col gap-3"
        style={{ width: '80vw', maxWidth: '1200px' }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="text-sm font-medium text-[#e8e8f0] leading-snug">{video.title}</div>
          <button onClick={onClose} className="text-[#9090a8] hover:text-[#f87171] flex-shrink-0 transition-colors text-lg leading-none">
            ✕
          </button>
        </div>
        <video
          controls
          autoPlay
          src={youtubeVideosApi.streamUrl(video.id)}
          className="w-full rounded-lg bg-black"
          style={{ aspectRatio: '16/9', maxHeight: '70vh', objectFit: 'contain' }}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Add previewVideo state and Preview button**

In `YouTubeVideosPage` component, add state after existing state declarations (around line 600):

```js
  const [previewVideo, setPreviewVideo] = useState(null)
```

In the video card actions (around line 715–735), add a Preview button for `ready` videos:

```jsx
                    {v.status === 'ready' && (
                      <>
                        <Button variant="ghost" size="sm" onClick={() => setPreviewVideo(v)}>
                          ▶ Preview
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setMakeShortVideo(v)}>
                          + Make Short
                        </Button>
                      </>
                    )}
```

Add the modal at the end of the return, before the closing `</div>` (after the MakeShortModal block):

```jsx
      {previewVideo && (
        <VideoPreviewModal video={previewVideo} onClose={() => setPreviewVideo(null)} />
      )}
```

- [ ] **Step 4: Manual test**

Render a YouTube video to `ready` status (or manually set status via DB). Click "▶ Preview" — a 16:9 video player should open and stream the file.

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/api/client.js console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: youtube videos — add rendered video preview modal"
```

---

## Task 8: Multi-credential service methods

**Files:**
- Modify: `console/backend/services/credential_service.py`

The existing `upsert_credential` and `build_oauth_url` always query by platform (one row per platform). The wizard needs to create multiple YouTube credentials and build OAuth URLs per credential ID.

- [ ] **Step 1: Add 5 new methods to CredentialService**

At the end of `credential_service.py` (before the `_get_or_404` helper), add:

```python
    # ── Wizard: multi-credential support ─────────────────────────────────────

    def create_youtube_credential(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict:
        """Create a new YouTube credential row (always inserts, never upserts)."""
        defaults = PLATFORM_DEFAULTS["youtube"]
        cred = PlatformCredential(
            platform="youtube",
            name=name,
            auth_endpoint=defaults["auth_endpoint"],
            token_endpoint=defaults["token_endpoint"],
            scopes=defaults["scopes"],
            client_id=client_id,
            client_secret=encrypt(client_secret),
            redirect_uri=redirect_uri,
            status="pending",
        )
        self.db.add(cred)
        self.db.commit()
        self.db.refresh(cred)
        return self._safe_dict(cred)

    def build_oauth_url_for_credential(self, cred_id: int, state: str) -> str:
        """Build Google OAuth URL for a specific credential row."""
        cred = self._get_or_404(cred_id)
        if not cred.client_id or not cred.auth_endpoint:
            raise ValueError(f"Credential {cred_id} is not fully configured")
        params = {
            "client_id":     cred.client_id,
            "redirect_uri":  cred.redirect_uri or "",
            "response_type": "code",
            "scope":         " ".join(cred.scopes or []),
            "access_type":   "offline",
            "prompt":        "consent",  # always returns refresh_token
            "state":         state,
        }
        return f"{cred.auth_endpoint}?{urlencode(params)}"

    def exchange_code_for_credential(self, cred_id: int, code: str) -> dict:
        """Exchange OAuth code for a specific credential row (not platform-wide)."""
        cred = self._get_or_404(cred_id)
        if not cred.token_endpoint:
            raise ValueError(f"Credential {cred_id} not configured")
        client_secret = decrypt(cred.client_secret) if cred.client_secret else ""
        resp = httpx.post(
            cred.token_endpoint,
            data={
                "code":          code,
                "client_id":     cred.client_id,
                "client_secret": client_secret,
                "redirect_uri":  cred.redirect_uri,
                "grant_type":    "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
        cred.access_token = encrypt(tokens["access_token"])
        if "refresh_token" in tokens:
            cred.refresh_token = encrypt(tokens["refresh_token"])
        expires_in = tokens.get("expires_in", 3600)
        cred.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        cred.last_refreshed = datetime.now(timezone.utc)
        cred.status = "connected"
        cred.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return self._safe_dict(cred)

    def verify_youtube_credential(self, cred_id: int) -> dict:
        """Call YouTube Data API channels.list to confirm the token works.

        Returns { channel_id, channel_title, subscriber_count }.
        Costs 1 quota unit (10,000 unit daily limit).
        """
        cred = self._get_or_404(cred_id)
        if not cred.access_token:
            raise ValueError("No access token — complete OAuth authorization first")
        access_token = decrypt(cred.access_token)
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet,statistics", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            raise ValueError(f"YouTube API error {resp.status_code}: {resp.text[:300]}")
        items = resp.json().get("items", [])
        if not items:
            raise ValueError("No YouTube channel found for this Google account")
        ch = items[0]
        return {
            "channel_id":       ch["id"],
            "channel_title":    ch["snippet"]["title"],
            "subscriber_count": int(ch.get("statistics", {}).get("subscriberCount", 0)),
        }

    def create_channel_from_credential(self, cred_id: int) -> dict:
        """Verify the credential then create a Channel row linked to it."""
        from console.backend.models.channel import Channel
        info = self.verify_youtube_credential(cred_id)
        cred = self._get_or_404(cred_id)
        channel = Channel(
            name=info["channel_title"],
            platform="youtube",
            credential_id=cred.id,
            subscriber_count=info["subscriber_count"],
            status="active",
        )
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return {
            "id":               channel.id,
            "name":             channel.name,
            "platform":         channel.platform,
            "status":           channel.status,
            "channel_id":       info["channel_id"],
            "subscriber_count": info["subscriber_count"],
        }
```

- [ ] **Step 2: Verify the server restarts cleanly**

```bash
# In the terminal running uvicorn, check for import errors after saving
# If running with --reload, watch the terminal output
curl -s http://localhost:8080/api/credentials -H "Authorization: Bearer $(cat /tmp/test_token 2>/dev/null || echo invalid)" | head -c 100
```

Expected: either a credentials list or a 401 — confirms the module loads without error.

- [ ] **Step 3: Commit**

```bash
git add console/backend/services/credential_service.py
git commit -m "feat: credential service — add multi-credential wizard methods for YouTube"
```

---

## Task 9: Wizard backend endpoints

**Files:**
- Modify: `console/backend/routers/credentials.py`

- [ ] **Step 1: Add WizardStartBody schema and 4 wizard endpoints**

At the end of `console/backend/routers/credentials.py`, add:

```python

# ── YouTube Setup Wizard ──────────────────────────────────────────────────────

class WizardStartBody(BaseModel):
    name: str
    client_id: str
    client_secret: str
    redirect_uri: str


@router.post("/youtube/setup/start", status_code=201)
def wizard_start(
    body: WizardStartBody,
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    """Create a new pending YouTube credential and return the OAuth URL."""
    svc = CredentialService(db)
    cred = svc.create_youtube_credential(
        name=body.name,
        client_id=body.client_id,
        client_secret=body.client_secret,
        redirect_uri=body.redirect_uri,
    )
    cred_id = cred["id"]
    oauth_url = svc.build_oauth_url_for_credential(cred_id, state=f"cred_{cred_id}")
    return {"cred_id": cred_id, "oauth_url": oauth_url}


@router.get("/youtube/setup/status/{cred_id}")
def wizard_status(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Poll this endpoint to detect when OAuth callback has completed."""
    try:
        cred = CredentialService(db).get_credential(cred_id)
        return {"status": cred["status"], "connected_at": cred.get("last_refreshed")}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/youtube/setup/verify/{cred_id}")
def wizard_verify(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Call YouTube channels.list to confirm the token works."""
    try:
        return CredentialService(db).verify_youtube_credential(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/youtube/setup/create-channel/{cred_id}", status_code=201)
def wizard_create_channel(
    cred_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Create a Channel row linked to the credential (calls verify internally)."""
    try:
        return CredentialService(db).create_channel_from_credential(cred_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: Modify oauth_callback to support credential-scoped state**

Replace the existing `oauth_callback` function (lines 70-82):

```python
@router.get("/{platform}/callback")
def oauth_callback(
    platform: str,
    code: str = Query(...),
    state: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """OAuth callback — exchanges auth code for tokens and stores encrypted.

    If state starts with 'cred_' (wizard flow), routes to the specific credential.
    Otherwise falls back to the legacy platform-wide credential lookup.
    """
    from fastapi.responses import HTMLResponse
    try:
        svc = CredentialService(db)
        if state and state.startswith("cred_"):
            cred_id = int(state.removeprefix("cred_"))
            svc.exchange_code_for_credential(cred_id, code)
        else:
            svc.exchange_code(platform, code)
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;padding:2rem;background:#0d0d0f;color:#34d399'>"
            "<h2>✓ Authorization successful</h2>"
            "<p style='color:#9090a8'>You can close this tab and return to the console.</p>"
            "<script>setTimeout(()=>window.close(),2000)</script>"
            "</body></html>"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {e}")
```

- [ ] **Step 3: Check endpoints are accessible in API docs**

```bash
curl -s http://localhost:8080/openapi.json | python3 -c "
import json,sys
spec = json.load(sys.stdin)
wizard = [p for p in spec['paths'] if 'setup' in p]
print('Wizard endpoints:', wizard)
"
```

Expected output includes all 4 setup paths:
```
Wizard endpoints: ['/api/credentials/youtube/setup/start', '/api/credentials/youtube/setup/status/{cred_id}', '/api/credentials/youtube/setup/verify/{cred_id}', '/api/credentials/youtube/setup/create-channel/{cred_id}']
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/credentials.py
git commit -m "feat: wizard endpoints for multi-channel YouTube setup + HTML callback response"
```

---

## Task 10: YouTubeSetupWizard component

**Files:**
- Create: `console/frontend/src/components/YouTubeSetupWizard.jsx`

- [ ] **Step 1: Create the wizard component**

Create `console/frontend/src/components/YouTubeSetupWizard.jsx`:

```jsx
import { useState, useEffect, useRef } from 'react'
import { Modal, Input, Button, Toast } from './index.jsx'
import { fetchApi } from '../api/client.js'

// The backend callback URL. Port 8080 is the FastAPI server (not the Vite dev server).
const CALLBACK_URI = `${window.location.protocol}//${window.location.hostname}:8080/api/credentials/youtube/callback`

const STEPS = [
  {
    id: 'gcp_project',
    label: 'Create Google Cloud Project',
    type: 'manual',
    description: 'Create a project in Google Cloud Console to house your YouTube API credentials. If you already have one, skip this step.',
    link: 'https://console.cloud.google.com/projectcreate',
    linkLabel: 'Open Google Cloud Console →',
  },
  {
    id: 'enable_api',
    label: 'Enable YouTube Data API v3',
    type: 'manual',
    description: 'In your Google Cloud project, enable the YouTube Data API v3.',
    link: 'https://console.cloud.google.com/apis/library/youtube.googleapis.com',
    linkLabel: 'Open YouTube Data API Library →',
  },
  {
    id: 'create_oauth',
    label: 'Create OAuth 2.0 Credentials',
    type: 'manual',
    description: 'Create a Web Application OAuth 2.0 client ID. In "Authorized redirect URIs", add the URI shown below exactly as written.',
    link: 'https://console.cloud.google.com/apis/credentials',
    linkLabel: 'Open Credentials Page →',
    callbackUri: true,
  },
  {
    id: 'enter_creds',
    label: 'Enter Credentials',
    type: 'form',
  },
  {
    id: 'authorize',
    label: 'Authorize with Google',
    type: 'oauth',
  },
  {
    id: 'verify',
    label: 'Verify Connection',
    type: 'verify',
  },
  {
    id: 'create_channel',
    label: 'Create Channel Entry',
    type: 'create',
  },
]

export default function YouTubeSetupWizard({ onClose, onComplete }) {
  const [step, setStep] = useState(0)
  const [manualChecked, setManualChecked] = useState({})
  const [form, setForm] = useState({ name: '', client_id: '', client_secret: '' })
  const [credId, setCredId] = useState(null)
  const [oauthUrl, setOauthUrl] = useState(null)
  const [verifyResult, setVerifyResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const pollRef = useRef(null)

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5000)
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const current = STEPS[step]

  const handleNext = async () => {
    if (current.type === 'manual') {
      setStep(s => s + 1)
      return
    }

    if (current.type === 'form') {
      if (!form.name.trim() || !form.client_id.trim() || !form.client_secret.trim()) {
        showToast('All three fields are required')
        return
      }
      setLoading(true)
      try {
        const res = await fetchApi('/api/credentials/youtube/setup/start', {
          method: 'POST',
          body: JSON.stringify({
            name: form.name.trim(),
            client_id: form.client_id.trim(),
            client_secret: form.client_secret.trim(),
            redirect_uri: CALLBACK_URI,
          }),
        })
        setCredId(res.cred_id)
        setOauthUrl(res.oauth_url)
        setStep(s => s + 1)
      } catch (e) {
        showToast(e.message)
      } finally {
        setLoading(false)
      }
      return
    }

    if (current.type === 'verify') {
      setLoading(true)
      try {
        const res = await fetchApi(`/api/credentials/youtube/setup/verify/${credId}`, { method: 'POST' })
        setVerifyResult(res)
        setStep(s => s + 1)
      } catch (e) {
        showToast(e.message)
      } finally {
        setLoading(false)
      }
      return
    }

    if (current.type === 'create') {
      setLoading(true)
      try {
        await fetchApi(`/api/credentials/youtube/setup/create-channel/${credId}`, { method: 'POST' })
        onComplete?.()
        onClose()
      } catch (e) {
        showToast(e.message)
      } finally {
        setLoading(false)
      }
      return
    }
  }

  const startOAuth = () => {
    if (!oauthUrl) return
    window.open(oauthUrl, '_blank')
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetchApi(`/api/credentials/youtube/setup/status/${credId}`)
        if (res.status === 'connected') {
          clearInterval(pollRef.current)
          setStep(s => s + 1)
        }
      } catch {}
    }, 3000)
  }

  const canNext = () => {
    if (current.type === 'manual') return !!manualChecked[current.id]
    if (current.type === 'form') return true
    if (current.type === 'oauth') return false
    if (current.type === 'verify') return true
    if (current.type === 'create') return true
    return false
  }

  const isLastStep = step === STEPS.length - 1

  const cliCommand = `python3 scripts/setup_youtube_oauth.py \\
  --client-id  "${form.client_id || 'YOUR_CLIENT_ID'}" \\
  --client-secret "${form.client_secret || 'YOUR_CLIENT_SECRET'}" \\
  --channel-name "${form.name || 'ChannelName'}"`

  return (
    <Modal
      open
      onClose={onClose}
      title="Add YouTube Channel"
      width="max-w-xl"
      footer={
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          {current.type !== 'oauth' && (
            <Button variant="primary" loading={loading} disabled={!canNext()} onClick={handleNext}>
              {isLastStep ? 'Finish' : 'Next →'}
            </Button>
          )}
        </div>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

      {/* Progress bar */}
      <div className="flex gap-1 mb-5">
        {STEPS.map((s, i) => (
          <div key={s.id} className={`flex-1 h-1 rounded-full transition-colors ${
            i < step ? 'bg-[#34d399]' : i === step ? 'bg-[#7c6af7]' : 'bg-[#2a2a32]'
          }`} />
        ))}
      </div>

      <div className="text-[10px] text-[#5a5a70] font-mono uppercase tracking-widest mb-1">
        Step {step + 1} of {STEPS.length}
      </div>
      <div className="text-base font-semibold text-[#e8e8f0] mb-4">{current.label}</div>

      {/* Manual step */}
      {current.type === 'manual' && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#9090a8] leading-relaxed">{current.description}</p>
          {current.callbackUri && (
            <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
              <div className="text-xs text-[#5a5a70] mb-1.5">Authorized Redirect URI to add:</div>
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono text-[#7c6af7] flex-1 break-all">{CALLBACK_URI}</code>
                <button
                  onClick={() => navigator.clipboard.writeText(CALLBACK_URI)}
                  className="text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-0.5 bg-[#16161a] rounded border border-[#2a2a32] flex-shrink-0"
                >
                  Copy
                </button>
              </div>
            </div>
          )}
          <a
            href={current.link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sm text-[#7c6af7] hover:text-[#9d8df8] transition-colors"
          >
            {current.linkLabel}
          </a>
          <label className="flex items-center gap-2 text-sm text-[#9090a8] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={!!manualChecked[current.id]}
              onChange={e => setManualChecked(p => ({ ...p, [current.id]: e.target.checked }))}
              className="accent-[#7c6af7]"
            />
            Done — ready to continue
          </label>
        </div>
      )}

      {/* Form step */}
      {current.type === 'form' && (
        <div className="flex flex-col gap-3">
          <Input
            label="Channel Nickname"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="e.g. Sleep Sounds Main"
          />
          <Input
            label="Client ID"
            value={form.client_id}
            onChange={e => setForm(f => ({ ...f, client_id: e.target.value }))}
            placeholder="1234567890-xxxx.apps.googleusercontent.com"
          />
          <Input
            label="Client Secret"
            type="password"
            value={form.client_secret}
            onChange={e => setForm(f => ({ ...f, client_secret: e.target.value }))}
            placeholder="GOCSPX-..."
          />
          <details className="mt-1 group">
            <summary className="text-xs text-[#5a5a70] cursor-pointer hover:text-[#9090a8]">
              Advanced: run via CLI instead
            </summary>
            <div className="mt-2 bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
              <pre className="text-xs font-mono text-[#9090a8] whitespace-pre-wrap break-all pr-12">{cliCommand}</pre>
              <button
                onClick={() => navigator.clipboard.writeText(cliCommand)}
                className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-0.5 bg-[#16161a] rounded border border-[#2a2a32]"
              >
                Copy
              </button>
            </div>
          </details>
        </div>
      )}

      {/* OAuth step */}
      {current.type === 'oauth' && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#9090a8] leading-relaxed">
            Click below to open Google's authorization screen in a new tab. Sign in with the Google account that owns the YouTube channel.
          </p>
          <div className="bg-[#fbbf24]/10 border border-[#fbbf24]/30 rounded-lg p-3 text-xs text-[#fbbf24] leading-relaxed">
            If your OAuth app is in <strong>Testing mode</strong>, only accounts listed as Test Users can authorize.{' '}
            <a
              href="https://console.cloud.google.com/apis/credentials/consent"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              Add your account → OAuth consent screen → Test users
            </a>
          </div>
          <Button variant="primary" onClick={startOAuth}>
            Open Google Authorization →
          </Button>
          <div className="flex items-center gap-2 text-xs text-[#5a5a70]">
            <div className="flex gap-1">
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-[#7c6af7] animate-pulse"
                  style={{ animationDelay: `${i * 200}ms` }}
                />
              ))}
            </div>
            Waiting for authorization…
          </div>
        </div>
      )}

      {/* Verify step */}
      {current.type === 'verify' && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[#9090a8]">
            Click "Next" to verify your YouTube connection and retrieve your channel name.
          </p>
        </div>
      )}

      {/* Create channel step */}
      {current.type === 'create' && (
        <div className="flex flex-col gap-4">
          {verifyResult && (
            <div className="bg-[#34d399]/10 border border-[#34d399]/30 rounded-lg p-4">
              <div className="text-xs text-[#5a5a70] mb-1">Connected channel</div>
              <div className="text-sm font-semibold text-[#e8e8f0]">{verifyResult.channel_title}</div>
              {verifyResult.subscriber_count > 0 && (
                <div className="text-xs text-[#9090a8] mt-0.5">{verifyResult.subscriber_count.toLocaleString()} subscribers</div>
              )}
            </div>
          )}
          <p className="text-sm text-[#9090a8] leading-relaxed">
            Click "Finish" to create the channel entry in your console. It will appear in the Channels tab and can be targeted for uploads.
          </p>
        </div>
      )}
    </Modal>
  )
}
```

- [ ] **Step 2: Verify no syntax errors**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend
npm run build 2>&1 | tail -20
```

Expected: build succeeds with no errors. (Warnings are OK.)

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/components/YouTubeSetupWizard.jsx
git commit -m "feat: YouTubeSetupWizard — 7-step in-app YouTube channel onboarding"
```

---

## Task 11: Wire wizard into Uploads Credentials tab

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx:252-314`

- [ ] **Step 1: Import wizard in UploadsPage**

At the top of `UploadsPage.jsx`, add the import (after the existing imports, around line 5):

```js
import YouTubeSetupWizard from '../components/YouTubeSetupWizard.jsx'
```

- [ ] **Step 2: Add wizard state to CredentialsTab**

Inside `CredentialsTab` (around line 257, after `const [toast, setToast] = useState(null)`):

```js
  const [showWizard, setShowWizard] = useState(false)
```

- [ ] **Step 3: Add "+ Add YouTube Channel" button**

In `CredentialsTab`'s return, find the `PLATFORMS.map(...)` section. Add a button at the top of the section (before the map), after the opening `<div className="space-y-3">` (around line 316):

```jsx
      {/* Quick-add wizard for YouTube — supports multiple accounts */}
      <div className="flex justify-end">
        <Button variant="primary" onClick={() => setShowWizard(true)}>
          + Add YouTube Channel
        </Button>
      </div>
```

- [ ] **Step 4: Render the wizard**

At the end of `CredentialsTab`'s return (after the toast, before the closing `</div>`):

```jsx
      {showWizard && (
        <YouTubeSetupWizard
          onClose={() => setShowWizard(false)}
          onComplete={() => { setShowWizard(false); load() }}
        />
      )}
```

- [ ] **Step 5: Manual test end-to-end**

1. Open http://localhost:5173, navigate to Uploads → Credentials
2. Click "+ Add YouTube Channel"
3. Wizard opens with 7-step progress bar
4. Steps 1-3: check the checkbox and advance with "Next →"
5. Step 4: fill in a test Client ID/Secret/Name, click "Next →"
6. Step 5: click "Open Google Authorization →" — new tab opens, 3 pulsing dots appear
7. (If you don't have real credentials, verify the wizard waits and doesn't crash)
8. Close wizard — Channels tab should be unchanged (no channel created without full flow)

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/UploadsPage.jsx
git commit -m "feat: uploads credentials tab — Add YouTube Channel wizard trigger"
```

---

## Task 12: Update YouTube channel setup guide

**Files:**
- Create: `docs/guides/youtube-channel-setup.md`
- (The old file `docs/guides/youtube-upload-setup.md` can be kept or removed — keep it to avoid broken references)

- [ ] **Step 1: Create the updated guide**

Create `docs/guides/youtube-channel-setup.md`:

```markdown
# YouTube Channel Setup Guide

This guide covers connecting one or more YouTube channels to the console so the
pipeline can automatically upload Long-form and Shorts videos.

---

## Recommended path: In-App Wizard

Open the console → **Uploads** tab → **Credentials** sub-tab → click **"+ Add YouTube Channel"**.

The wizard walks through all 7 steps with links and forms. Run it once per Google account.

---

## Manual path: CLI script

For automation, CI, or headless setups:

```bash
cd /path/to/ai-media-automation

python3 scripts/setup_youtube_oauth.py \
  --client-id  "YOUR_CLIENT_ID.apps.googleusercontent.com" \
  --client-secret "YOUR_CLIENT_SECRET" \
  --channel-name "MyChannel"
```

Run once per channel account.

---

## Prerequisites

- Python 3.11+ with `httpx`, `cryptography`, `python-dotenv`, `sqlalchemy`
- Console backend running with a valid PostgreSQL connection (`console/.env` configured)
- A Google account that owns the target YouTube channel

---

## Step 1 — Create a Google Cloud Project

[Open Google Cloud Console →](https://console.cloud.google.com/projectcreate)

Click **Select a project** → **New Project**. Name it (e.g. `ai-media-pipeline`) → **Create**.

---

## Step 2 — Enable YouTube Data API v3

[Open YouTube Data API v3 →](https://console.cloud.google.com/apis/library/youtube.googleapis.com)

Click **Enable**.

---

## Step 3 — Create OAuth 2.0 Credentials

[Open Credentials Page →](https://console.cloud.google.com/apis/credentials)

1. **Create Credentials → OAuth client ID**
2. Configure OAuth consent screen if prompted:
   - User Type: **External**
   - App name: anything (e.g. `AI Media Pipeline`)
   - Add your Google account as a **Test user** (required while in Testing mode)
3. Application type: **Web Application**
4. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:8080/api/credentials/youtube/callback
   ```
   *(Replace port if your backend runs on a different port.)*
5. Copy the **Client ID** and **Client Secret**.

> **Testing mode note:** While your OAuth app is in Testing mode, only accounts listed as
> Test Users can authorize. To add users: [OAuth consent screen → Test users](https://console.cloud.google.com/apis/credentials/consent).
> For production use (>100 users), submit the app for verification.

---

## Step 4 — Authorize & Connect

**In-app wizard:** Enter Client ID, Client Secret, and a nickname. Click "Open Google Authorization →", sign in, then the wizard auto-advances.

**CLI:** Run the script above. It opens a browser, handles the OAuth flow on `http://localhost:8888/callback`, and stores encrypted tokens in PostgreSQL.

---

## Multiple Channels

Run the wizard (or CLI script) **once per Google account**. Each run creates a separate
`PlatformCredential` row and a `Channel` row. Channels from different Google accounts
each need their own OAuth consent.

If both channels share the same Google OAuth app but different Google accounts, add each
account as a Test User in the OAuth consent screen.

---

## Token Refresh

Access tokens expire after ~1 hour. The pipeline auto-refreshes using the stored
refresh token. The Celery beat task `refresh_expiring_tokens` runs every 30 minutes.

If a refresh fails (user revoked access): re-run the wizard or CLI script with the same
channel name to re-authorize in place.

---

## Uploading

1. Go to **Uploads** tab → **Videos** sub-tab
2. Filter by format (Short or YouTube Long)
3. Use the channel picker to select the target channel
4. Click **Upload** — a Celery task is queued

Videos are uploaded as **Unlisted**. To publish:
1. Open [YouTube Studio](https://studio.youtube.com/) → Content
2. Find the video → Edit → Visibility → **Public** → Save
```

- [ ] **Step 2: Commit both files**

```bash
git add docs/guides/youtube-channel-setup.md
git commit -m "docs: add youtube-channel-setup.md — covers long-form, shorts, multi-account, in-app wizard"
```

---

## Self-Review — Spec Coverage Check

| Spec requirement | Task |
|---|---|
| SFX silent playback fix | Task 1 |
| SFX duration bar | Task 2 |
| SFX play error handling | Task 2 |
| Uploads VideoPreviewModal aspect ratio | Task 3 |
| CreationPanel 10min preset | Task 4 |
| CreationPanel AI-only asset filter | Task 4 |
| CreationPanel scroll fix (toast) | Task 4 |
| Pipeline YouTube video title label | Task 5 |
| YouTube Videos stream backend endpoint | Task 6 |
| YouTube Videos preview modal frontend | Task 7 |
| Multi-credential service methods | Task 8 |
| Wizard backend endpoints (start, status, verify, create-channel) | Task 9 |
| Modified callback to support cred-scoped state | Task 9 |
| YouTubeSetupWizard component (7 steps, deep links, CLI block) | Task 10 |
| Wizard wired into Uploads Credentials tab | Task 11 |
| Updated guide (renamed, multi-account, in-app wizard ref) | Task 12 |
