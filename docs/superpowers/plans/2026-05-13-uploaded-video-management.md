# Uploaded Video Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface three post-upload actions on the `UploadsPage` `YouTubeLongSection` row — open the live YouTube URL, fetch live stats from YouTube on demand, and create a Short with a "Watch the full video → URL" prefix in the description.

**Architecture:** Each `YoutubeVideoUpload` chip on the page gets a small inline action strip (`↗ Watch · ↻ Stats · + Make Short`) when its status is `done`. F1 + F3 are pure frontend. F2 adds a single live-fetch endpoint backed by a thin Python service that calls YouTube Data API v3 (statistics) and YouTube Analytics API v2 (estimatedMinutesWatched), both fail-soft per field. No DB persistence anywhere.

**Tech Stack:** React 18 + Vite · FastAPI · `googleapiclient` (already in deps) · pytest

**Spec:** `docs/superpowers/specs/2026-05-13-uploaded-video-management-design.md`

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `console/frontend/src/api/client.js` | Add `youtubeWatchUrl` helper and `fetchUploadStats` API method. | T1, T6 |
| `console/frontend/src/pages/UploadsPage.jsx` | Add per-chip action strip in `YouTubeLongSection`: ↗ Watch, ↻ Stats, + Make Short. State for fetched-stats. | T1, T3, T6 |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | `MakeShortModal` accepts new `originalUploadUrl` prop and prefixes `seo_description`. | T2 |
| `console/backend/services/credential_service.py` | Add `yt-analytics.readonly` to `YOUTUBE_SCOPES`. | T4 |
| `console/backend/services/upload_stats_service.py` (NEW) | `fetch_stats(upload_id, db)` — Data API + Analytics API, fail-soft per field. | T5 |
| `console/backend/routers/youtube_videos.py` | New `GET /uploads/{upload_id}/stats` endpoint. | T5 |
| `tests/test_upload_stats_service.py` (NEW) | Service unit tests with mocked googleapiclient. | T5 |
| `tests/test_youtube_videos_uploads_stats.py` (NEW) | Endpoint integration test via FastAPI TestClient. | T5 |

No DB migration. No Celery task.

---

# F1 — Open YouTube link in a new tab

### Task 1: Watch button on each done upload chip

**Files:**
- Modify: `console/frontend/src/api/client.js` (export helper)
- Modify: `console/frontend/src/pages/UploadsPage.jsx` (render button)

- [ ] **Step 1: Read the current chip render**

```bash
sed -n '405,440p' /Volumes/SSD/Workspace/ai-media-automation/console/frontend/src/pages/UploadsPage.jsx
```

Confirm each upload chip is rendered around line 410-435 inside `uploads.map(u => …)`. Each `u` carries `id`, `channel_id`, `channel_name`, `status`, `error`, and (post-upload) `platform_id`.

- [ ] **Step 2: Add `youtubeWatchUrl` helper to `client.js`**

Find a good location in `console/frontend/src/api/client.js` (after the existing exports, before `youtubeVideosApi`, OR alongside any url-helpers). Add:

```js
export const youtubeWatchUrl = (platformId) =>
  `https://www.youtube.com/watch?v=${platformId}`
```

- [ ] **Step 3: Import the helper in `UploadsPage.jsx`**

Update the existing import at line 5:

```jsx
import { fetchApi, youtubeVideosApi, youtubeWatchUrl } from '../api/client.js'
```

- [ ] **Step 4: Render the ↗ button on each done chip**

Inside the chip span (around lines 411-435 of `UploadsPage.jsx`), after the `channel_name` and the existing `failed → ↺` retry button, add a new button visible only when `u.status === 'done' && u.platform_id`:

```jsx
{u.status === 'done' && u.platform_id && (
  <button
    title="Watch on YouTube"
    onClick={(e) => { e.stopPropagation(); window.open(youtubeWatchUrl(u.platform_id), '_blank', 'noopener,noreferrer') }}
    className="ml-0.5 text-[#34d399] hover:text-[#6ee7b7] transition-colors leading-none"
  >
    ↗
  </button>
)}
```

(The styling matches the existing retry `↺` button: small inline glyph, `ml-0.5`, hover color shift.)

- [ ] **Step 5: Frontend build sanity check**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -5
```

Expected: `✓ built in …`.

- [ ] **Step 6: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/frontend/src/api/client.js console/frontend/src/pages/UploadsPage.jsx
git commit -m "feat(uploads): ↗ Watch on YouTube button on done upload chips

Adds a youtubeWatchUrl(platformId) helper and a small ↗ button on each
done upload chip in YouTubeLongSection. Clicking opens the live video
URL in a new tab using the platform_id already persisted on
YoutubeVideoUpload after a successful insert."
```

---

# F3 — Make Short with link to original in description

### Task 2: `MakeShortModal` accepts `originalUploadUrl` and prefixes seo_description

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (MakeShortModal component around lines 1844-1936)

The plan's spec sets the description prefix format:
```
Watch the full video → https://www.youtube.com/watch?v=<id>

<parent.seo_description or "">
```

- [ ] **Step 1: Read the current `handleSubmit` payload**

```bash
sed -n '1844,1880p' /Volumes/SSD/Workspace/ai-media-automation/console/frontend/src/pages/YouTubeVideosPage.jsx
```

Confirm the current shape passes `seo_description: video.seo_description ?? null` (added in commit `7b95a97`).

- [ ] **Step 2: Update the `MakeShortModal` signature to accept `originalUploadUrl`**

Find the `function MakeShortModal({ video, shortTemplates, onClose, onCreated })` declaration (line 1844) and change to:

```jsx
function MakeShortModal({ video, shortTemplates, onClose, onCreated, originalUploadUrl = null }) {
```

- [ ] **Step 3: Update the payload to prefix `seo_description` when `originalUploadUrl` is set**

Find the `await youtubeVideosApi.create({ ... })` block (around lines 1861-1877). Replace the existing `seo_description: video.seo_description ?? null,` line with the computed prefix:

```jsx
        seo_description: (() => {
          const base = video.seo_description ?? ''
          return originalUploadUrl
            ? `Watch the full video → ${originalUploadUrl}\n\n${base}`.trimEnd()
            : (base || null)
        })(),
```

(Wrapped in IIFE to keep the object literal readable. The `trimEnd()` drops trailing whitespace when `base` is empty. The `|| null` preserves the existing "send null when there's nothing" contract when no link is provided.)

- [ ] **Step 4: Frontend build sanity check**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -5
```

Expected: clean build.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(short): MakeShortModal supports originalUploadUrl prop

When originalUploadUrl is provided, the new Short's seo_description is
prefixed with 'Watch the full video → URL' and a blank line before the
parent's description. Used by the next commit to wire the upload row's
Make-Short button to the live YouTube URL of the source video."
```

### Task 3: + Make Short button on done upload chip

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx`

Each `YouTubeLongSection` row already has the parent `video` in scope. The new short reuses the same MakeShortModal that lives in `YouTubeVideosPage.jsx`. To avoid duplicating the modal source, we import it.

- [ ] **Step 1: Export `MakeShortModal` from `YouTubeVideosPage.jsx`**

`MakeShortModal` is currently declared as `function MakeShortModal(...)` (line 1844) inside the module but not exported. The component is referenced only within the same file today. To use it from `UploadsPage`, export it.

Add at line 1843 (the line immediately before `function MakeShortModal(...)`):

```jsx
export
```

So the line becomes `export function MakeShortModal({ video, shortTemplates, onClose, onCreated, originalUploadUrl = null }) {`.

Also confirm there's no name collision: search the file for any other `MakeShortModal` symbol; there should be only the one declaration.

- [ ] **Step 2: Add upload-row state to `UploadsPage` `YouTubeLongSection`**

Read the existing state at the top of `function YouTubeLongSection({ channels })` (line 267-340). Find where other `useState` calls live (`videos`, `selectedChannel`, `confirmDelete`, `previewVideo`, `toast`).

Add a new state for "which upload triggered the modal":

```jsx
const [makeShortFromUpload, setMakeShortFromUpload] = useState(null) // { video, originalUploadUrl } | null
```

- [ ] **Step 3: Import `MakeShortModal` and `Button` (if not already imported)**

At the top of `UploadsPage.jsx` (around line 5), add the import. The file is a `.jsx` so it uses the same module-resolution path:

```jsx
import { MakeShortModal } from './YouTubeVideosPage.jsx'
```

Verify `Button` is already imported from the components index — if not, add it. Same with `Toast`, `Modal`, etc. (these are likely already imported.)

- [ ] **Step 4: Add the "+ Make Short" button on each done chip**

In the same chip render block from Task 1 (after the `↗` button), add:

```jsx
{u.status === 'done' && u.platform_id && (
  <button
    title="Create a Short from this video, with a link back to it in the description"
    onClick={(e) => {
      e.stopPropagation()
      setMakeShortFromUpload({ video: v, originalUploadUrl: youtubeWatchUrl(u.platform_id) })
    }}
    className="ml-0.5 text-[#7c6af7] hover:text-[#a594f9] transition-colors leading-none text-[10px]"
  >
    +Short
  </button>
)}
```

(Distinct color from the watch button so the row stays readable.)

- [ ] **Step 5: Render `MakeShortModal` when triggered**

`MakeShortModal` requires `shortTemplates` — a list of template rows where `output_format === 'short'`. The page must load templates first. Check if there's an existing fetch; if not, add one.

```bash
grep -n "templates\|video_templates\|/api/video-templates" /Volumes/SSD/Workspace/ai-media-automation/console/frontend/src/pages/UploadsPage.jsx | head -10
```

Likely no existing template fetch. Add to `YouTubeLongSection`:

```jsx
const [shortTemplates, setShortTemplates] = useState([])

useEffect(() => {
  fetchApi('/api/video-templates?output_format=short')
    .then(res => setShortTemplates(res.items || res || []))
    .catch(() => {})  // page still works without Make-Short
}, [])
```

(Adapt the response unwrapping to whatever the endpoint returns — `res.items` if paginated, plain `res` if a flat list. `grep -n "video-templates" console/backend/routers/` to confirm the shape if uncertain.)

Then, just before the closing `</Card>` of `YouTubeLongSection` (around line 508), render the modal:

```jsx
{makeShortFromUpload && shortTemplates.length > 0 && (
  <MakeShortModal
    video={makeShortFromUpload.video}
    shortTemplates={shortTemplates}
    originalUploadUrl={makeShortFromUpload.originalUploadUrl}
    onClose={() => setMakeShortFromUpload(null)}
    onCreated={() => {
      setMakeShortFromUpload(null)
      showToast('Short queued', 'success')
    }}
  />
)}
```

If `shortTemplates` is empty (no short template configured), the button still shows but the modal's existing guard (`if (!shortTemplate) { showToast('No short template found', 'error') }`) handles that path on Submit. To avoid showing a non-functional button at all, you can gate:

```jsx
{u.status === 'done' && u.platform_id && shortTemplates.length > 0 && (
  <button ...>+Short</button>
)}
```

Use the gated form.

- [ ] **Step 6: Build sanity check**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 7: Manual smoke test** (no automated test surface for the frontend)

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
./console/start.sh  # or confirm uvicorn :8080 is up
# in another terminal:
cd console/frontend && npm run dev
```

In the browser, open `/uploads`, find a done upload, click `+Short` on its chip. Verify:
1. Modal opens preloaded with the parent video's title and theme.
2. Submit → renders a new short.
3. After it queues, open the new short's record on `/youtube` and confirm its `seo_description` starts with `Watch the full video → https://www.youtube.com/watch?v=<id>` followed by the parent's original description.

- [ ] **Step 8: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/frontend/src/pages/UploadsPage.jsx console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(uploads): + Make Short button per done upload chip

Exports MakeShortModal from YouTubeVideosPage, surfaces it from each
done upload chip on the Uploads page. The new short's seo_description
is prefixed with a 'Watch the full video → URL' line that links back
to the original upload's YouTube watch URL."
```

---

# F2 — Live YouTube stats fetch

### Task 4: Add `yt-analytics.readonly` to OAuth scopes

**Files:**
- Modify: `console/backend/services/credential_service.py:19-22`

- [ ] **Step 1: Read the current scope block**

```bash
sed -n '15,30p' /Volumes/SSD/Workspace/ai-media-automation/console/backend/services/credential_service.py
```

You should see `YOUTUBE_SCOPES = [..., "https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly", ...]` (or similar).

- [ ] **Step 2: Add the analytics scope**

Edit the scope list to add (placement: alphabetical or at the end is fine — match surrounding style):

```python
"https://www.googleapis.com/auth/yt-analytics.readonly",
```

- [ ] **Step 3: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/backend/services/credential_service.py
git commit -m "feat(credentials): request yt-analytics.readonly scope for stats

New scope unlocks YouTube Analytics API for watch_time_minutes lookups
in upload_stats_service. Existing tokens lack this scope; the stats
service treats Analytics calls as fail-soft and surfaces a re-auth
link inline on the affected upload row."
```

### Task 5: `upload_stats_service.fetch_stats` + endpoint

**Files:**
- Create: `console/backend/services/upload_stats_service.py`
- Modify: `console/backend/routers/youtube_videos.py` (new endpoint)
- Create: `tests/test_upload_stats_service.py`
- Create: `tests/test_youtube_videos_uploads_stats.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_upload_stats_service.py`:

```python
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from console.backend.models.channel import Channel
from console.backend.models.credentials import PlatformCredential
from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.models.youtube_video_upload import YoutubeVideoUpload


def _seed_upload(db, *, status="done", platform_id="vid123",
                 uploaded_at=None) -> YoutubeVideoUpload:
    slug = f"stats-{uuid.uuid4().hex[:6]}"
    template = VideoTemplate(slug=slug, label="x", output_format="landscape_long")
    db.add(template); db.flush()

    video = YoutubeVideo(title="x", template_id=template.id)
    db.add(video); db.flush()

    channel = Channel(
        platform="youtube",
        name="Test Channel",
        platform_channel_id="UC_test",
    )
    db.add(channel); db.flush()

    upload = YoutubeVideoUpload(
        youtube_video_id=video.id,
        channel_id=channel.id,
        platform_id=platform_id,
        status=status,
        uploaded_at=uploaded_at or datetime.now(timezone.utc) - timedelta(days=3),
    )
    db.add(upload); db.flush()
    return upload


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_happy_path_returns_all_metrics(mock_build, mock_creds, db):
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {
            "viewCount": "1234",
            "likeCount": "42",
            "commentCount": "5",
        }}],
    }
    analytics = MagicMock()
    analytics.reports().query().execute.return_value = {
        "rows": [[789]],  # estimatedMinutesWatched
        "columnHeaders": [{"name": "estimatedMinutesWatched"}],
    }

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)

    assert result["view_count"] == 1234
    assert result["like_count"] == 42
    assert result["comment_count"] == 5
    assert result["watch_time_minutes"] == 789
    assert result["watch_time_available"] is True
    assert isinstance(result["fetched_at"], datetime)


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_analytics_fails_soft(mock_build, mock_creds, db):
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {"viewCount": "10"}}],
    }
    analytics = MagicMock()
    analytics.reports().query().execute.side_effect = RuntimeError("scope missing")

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)

    assert result["view_count"] == 10
    assert result["like_count"] is None
    assert result["comment_count"] is None
    assert result["watch_time_minutes"] is None
    assert result["watch_time_available"] is False


def test_fetch_stats_rejects_non_done_upload(db):
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db, status="queued", platform_id=None)
    with pytest.raises(ValueError, match="not ready"):
        fetch_stats(upload.id, db)


def test_fetch_stats_rejects_missing_upload(db):
    from console.backend.services.upload_stats_service import fetch_stats
    with pytest.raises(ValueError, match="not found"):
        fetch_stats(999999, db)


@patch("console.backend.services.upload_stats_service._get_credentials_for_channel")
@patch("console.backend.services.upload_stats_service.build")
def test_fetch_stats_handles_missing_data_api_fields(mock_build, mock_creds, db):
    """Data API may return only some statistics fields (e.g. comments disabled)."""
    from console.backend.services.upload_stats_service import fetch_stats

    upload = _seed_upload(db)
    mock_creds.return_value = MagicMock(expired=False)

    data_api = MagicMock()
    data_api.videos().list().execute.return_value = {
        "items": [{"statistics": {"viewCount": "100"}}],  # no like/comment
    }
    analytics = MagicMock()
    analytics.reports().query().execute.return_value = {"rows": [[50]]}

    def _build_side_effect(name, *args, **kwargs):
        return data_api if name == "youtube" else analytics
    mock_build.side_effect = _build_side_effect

    result = fetch_stats(upload.id, db)
    assert result["view_count"] == 100
    assert result["like_count"] is None
    assert result["comment_count"] is None
    assert result["watch_time_minutes"] == 50
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
pytest tests/test_upload_stats_service.py -v
```

Expected: ImportError or ModuleNotFoundError — the service doesn't exist yet.

- [ ] **Step 3: Create `console/backend/services/upload_stats_service.py`**

```python
"""Live YouTube stats fetcher for uploaded videos. No DB persistence.

Calls YouTube Data API v3 statistics for views/likes/comments and the
YouTube Analytics API v2 for estimatedMinutesWatched. Each API call is
independent; a failure on one does not block the other.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _get_credentials_for_channel(channel_id: int, db: Session) -> Credentials:
    """Build google Credentials from the channel's stored OAuth tokens.

    Mirrors the pattern in uploader/youtube_uploader.py; reused so callers can
    monkeypatch _get_credentials_for_channel in tests.
    """
    from console.backend.services.credential_service import CredentialService
    svc = CredentialService(db)
    token_data = svc.get_decrypted_tokens_for_channel(channel_id, platform="youtube")
    return Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        token_uri="https://oauth2.googleapis.com/token",
    )


def _fetch_data_api_stats(creds: Credentials, platform_id: str) -> dict:
    """Call YouTube Data API v3 videos().list and parse the statistics block."""
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    response = youtube.videos().list(id=platform_id, part="statistics").execute()
    items = response.get("items") or []
    if not items:
        return {"view_count": None, "like_count": None, "comment_count": None}
    stats = items[0].get("statistics") or {}

    def _as_int(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "view_count":    _as_int(stats.get("viewCount")),
        "like_count":    _as_int(stats.get("likeCount")),
        "comment_count": _as_int(stats.get("commentCount")),
    }


def _fetch_analytics_watch_time(creds: Credentials, platform_id: str, start_date) -> int | None:
    """Call YouTube Analytics API v2 for estimatedMinutesWatched. None on error.

    start_date should be the upload date (or any date ≤ today). YouTube Analytics
    only accepts string dates in YYYY-MM-DD format.
    """
    analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    end_date = datetime.now(timezone.utc).date().isoformat()
    response = analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
        endDate=end_date,
        metrics="estimatedMinutesWatched",
        filters=f"video=={platform_id}",
    ).execute()
    rows = response.get("rows") or []
    if not rows or not rows[0]:
        return 0  # video has no watch time yet (or no rows returned)
    try:
        return int(rows[0][0])
    except (TypeError, ValueError):
        return None


def fetch_stats(upload_id: int, db: Session) -> dict:
    """Fetch live YouTube stats for one upload. Synchronous; no DB writes.

    Returns:
        {
            "view_count":           int | None,
            "like_count":           int | None,
            "comment_count":        int | None,
            "watch_time_minutes":   int | None,
            "fetched_at":           datetime,
            "watch_time_available": bool,
        }

    Raises:
        ValueError("YoutubeVideoUpload {id} not found") when upload doesn't exist.
        ValueError("upload not ready for stats") when status != 'done' or platform_id is missing.
    """
    from console.backend.models.youtube_video_upload import YoutubeVideoUpload

    upload = db.get(YoutubeVideoUpload, upload_id)
    if upload is None:
        raise ValueError(f"YoutubeVideoUpload {upload_id} not found")
    if upload.status != "done" or not upload.platform_id:
        raise ValueError("upload not ready for stats")

    creds = _get_credentials_for_channel(upload.channel_id, db)

    data_stats = _fetch_data_api_stats(creds, upload.platform_id)

    watch_time_minutes: int | None = None
    watch_time_available = False
    try:
        start_date = (upload.uploaded_at or upload.created_at).date()
        watch_time_minutes = _fetch_analytics_watch_time(creds, upload.platform_id, start_date)
        watch_time_available = watch_time_minutes is not None or watch_time_minutes == 0
        # treat 0 (real value) and any int as "available"
        watch_time_available = True
    except Exception as exc:  # noqa: BLE001 — analytics fail-soft by design
        logger.warning(
            "YouTube Analytics fetch failed for upload %s (platform_id=%s): %s",
            upload_id, upload.platform_id, exc,
        )

    return {
        "view_count":           data_stats["view_count"],
        "like_count":           data_stats["like_count"],
        "comment_count":        data_stats["comment_count"],
        "watch_time_minutes":   watch_time_minutes,
        "fetched_at":           datetime.now(timezone.utc),
        "watch_time_available": watch_time_available,
    }
```

Note: if `CredentialService` exposes a different method name than `get_decrypted_tokens_for_channel`, adjust to whatever the existing service uses (it's a single-line change in `_get_credentials_for_channel`). The uploader pattern at `uploader/youtube_uploader.py` reads tokens via the same service — read it for the right method name:

```bash
grep -n "get_decrypted\|decrypt\|for_channel\|tokens" /Volumes/SSD/Workspace/ai-media-automation/console/backend/services/credential_service.py
```

- [ ] **Step 4: Run service tests, verify they pass**

```bash
pytest tests/test_upload_stats_service.py -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Write failing endpoint test**

Create `tests/test_youtube_videos_uploads_stats.py`:

```python
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest


def _seed_upload(db, *, platform_id="vid_endpoint", status="done"):
    from console.backend.models.channel import Channel
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.youtube_video_upload import YoutubeVideoUpload

    template = VideoTemplate(
        slug=f"stats-ep-{uuid.uuid4().hex[:6]}",
        label="x",
        output_format="landscape_long",
    )
    db.add(template); db.flush()
    video = YoutubeVideo(title="x", template_id=template.id)
    db.add(video); db.flush()
    channel = Channel(platform="youtube", name="Test", platform_channel_id="UC_x")
    db.add(channel); db.flush()
    upload = YoutubeVideoUpload(
        youtube_video_id=video.id,
        channel_id=channel.id,
        platform_id=platform_id,
        status=status,
        uploaded_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(upload); db.flush()
    return upload


def test_get_upload_stats_returns_json(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    upload = _seed_upload(db)
    db.commit()

    def _get_db_override():
        yield db
    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()

    fake_result = {
        "view_count": 100, "like_count": 5, "comment_count": 1,
        "watch_time_minutes": 25, "fetched_at": datetime.now(timezone.utc),
        "watch_time_available": True,
    }
    try:
        with patch("console.backend.routers.youtube_videos.fetch_upload_stats",
                   return_value=fake_result) as mock_fn:
            with TestClient(app) as client:
                resp = client.get(f"/api/youtube-videos/uploads/{upload.id}/stats")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["view_count"] == 100
        assert body["watch_time_minutes"] == 25
        assert body["watch_time_available"] is True
        assert "fetched_at" in body
        mock_fn.assert_called_once_with(upload.id, db)
    finally:
        app.dependency_overrides.clear()


def test_get_upload_stats_404_when_missing(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    def _get_db_override():
        yield db
    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with patch(
            "console.backend.routers.youtube_videos.fetch_upload_stats",
            side_effect=ValueError("YoutubeVideoUpload 999 not found"),
        ):
            with TestClient(app) as client:
                resp = client.get("/api/youtube-videos/uploads/999/stats")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_upload_stats_400_when_not_ready(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    upload = _seed_upload(db, status="queued", platform_id=None)
    db.commit()

    def _get_db_override():
        yield db
    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with patch(
            "console.backend.routers.youtube_videos.fetch_upload_stats",
            side_effect=ValueError("upload not ready for stats"),
        ):
            with TestClient(app) as client:
                resp = client.get(f"/api/youtube-videos/uploads/{upload.id}/stats")
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 6: Run, verify FAIL**

```bash
pytest tests/test_youtube_videos_uploads_stats.py -v
```

Expected: FAIL — endpoint doesn't exist yet (404 with no route).

- [ ] **Step 7: Add endpoint to `console/backend/routers/youtube_videos.py`**

Find a good location (near the other upload-related endpoints — e.g., near `recreate` or near `upload` endpoints). At the top of the file with the other imports, add:

```python
from console.backend.services.upload_stats_service import fetch_stats as fetch_upload_stats
```

(Renamed alias keeps the router's wrapper distinct from the service function name.)

Then add the endpoint:

```python
@router.get("/uploads/{upload_id}/stats")
def get_upload_stats(
    upload_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    """Live YouTube stats fetch for one upload. No DB write."""
    try:
        return fetch_upload_stats(upload_id, db)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
```

- [ ] **Step 8: Run endpoint tests, verify they pass**

```bash
pytest tests/test_youtube_videos_uploads_stats.py -v
```

Expected: all 3 PASS.

- [ ] **Step 9: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/backend/services/upload_stats_service.py console/backend/routers/youtube_videos.py tests/test_upload_stats_service.py tests/test_youtube_videos_uploads_stats.py
git commit -m "feat(uploads): GET /uploads/{id}/stats returns live YouTube metrics

upload_stats_service.fetch_stats hits YouTube Data API v3 for views/
likes/comments and YouTube Analytics API v2 for estimatedMinutesWatched.
Each API is independent — Analytics failure (e.g. missing yt-analytics
.readonly scope) returns watch_time_available=false with the other
fields still populated. No DB persistence; each call is live."
```

### Task 6: Stats button + strip on each done upload chip

**Files:**
- Modify: `console/frontend/src/api/client.js` (new API method)
- Modify: `console/frontend/src/pages/UploadsPage.jsx` (state + button + strip)

- [ ] **Step 1: Add `fetchUploadStats` API method**

In `console/frontend/src/api/client.js`, inside the `youtubeVideosApi` object, add:

```js
  fetchUploadStats: (uploadId) =>
    fetchApi(`/api/youtube-videos/uploads/${uploadId}/stats`, { method: 'GET' }),
```

- [ ] **Step 2: Add stats state to `YouTubeLongSection`**

Inside the component (around the other `useState` calls), add:

```jsx
// statsByUpload[upload.id] = { loading, data, error } | undefined
const [statsByUpload, setStatsByUpload] = useState({})

const handleFetchStats = async (uploadId) => {
  setStatsByUpload(prev => ({ ...prev, [uploadId]: { loading: true } }))
  try {
    const data = await youtubeVideosApi.fetchUploadStats(uploadId)
    setStatsByUpload(prev => ({ ...prev, [uploadId]: { loading: false, data } }))
  } catch (e) {
    setStatsByUpload(prev => ({ ...prev, [uploadId]: { loading: false, error: e.message } }))
    showToast(e.message, 'error')
  }
}
```

- [ ] **Step 3: Add a number formatter helper**

Inside the same component file (above the component declaration is fine), or in a `utils` module if one already exists:

```jsx
function formatCount(n) {
  if (n == null) return null
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatWatchTime(min) {
  if (min == null) return null
  if (min < 60) return `${min}m`
  return `${Math.floor(min / 60)}h ${min % 60}m`
}
```

Reuse if these already exist in `utils.js` — grep first to avoid duplicating.

- [ ] **Step 4: Add the ↻ button + strip on each done chip**

In the chip render block (right after the `+Short` button from Task 3), add:

```jsx
{u.status === 'done' && u.platform_id && (
  <button
    title="Fetch live stats from YouTube"
    onClick={(e) => { e.stopPropagation(); handleFetchStats(u.id) }}
    className="ml-0.5 text-[#9090a8] hover:text-[#e8e8f0] transition-colors leading-none text-[10px]"
  >
    {statsByUpload[u.id]?.loading ? '⟳' : '↻'}
  </button>
)}
```

After the chip itself (still inside `uploads.map(...)`, but after the `</span>` closing the chip — so it renders on the next inline element OR as a block under the chip), render the stats strip. Easiest placement: wrap the existing chip in a `<div className="flex flex-col gap-0.5">` so a stats line can sit below:

Before — chip is bare `<span>`. After — wrap in flex column. Find the existing `<span key={u.id} ...>` (around line 411) and wrap it as:

```jsx
<div key={u.id} className="flex flex-col items-start gap-0.5">
  <span title={u.error || undefined} className="...same classes as before...">
    {/* existing chip contents */}
  </span>
  {statsByUpload[u.id]?.data && (
    <div className="text-[10px] text-[#9090a8] flex items-center gap-1.5 pl-1">
      {(() => {
        const d = statsByUpload[u.id].data
        const parts = []
        if (d.view_count != null)   parts.push(`${formatCount(d.view_count)} views`)
        if (d.watch_time_minutes != null) parts.push(`${formatWatchTime(d.watch_time_minutes)} watched`)
        if (d.like_count != null)   parts.push(`${formatCount(d.like_count)} likes`)
        if (d.comment_count != null) parts.push(`${formatCount(d.comment_count)} comments`)
        return parts.join(' · ')
      })()}
      {!statsByUpload[u.id].data.watch_time_available && (
        <a
          href="#"
          onClick={(e) => { e.preventDefault(); /* TODO: route to credentials tab */ }}
          className="text-[#fbbf24] hover:underline"
        >
          Re-auth channel for watch time
        </a>
      )}
    </div>
  )}
</div>
```

NOTE: the inline `TODO` for routing to the credentials tab — replace with whatever the page's tab-switch mechanism is. Check the parent component (`UploadsPage` proper) for the `tab` state. If `tab` is a prop passed down to `YouTubeLongSection`, plumb a `setTab` prop and call `setTab('credentials')`. If you can't find it cleanly, fall back to a plain anchor with `href="#credentials"` and document that future work hooks the tab switch.

Replace the `TODO` with a working `onClick` if the plumbing is straightforward (≤5 lines of changes). Otherwise leave a working anchor (clickable, doesn't crash) and mention it in the commit body.

- [ ] **Step 5: Frontend build sanity check**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 6: Manual smoke test**

In the browser, on `/uploads`:
1. Find a done upload. Click the `↻` icon on the chip.
2. Verify a stats line appears under the chip within ~2 s with views/likes/comments.
3. If the channel hasn't been re-authed with the new scope, watch time should NOT appear and a "Re-auth channel for watch time" link should show.
4. Click ↻ again to re-fetch.

- [ ] **Step 7: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/frontend/src/api/client.js console/frontend/src/pages/UploadsPage.jsx
git commit -m "feat(uploads): ↻ Fetch stats button + live stats strip per done chip

Adds youtubeVideosApi.fetchUploadStats and a per-chip ↻ button that
triggers a live fetch. Renders views, watch_time_minutes, likes, and
comments inline; when watch_time isn't available (channel lacks the
yt-analytics.readonly scope), a 'Re-auth channel for watch time' link
appears in its place. Stats are session-scoped — no persistence."
```

---

## Final integration check

### Task 7: Full test surface + cross-cutting verification

- [ ] **Step 1: Run the entire relevant test surface**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
pytest tests/test_upload_stats_service.py tests/test_youtube_videos_uploads_stats.py tests/test_youtube_uploader.py -v 2>&1 | tail -15
```

Expected: all the new tests PASS. The pre-existing teardown error (drop_all CASCADE on youtube_videos) may still appear — ignore.

- [ ] **Step 2: Frontend final build**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -3
```

Expected: clean build.

- [ ] **Step 3: Browse changelog**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git log --oneline main..HEAD 2>/dev/null || git log --oneline -10
```

Expected: ~6 commits (Tasks 1-6 each commit once; Task 7 is verification, no commit).

- [ ] **Step 4: Manual end-to-end on /uploads page**

1. **F1:** click ↗ on a done chip → opens YouTube tab.
2. **F3:** click +Short on a done chip → MakeShortModal opens with parent preset → Submit → on /youtube, find the new short, confirm `seo_description` begins with `Watch the full video → https://...`.
3. **F2:** click ↻ on a done chip → stats appear within ~2s. If a channel was re-authed with the new scope, watch time appears too; otherwise re-auth link appears.

No commit — verification step.

---

## Self-Review

**1. Spec coverage:**
- F1 (open YouTube link): T1.
- F2 backend (live stats fetch, no DB): T4 (scope), T5 (service + endpoint).
- F2 frontend (button + strip + re-auth link): T6.
- F3 backend: none needed (existing `create_video` accepts `seo_description`).
- F3 frontend (Make Short from upload row + link prefix): T2 (modal prop) + T3 (button).
- Final verification: T7.

All spec sections covered.

**2. Placeholder scan:**
- One intentional inline note in T6 Step 4 about the credentials-tab routing: states "Replace the TODO with a working onClick if the plumbing is straightforward (≤5 lines)…" — this is a graduated instruction with a fallback (plain anchor), not a placeholder. Acceptable.
- No "TBD", "implement later", "similar to" patterns elsewhere.

**3. Type consistency:**
- `youtubeWatchUrl(platformId)` referenced consistently (T1 helper, T3 use, T6 use).
- `fetch_stats(upload_id, db)` returns the same dict shape everywhere (T5 service spec, T5 router alias `fetch_upload_stats`, T6 frontend consumption).
- `originalUploadUrl` prop name consistent in T2 (definition) and T3 (use).
- Field names match across backend dict, JSON response, and frontend consumption: `view_count`, `like_count`, `comment_count`, `watch_time_minutes`, `fetched_at`, `watch_time_available`.

**Files touched (recap):**

```
console/frontend/src/api/client.js                       (T1, T6)
console/frontend/src/pages/UploadsPage.jsx               (T1, T3, T6)
console/frontend/src/pages/YouTubeVideosPage.jsx         (T2, T3 — export)
console/backend/services/credential_service.py           (T4)
console/backend/services/upload_stats_service.py  (NEW)  (T5)
console/backend/routers/youtube_videos.py                (T5)
tests/test_upload_stats_service.py                (NEW)  (T5)
tests/test_youtube_videos_uploads_stats.py        (NEW)  (T5)
```

No DB migration. No Celery task. No new Pydantic schemas (the endpoint returns the service dict directly).
