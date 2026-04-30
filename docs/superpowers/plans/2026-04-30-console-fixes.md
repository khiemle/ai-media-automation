# Console Fixes & Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix SFX import display bug, add login persistence, restructure nav, add asset file upload, and add inline upload to YouTube creation panel.

**Architecture:** All changes are additive. Backend gets one new endpoint (`POST /api/production/assets/upload`) and one new service method (`import_asset`). Frontend gets URLSearchParams fixes, sessionStorage token persistence, nav section change, and two new upload UI components.

**Tech Stack:** FastAPI · SQLAlchemy `Mapped[]` style · React 18 + Vite + Tailwind CSS · sessionStorage

---

## File Map

### Modified backend files
| Path | Change |
|---|---|
| `console/backend/services/production_service.py` | + `import_asset()` method |
| `console/backend/routers/production.py` | + `POST /assets/upload` endpoint |

### New test file
| Path | Responsibility |
|---|---|
| `tests/test_production_import.py` | TDD tests for `import_asset()` |

### Modified frontend files
| Path | Change |
|---|---|
| `console/frontend/src/api/client.js` | Fix URLSearchParams; add `restoreToken`; add `assetsApi.upload` |
| `console/frontend/src/App.jsx` | Move Uploads+Pipeline to admin section; sessionStorage restore on mount |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | + Import Asset button + `ImportAssetModal` |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | + Inline upload panels for music + visual in `CreationPanel` |

---

## Task 1: Fix URLSearchParams Bug in API Client

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Fix `sfxApi.list`**

In `console/frontend/src/api/client.js`, replace the `sfxApi.list` method:

```js
// Before
list: (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return fetchApi(`/api/sfx${qs ? `?${qs}` : ''}`)
},

// After
list: (params = {}) => {
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  )
  const qs = new URLSearchParams(filtered).toString()
  return fetchApi(`/api/sfx${qs ? `?${qs}` : ''}`)
},
```

- [ ] **Step 2: Fix `youtubeVideosApi.list`**

In the same file, replace the `youtubeVideosApi.list` method:

```js
// Before
list: (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return fetchApi(`/api/youtube-videos${qs ? `?${qs}` : ''}`)
},

// After
list: (params = {}) => {
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  )
  const qs = new URLSearchParams(filtered).toString()
  return fetchApi(`/api/youtube-videos${qs ? `?${qs}` : ''}`)
},
```

- [ ] **Step 3: Verify fix manually**

Open the SFX page in browser. Import an SFX file. After import the list should refresh and show the new item (not empty).

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "fix: filter undefined params from URLSearchParams in sfxApi and youtubeVideosApi"
```

---

## Task 2: Login Persistence via sessionStorage

**Files:**
- Modify: `console/frontend/src/api/client.js`
- Modify: `console/frontend/src/App.jsx`

- [ ] **Step 1: Update `setToken`, `clearToken`, add `restoreToken` in client.js**

In `console/frontend/src/api/client.js`, replace the token storage section at the top of the file:

```js
// ── Token storage (session-persistent) ────────────────────────────────────────
let _token = null

export function setToken(token) {
  if (!token) return
  _token = token
  sessionStorage.setItem('console_token', token)
}

export function clearToken() {
  _token = null
  sessionStorage.removeItem('console_token')
}

export function getToken() { return _token }

export function restoreToken() {
  const t = sessionStorage.getItem('console_token')
  if (t) _token = t
  return t || null
}
```

- [ ] **Step 2: Add session restore on App mount in App.jsx**

In `console/frontend/src/App.jsx`, update the import line to include `restoreToken`:

```js
import { setToken, clearToken, restoreToken, authApi } from './api/client.js'
```

Then replace the empty `useEffect` in the `App` component:

```js
// Before
useEffect(() => {
  // No persisted token — user must log in each session
}, [])

// After
useEffect(() => {
  const token = restoreToken()
  if (!token) return
  authApi.me()
    .then(userData => setUser(userData))
    .catch(() => clearToken())
}, [])
```

- [ ] **Step 3: Verify persistence**

1. Log in to the console
2. Reload the page (Cmd+R / F5)
3. Confirm you stay logged in without seeing the login screen

- [ ] **Step 4: Verify logout clears session**

1. Click logout
2. Reload the page
3. Confirm the login screen appears

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/api/client.js console/frontend/src/App.jsx
git commit -m "feat: persist JWT in sessionStorage for reload-proof login"
```

---

## Task 3: Nav Restructure — Uploads + Pipeline → Admin

**Files:**
- Modify: `console/frontend/src/App.jsx`

- [ ] **Step 1: Move Uploads and Pipeline to admin section**

In `console/frontend/src/App.jsx`, find the `ALL_TABS` array and change the two entries:

```js
// Before
{ id: 'uploads',  label: 'Uploads',  Icon: Icons.Uploads,  roles: ['admin', 'editor'], section: 'shared' },
{ id: 'pipeline', label: 'Pipeline', Icon: Icons.Pipeline, roles: ['admin', 'editor'], section: 'shared' },

// After
{ id: 'uploads',  label: 'Uploads',  Icon: Icons.Uploads,  roles: ['admin', 'editor'], section: 'admin' },
{ id: 'pipeline', label: 'Pipeline', Icon: Icons.Pipeline, roles: ['admin', 'editor'], section: 'admin' },
```

- [ ] **Step 2: Remove the now-unused `shared` section from SECTION_LABELS**

Find and update `SECTION_LABELS`:

```js
// Before
const SECTION_LABELS = {
  library: 'LIBRARY',
  short:   'SHORT VIDEOS',
  youtube: 'YOUTUBE VIDEOS',
  shared:  null,
  admin:   'ADMIN',
}

// After
const SECTION_LABELS = {
  library: 'LIBRARY',
  short:   'SHORT VIDEOS',
  youtube: 'YOUTUBE VIDEOS',
  admin:   'ADMIN',
}
```

- [ ] **Step 3: Verify in browser**

Open the console. Confirm the sidebar shows Uploads and Pipeline under the ADMIN section header, below LLM/Performance/System.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/App.jsx
git commit -m "feat: move Uploads and Pipeline tabs under Admin nav section"
```

---

## Task 4: Backend Asset Upload — TDD

**Files:**
- Create: `tests/test_production_import.py`
- Modify: `console/backend/services/production_service.py`
- Modify: `console/backend/routers/production.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_production_import.py`:

```python
import pytest
from pathlib import Path
from console.backend.services.production_service import ProductionService


def test_import_image_asset(db, tmp_path):
    svc = ProductionService(db)
    fake_jpg = b'\xff\xd8\xff\xe0' + b'\x00' * 40  # minimal JPEG header
    result = svc.import_asset(
        file_bytes=fake_jpg,
        filename='photo.jpg',
        source='midjourney',
        description='A dark rainy window',
        keywords=['rain', 'dark', 'window'],
        assets_dir=tmp_path,
    )
    assert result['id'] is not None
    assert result['asset_type'] == 'still_image'
    assert result['source'] == 'midjourney'
    assert result['description'] == 'A dark rainy window'
    assert result['keywords'] == ['rain', 'dark', 'window']
    assert Path(result['file_path']).exists()


def test_import_video_asset(db, tmp_path):
    svc = ProductionService(db)
    fake_mp4 = b'\x00\x00\x00\x18ftyp' + b'\x00' * 40
    result = svc.import_asset(
        file_bytes=fake_mp4,
        filename='loop.mp4',
        source='manual',
        description=None,
        keywords=None,
        assets_dir=tmp_path,
    )
    assert result['asset_type'] == 'video_clip'
    assert result['source'] == 'manual'
    assert result['keywords'] == []


def test_import_asset_filename_uses_id(db, tmp_path):
    svc = ProductionService(db)
    result = svc.import_asset(
        file_bytes=b'\xff\xd8\xff' + b'\x00' * 20,
        filename='test.png',
        source='manual',
        description=None,
        keywords=None,
        assets_dir=tmp_path,
    )
    expected_name = f"asset_{result['id']}.png"
    assert Path(result['file_path']).name == expected_name


def test_import_unsupported_extension_raises(db, tmp_path):
    svc = ProductionService(db)
    with pytest.raises(ValueError, match="Unsupported file type"):
        svc.import_asset(
            file_bytes=b'data',
            filename='file.txt',
            source='manual',
            description=None,
            keywords=None,
            assets_dir=tmp_path,
        )
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -m pytest tests/test_production_import.py -v 2>&1 | head -20
```

Expected: `AttributeError: 'ProductionService' object has no attribute 'import_asset'`

- [ ] **Step 3: Implement `import_asset` in ProductionService**

**3a.** In `console/backend/services/production_service.py`, update the top-of-file imports to add `os` and `Path`:

```python
# Add to existing imports at top of file
import os
from pathlib import Path
```

**3b.** Add module-level constants directly after the imports (before the `class ProductionService` line):

```python
_ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
_ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mov', '.webm'}
_ALLOWED_ASSET_EXTENSIONS = _ALLOWED_IMAGE_EXTENSIONS | _ALLOWED_VIDEO_EXTENSIONS
_DEFAULT_ASSETS_DIR = Path(os.path.abspath(
    os.environ.get('ASSETS_PATH', './assets/video_db/manual')
))
```

**3c.** Add the method to the `ProductionService` class after the `delete_asset` method (around line 133):

```python
def import_asset(
    self,
    file_bytes: bytes,
    filename: str,
    source: str,
    description: str | None,
    keywords: list[str] | None,
    assets_dir: Path | None = None,
) -> dict:
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_ASSET_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    asset_type = 'still_image' if ext in _ALLOWED_IMAGE_EXTENSIONS else 'video_clip'
    save_dir = Path(assets_dir) if assets_dir else _DEFAULT_ASSETS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    row = VideoAsset(
        file_path='',
        source=source,
        asset_type=asset_type,
        description=description,
        keywords=keywords or [],
    )
    self.db.add(row)
    self.db.flush()

    dest = save_dir / f'asset_{row.id}{ext}'
    dest.write_bytes(file_bytes)
    row.file_path = str(dest)
    self.db.commit()
    self.db.refresh(row)
    return self._asset_to_dict(row)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_production_import.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Add the upload endpoint to production router**

In `console/backend/routers/production.py`, add these imports at the top if not present:

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
```

Then add the new endpoint after the `delete_asset` route (after line ~118):

```python
ASSET_UPLOAD_ALLOWED = {'.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.webm'}
MAX_ASSET_BYTES = 500 * 1024 * 1024  # 500 MB
ASSET_SOURCES = {'manual', 'midjourney', 'runway', 'pexels', 'veo', 'stock'}


@router.post("/assets/upload", status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    source: str = Form(default='manual'),
    description: str = Form(default=''),
    keywords: str = Form(default=''),
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    from pathlib import Path
    ext = Path(file.filename or '').suffix.lower()
    if ext not in ASSET_UPLOAD_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    if source not in ASSET_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    content = await file.read(MAX_ASSET_BYTES + 1)
    if len(content) > MAX_ASSET_BYTES:
        raise HTTPException(status_code=413, detail='File too large (max 500 MB)')

    kw_list = [k.strip() for k in keywords.split(',') if k.strip()] if keywords else []
    try:
        return ProductionService(db).import_asset(
            file_bytes=content,
            filename=file.filename or 'asset',
            source=source,
            description=description or None,
            keywords=kw_list or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 6: Verify endpoint appears in OpenAPI docs**

```bash
curl -s http://localhost:8080/docs | grep -c "assets/upload"
```

Expected: `1` (or greater, confirming the route is registered).

- [ ] **Step 7: Commit**

```bash
git add tests/test_production_import.py \
        console/backend/services/production_service.py \
        console/backend/routers/production.py
git commit -m "feat: add import_asset to ProductionService + POST /assets/upload endpoint"
```

---

## Task 5: VideoAssetsPage — Import Asset Modal

**Files:**
- Modify: `console/frontend/src/api/client.js`
- Modify: `console/frontend/src/pages/VideoAssetsPage.jsx`

- [ ] **Step 1: Add `assetsApi.upload` to client.js**

In `console/frontend/src/api/client.js`, add `upload` to the `assetsApi` object after `thumbnailUrl`:

```js
upload: (file, metadata) => {
  const form = new FormData()
  form.append('file', file)
  form.append('source', metadata.source || 'manual')
  if (metadata.description) form.append('description', metadata.description)
  if (metadata.keywords) form.append('keywords', metadata.keywords)
  const headers = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch('/api/production/assets/upload', { method: 'POST', body: form, headers })
    .then(async res => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      return res.json()
    })
},
```

- [ ] **Step 2: Add `ImportAssetModal` component to VideoAssetsPage.jsx**

In `console/frontend/src/pages/VideoAssetsPage.jsx`, add this component before the `VideoAssetsPage` default export:

```jsx
const ASSET_SOURCES = ['manual', 'midjourney', 'runway', 'pexels', 'veo', 'stock']
const IMAGE_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp'])
const VIDEO_EXTS = new Set(['.mp4', '.mov', '.webm'])

function getAssetType(filename) {
  if (!filename) return null
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase()
  if (IMAGE_EXTS.has(ext)) return 'still_image'
  if (VIDEO_EXTS.has(ext)) return 'video_clip'
  return null
}

function ImportAssetModal({ onClose, onImported }) {
  const [file, setFile]               = useState(null)
  const [source, setSource]           = useState('manual')
  const [description, setDescription] = useState('')
  const [keywords, setKeywords]       = useState('')
  const [loading, setLoading]         = useState(false)
  const [toast, setToast]             = useState(null)

  const showToast = (msg, type = 'error') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  const detectedType = file ? getAssetType(file.name) : null

  const handleSubmit = async () => {
    if (!file) { showToast('Please select a file'); return }
    if (!detectedType) { showToast('Unsupported file type. Use jpg/png/webp/mp4/mov/webm'); return }
    setLoading(true)
    try {
      await assetsApi.upload(file, { source, description, keywords })
      onImported()
      onClose()
    } catch (e) {
      showToast(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Import Asset"
      width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">File <span className="text-[#5a5a70]">(jpg / png / webp / mp4 / mov / webm)</span></label>
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
          {detectedType && (
            <span className="text-xs text-[#34d399] mt-0.5">
              Detected: {detectedType === 'still_image' ? '🖼 Still Image' : '🎬 Video Clip'}
            </span>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Source</label>
          <select
            value={source}
            onChange={e => setSource(e.target.value)}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors"
          >
            {ASSET_SOURCES.map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>

        <Input
          label="Description (optional)"
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="e.g. Dark rainy window at night"
        />

        <Input
          label="Keywords (comma-separated, optional)"
          value={keywords}
          onChange={e => setKeywords(e.target.value)}
          placeholder="rain, dark, window, night"
        />
      </div>
    </Modal>
  )
}
```

- [ ] **Step 3: Add state + button to VideoAssetsPage**

In `VideoAssetsPage`, add the import modal state near the other state declarations (after `const [toast, setToast] = useState(null)`):

```jsx
const [showImport, setShowImport] = useState(false)
```

In the page header section, add the Import button next to the title. The header `div` currently looks like:

```jsx
<div>
  <h1 className="text-xl font-bold text-[#e8e8f0]">Video Assets</h1>
  <p className="text-sm text-[#9090a8] mt-0.5">
    Manage video clips downloaded from Pexels or generated by Veo
  </p>
</div>
```

Wrap it and add the button:

```jsx
<div className="flex items-center justify-between">
  <div>
    <h1 className="text-xl font-bold text-[#e8e8f0]">Video Assets</h1>
    <p className="text-sm text-[#9090a8] mt-0.5">
      Manage video clips downloaded from Pexels or generated by Veo
    </p>
  </div>
  <Button variant="primary" onClick={() => setShowImport(true)}>+ Import Asset</Button>
</div>
```

At the bottom of the component's return, before the closing `</div>`, add the modal after the existing modals:

```jsx
{showImport && (
  <ImportAssetModal
    onClose={() => setShowImport(false)}
    onImported={refetch}
  />
)}
```

- [ ] **Step 4: Verify in browser**

1. Navigate to Assets page
2. Click "Import Asset"
3. Select a JPG or PNG file
4. Confirm "Still Image" type is detected
5. Select source "midjourney", add description/keywords
6. Click Import → confirm new asset appears in the table with correct source badge

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/api/client.js \
        console/frontend/src/pages/VideoAssetsPage.jsx
git commit -m "feat: add asset import modal to VideoAssetsPage"
```

---

## Task 6: YouTube Creation — Inline Upload Panels

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

- [ ] **Step 1: Add music upload state + panel to CreationPanel**

In `YouTubeVideosPage.jsx`, inside the `CreationPanel` component, add new state after the existing state declarations:

```jsx
const [showMusicUpload,    setShowMusicUpload]    = useState(false)
const [musicUploadFile,    setMusicUploadFile]    = useState(null)
const [musicUploadTitle,   setMusicUploadTitle]   = useState('')
const [musicUploading,     setMusicUploading]     = useState(false)
```

Add this helper inside `CreationPanel` (before the `return`):

```jsx
const handleMusicUpload = async () => {
  if (!musicUploadFile || !musicUploadTitle) return
  setMusicUploading(true)
  try {
    const track = await musicApi.upload(musicUploadFile, {
      title: musicUploadTitle,
      niches: [], moods: [], genres: [],
      is_vocal: false,
      volume: 0.15,
      quality_score: 80,
    })
    setMusicList(prev => [...prev, track])
    setForm(f => ({ ...f, music_track_id: String(track.id) }))
    setShowMusicUpload(false)
    setMusicUploadFile(null)
    setMusicUploadTitle('')
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    setMusicUploading(false)
  }
}
```

In the `② MUSIC` section JSX, replace the current content:

```jsx
{/* ② MUSIC */}
<section>
  <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">② MUSIC</div>
  <div className="flex flex-col gap-3">
    <div className="flex items-center gap-2">
      <div className="flex-1">
        <Select
          label="Music Track"
          value={form.music_track_id || ''}
          onChange={e => setForm(f => ({ ...f, music_track_id: e.target.value || null }))}
        >
          <option value="">— Select from library —</option>
          {musicList.map(m => (
            <option key={m.id} value={m.id}>{m.title} ({m.provider})</option>
          ))}
        </Select>
      </div>
      <button
        type="button"
        onClick={() => setShowMusicUpload(v => !v)}
        className={`mt-5 px-3 py-1.5 rounded-lg text-xs border transition-colors flex-shrink-0 ${
          showMusicUpload
            ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
            : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
        }`}
      >
        Upload
      </button>
    </div>

    {showMusicUpload && (
      <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 flex flex-col gap-3">
        <div className="text-xs text-[#5a5a70] font-medium">Upload Music File</div>
        <Input
          label="Title"
          value={musicUploadTitle}
          onChange={e => setMusicUploadTitle(e.target.value)}
          placeholder="e.g. Heavy Rain ASMR Track"
        />
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">File (mp3 / wav / m4a)</label>
          <input
            type="file"
            accept=".mp3,.wav,.m4a,.ogg"
            onChange={e => {
              const f = e.target.files?.[0] || null
              setMusicUploadFile(f)
              if (f && !musicUploadTitle) setMusicUploadTitle(f.name.replace(/\.[^.]+$/, ''))
            }}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        </div>
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" size="sm" onClick={() => setShowMusicUpload(false)}>Cancel</Button>
          <Button
            variant="primary"
            size="sm"
            loading={musicUploading}
            disabled={!musicUploadFile || !musicUploadTitle}
            onClick={handleMusicUpload}
          >
            Upload &amp; Link
          </Button>
        </div>
      </div>
    )}

    {template?.suno_prompt_template && (
      <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
        <div className="text-xs text-[#5a5a70] mb-1">Suno Prompt (reference)</div>
        <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
          {template.suno_prompt_template}
        </p>
        <button
          onClick={() => navigator.clipboard.writeText(template.suno_prompt_template)}
          className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
        >
          Copy
        </button>
      </div>
    )}
  </div>
</section>
```

- [ ] **Step 2: Add visual upload state + panel to CreationPanel**

Add new state after the music upload state:

```jsx
const [showVisualUpload,   setShowVisualUpload]   = useState(false)
const [visualUploadFile,   setVisualUploadFile]   = useState(null)
const [visualUploadDesc,   setVisualUploadDesc]   = useState('')
const [visualUploadSrc,    setVisualUploadSrc]    = useState('manual')
const [visualUploading,    setVisualUploading]    = useState(false)
```

Add this helper inside `CreationPanel` (before the `return`):

```jsx
const handleVisualUpload = async () => {
  if (!visualUploadFile) return
  setVisualUploading(true)
  try {
    const asset = await assetsApi.upload(visualUploadFile, {
      source: visualUploadSrc,
      description: visualUploadDesc,
      keywords: '',
    })
    setAssetList(prev => [...prev, asset])
    setForm(f => ({ ...f, visual_asset_id: String(asset.id) }))
    setShowVisualUpload(false)
    setVisualUploadFile(null)
    setVisualUploadDesc('')
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    setVisualUploading(false)
  }
}
```

Add `assetsApi` to the import at the top of `YouTubeVideosPage.jsx`:

```jsx
// Before
import { youtubeVideosApi, musicApi, assetsApi } from '../api/client.js'
```

(It's already imported — no change needed.)

- [ ] **Step 3: Update the `③ VISUAL` section JSX**

Replace the current `③ VISUAL` section content:

```jsx
{/* ③ VISUAL */}
<section>
  <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">③ VISUAL</div>
  <div className="flex flex-col gap-3">
    <div className="flex items-center gap-2">
      <div className="flex-1">
        <Select
          label="Visual Loop"
          value={form.visual_asset_id || ''}
          onChange={e => setForm(f => ({ ...f, visual_asset_id: e.target.value || null }))}
        >
          <option value="">— Select from library —</option>
          {assetList.map(a => (
            <option key={a.id} value={a.id}>
              {a.description || `Asset #${a.id}`} ({a.source})
            </option>
          ))}
        </Select>
      </div>
      <button
        type="button"
        onClick={() => setShowVisualUpload(v => !v)}
        className={`mt-5 px-3 py-1.5 rounded-lg text-xs border transition-colors flex-shrink-0 ${
          showVisualUpload
            ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
            : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
        }`}
      >
        Upload
      </button>
    </div>

    {showVisualUpload && (
      <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 flex flex-col gap-3">
        <div className="text-xs text-[#5a5a70] font-medium">Upload Visual Asset</div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">File <span className="text-[#5a5a70]">(jpg / png / webp / mp4 / mov)</span></label>
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm"
            onChange={e => setVisualUploadFile(e.target.files?.[0] || null)}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Source</label>
          <select
            value={visualUploadSrc}
            onChange={e => setVisualUploadSrc(e.target.value)}
            className="bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7] transition-colors"
          >
            {['manual', 'midjourney', 'runway', 'pexels', 'veo', 'stock'].map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
        <Input
          label="Description (optional)"
          value={visualUploadDesc}
          onChange={e => setVisualUploadDesc(e.target.value)}
          placeholder="e.g. Rain on window loop"
        />
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" size="sm" onClick={() => setShowVisualUpload(false)}>Cancel</Button>
          <Button
            variant="primary"
            size="sm"
            loading={visualUploading}
            disabled={!visualUploadFile}
            onClick={handleVisualUpload}
          >
            Upload &amp; Link
          </Button>
        </div>
      </div>
    )}

    {template?.runway_prompt_template && (
      <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
        <div className="text-xs text-[#5a5a70] mb-1">Runway Prompt (reference)</div>
        <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
          {template.runway_prompt_template}
        </p>
        <button
          onClick={() => navigator.clipboard.writeText(template.runway_prompt_template)}
          className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
        >
          Copy
        </button>
      </div>
    )}
  </div>
</section>
```

- [ ] **Step 4: Verify in browser**

1. Navigate to YouTube Videos page, click "+ New ASMR"
2. In the `② MUSIC` section, click "Upload"
3. Select an audio file, set a title, click "Upload & Link"
4. Confirm the track auto-appears in the dropdown selected
5. In the `③ VISUAL` section, click "Upload"
6. Select an image or video file, set source to "midjourney", click "Upload & Link"
7. Confirm the asset auto-appears in the dropdown selected

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: inline music and visual upload panels in YouTube creation panel"
```
