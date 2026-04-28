# Manage Videos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Video Assets management tab, a rendered-video preview player in the Uploads tab, and fix the channel-loading bug in the Uploads > Videos sub-tab.

**Architecture:** Three independent changes that share no state. The bug fix is a one-line `useEffect` change in `UploadsPage`. The Video Assets page mirrors the existing `MusicPage` pattern — new backend endpoints on the existing production router + a new React page + nav entry. The upload video preview adds a `stream` endpoint to the uploads router and a modal player in `UploadsPage`.

**Tech Stack:** FastAPI (Python 3.11+), SQLAlchemy ORM, React 18 + Vite + Tailwind CSS, existing `useApi` hook, `fetchApi` wrapper.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `console/backend/models/video_asset.py` | Modify | Add `description` column to ORM model |
| `console/backend/services/production_service.py` | Modify | Add `description` to `_asset_to_dict`; add `update_asset`, `delete_asset`, `stream_asset_path` |
| `console/backend/routers/production.py` | Modify | Add `PUT /assets/{id}`, `DELETE /assets/{id}`, `GET /assets/{id}/stream` |
| `console/backend/services/upload_service.py` | Modify | Add `has_video` to `list_videos` output; add `stream_video_path` |
| `console/backend/routers/uploads.py` | Modify | Add `GET /videos/{id}/stream` |
| `console/frontend/src/api/client.js` | Modify | Add `assetsApi` |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | Create | Full video asset management page |
| `console/frontend/src/App.jsx` | Modify | Add `assets` nav tab, import `VideoAssetsPage` |
| `console/frontend/src/pages/UploadsPage.jsx` | Modify | Fix channel loading bug; add `VideoPreviewModal` + ▶ button |

---

## Task 1: Bug Fix — Channels not loading in Uploads > Videos tab

**Root cause:** `UploadsPage` starts with `channels = []`. The only way to populate it is via `onChannelsLoaded` callback fired by `ChannelsTab` — but `ChannelsTab` only mounts when the user clicks the "Channels" sub-tab. The default sub-tab is "Videos", so `channels` stays empty and `ChannelPicker` shows "No active channels".

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx`

- [ ] **Step 1: Open UploadsPage.jsx and locate the `UploadsPage` component**

The component is at line 519. It currently has:
```js
const [channels, setChannels] = useState([])
```
and no `useEffect` to load channels.

- [ ] **Step 2: Add channel fetch on mount**

Add this `useEffect` inside `UploadsPage`, right after the `useState` declarations (before the `platformStats` calculation):

```js
// Fetch channels on mount so VideosTab has them without requiring ChannelsTab to load first
useEffect(() => {
  fetchApi('/api/channels')
    .then(data => setChannels(Array.isArray(data) ? data : []))
    .catch(() => {})
}, [])
```

The import of `useEffect` is already at line 1 (`import { useState, useEffect, useCallback } from 'react'`).

- [ ] **Step 3: Verify fix manually**

1. Start the API: `cd ai-media-automation && uvicorn console.backend.main:app --port 8080 --reload`
2. Start frontend: `cd console/frontend && npm run dev`
3. Navigate to Uploads — stay on the default Videos sub-tab
4. Click the "Target" button on any video row
5. Confirm the dropdown shows your channels **without** first visiting the Channels sub-tab

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/UploadsPage.jsx
git commit -m "fix: load channels on mount in UploadsPage so VideosTab ChannelPicker works without visiting Channels tab first"
```

---

## Task 2: VideoAsset ORM model — add description field

The console's `VideoAsset` ORM model is missing the `description` column that exists on the `video_assets` table (added by the pipeline migration). Add it so the service layer can read and write it.

**Files:**
- Modify: `console/backend/models/video_asset.py`

- [ ] **Step 1: Add `description` column to the model**

Open `console/backend/models/video_asset.py`. After the `source` mapped column (line ~16), add:

```python
description: Mapped[str | None] = mapped_column(Text, nullable=True)
```

The full updated model should look like:

```python
from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    niche: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 2: Verify no migration needed**

The column already exists on the table (added by the pipeline migration). Confirm:

```bash
cd console/backend && python -c "
from database.connection import engine
from sqlalchemy import inspect
cols = [c['name'] for c in inspect(engine).get_columns('video_assets')]
print('description' in cols, cols)
"
```

Expected: `True [... 'description' ...]`

- [ ] **Step 3: Commit**

```bash
git add console/backend/models/video_asset.py
git commit -m "feat: add description column to console VideoAsset ORM model"
```

---

## Task 3: Production service — asset update, delete, stream

**Files:**
- Modify: `console/backend/services/production_service.py`

- [ ] **Step 1: Update `_asset_to_dict` to include description**

Find `_asset_to_dict` (starts at line 69). Replace the return dict to add `description`:

```python
def _asset_to_dict(self, asset: VideoAsset) -> dict:
    return {
        "id": asset.id,
        "file_path": asset.file_path,
        "thumbnail_url": asset.thumbnail_path,
        "source": asset.source,
        "description": asset.description,
        "keywords": asset.keywords or [],
        "niche": asset.niche or [],
        "duration_s": asset.duration_s,
        "resolution": asset.resolution,
        "quality_score": asset.quality_score,
        "usage_count": asset.usage_count,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }
```

- [ ] **Step 2: Add `update_asset`, `delete_asset`, `stream_asset_path` methods**

Append these three methods to `ProductionService`, after `_asset_to_dict` (before `# ── Scene editing`):

```python
def update_asset(
    self,
    asset_id: int,
    description: str | None = None,
    keywords: list[str] | None = None,
    niche: list[str] | None = None,
    quality_score: float | None = None,
) -> dict:
    asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
    if not asset:
        raise KeyError(f"Asset {asset_id} not found")
    if description is not None:
        asset.description = description
    if keywords is not None:
        asset.keywords = keywords
    if niche is not None:
        asset.niche = niche
    if quality_score is not None:
        asset.quality_score = quality_score
    self.db.commit()
    self.db.refresh(asset)
    return self._asset_to_dict(asset)

def delete_asset(self, asset_id: int) -> None:
    asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
    if not asset:
        raise KeyError(f"Asset {asset_id} not found")
    self.db.delete(asset)
    self.db.commit()

def stream_asset_path(self, asset_id: int) -> str:
    asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
    if not asset:
        raise KeyError(f"Asset {asset_id} not found")
    if not asset.file_path:
        raise ValueError(f"Asset {asset_id} has no file path")
    return asset.file_path
```

- [ ] **Step 3: Verify syntax**

```bash
cd ai-media-automation
python -c "from console.backend.services.production_service import ProductionService; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/production_service.py
git commit -m "feat: add update_asset, delete_asset, stream_asset_path to ProductionService"
```

---

## Task 4: Production router — PUT / DELETE / stream asset endpoints

**Files:**
- Modify: `console/backend/routers/production.py`

- [ ] **Step 1: Add imports at the top of production.py**

After the existing imports, add:

```python
from pathlib import Path
from fastapi.responses import FileResponse
```

- [ ] **Step 2: Add `UpdateAssetBody` schema**

After the existing `ReplaceAssetBody` class, add:

```python
class UpdateAssetBody(BaseModel):
    description: str | None = None
    keywords: list[str] | None = None
    niche: list[str] | None = None
    quality_score: float | None = None
```

- [ ] **Step 3: Add the three new endpoints**

Append these after the existing `GET /assets/{asset_id}` endpoint (after line 54):

```python
@router.get("/assets/{asset_id}/stream")
def stream_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        path = ProductionService(db).stream_asset_path(asset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(path), media_type="video/mp4")


@router.put("/assets/{asset_id}")
def update_asset(
    asset_id: int,
    body: UpdateAssetBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return ProductionService(db).update_asset(
            asset_id,
            description=body.description,
            keywords=body.keywords,
            niche=body.niche,
            quality_score=body.quality_score,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        ProductionService(db).delete_asset(asset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 4: Verify endpoints appear in API docs**

Restart the API server and open `http://localhost:8080/docs`. Confirm these three endpoints appear under the **production** tag:
- `GET /api/production/assets/{asset_id}/stream`
- `PUT /api/production/assets/{asset_id}`
- `DELETE /api/production/assets/{asset_id}`

- [ ] **Step 5: Commit**

```bash
git add console/backend/routers/production.py
git commit -m "feat: add PUT/DELETE/stream endpoints for video assets on production router"
```

---

## Task 5: Upload service + router — has_video field and stream endpoint

**Files:**
- Modify: `console/backend/services/upload_service.py`
- Modify: `console/backend/routers/uploads.py`

- [ ] **Step 1: Add `import os` to upload_service.py**

At the top of `console/backend/services/upload_service.py`, after the existing imports, add:

```python
import os
```

- [ ] **Step 2: Add `gs.output_path` to the `data_sql` SELECT**

In `list_videos`, find the `data_sql` string (around line 49). Change:

```python
data_sql = f"""
    SELECT
        gs.id, gs.status, gs.script_json,
```

to:

```python
data_sql = f"""
    SELECT
        gs.id, gs.status, gs.script_json, gs.output_path,
```

- [ ] **Step 3: Add `has_video` to each item in the loop**

In the `for row in rows:` loop (around line 84), change the `items.append(...)` call to:

```python
for row in rows:
    sj = row.script_json if isinstance(row.script_json, dict) else {}
    video = sj.get("video", {})
    meta  = sj.get("meta", {})
    has_video = bool(row.output_path and os.path.isfile(row.output_path))
    items.append({
        "id":        row.id,
        "title":     video.get("title") or meta.get("topic") or f"Script #{row.id}",
        "template":  meta.get("template"),
        "niche":     meta.get("niche"),
        "status":    row.status,
        "targets":   row.targets if isinstance(row.targets, list) else [],
        "has_video": has_video,
    })
```

- [ ] **Step 4: Add `stream_video_path` method to `UploadService`**

Append this method to `UploadService` (after `upload_all_ready`):

```python
def stream_video_path(self, video_id: str) -> str:
    row = self.db.execute(
        text("SELECT output_path FROM generated_scripts WHERE id = :id"),
        {"id": video_id},
    ).fetchone()
    if not row:
        raise KeyError(f"Video {video_id} not found")
    if not row.output_path or not os.path.isfile(row.output_path):
        raise ValueError(f"Video {video_id} has no rendered file on disk")
    return row.output_path
```

- [ ] **Step 5: Add stream endpoint to uploads router**

In `console/backend/routers/uploads.py`, add at the top after existing imports:

```python
from pathlib import Path
from fastapi.responses import FileResponse
```

Then append this endpoint after the existing `upload_all_ready` endpoint:

```python
@router.get("/videos/{video_id}/stream")
def stream_video(
    video_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        path = UploadService(db).stream_video_path(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return FileResponse(str(path), media_type="video/mp4")
```

- [ ] **Step 6: Verify syntax**

```bash
python -c "
from console.backend.services.upload_service import UploadService
from console.backend.routers.uploads import router
print('OK')
"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add console/backend/services/upload_service.py console/backend/routers/uploads.py
git commit -m "feat: add has_video field to upload list and stream endpoint for rendered videos"
```

---

## Task 6: Frontend — add assetsApi to client.js

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Append `assetsApi` export to client.js**

After the closing `}` of `musicApi` (line 134), add:

```js
// ── Video Assets ───────────────────────────────────────────────────────────────
export const assetsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    )
    return fetchApi(`/api/production/assets?${q}`)
  },
  update: (id, body) =>
    fetchApi(`/api/production/assets/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) =>
    fetchApi(`/api/production/assets/${id}`, { method: 'DELETE' }),
  streamUrl: (id) => `/api/production/assets/${id}/stream`,
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add assetsApi to frontend API client"
```

---

## Task 7: Frontend — VideoAssetsPage.jsx

**Files:**
- Create: `console/frontend/src/pages/VideoAssetsPage.jsx`

- [ ] **Step 1: Create the file with the full implementation**

```jsx
import { useState } from 'react'
import { assetsApi } from '../api/client.js'
import { nichesApi } from '../api/client.js'
import { useApi } from '../hooks/useApi.js'
import { Card, Button, StatBox, Modal, Spinner, EmptyState, Toast } from '../components/index.jsx'

// ── Source badge ──────────────────────────────────────────────────────────────
const SOURCE_COLORS = {
  pexels: 'bg-[#001624] text-[#4a9eff] border-[#002840]',
  veo:    'bg-[#001e12] text-[#34d399] border-[#003020]',
  manual: 'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]',
  stock:  'bg-[#1e1e2e] text-[#9090a8] border-[#2a2a42]',
}

function SourceBadge({ source }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${SOURCE_COLORS[source] || SOURCE_COLORS.manual}`}>
      {(source || 'manual').toUpperCase()}
    </span>
  )
}

// ── Niche multi-select pills ──────────────────────────────────────────────────
function NicheSelect({ options, value = [], onChange }) {
  const toggle = (opt) =>
    onChange(value.includes(opt) ? value.filter(v => v !== opt) : [...value, opt])
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-[#9090a8] font-medium">Niches</label>
      <div className="flex flex-wrap gap-1.5">
        {options.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
              value.includes(opt)
                ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:border-[#7c6af7] hover:text-[#e8e8f0]'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Preview modal — inline video player ───────────────────────────────────────
function PreviewModal({ asset, onClose }) {
  return (
    <Modal open onClose={onClose} title={asset.description || `Asset #${asset.id}`} width="max-w-xs">
      <div className="aspect-[9/16] bg-[#0d0d0f] rounded-lg overflow-hidden">
        <video
          controls
          autoPlay
          src={assetsApi.streamUrl(asset.id)}
          className="w-full h-full object-contain"
        />
      </div>
      {(asset.keywords || []).length > 0 && (
        <div className="mt-2 flex gap-1.5 flex-wrap">
          {asset.keywords.map(k => (
            <span key={k} className="text-[10px] bg-[#2a2a32] text-[#9090a8] rounded px-1.5 py-0.5">{k}</span>
          ))}
        </div>
      )}
    </Modal>
  )
}

// ── Edit modal ────────────────────────────────────────────────────────────────
function EditModal({ asset, niches, onClose, onSaved }) {
  const [description,  setDescription]  = useState(asset.description || '')
  const [keywords,     setKeywords]     = useState((asset.keywords || []).join(', '))
  const [selNiches,    setSelNiches]    = useState(asset.niche || [])
  const [qualityScore, setQualityScore] = useState(asset.quality_score ?? 0)
  const [saving,       setSaving]       = useState(false)
  const [toast,        setToast]        = useState(null)

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await assetsApi.update(asset.id, {
        description: description || null,
        keywords: keywords.split(',').map(k => k.trim()).filter(Boolean),
        niche: selNiches,
        quality_score: parseFloat(qualityScore) || 0,
      })
      onSaved()
      onClose()
    } catch (e) {
      showToast(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Edit Asset #${asset.id}`}
      width="max-w-xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={saving} onClick={handleSave}>Save</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Description</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            rows={3}
            placeholder="Describe this video clip…"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] resize-y"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">
            Keywords <span className="text-[#5a5a70]">(comma-separated)</span>
          </label>
          <input
            value={keywords}
            onChange={e => setKeywords(e.target.value)}
            placeholder="nature, outdoor, sunset"
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7]"
          />
        </div>
        <NicheSelect options={niches.map(n => n.name)} value={selNiches} onChange={setSelNiches} />
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Quality Score (0–100)</label>
          <input
            type="number"
            min="0"
            max="100"
            value={qualityScore}
            onChange={e => setQualityScore(e.target.value)}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] w-32"
          />
        </div>
      </div>
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </Modal>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function VideoAssetsPage() {
  const [filterKeywords, setFilterKeywords] = useState('')
  const [filterSource,   setFilterSource]   = useState('')
  const [filterNiche,    setFilterNiche]    = useState('')
  const [filterMinDur,   setFilterMinDur]   = useState('')
  const [previewAsset,   setPreviewAsset]   = useState(null)
  const [editingAsset,   setEditingAsset]   = useState(null)
  const [deletingId,     setDeletingId]     = useState(null)
  const [toast,          setToast]          = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const { data: nicheData = [] } = useApi(() => nichesApi.list(), [])
  const { data: result, loading, refetch } = useApi(
    () => assetsApi.list({
      keywords:     filterKeywords || undefined,
      source:       filterSource   || undefined,
      niche:        filterNiche    || undefined,
      min_duration: filterMinDur   || undefined,
    }),
    [filterKeywords, filterSource, filterNiche, filterMinDur]
  )

  const assets    = result?.items || []
  const nicheList = nicheData || []

  const pexelsCount = assets.filter(a => a.source === 'pexels').length
  const veoCount    = assets.filter(a => a.source === 'veo').length
  const manualCount = assets.filter(a => !['pexels', 'veo'].includes(a.source)).length

  const handleDelete = async (asset) => {
    if (!window.confirm(`Delete asset #${asset.id}? The database record will be removed.`)) return
    setDeletingId(asset.id)
    try {
      await assetsApi.delete(asset.id)
      showToast('Asset deleted')
      refetch()
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[#e8e8f0]">Video Assets</h1>
        <p className="text-sm text-[#9090a8] mt-0.5">Manage video clips downloaded from Pexels or generated by Veo</p>
      </div>

      {/* Stats */}
      <div className="flex gap-3 flex-wrap">
        <StatBox label="Total" value={result?.total ?? 0} />
        <StatBox label="Pexels" value={pexelsCount} />
        <StatBox label="Veo" value={veoCount} />
        <StatBox label="Other" value={manualCount} />
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <input
          value={filterKeywords}
          onChange={e => setFilterKeywords(e.target.value)}
          placeholder="Keywords (comma-separated)…"
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] w-52"
        />
        <select
          value={filterSource}
          onChange={e => setFilterSource(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
        >
          <option value="">All sources</option>
          <option value="pexels">Pexels</option>
          <option value="veo">Veo</option>
          <option value="manual">Manual</option>
        </select>
        <select
          value={filterNiche}
          onChange={e => setFilterNiche(e.target.value)}
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
        >
          <option value="">All niches</option>
          {nicheList.map(n => <option key={n.id} value={n.name}>{n.name}</option>)}
        </select>
        <input
          type="number"
          value={filterMinDur}
          onChange={e => setFilterMinDur(e.target.value)}
          placeholder="Min duration (s)"
          className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] w-40"
        />
      </div>

      {/* Table */}
      <Card>
        {loading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : assets.length === 0 ? (
          <EmptyState
            icon="🎬"
            title="No video assets yet"
            description="Assets are added automatically when the pipeline downloads from Pexels or generates with Veo."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#2a2a32] text-left">
                  {['', 'Description', 'Source', 'Duration', 'Resolution', 'Niches', 'Score', 'Uses', ''].map((h, i) => (
                    <th key={i} className="pb-2 pr-4 text-xs font-semibold text-[#9090a8] uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {assets.map(a => (
                  <tr key={a.id} className="border-b border-[#2a2a32] hover:bg-[#16161a] transition-colors">
                    {/* Thumbnail */}
                    <td className="py-2.5 pr-3 w-16">
                      {a.thumbnail_url ? (
                        <img src={a.thumbnail_url} alt="" className="w-14 h-10 object-cover rounded border border-[#2a2a32]" />
                      ) : (
                        <div className="w-14 h-10 bg-[#2a2a32] rounded flex items-center justify-center text-[#5a5a70] text-lg">🎬</div>
                      )}
                    </td>
                    {/* Description + keywords */}
                    <td className="py-2.5 pr-4 max-w-[200px]">
                      <div className="text-xs text-[#e8e8f0] truncate">{a.description || `Asset #${a.id}`}</div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(a.keywords || []).slice(0, 3).map(k => (
                          <span key={k} className="text-[9px] bg-[#2a2a32] text-[#9090a8] rounded px-1 py-0.5">{k}</span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2.5 pr-4"><SourceBadge source={a.source} /></td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs whitespace-nowrap">
                      {a.duration_s != null ? `${a.duration_s.toFixed(1)}s` : '—'}
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs whitespace-nowrap">
                      {a.resolution || '—'}
                    </td>
                    <td className="py-2.5 pr-4">
                      <div className="flex flex-wrap gap-1 max-w-[140px]">
                        {(a.niche || []).slice(0, 2).map(n => (
                          <span key={n} className="text-[9px] bg-[#1c1c22] border border-[#2a2a32] text-[#9090a8] rounded px-1.5 py-0.5">{n}</span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">
                      {a.quality_score != null ? a.quality_score.toFixed(0) : '—'}
                    </td>
                    <td className="py-2.5 pr-4 font-mono text-[#9090a8] text-xs">{a.usage_count}</td>
                    <td className="py-2.5">
                      <div className="flex gap-1">
                        <Button variant="ghost" size="sm" onClick={() => setPreviewAsset(a)}>▶</Button>
                        <Button variant="ghost" size="sm" onClick={() => setEditingAsset(a)}>✎</Button>
                        <Button variant="danger" size="sm" loading={deletingId === a.id} onClick={() => handleDelete(a)}>✕</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {previewAsset && <PreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} />}
      {editingAsset && (
        <EditModal
          asset={editingAsset}
          niches={nicheList}
          onClose={() => setEditingAsset(null)}
          onSaved={refetch}
        />
      )}
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
```

- [ ] **Step 2: Verify the file parses (no JSX syntax errors)**

```bash
cd console/frontend && npx --yes acorn --ecma2020 --module src/pages/VideoAssetsPage.jsx > /dev/null && echo OK
```

Expected: `OK` (or no error output). If `acorn` isn't available, just start the dev server and check the browser console.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/VideoAssetsPage.jsx
git commit -m "feat: add VideoAssetsPage — browse, preview, edit, delete video assets"
```

---

## Task 8: Frontend — App.jsx, add Assets nav tab

**Files:**
- Modify: `console/frontend/src/App.jsx`

- [ ] **Step 1: Import VideoAssetsPage**

At the top of `App.jsx`, after the `MusicPage` import (line 15), add:

```js
import VideoAssetsPage from './pages/VideoAssetsPage.jsx'
```

- [ ] **Step 2: Add Assets icon to `Icons`**

Inside the `Icons` object (after `Icons.Composer`), add:

```js
Assets: () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="2" width="8" height="8" rx="1"/><rect x="14" y="2" width="8" height="8" rx="1"/><rect x="14" y="14" width="8" height="8" rx="1"/><rect x="2" y="14" width="8" height="8" rx="1"/>
  </svg>
),
```

- [ ] **Step 3: Add the tab entry to `ALL_TABS`**

In `ALL_TABS`, after the `music` entry, add:

```js
{ id: 'assets', label: 'Assets', Icon: Icons.Assets, roles: ['admin', 'editor'] },
```

- [ ] **Step 4: Add the render case in `renderPage`**

In the `renderPage` switch, after `case 'music':`, add:

```js
case 'assets':     return <VideoAssetsPage />
```

- [ ] **Step 5: Verify in browser**

1. Navigate to `http://localhost:5173`
2. Confirm "Assets" appears in the sidebar between Music and Composer
3. Click it — the page should load (empty state if no assets yet)

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/App.jsx
git commit -m "feat: add Assets nav tab to App sidebar routing"
```

---

## Task 9: Frontend — UploadsPage.jsx, video preview modal

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx`

- [ ] **Step 1: Add `VideoPreviewModal` component**

Add this component above the `VideosTab` function definition (around line 32, after the `StatusBadge` function):

```jsx
function VideoPreviewModal({ video, onClose }) {
  return (
    <Modal open onClose={onClose} title={video.title} width="max-w-sm">
      <div className="aspect-[9/16] bg-[#0d0d0f] rounded-lg overflow-hidden">
        <video
          controls
          autoPlay
          src={`/api/uploads/videos/${video.id}/stream`}
          className="w-full h-full object-contain"
        />
      </div>
      <div className="mt-2 text-xs text-[#9090a8] font-mono text-center">{video.niche}</div>
    </Modal>
  )
}
```

- [ ] **Step 2: Add `previewVideo` state to `VideosTab`**

Inside `VideosTab`, after the existing state declarations (`const [toast, setToast] = useState(null)`), add:

```js
const [previewVideo, setPreviewVideo] = useState(null)
```

- [ ] **Step 3: Add ▶ button to each video row**

In the `<td className="py-2.5 text-right">` cell (around line 152), inside the `<div className="flex items-center gap-1 justify-end">`, add a play button before the Upload button:

```jsx
{v.has_video && (
  <Button variant="ghost" className="text-xs px-2 py-1" onClick={() => setPreviewVideo(v)}>
    ▶
  </Button>
)}
```

The full actions cell should be:

```jsx
<td className="py-2.5 text-right">
  <div className="flex items-center gap-1 justify-end">
    {v.has_video && (
      <Button variant="ghost" className="text-xs px-2 py-1" onClick={() => setPreviewVideo(v)}>
        ▶
      </Button>
    )}
    {uploadable && vTargets.length > 0 && (
      <Button variant="primary" className="text-xs px-2 py-1" onClick={() => handleUpload(v.id)}>
        Upload
      </Button>
    )}
    <Button variant="danger" className="text-xs px-2 py-1" onClick={() => handleDelete(v.id)}>
      Remove
    </Button>
  </div>
</td>
```

- [ ] **Step 4: Render the modal at the bottom of `VideosTab`**

Inside the `VideosTab` return, just before the closing `</Card>` tag (before `{toast && <Toast ...`), add:

```jsx
{previewVideo && <VideoPreviewModal video={previewVideo} onClose={() => setPreviewVideo(null)} />}
```

- [ ] **Step 5: Verify in browser**

1. Navigate to Uploads > Videos
2. For a script that has `output_path` set (status `completed` or `producing`), a ▶ button should appear
3. Click ▶ — video modal should open and play
4. For scripts without a rendered file, no ▶ button appears

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/UploadsPage.jsx
git commit -m "feat: add video preview modal to Uploads Videos tab"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|-----------|
| Video Assets tab — browse Pexels/Veo assets | Task 7 (VideoAssetsPage), Task 8 (App.jsx nav) |
| Video Assets — edit metadata (keywords, niche, quality score) | Task 3 (service), Task 4 (router), Task 7 (EditModal) |
| Video Assets — delete asset | Task 3 (service), Task 4 (router), Task 7 (delete button) |
| Video Assets — preview clip | Task 3 (stream endpoint), Task 4 (router), Task 7 (PreviewModal) |
| Rendered video playable in Uploads tab | Task 5 (service+router stream), Task 9 (VideoPreviewModal + ▶ button) |
| Channel loading bug fix | Task 1 (UploadsPage useEffect) |
| `description` exposed in asset API | Task 2 (model), Task 3 (service _asset_to_dict) |

**Placeholder scan:** No TBD, no "implement later", all code steps include complete code blocks.

**Type consistency check:**
- `assetsApi.streamUrl(id)` defined in Task 6, called in `PreviewModal` in Task 7 ✓
- `assetsApi.update(id, body)` defined in Task 6, called in `EditModal.handleSave` in Task 7 ✓
- `assetsApi.delete(id)` defined in Task 6, called in `handleDelete` in Task 7 ✓
- `ProductionService.update_asset(...)` defined in Task 3, called from router in Task 4 ✓
- `ProductionService.delete_asset(asset_id)` defined in Task 3, called from router in Task 4 ✓
- `ProductionService.stream_asset_path(asset_id)` defined in Task 3, called from router in Task 4 ✓
- `UploadService.stream_video_path(video_id)` defined in Task 5, called from router in Task 5 ✓
- `has_video` added to `list_videos` in Task 5, read as `v.has_video` in Task 9 ✓
- `VideoPreviewModal` defined in Task 9, rendered in Task 9 ✓
