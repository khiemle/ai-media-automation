# YouTube Pipeline Fixes & SFX Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix six issues: broken preview button, empty visual asset list, missing YouTube Long uploads section, Uploads format filter bug, SFX audio not applied in render, and SFX Library UI redesign to a grid layout.

**Architecture:** Five backend/frontend files modified + one new backend task file. No DB schema changes needed. Tasks are ordered by dependency: client.js and Celery task before the pages and router that import them.

**Tech Stack:** FastAPI (Python 3.11), React 18 + Vite + Tailwind CSS, SQLAlchemy, FFmpeg (filter_complex for dynamic audio mixing), Celery

---

## File Map

| File | Action | What changes |
|---|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Modify | Fix Preview status check; fix STATUS_COLORS; fix asset list per_page |
| `console/frontend/src/api/client.js` | Modify | Add `youtubeVideosApi.upload()` |
| `console/frontend/src/pages/UploadsPage.jsx` | Modify | Remove youtube_long from format filter; add YouTubeLongSection component |
| `console/frontend/src/pages/SFXPage.jsx` | Modify | Redesign to 3-column grid |
| `console/backend/tasks/youtube_upload_task.py` | Create | Celery task for uploading YouTube Long videos |
| `console/backend/routers/youtube_videos.py` | Modify | Add `POST /{video_id}/upload` endpoint |
| `console/backend/tasks/youtube_render_task.py` | Modify | Add `_resolve_sfx_layers()`, update `_render_video()` for dynamic audio |

---

## Task 1: Fix YouTube video preview button and STATUS_COLORS

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx:5-10, 766-774`

The render pipeline sets video status to `'done'`, but the Preview button checks `v.status === 'ready'`. Additionally, STATUS_COLORS uses `'ready'` and `'uploaded'` which are not real statuses.

- [ ] **Step 1: Fix STATUS_COLORS and the preview condition**

In `YouTubeVideosPage.jsx`, replace lines 5–10:

```jsx
const STATUS_COLORS = {
  draft:     '#9090a8',
  queued:    '#fbbf24',
  rendering: '#fbbf24',
  done:      '#34d399',
  failed:    '#f87171',
  published: '#4a9eff',
}
```

Then replace line 766 (the `v.status === 'ready'` check):

```jsx
                    {v.status === 'done' && (
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

- [ ] **Step 2: Manual test**

Start the dev server (`npm run dev` in `console/frontend`). Render a YouTube video (or set status to `done` via the DB: `UPDATE youtube_videos SET status='done', output_path='/tmp/test.mp4' WHERE id=<id>`). The Preview button should appear, and the status dot next to `● done` should be green.

```bash
psql "postgresql://admin:123456@localhost:5432/ai_media" \
  -c "SELECT id, title, status FROM youtube_videos LIMIT 5"
```

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "fix: youtube videos preview button — check status 'done' not 'ready', fix STATUS_COLORS"
```

---

## Task 2: Fix visual asset list empty in CreationPanel

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx:153`

`assetsApi.list({ asset_type: 'video_clip' })` uses the default `per_page=20`. The DB has 170 video clips — 163 pexels, 4 manual, 3 midjourney — so the first page of 20 items is all pexels, and the client-side `AI_SOURCES` filter returns nothing.

Fix: pass `per_page: 200` to fetch all clips before filtering.

- [ ] **Step 1: Update the assetsApi call in the useEffect**

In `YouTubeVideosPage.jsx`, replace line 153:

```js
    assetsApi.list({ asset_type: 'video_clip', per_page: 200 })
```

The full updated `useEffect` (lines 148–162) becomes:

```js
  useEffect(() => {
    let mounted = true
    musicApi.list({ status: 'ready' })
      .then(d => { if (mounted) setMusicList(d.items || d || []) })
      .catch(() => {})
    assetsApi.list({ asset_type: 'video_clip', per_page: 200 })
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

- [ ] **Step 2: Manual test**

Open YouTube Videos → New Video (via a template). In the CreationPanel, scroll to the "Visual Loop" Select. The dropdown should now list midjourney/runway/veo assets. Confirm the helper text "Showing AI-generated clips only" is visible.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "fix: creation panel visual asset list — fetch per_page=200 before AI source filter"
```

---

## Task 3: Add `upload` method to `youtubeVideosApi` in client.js

**Files:**
- Modify: `console/frontend/src/api/client.js:229-231`

The YouTube Long section (Task 4) needs a method to call `POST /api/youtube-videos/{id}/upload`.

- [ ] **Step 1: Add the upload method**

In `console/frontend/src/api/client.js`, replace lines 229–231 (the `render` and `streamUrl` lines at the end of `youtubeVideosApi`):

```js
  render: (id) => fetchApi(`/api/youtube-videos/${id}/render`, { method: 'POST' }),
  streamUrl: (id) => `/api/youtube-videos/${id}/stream`,
  upload: (id, channelId) => fetchApi(`/api/youtube-videos/${id}/upload`, {
    method: 'POST',
    body: JSON.stringify({ channel_id: channelId }),
  }),
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add youtubeVideosApi.upload() to client.js"
```

---

## Task 4: Fix Uploads format filter + add YouTube Long Videos section

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx:5, 153, 248-252`

Two changes:
1. Remove `youtube_long` from the Production Videos format filter (it queries the uploads table which has no youtube_long entries — causes layout collapse).
2. Add a `YouTubeLongSection` component below the Production Videos `Card`, querying `/api/youtube-videos?status=done`.

- [ ] **Step 1: Add youtubeVideosApi to the import on line 5**

Replace line 5:

```js
import { fetchApi, youtubeVideosApi } from '../api/client.js'
```

- [ ] **Step 2: Remove `youtube_long` from the format filter**

In `VideosTab`, replace the `{['all', 'short', 'youtube_long'].map(...)` block (lines 153–165):

```jsx
            <div className="flex items-center gap-1 bg-[#16161a] border border-[#2a2a32] rounded-lg p-1">
              {['all', 'short'].map(f => (
                <button
                  key={f}
                  onClick={() => setVideoFormat(f)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    videoFormat === f
                      ? 'bg-[#7c6af7] text-white'
                      : 'text-[#9090a8] hover:text-[#e8e8f0]'
                  }`}
                >
                  {f === 'all' ? 'All' : 'Short'}
                </button>
              ))}
            </div>
```

- [ ] **Step 3: Add YouTubeLongSection component**

Add this component definition after the closing `}` of `VideosTab` (before `CredentialsTab`), at approximately line 254:

```jsx
// ── YouTube Long Videos Sub-section ──────────────────────────────────────────
function YouTubeLongSection({ channels }) {
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedChannel, setSelectedChannel] = useState({}) // { video_id: channel_id }
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await youtubeVideosApi.list({ status: 'done' })
      setVideos(res.items || res || [])
    } catch { setVideos([]) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleUpload = async (videoId) => {
    const channelId = selectedChannel[videoId]
    if (!channelId) { showToast('Select a channel first', 'error'); return }
    try {
      await youtubeVideosApi.upload(videoId, channelId)
      showToast('Upload queued')
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const ytChannels = channels.filter(c => c.platform === 'youtube')

  return (
    <Card title="YouTube Long Videos">
      {loading ? (
        <div className="flex items-center justify-center h-40"><Spinner /></div>
      ) : videos.length === 0 ? (
        <EmptyState
          title="No rendered YouTube Long videos"
          description="Videos appear here when rendering completes (status: done)."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2a2a32] text-xs text-[#5a5a70] uppercase tracking-wider">
                <th className="pb-2 text-left font-medium">Title</th>
                <th className="pb-2 text-left font-medium">Duration</th>
                <th className="pb-2 text-left font-medium">Created</th>
                <th className="pb-2 text-left font-medium">Channel</th>
                <th className="pb-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#2a2a32]">
              {videos.map(v => (
                <tr key={v.id}>
                  <td className="py-2.5 pr-4 text-xs text-[#e8e8f0] font-medium max-w-[200px] truncate">{v.title}</td>
                  <td className="py-2.5 pr-4 text-xs text-[#9090a8] font-mono">
                    {v.target_duration_h ? `${v.target_duration_h}h` : '—'}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-[#9090a8]">
                    {new Date(v.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-2.5 pr-4">
                    <ChannelPicker
                      channels={ytChannels}
                      selected={selectedChannel[v.id] ? [selectedChannel[v.id]] : []}
                      onChange={(ids) => setSelectedChannel(prev => ({ ...prev, [v.id]: ids[0] ?? null }))}
                      onDone={(ids) => setSelectedChannel(prev => ({ ...prev, [v.id]: ids[0] ?? null }))}
                    />
                  </td>
                  <td className="py-2.5 text-right">
                    <Button
                      variant="primary"
                      className="text-xs px-2 py-1"
                      disabled={!selectedChannel[v.id]}
                      onClick={() => handleUpload(v.id)}
                    >
                      Upload
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Card>
  )
}
```

- [ ] **Step 4: Render YouTubeLongSection in the Videos tab**

In `UploadsPage`'s return, find line 669:

```jsx
      {tab === 'videos'      && <VideosTab channels={channels} />}
```

Replace with:

```jsx
      {tab === 'videos'      && (
        <div className="flex flex-col gap-6">
          <VideosTab channels={channels} />
          <YouTubeLongSection channels={channels} />
        </div>
      )}
```

- [ ] **Step 5: Manual test**

Open Uploads → Videos tab:
- Format filter should show only "All" and "Short" — no "YouTube Long" option
- "YouTube Long Videos" section appears below Production Videos
- With no `done` youtube videos, it shows the empty state message
- To test with data: `UPDATE youtube_videos SET status='done', output_path='/tmp/test.mp4' WHERE id=<id>`

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/UploadsPage.jsx
git commit -m "feat: uploads — remove youtube_long from format filter, add YouTube Long Videos section"
```

---

## Task 5: Create youtube_upload_task Celery task

**Files:**
- Create: `console/backend/tasks/youtube_upload_task.py`

The existing `upload_to_channel_task` is tightly coupled to `GeneratedScript`. YouTube Long videos use `YoutubeVideo` with a direct `output_path`. This new task handles that model.

- [ ] **Step 1: Create the task file**

Create `console/backend/tasks/youtube_upload_task.py`:

```python
"""Celery task: upload a rendered YouTube Long video to a YouTube channel."""
from __future__ import annotations

import logging

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="tasks.upload_youtube_video",
    queue="upload_q",
    max_retries=2,
    default_retry_delay=60,
)
def upload_youtube_video_task(self, youtube_video_id: int, channel_id: int):
    """Upload a rendered YouTube Long video to a YouTube channel."""
    from datetime import datetime, timezone

    from cryptography.fernet import Fernet

    from console.backend.config import settings
    from console.backend.database import SessionLocal
    from console.backend.models.channel import Channel
    from console.backend.models.credentials import PlatformCredential
    from console.backend.models.youtube_video import YoutubeVideo

    db = SessionLocal()
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            raise ValueError(f"YoutubeVideo {youtube_video_id} not found")
        if not video.output_path:
            raise ValueError(f"YoutubeVideo {youtube_video_id} has no output_path")

        channel = db.get(Channel, channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        cred = db.get(PlatformCredential, channel.credential_id)
        if not cred:
            raise ValueError(f"Credential not found for channel {channel_id}")

        fernet = Fernet(settings.FERNET_KEY.encode())

        def _decrypt(val: str | None) -> str | None:
            return fernet.decrypt(val.encode()).decode() if val else None

        credentials_dict = {
            "client_id":     cred.client_id,
            "client_secret": _decrypt(cred.client_secret),
            "access_token":  _decrypt(cred.access_token),
            "refresh_token": _decrypt(cred.refresh_token),
        }

        video_meta = {
            "title":          video.seo_title or video.title,
            "description":    video.seo_description or "",
            "tags":           video.seo_tags or [],
            "language":       channel.default_language or "en",
            "privacy_status": "unlisted",
        }

        from uploader.youtube_uploader import upload_to_youtube
        platform_id = upload_to_youtube(video.output_path, video_meta, credentials_dict)

        video.status = "published"
        video.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "YoutubeVideo %s uploaded to channel %s → platform_id=%s",
            youtube_video_id, channel_id, platform_id,
        )
        return {
            "youtube_video_id": youtube_video_id,
            "channel_id":       channel_id,
            "platform_id":      platform_id,
        }

    except Exception as exc:
        logger.exception(
            "Upload failed for YoutubeVideo %s to channel %s: %s",
            youtube_video_id, channel_id, exc,
        )
        raise self.retry(exc=exc)
    finally:
        db.close()
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "from console.backend.tasks.youtube_upload_task import upload_youtube_video_task; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add console/backend/tasks/youtube_upload_task.py
git commit -m "feat: add upload_youtube_video_task for YouTube Long video channel uploads"
```

---

## Task 6: Add POST `/{video_id}/upload` endpoint to youtube_videos router

**Files:**
- Modify: `console/backend/routers/youtube_videos.py` (append after line 193)

- [ ] **Step 1: Add UploadBody schema and upload endpoint**

Append to the end of `console/backend/routers/youtube_videos.py` (after the stream endpoint):

```python

class UploadBody(BaseModel):
    channel_id: int


@router.post("/{video_id}/upload", status_code=202)
def start_upload(
    video_id: int,
    body: UploadBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Queue a rendered YouTube Long video for upload to a channel."""
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.tasks.youtube_upload_task import upload_youtube_video_task

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Video must be in 'done' status to upload (current: '{video.status}')",
        )

    task = upload_youtube_video_task.delay(video_id, body.channel_id)
    return {"task_id": task.id, "status": "queued"}
```

- [ ] **Step 2: Verify the endpoint appears in OpenAPI**

```bash
curl -s http://localhost:8080/openapi.json | python3 -c "
import json, sys
spec = json.load(sys.stdin)
upload_paths = [p for p in spec['paths'] if 'upload' in p and 'youtube' in p]
print('Upload endpoints:', upload_paths)
"
```

Expected: `Upload endpoints: ['/api/youtube-videos/{video_id}/upload']`

- [ ] **Step 3: Smoke-test the endpoint**

```bash
# Should return 404 for a non-existent video
curl -s -X POST http://localhost:8080/api/youtube-videos/99999/upload \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin123"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')" \
  -d '{"channel_id": 1}'
```

Expected: `{"detail":"Video not found"}`

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/youtube_videos.py
git commit -m "feat: add POST /api/youtube-videos/{id}/upload endpoint"
```

---

## Task 7: Add SFX audio layers to YouTube render task

**Files:**
- Modify: `console/backend/tasks/youtube_render_task.py:88-149, 166-177`

The `_render_video()` function currently resolves one audio input (music). It needs to also resolve up to 3 SFX layers from `video.sfx_overrides` and mix all audio inputs together via FFmpeg's `filter_complex` + `amix`.

`sfx_overrides` shape stored by the frontend:
```json
{
  "foreground": {"asset_id": 12, "volume": 0.6},
  "midground":  {"asset_id": 7,  "volume": 0.3},
  "background": {"asset_id": 3,  "volume": 0.1}
}
```

Any or all keys may be absent. `asset_id` may be null.

- [ ] **Step 1: Add `_resolve_sfx_layers()` helper**

Add this function after `_resolve_audio()` (after line 177):

```python

def _resolve_sfx_layers(video, db) -> list[tuple[str, float]]:
    """Resolve SFX layer file paths from video.sfx_overrides.

    Returns a list of (file_path, volume) for each configured layer that has
    a valid asset_id and an existing file on disk. Skips missing entries.
    """
    overrides = video.sfx_overrides
    if not overrides:
        return []

    results = []
    for layer_name in ("foreground", "midground", "background"):
        layer = overrides.get(layer_name)
        if not layer:
            continue
        asset_id = layer.get("asset_id")
        volume = float(layer.get("volume", 0.5))
        if not asset_id:
            continue
        try:
            from console.backend.models.sfx_asset import SfxAsset
            asset = db.get(SfxAsset, int(asset_id))
            if asset and asset.file_path and Path(asset.file_path).is_file():
                results.append((asset.file_path, volume))
            else:
                logger.warning("SFX asset %s not found or missing file on disk", asset_id)
        except Exception as exc:
            logger.warning("Could not resolve SFX asset %s: %s", asset_id, exc)

    return results
```

- [ ] **Step 2: Replace `_render_video()` with the new dynamic audio version**

Replace the entire `_render_video()` function (lines 88–149):

```python
def _render_video(video, output_path: Path, db) -> None:
    """Compose the YouTube video using visual asset, music track, and SFX layers."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    duration_s = int((video.target_duration_h or 3.0) * 3600)
    scale = _QUALITY_SCALE.get(getattr(video, "output_quality", None) or "1080p", _DEFAULT_SCALE)
    w, h = scale.split(":")

    visual_path = _resolve_visual(video, db)
    music_path = _resolve_audio(video, db)
    sfx_layers = _resolve_sfx_layers(video, db)
    is_image = visual_path is not None and Path(visual_path).suffix.lower() in _IMAGE_EXTS

    # Collect all audio inputs: music first, then SFX layers (in foreground→background order)
    audio_inputs: list[tuple[str, float]] = []
    if music_path and Path(music_path).is_file():
        audio_inputs.append((music_path, 1.0))
    audio_inputs.extend(sfx_layers)

    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
    )

    cmd = ["ffmpeg", "-y"]

    # ── Video input (index 0) ─────────────────────────────────────────────────
    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    # ── Audio inputs (indices 1+) ─────────────────────────────────────────────
    if audio_inputs:
        for (path, _) in audio_inputs:
            cmd += ["-stream_loop", "-1", "-i", path]

        # Build filter_complex: per-input volume scaling + optional amix + video vf
        # Video filter must live in filter_complex when -map is used explicitly.
        parts: list[str] = []
        audio_labels: list[str] = []
        for i, (_, vol) in enumerate(audio_inputs):
            parts.append(f"[{i + 1}:a]volume={vol}[a{i}]")
            audio_labels.append(f"[a{i}]")

        parts.append(f"[0:v]{vf}[vout]")

        if len(audio_inputs) == 1:
            filter_complex = ";".join(parts)
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[a0]",
            ]
        else:
            mix_in = "".join(audio_labels)
            parts.append(
                f"{mix_in}amix=inputs={len(audio_inputs)}:duration=first:normalize=0[aout]"
            )
            cmd += [
                "-filter_complex", ";".join(parts),
                "-map", "[vout]",
                "-map", "[aout]",
            ]
    else:
        # No audio at all — silence fallback, use simple -vf (no explicit -map needed)
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-vf", vf]

    # ── Duration ──────────────────────────────────────────────────────────────
    cmd += ["-t", str(duration_s)]

    # ── Codec settings ────────────────────────────────────────────────────────
    if is_image:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "18"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]

    cmd += [
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logger.info("ffmpeg render cmd: %s", " ".join(cmd))

    timeout = max(duration_s * 4, 600)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s")

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(result.stderr or '')[-800:]}")
```

- [ ] **Step 3: Verify the module imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "from console.backend.tasks.youtube_render_task import render_youtube_video_task, _resolve_sfx_layers; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Smoke-test the FFmpeg command shape**

Run this script to print the command that would be generated for a video with music + 2 SFX layers:

```python
# Run as: python3 -c "$(cat << 'EOF'
import sys
sys.path.insert(0, '/Volumes/SSD/Workspace/ai-media-automation')
from pathlib import Path
from console.backend.tasks.youtube_render_task import _render_video

class FakeVideo:
    target_duration_h = 0.001  # ~3 seconds for quick test
    output_quality = "1080p"
    visual_asset_id = None
    music_track_id = None
    sfx_overrides = {
        "foreground": {"asset_id": None, "volume": 0.6},
    }

import unittest.mock as m
with m.patch('console.backend.tasks.youtube_render_task._resolve_visual', return_value=None), \
     m.patch('console.backend.tasks.youtube_render_task._resolve_audio', return_value=None), \
     m.patch('console.backend.tasks.youtube_render_task._resolve_sfx_layers', return_value=[('/tmp/sfx.wav', 0.6)]), \
     m.patch('shutil.which', return_value='/usr/bin/ffmpeg'), \
     m.patch('subprocess.run') as mock_run:
    mock_run.return_value = m.Mock(returncode=0, stderr='')
    _render_video(FakeVideo(), Path('/tmp/out.mp4'), None)
    print('CMD:', ' '.join(mock_run.call_args[0][0]))
# EOF
# )"
```

Expected: command includes `-filter_complex`, `volume=0.6`, `[vout]`, `[a0]`.

- [ ] **Step 5: Commit**

```bash
git add console/backend/tasks/youtube_render_task.py
git commit -m "feat: youtube render — dynamic audio mix with music + SFX layers via ffmpeg filter_complex"
```

---

## Task 8: Redesign SFX Library page to 3-column grid

**Files:**
- Modify: `console/frontend/src/pages/SFXPage.jsx:236-318`

Replace the `<div className="flex flex-col gap-2">` list (lines 265–312) with a 3-column grid of compact cards. The `ImportModal`, `handlePlay`, `handleDelete`, state, and filter bar remain unchanged.

- [ ] **Step 1: Replace the list section in SFXPage's return**

Replace lines 265–312 (the `sfxList.map(...)` render inside the `flex flex-col gap-2` div):

```jsx
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {sfxList.map(sfx => (
            <div
              key={sfx.id}
              className="relative bg-[#1c1c22] border border-[#2a2a32] rounded-xl p-3 flex flex-col gap-2 group"
            >
              {/* Delete — visible on hover */}
              <button
                onClick={() => handleDelete(sfx)}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-[#5a5a70] hover:text-[#f87171] text-xs leading-none"
                title="Delete"
              >
                ✕
              </button>

              {/* Top row: play button + sound type badge */}
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={() => handlePlay(sfx)}
                  className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs transition-colors ${
                    playing === sfx.id
                      ? 'bg-[#f87171] text-white'
                      : 'bg-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                  }`}
                >
                  {playing === sfx.id ? '■' : '▶'}
                </button>
                <span className="text-[9px] font-mono text-[#5a5a70] truncate max-w-[80px] text-right">
                  {sfx.sound_type || '—'}
                </span>
              </div>

              {/* Title */}
              <div
                className="text-xs font-medium text-[#e8e8f0] leading-snug"
                style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
              >
                {sfx.title}
              </div>

              {/* Duration bar + label */}
              <div className="flex items-center gap-2 mt-auto">
                {sfx.duration_s ? (
                  <>
                    <div className="flex-1 h-0.5 rounded-full bg-[#2a2a32]">
                      <div
                        className="h-0.5 rounded-full bg-[#7c6af7]"
                        style={{ width: `${Math.min(100, (sfx.duration_s / 60) * 100)}%` }}
                      />
                    </div>
                    <span className="text-[9px] font-mono text-[#5a5a70] flex-shrink-0">
                      {sfx.duration_s.toFixed(0)}s
                    </span>
                  </>
                ) : (
                  <span className="text-[9px] font-mono text-[#5a5a70]">—</span>
                )}
              </div>
            </div>
          ))}
        </div>
```

- [ ] **Step 2: Manual test**

Open the SFX Library page. Verify:
- Items render as a grid (3 columns at typical screen width, 2 on narrow, 4 on wide)
- Each card shows: play button, sound type, title (truncated at 2 lines), duration bar, duration label
- Clicking play icon plays audio, icon changes to stop (■), clicking again stops
- Hovering over a card reveals the ✕ delete button in the top-right corner
- Delete works (confirms, then removes item from grid)

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/SFXPage.jsx
git commit -m "feat: sfx library — redesign to 3-column compact grid layout"
```

---

## Task 9: Fix Make Short — parent_youtube_video_id column + modal data fix

**Files:**
- Create: `console/backend/alembic/versions/009_youtube_video_parent.py`
- Modify: `console/backend/models/youtube_video.py`
- Modify: `console/backend/routers/youtube_videos.py:19-30`
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx:561-579`

**What's broken:**
- `MakeShortModal` packs `parent_youtube_video_id` inside `sfx_overrides` JSON (line 573) instead of a dedicated DB column
- `YoutubeVideo` model has no `parent_youtube_video_id` field — the parent link is stored but not queryable
- `sfx_overrides` receives `{ parent_youtube_video_id, cta_text, cta_position }` which should be `{ cta: { text, position } }` so SFX layer keys remain unambiguous
- The `+ Make Short` button visibility is fixed by Task 1 (status `'done'`)

- [ ] **Step 1: Create migration 009**

Create `console/backend/alembic/versions/009_youtube_video_parent.py`:

```python
"""youtube_videos — add parent_youtube_video_id self-FK

Revision ID: 009
Revises: 008
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "parent_youtube_video_id",
            sa.Integer,
            sa.ForeignKey("youtube_videos.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("youtube_videos", "parent_youtube_video_id")
```

- [ ] **Step 2: Run the migration**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic upgrade head
```

Expected: `Running upgrade 008 -> 009, youtube_videos — add parent_youtube_video_id self-FK`

- [ ] **Step 3: Add `parent_youtube_video_id` to the YoutubeVideo model**

In `console/backend/models/youtube_video.py`, add after line 21 (`visual_asset_id`):

```python
    parent_youtube_video_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("youtube_videos.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 4: Add `parent_youtube_video_id` to `YoutubeVideoCreate` schema**

In `console/backend/routers/youtube_videos.py`, replace the `YoutubeVideoCreate` class (lines 19–30):

```python
class YoutubeVideoCreate(BaseModel):
    title: str
    template_id: int
    theme: str | None = None
    music_track_id: int | None = None
    sfx_overrides: dict | None = None
    visual_asset_id: int | None = None
    target_duration_h: float | None = None
    output_quality: str = "1080p"
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] | None = None
    parent_youtube_video_id: int | None = None
```

- [ ] **Step 5: Persist `parent_youtube_video_id` in YoutubeVideoService**

In `console/backend/services/youtube_video_service.py`, replace the `YoutubeVideo(...)` constructor block (lines 125–138):

```python
        video = YoutubeVideo(
            title=data["title"],
            template_id=template_id,
            theme=data.get("theme"),
            music_track_id=data.get("music_track_id"),
            visual_asset_id=data.get("visual_asset_id"),
            sfx_overrides=data.get("sfx_overrides"),
            target_duration_h=data.get("target_duration_h"),
            output_quality=data.get("output_quality", "1080p"),
            seo_title=data.get("seo_title"),
            seo_description=data.get("seo_description"),
            seo_tags=data.get("seo_tags"),
            parent_youtube_video_id=data.get("parent_youtube_video_id"),
            status="draft",
        )
```

Also update `_video_to_dict` (lines 44–63) to expose the field in API responses — add after `"sfx_overrides"`:

```python
        "parent_youtube_video_id": v.parent_youtube_video_id,
```

- [ ] **Step 6: Fix MakeShortModal to pass parent_youtube_video_id as a top-level field**

In `console/frontend/src/pages/YouTubeVideosPage.jsx`, replace the `handleSubmit` function inside `MakeShortModal` (lines 561–579):

```js
  const handleSubmit = async () => {
    if (loading) return
    if (!shortTemplate) { showToast('No short template found', 'error'); return }
    setLoading(true)
    try {
      await youtubeVideosApi.create({
        title: `${video.title} — Short`,
        template_id: shortTemplate.id,
        theme: video.theme,
        target_duration_h: 58 / 3600,
        music_track_id: form.sameMusic ? video.music_track_id : null,
        visual_asset_id: form.sameVisual ? video.visual_asset_id : null,
        parent_youtube_video_id: video.id,
        sfx_overrides: { cta: { text: form.ctaText, position: form.ctaPosition } },
      })
      onCreated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }
```

- [ ] **Step 7: Verify the module imports cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "
from console.backend.models.youtube_video import YoutubeVideo
print('parent_youtube_video_id field:', hasattr(YoutubeVideo, 'parent_youtube_video_id'))
"
```

Expected: `parent_youtube_video_id field: True`

- [ ] **Step 8: Manual test**

1. Set a YouTube video to `done` status in the DB:
   ```bash
   psql "postgresql://admin:123456@localhost:5432/ai_media" \
     -c "UPDATE youtube_videos SET status='done', output_path='/tmp/test.mp4' WHERE id=<id>"
   ```
2. Open YouTube Videos page — the video card should show `▶ Preview` and `+ Make Short` buttons (Task 1 fix required)
3. Click `+ Make Short` — modal opens showing parent video name, Music/Visual toggles, CTA field, CTA position
4. Fill in CTA text, click "Queue Render →"
5. Verify in the DB that a new `youtube_videos` row was created with `parent_youtube_video_id` set:
   ```bash
   psql "postgresql://admin:123456@localhost:5432/ai_media" \
     -c "SELECT id, title, status, parent_youtube_video_id, sfx_overrides FROM youtube_videos ORDER BY id DESC LIMIT 3"
   ```
   Expected: newest row has `parent_youtube_video_id = <parent_id>` and `sfx_overrides = {"cta": {"text": "...", "position": "..."}}`

- [ ] **Step 9: Commit**

```bash
git add \
  console/backend/alembic/versions/009_youtube_video_parent.py \
  console/backend/models/youtube_video.py \
  console/backend/routers/youtube_videos.py \
  console/backend/services/youtube_video_service.py \
  console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "fix: make short — add parent_youtube_video_id column, fix modal data shape"
```

---

## Self-Review — Spec Coverage Check

| Spec requirement | Task |
|---|---|
| Fix Preview button (wrong status check) | Task 1 |
| Fix STATUS_COLORS to match real statuses | Task 1 |
| Fix visual asset list empty (per_page) | Task 2 |
| Add youtubeVideosApi.upload() to client.js | Task 3 |
| Remove youtube_long from format filter | Task 4 |
| Add YouTube Long Videos section in Uploads | Task 4 |
| New Celery task for YouTube Long uploads | Task 5 |
| POST /{video_id}/upload backend endpoint | Task 6 |
| _resolve_sfx_layers() helper | Task 7 |
| Dynamic audio mix in _render_video() | Task 7 |
| SFX Library grid redesign | Task 8 |
| Migration 009 — parent_youtube_video_id column | Task 9 |
| YoutubeVideo model + schema update | Task 9 |
| MakeShortModal data shape fix | Task 9 |
