# Asset Thumbnail Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and serve thumbnail previews for all asset types — images serve themselves, videos get a JPEG frame extracted at 1 second by ffmpeg — with lazy generation for existing assets and immediate generation on upload.

**Architecture:** A new `generate_video_thumbnail()` utility in `production_service.py` wraps ffmpeg and is called synchronously in `import_asset()` for new uploads. A new `GET /assets/{id}/thumbnail` endpoint serves the thumbnail file and optionally triggers lazy generation (suppressed by `?generate=false` for use by AssetBrowser). The frontend always renders `<img>` elements pointed at the endpoint, using `onError` for graceful fallback.

**Tech Stack:** Python subprocess (ffmpeg), FastAPI FileResponse, React `<img>` onError, mimetypes stdlib

---

## File Map

| File | Change |
|------|--------|
| `console/backend/services/production_service.py` | Add `generate_video_thumbnail()`, update `import_asset()` |
| `console/backend/routers/production.py` | Add `GET /assets/{id}/thumbnail` endpoint |
| `console/frontend/src/api/client.js` | Update `thumbnailUrl()` to accept `{ generate }` option |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | Replace conditional thumbnail with always-render `<img>` |
| `console/frontend/src/components/AssetBrowser.jsx` | Replace conditional thumbnail with always-render `<img generate=false>` |
| `tests/test_thumbnail_generation.py` | Tests for `generate_video_thumbnail()` and updated `import_asset()` |
| `tests/test_thumbnail_endpoint.py` | Tests for the new thumbnail endpoint |

---

## Task 1: `generate_video_thumbnail()` utility

**Files:**
- Modify: `console/backend/services/production_service.py`
- Create: `tests/test_thumbnail_generation.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_thumbnail_generation.py`:

```python
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_generate_thumbnail_returns_path_on_success(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_1.mp4"
    video.write_bytes(b"\x00" * 16)
    thumb = tmp_path / "asset_1_thumb.jpg"
    thumb.write_bytes(b"\xff\xd8\xff")  # fake JPEG so is_file() is True

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = generate_video_thumbnail(str(video))

    assert result == str(thumb)


def test_generate_thumbnail_returns_none_on_ffmpeg_failure(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_2.mp4"
    video.write_bytes(b"\x00" * 16)

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = generate_video_thumbnail(str(video))

    assert result is None


def test_generate_thumbnail_returns_none_when_ffmpeg_missing(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_3.mp4"
    video.write_bytes(b"\x00" * 16)

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError
        result = generate_video_thumbnail(str(video))

    assert result is None


def test_generate_thumbnail_returns_none_on_timeout(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "asset_4.mp4"
    video.write_bytes(b"\x00" * 16)

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)
        result = generate_video_thumbnail(str(video))

    assert result is None


def test_generate_thumbnail_uses_correct_ffmpeg_args(tmp_path):
    from console.backend.services.production_service import generate_video_thumbnail
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 16)
    thumb = tmp_path / "clip_thumb.jpg"
    thumb.write_bytes(b"\xff\xd8\xff")

    with patch("console.backend.services.production_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        generate_video_thumbnail(str(video))

    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "ffmpeg"
    assert "-ss" in call_args
    assert "1" in call_args
    assert str(thumb) in call_args
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_thumbnail_generation.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` — `generate_video_thumbnail` does not exist yet.

- [ ] **Step 3: Add `generate_video_thumbnail()` to `production_service.py`**

Add `import subprocess` at the top of `console/backend/services/production_service.py` (alongside existing imports), then add this function at module level just before the `ProductionService` class:

```python
import subprocess


def generate_video_thumbnail(video_path: str) -> str | None:
    p = Path(video_path)
    thumb_path = p.parent / f"{p.stem}_thumb.jpg"
    try:
        result = subprocess.run(
            ["ffmpeg", "-ss", "1", "-i", str(p), "-frames:v", "1", "-q:v", "2", str(thumb_path), "-y"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and thumb_path.is_file():
            return str(thumb_path)
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_thumbnail_generation.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/production_service.py tests/test_thumbnail_generation.py
git commit -m "feat: add generate_video_thumbnail utility (ffmpeg @ 1s)"
```

---

## Task 2: Update `import_asset()` to set `thumbnail_path`

**Files:**
- Modify: `console/backend/services/production_service.py`
- Modify: `tests/test_thumbnail_generation.py`

- [ ] **Step 1: Add failing tests for updated `import_asset()` behaviour**

Append to `tests/test_thumbnail_generation.py`:

```python
def test_import_image_sets_thumbnail_path_to_file_path(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    svc = ProductionService(db)
    result = svc.import_asset(
        file_bytes=b"\xff\xd8\xff" + b"\x00" * 20,
        filename="photo.jpg",
        source="midjourney",
        description=None,
        keywords=None,
        assets_dir=tmp_path,
    )
    assert result["thumbnail_url"] == result["file_path"]


def test_import_video_sets_thumbnail_path_when_ffmpeg_succeeds(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    svc = ProductionService(db)

    def fake_generate(video_path):
        thumb = Path(video_path).parent / (Path(video_path).stem + "_thumb.jpg")
        thumb.write_bytes(b"\xff\xd8\xff")
        return str(thumb)

    with patch("console.backend.services.production_service.generate_video_thumbnail", side_effect=fake_generate):
        result = svc.import_asset(
            file_bytes=b"\x00\x00\x00\x18ftyp" + b"\x00" * 40,
            filename="loop.mp4",
            source="manual",
            description=None,
            keywords=None,
            assets_dir=tmp_path,
        )

    assert result["thumbnail_url"] is not None
    assert result["thumbnail_url"].endswith("_thumb.jpg")


def test_import_video_thumbnail_path_none_when_ffmpeg_fails(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    svc = ProductionService(db)

    with patch("console.backend.services.production_service.generate_video_thumbnail", return_value=None):
        result = svc.import_asset(
            file_bytes=b"\x00\x00\x00\x18ftyp" + b"\x00" * 40,
            filename="loop.mp4",
            source="manual",
            description=None,
            keywords=None,
            assets_dir=tmp_path,
        )

    assert result["thumbnail_url"] is None
    assert result["id"] is not None  # upload still succeeded
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_thumbnail_generation.py::test_import_image_sets_thumbnail_path_to_file_path tests/test_thumbnail_generation.py::test_import_video_sets_thumbnail_path_when_ffmpeg_succeeds tests/test_thumbnail_generation.py::test_import_video_thumbnail_path_none_when_ffmpeg_fails -v
```

Expected: FAIL — `thumbnail_url` is `None` for images and videos.

- [ ] **Step 3: Update `import_asset()` in `production_service.py`**

Find the block after `dest.write_bytes(file_bytes)` and `row.file_path = str(dest)` (around line 183-184) and add thumbnail logic before the `_audit` call:

```python
        dest.write_bytes(file_bytes)
        row.file_path = str(dest)

        # Set thumbnail_path based on asset type
        if asset_type == 'still_image':
            row.thumbnail_path = str(dest)
        elif asset_type == 'video_clip':
            row.thumbnail_path = generate_video_thumbnail(str(dest))

        if user_id is not None:
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_thumbnail_generation.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/production_service.py tests/test_thumbnail_generation.py
git commit -m "feat: set thumbnail_path during import_asset for images and videos"
```

---

## Task 3: Add `GET /api/production/assets/{id}/thumbnail` endpoint

**Files:**
- Modify: `console/backend/routers/production.py`
- Create: `tests/test_thumbnail_endpoint.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_thumbnail_endpoint.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import patch
from console.backend.models.video_asset import VideoAsset


def _make_asset(db, tmp_path, asset_type="video_clip", with_thumb=False):
    video_file = tmp_path / "asset_99.mp4"
    video_file.write_bytes(b"\x00" * 16)
    thumb_file = tmp_path / "asset_99_thumb.jpg"
    if with_thumb:
        thumb_file.write_bytes(b"\xff\xd8\xff")

    asset = VideoAsset(
        file_path=str(video_file),
        thumbnail_path=str(thumb_file) if with_thumb else None,
        source="manual",
        asset_type=asset_type,
        keywords=[],
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _make_image_asset(db, tmp_path):
    img_file = tmp_path / "asset_88.jpg"
    img_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 20)
    asset = VideoAsset(
        file_path=str(img_file),
        thumbnail_path=None,
        source="midjourney",
        asset_type="still_image",
        keywords=[],
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def test_thumbnail_serves_existing_thumb(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_asset(db, tmp_path, with_thumb=True)
    svc = ProductionService(db)
    path, media_type = svc.get_thumbnail_path(asset.id, generate=True)
    assert path == asset.thumbnail_path
    assert "image" in media_type


def test_thumbnail_returns_none_when_no_thumb_and_generate_false(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_asset(db, tmp_path, with_thumb=False)
    svc = ProductionService(db)
    result = svc.get_thumbnail_path(asset.id, generate=False)
    assert result is None


def test_thumbnail_generates_lazily_for_video(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_asset(db, tmp_path, with_thumb=False)

    def fake_generate(video_path):
        thumb = tmp_path / "asset_99_thumb.jpg"
        thumb.write_bytes(b"\xff\xd8\xff")
        return str(thumb)

    with patch("console.backend.services.production_service.generate_video_thumbnail", side_effect=fake_generate):
        svc = ProductionService(db)
        result = svc.get_thumbnail_path(asset.id, generate=True)

    assert result is not None
    path, media_type = result
    assert path.endswith("_thumb.jpg")
    db.refresh(asset)
    assert asset.thumbnail_path == path  # persisted to DB


def test_thumbnail_lazy_for_still_image(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_image_asset(db, tmp_path)
    svc = ProductionService(db)
    result = svc.get_thumbnail_path(asset.id, generate=True)
    assert result is not None
    path, _ = result
    assert path == asset.file_path
    db.refresh(asset)
    assert asset.thumbnail_path == path  # persisted


def test_thumbnail_returns_none_for_missing_asset(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    svc = ProductionService(db)
    result = svc.get_thumbnail_path(99999, generate=True)
    assert result is None
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_thumbnail_endpoint.py -v 2>&1 | head -20
```

Expected: `ImportError` — `get_thumbnail_path` does not exist yet.

- [ ] **Step 3: Add `get_thumbnail_path()` to `ProductionService`**

Add this method to the `ProductionService` class in `console/backend/services/production_service.py`:

```python
    def get_thumbnail_path(self, asset_id: int, generate: bool) -> tuple[str, str] | None:
        import mimetypes
        asset = self.db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            return None

        # Serve existing thumbnail
        if asset.thumbnail_path and Path(asset.thumbnail_path).is_file():
            media_type, _ = mimetypes.guess_type(asset.thumbnail_path)
            return (asset.thumbnail_path, media_type or "image/jpeg")

        if not generate:
            return None

        # Lazy generation for videos
        if asset.asset_type == 'video_clip':
            if not Path(asset.file_path).is_file():
                return None
            thumb_path = generate_video_thumbnail(asset.file_path)
            if thumb_path is None:
                return None
            if asset.thumbnail_path is None:  # race condition guard
                asset.thumbnail_path = thumb_path
                self.db.commit()
            return (thumb_path, "image/jpeg")

        # Still images serve themselves
        if asset.asset_type == 'still_image':
            if not Path(asset.file_path).is_file():
                return None
            if asset.thumbnail_path is None:
                asset.thumbnail_path = asset.file_path
                self.db.commit()
            media_type, _ = mimetypes.guess_type(asset.file_path)
            return (asset.file_path, media_type or "image/jpeg")

        return None
```

- [ ] **Step 4: Run service tests to verify they pass**

```bash
python -m pytest tests/test_thumbnail_endpoint.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Add the endpoint to `production.py`**

Insert this endpoint in `console/backend/routers/production.py` immediately after the existing `stream_asset` endpoint (after line ~82). The existing imports already include `FileResponse` and `Path`:

```python
@router.get("/assets/{asset_id}/thumbnail")
def get_asset_thumbnail(
    asset_id: int,
    generate: bool = True,
    db: Session = Depends(get_db),
):
    result = ProductionService(db).get_thumbnail_path(asset_id, generate=generate)
    if result is None:
        raise HTTPException(status_code=404, detail="No thumbnail available")
    path, media_type = result
    return FileResponse(str(path), media_type=media_type)
```

- [ ] **Step 6: Run all thumbnail tests**

```bash
python -m pytest tests/test_thumbnail_generation.py tests/test_thumbnail_endpoint.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add console/backend/services/production_service.py console/backend/routers/production.py tests/test_thumbnail_endpoint.py
git commit -m "feat: add GET /api/production/assets/{id}/thumbnail endpoint with lazy generation"
```

---

## Task 4: Update `client.js` `thumbnailUrl()` to support `generate=false`

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Update `thumbnailUrl` in `client.js`**

Find line 156 in `console/frontend/src/api/client.js`:

```js
  thumbnailUrl: (id) => `/api/production/assets/${id}/thumbnail`,
```

Replace with:

```js
  thumbnailUrl: (id, { generate = true } = {}) =>
    generate
      ? `/api/production/assets/${id}/thumbnail`
      : `/api/production/assets/${id}/thumbnail?generate=false`,
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: thumbnailUrl() accepts { generate: false } to suppress lazy generation"
```

---

## Task 5: Update `VideoAssetsPage.jsx` thumbnail display

**Files:**
- Modify: `console/frontend/src/pages/VideoAssetsPage.jsx`

The page currently conditionally renders an emoji placeholder when `asset.thumbnail_url` is falsy. We replace this with an always-rendered `<img>` that hits the thumbnail endpoint (which triggers lazy generation for old video assets). Two spots to update.

- [ ] **Step 1: Update the assets table thumbnail cell (line ~591)**

Find this block in `console/frontend/src/pages/VideoAssetsPage.jsx`:

```jsx
                      {asset.thumbnail_url ? (
                        <img
                          src={asset.thumbnail_url}
                          alt="thumbnail"
                          className="w-16 h-9 object-cover rounded bg-[#0d0d0f]"
                        />
                      ) : (
                        <div className="w-16 h-9 flex items-center justify-center bg-[#0d0d0f] rounded text-xl">
                          🎬
                        </div>
                      )}
```

Replace with:

```jsx
                      <img
                        src={assetsApi.thumbnailUrl(asset.id)}
                        alt="thumbnail"
                        className="w-16 h-9 object-cover rounded bg-[#0d0d0f]"
                        onError={e => { e.currentTarget.style.display = 'none' }}
                      />
```

- [ ] **Step 2: Update the animate modal preview (line ~206)**

Find this block:

```jsx
        {asset.thumbnail_url && (
          <img src={assetsApi.thumbnailUrl(asset.id)} alt={asset.description} className="w-full h-32 object-cover rounded-lg" />
        )}
```

Replace with:

```jsx
        <img
          src={assetsApi.thumbnailUrl(asset.id)}
          alt={asset.description}
          className="w-full h-32 object-cover rounded-lg"
          onError={e => { e.currentTarget.style.display = 'none' }}
        />
```

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/VideoAssetsPage.jsx
git commit -m "feat: always render thumbnail img in VideoAssetsPage, lazy-generating for old assets"
```

---

## Task 6: Update `AssetBrowser.jsx` thumbnail display

**Files:**
- Modify: `console/frontend/src/components/AssetBrowser.jsx`

AssetBrowser is used for picking scene assets in the script editor. It must NOT trigger thumbnail generation — it passes `generate=false`.

- [ ] **Step 1: Update thumbnail display in `AssetBrowser.jsx` (line ~89)**

Find this block in `console/frontend/src/components/AssetBrowser.jsx`:

```jsx
                <div className="bg-[#0d0d0f] aspect-[9/16] flex items-center justify-center">
                  {asset.thumbnail_url ? (
                    <img
                      src={asset.thumbnail_url}
                      alt={asset.keywords?.join(', ')}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-[#5a5a70] text-xs font-mono p-2 text-center">
                      {asset.source || 'asset'}
                    </div>
                  )}
                </div>
```

Replace with:

```jsx
                <div className="bg-[#0d0d0f] aspect-[9/16] flex items-center justify-center">
                  <img
                    src={assetsApi.thumbnailUrl(asset.id, { generate: false })}
                    alt={asset.keywords?.join(', ')}
                    className="w-full h-full object-cover"
                    onError={e => { e.currentTarget.style.display = 'none' }}
                  />
                </div>
```

- [ ] **Step 2: Verify `assetsApi` is already imported at the top of `AssetBrowser.jsx`**

```bash
grep -n "assetsApi\|import.*client" /Volumes/SSD/Workspace/ai-media-automation/console/frontend/src/components/AssetBrowser.jsx | head -5
```

If `assetsApi` is not imported, add it:

```js
import { assetsApi } from '../api/client'
```

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/components/AssetBrowser.jsx
git commit -m "feat: AssetBrowser shows thumbnails without triggering generation"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Images serve themselves as thumbnail (Task 2: `import_asset` sets `thumbnail_path = file_path`)
- ✅ Videos get ffmpeg thumbnail at upload (Task 1 + Task 2)
- ✅ Lazy generation for old video assets (Task 3: endpoint generates when `thumbnail_path` is null)
- ✅ AssetBrowser suppresses generation (Task 4 + Task 6: `generate=false`)
- ✅ New endpoint served at `/api/production/assets/{id}/thumbnail` (Task 3)
- ✅ Thumbnail stored alongside video file (Task 1: `{stem}_thumb.jpg` in same directory)
- ✅ ffmpeg seeks to 1-second mark (Task 1: `-ss 1`)
- ✅ Race condition guard (Task 3: checks `thumbnail_path is None` before writing)
- ✅ ffmpeg failure does not break upload (Task 2: `thumbnail_path` may be `None`)

**Type consistency:**
- `get_thumbnail_path()` returns `tuple[str, str] | None` — used correctly in the endpoint
- `generate_video_thumbnail()` returns `str | None` — used correctly in `import_asset()` and `get_thumbnail_path()`
- `thumbnailUrl(id, { generate })` — used with `{ generate: false }` in AssetBrowser; called without options in VideoAssetsPage (defaults to `generate=true`)
