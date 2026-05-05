# YouTube Thumbnail Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Midjourney image upload + optional text overlay thumbnail generation to the YouTube video pipeline, with the thumbnail automatically set on YouTube at upload time.

**Architecture:** A new `pipeline/youtube_thumbnail.py` utility exposes `generate_thumbnail()` — the existing `make_youtube_thumbnail.py` CLI becomes a thin wrapper around it. The console backend gains four endpoints on `youtube_videos.py` router for upload/generate/serve. The Celery upload task calls `set_thumbnail()` after a successful YouTube upload. The creation/edit panel in `YouTubeVideosPage.jsx` gets a thumbnail section with file input, text input, and inline preview. Video cards show the thumbnail when available.

**Tech Stack:** Python 3.11 · Pillow (already a dep) · FastAPI `UploadFile` · SQLAlchemy · Google YouTube Data API v3 `thumbnails().set()` · React 18 / Vite

---

## File Map

| File | Change |
|---|---|
| `pipeline/youtube_thumbnail.py` | **Create** — `generate_thumbnail()` + all rendering helpers |
| `make_youtube_thumbnail.py` | **Modify** — thin CLI wrapper delegating to `pipeline.youtube_thumbnail` |
| `console/backend/alembic/versions/016_youtube_thumbnail.py` | **Create** — adds 3 columns to `youtube_videos` |
| `console/backend/models/youtube_video.py` | **Modify** — add 3 `Mapped` fields |
| `console/backend/services/youtube_video_service.py` | **Modify** — `_video_to_dict` exposes 3 new fields |
| `console/backend/routers/youtube_videos.py` | **Modify** — `ThumbnailGenerateRequest` + 4 new endpoints |
| `uploader/youtube_uploader.py` | **Modify** — add `set_thumbnail()` function |
| `console/backend/tasks/youtube_upload_task.py` | **Modify** — call `set_thumbnail` after upload |
| `console/frontend/src/api/client.js` | **Modify** — 3 new methods on `youtubeVideosApi` |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | **Modify** — thumbnail section in form + card image |
| `tests/test_youtube_thumbnail.py` | **Create** — unit tests for `generate_thumbnail` |
| `tests/test_youtube_uploader.py` | **Modify** — add `set_thumbnail` tests |
| `tests/test_youtube_upload_task.py` | **Modify** — thumbnail path tests |
| `tests/test_youtube_video_service_thumbnail.py` | **Create** — `_video_to_dict` thumbnail field tests |

---

### Task 1: Thumbnail generation utility

**Files:**
- Create: `pipeline/youtube_thumbnail.py`
- Modify: `make_youtube_thumbnail.py`
- Test: `tests/test_youtube_thumbnail.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_youtube_thumbnail.py
import pytest
from pathlib import Path


def _make_tiny_image(tmp_path: Path) -> Path:
    from PIL import Image
    p = tmp_path / "source.jpg"
    Image.new("RGB", (100, 100), color=(200, 50, 50)).save(p)
    return p


def test_generate_thumbnail_no_text_resizes_to_1280x720(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "out.png"
    result = generate_thumbnail(src, out, text=None)
    from PIL import Image
    assert result == out
    assert out.exists()
    assert Image.open(out).size == (1280, 720)


def test_generate_thumbnail_empty_string_resizes_only(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "out.png"
    generate_thumbnail(src, out, text="")
    from PIL import Image
    assert Image.open(out).size == (1280, 720)


def test_generate_thumbnail_creates_parent_dirs(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "a" / "b" / "c" / "out.png"
    generate_thumbnail(src, out, text=None)
    assert out.exists()


def test_generate_thumbnail_with_text_correct_size(tmp_path):
    from pipeline.youtube_thumbnail import generate_thumbnail, DEFAULT_REGULAR_FONT
    if not DEFAULT_REGULAR_FONT.exists():
        pytest.skip("System font not available in this environment")
    src = _make_tiny_image(tmp_path)
    out = tmp_path / "out.png"
    generate_thumbnail(src, out, text="DEEP FOCUS")
    from PIL import Image
    assert Image.open(out).size == (1280, 720)


def test_split_text_single_word():
    from pipeline.youtube_thumbnail import split_text
    assert split_text("FOCUS") == ["FOCUS"]


def test_split_text_three_words():
    from pipeline.youtube_thumbnail import split_text
    assert split_text("DEEP SLEEP MUSIC") == ["DEEP", "SLEEP", "MUSIC"]


def test_split_text_four_words_third_line_joins_remainder():
    from pipeline.youtube_thumbnail import split_text
    assert split_text("DEEP FOCUS STUDY MUSIC") == ["DEEP", "FOCUS", "STUDY MUSIC"]


def test_cover_resize_landscape_to_1280x720():
    from pipeline.youtube_thumbnail import cover_resize
    from PIL import Image
    result = cover_resize(Image.new("RGB", (2560, 1440)), (1280, 720))
    assert result.size == (1280, 720)


def test_cover_resize_portrait_to_1280x720():
    from pipeline.youtube_thumbnail import cover_resize
    from PIL import Image
    result = cover_resize(Image.new("RGB", (1080, 1920)), (1280, 720))
    assert result.size == (1280, 720)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_youtube_thumbnail.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'pipeline.youtube_thumbnail'`

- [ ] **Step 3: Create `pipeline/youtube_thumbnail.py`**

```python
"""Thumbnail generation utility for YouTube videos.

Canonical entry point: generate_thumbnail().
make_youtube_thumbnail.py delegates to this module as a thin CLI wrapper.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

THUMBNAIL_SIZE = (1280, 720)
DEFAULT_REGULAR_FONT = Path("/System/Library/Fonts/SFNS.ttf")
DEFAULT_BOLD_FONT = Path("/System/Library/Fonts/SFNS.ttf")


def split_text(text: str) -> list[str]:
    words = text.strip().split()
    if not words:
        raise ValueError("Text cannot be empty.")
    if len(words) <= 3:
        return words
    return [words[0], words[1], " ".join(words[2:])]


def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize(
        (round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS
    )
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def load_font(path: Path, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    if not path.exists():
        raise FileNotFoundError(f"Font file not found: {path}")
    font = ImageFont.truetype(str(path), size=size)
    if variation:
        try:
            font.set_variation_by_name(variation)
        except (AttributeError, OSError, ValueError):
            pass
    return font


def measure_lines(
    draw: ImageDraw.ImageDraw,
    lines: Iterable[str],
    font_size: int,
    regular_font_path: Path,
    bold_font_path: Path,
    bold_first_word: bool,
) -> tuple[int, int, list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]]:
    measured = []
    widths: list[int] = []
    heights: list[int] = []
    stroke_width = max(2, round(font_size * 0.045))
    spacing = max(8, round(font_size * 0.17))

    for index, line in enumerate(lines):
        is_bold = index == 0 and bold_first_word
        font_path = bold_font_path if is_bold else regular_font_path
        font = load_font(font_path, font_size, "Bold" if is_bold else "Regular")
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
        measured.append((line, font, stroke_width, bbox))

    total_height = sum(heights) + spacing * max(0, len(heights) - 1)
    return max(widths), total_height, measured


def fit_text(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    regular_font_path: Path,
    bold_font_path: Path,
    bold_first_word: bool,
    max_width: int,
    max_height: int,
    preferred_size: int,
    min_size: int,
) -> tuple[int, int, list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]]:
    for font_size in range(preferred_size, min_size - 1, -2):
        width, height, measured = measure_lines(
            draw, lines, font_size, regular_font_path, bold_font_path, bold_first_word
        )
        if width <= max_width and height <= max_height:
            return font_size, height, measured
    raise ValueError(
        f"Text is too large to fit. Try shorter text or lower min_font_size below {min_size}."
    )


def generate_thumbnail(
    source_path: Path | str,
    output_path: Path | str,
    text: str | None = None,
    font: Path = DEFAULT_REGULAR_FONT,
    bold_font: Path = DEFAULT_BOLD_FONT,
    bold_first_word: bool = True,
    preferred_font_size: int = 162,
    min_font_size: int = 48,
    margin_x: int = 58,
    margin_bottom: int = 48,
    fill: str = "#F7F2E8",
    stroke_fill: str = "#06100C",
) -> Path:
    """Generate a 1280×720 YouTube thumbnail PNG.

    text=None or empty: cover-resize only, no overlay.
    text provided: resize then draw text bottom-left with stroke.
    Returns output_path as a Path.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    image = Image.open(source_path).convert("RGB")
    canvas = cover_resize(image, THUMBNAIL_SIZE)

    if text and text.strip():
        draw = ImageDraw.Draw(canvas)
        lines = split_text(text.upper())
        max_width = THUMBNAIL_SIZE[0] - margin_x * 2
        max_height = THUMBNAIL_SIZE[1] - margin_bottom * 2
        font_size, block_height, measured = fit_text(
            draw, lines, font, bold_font, bold_first_word,
            max_width, max_height, preferred_font_size, min_font_size,
        )
        spacing = max(8, round(font_size * 0.17))
        x = margin_x
        y = THUMBNAIL_SIZE[1] - margin_bottom - block_height
        for line, line_font, stroke_width, bbox in measured:
            draw.text(
                (x - bbox[0], y - bbox[1]),
                line,
                font=line_font,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
            y += (bbox[3] - bbox[1]) + spacing

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path
```

- [ ] **Step 4: Replace `make_youtube_thumbnail.py` with thin wrapper**

```python
#!/usr/bin/env python3
"""
Create a YouTube thumbnail from an image and overlay large readable text.

Usage:
  python3 make_youtube_thumbnail.py input.png --text "DEEP FOCUS" --output output.png

Text layout:
  - 1 to 3 words: one word per line.
  - More than 3 words: first word on line 1, second word on line 2,
    all remaining words on line 3.
  - The first word is bold by default.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.youtube_thumbnail import (
    DEFAULT_BOLD_FONT,
    DEFAULT_REGULAR_FONT,
    generate_thumbnail,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a YouTube thumbnail with safe bottom-left text."
    )
    parser.add_argument("image", type=Path, help="Input image path.")
    parser.add_argument("--text", required=True, help='Thumbnail text, e.g. "DEEP FOCUS".')
    parser.add_argument("--output", type=Path, default=Path("youtube-thumbnail.png"))
    parser.add_argument("--font", type=Path, default=DEFAULT_REGULAR_FONT)
    parser.add_argument("--bold-font", type=Path, default=DEFAULT_BOLD_FONT)
    parser.add_argument(
        "--no-bold-first-word", dest="no_bold_first_word", action="store_true",
        help="Use regular style for every word.",
    )
    parser.add_argument(
        "--no-bold-first-line", dest="no_bold_first_word", action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--preferred-font-size", type=int, default=162)
    parser.add_argument("--min-font-size", type=int, default=48)
    parser.add_argument("--margin-x", type=int, default=58)
    parser.add_argument("--margin-bottom", type=int, default=48)
    parser.add_argument("--fill", default="#F7F2E8")
    parser.add_argument("--stroke-fill", default="#06100C")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_thumbnail(
        source_path=args.image,
        output_path=args.output,
        text=args.text,
        font=args.font,
        bold_font=args.bold_font,
        bold_first_word=not args.no_bold_first_word,
        preferred_font_size=args.preferred_font_size,
        min_font_size=args.min_font_size,
        margin_x=args.margin_x,
        margin_bottom=args.margin_bottom,
        fill=args.fill,
        stroke_fill=args.stroke_fill,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
python -m pytest tests/test_youtube_thumbnail.py -v
```

Expected: all tests pass (font-dependent test skips on CI if `/System/Library/Fonts/SFNS.ttf` absent).

- [ ] **Step 6: Commit**

```bash
git add pipeline/youtube_thumbnail.py make_youtube_thumbnail.py tests/test_youtube_thumbnail.py
git commit -m "feat: extract generate_thumbnail() into pipeline/youtube_thumbnail.py"
```

---

### Task 2: DB migration + model update

**Files:**
- Create: `console/backend/alembic/versions/016_youtube_thumbnail.py`
- Modify: `console/backend/models/youtube_video.py`

- [ ] **Step 1: Create the migration file**

```python
# console/backend/alembic/versions/016_youtube_thumbnail.py
"""Add thumbnail fields to youtube_videos

Revision ID: 016
Revises: 015
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "thumbnail_asset_id",
            sa.Integer(),
            sa.ForeignKey("video_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("youtube_videos", sa.Column("thumbnail_text", sa.Text(), nullable=True))
    op.add_column("youtube_videos", sa.Column("thumbnail_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("youtube_videos", "thumbnail_path")
    op.drop_column("youtube_videos", "thumbnail_text")
    op.drop_column("youtube_videos", "thumbnail_asset_id")
```

- [ ] **Step 2: Run the migration**

```bash
cd console/backend
alembic upgrade head
```

Expected output ending with: `Running upgrade 015 -> 016`

- [ ] **Step 3: Verify columns exist in DB**

```bash
psql $(grep DATABASE_URL /Volumes/SSD/Workspace/ai-media-automation/console/.env | cut -d= -f2-) \
  -c "\d youtube_videos" | grep thumbnail
```

Expected: 3 rows — `thumbnail_asset_id`, `thumbnail_text`, `thumbnail_path`.

- [ ] **Step 4: Add the three `Mapped` fields to `console/backend/models/youtube_video.py`**

After `visual_loop_mode` (the last field on line 62), add:

```python
    # Thumbnail fields (added by migration 016)
    thumbnail_asset_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("video_assets.id", ondelete="SET NULL"), nullable=True
    )
    thumbnail_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
```

The existing imports already include `Integer`, `Text`, `ForeignKey` — no new imports needed.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/backend/alembic/versions/016_youtube_thumbnail.py console/backend/models/youtube_video.py
git commit -m "feat: add thumbnail_asset_id/text/path columns to youtube_videos (migration 016)"
```

---

### Task 3: `set_thumbnail` in `uploader/youtube_uploader.py`

**Files:**
- Modify: `uploader/youtube_uploader.py`
- Modify: `tests/test_youtube_uploader.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_youtube_uploader.py`:

```python
def test_set_thumbnail_calls_thumbnails_set():
    from unittest.mock import MagicMock, patch
    mock_youtube = MagicMock()
    mock_creds = MagicMock()
    mock_creds.expired = False

    with patch("uploader.youtube_uploader.Credentials", return_value=mock_creds), \
         patch("uploader.youtube_uploader.build", return_value=mock_youtube), \
         patch("uploader.youtube_uploader.MediaFileUpload") as mock_media:
        from uploader.youtube_uploader import set_thumbnail
        set_thumbnail(
            "abc123",
            "/tmp/thumb.png",
            {"access_token": "tok", "refresh_token": "ref", "client_id": "cid", "client_secret": "sec"},
        )

    mock_youtube.thumbnails().set.assert_called_once_with(
        videoId="abc123", media_body=mock_media.return_value
    )
    mock_youtube.thumbnails().set().execute.assert_called_once()


def test_set_thumbnail_has_correct_signature():
    import inspect
    from uploader.youtube_uploader import set_thumbnail
    params = list(inspect.signature(set_thumbnail).parameters.keys())
    assert params == ["platform_video_id", "thumbnail_path", "credentials"]
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_youtube_uploader.py::test_set_thumbnail_calls_thumbnails_set -v
```

Expected: `ImportError: cannot import name 'set_thumbnail'`

- [ ] **Step 3: Add `set_thumbnail` to `uploader/youtube_uploader.py`**

Append after the `upload_to_youtube` alias at the bottom of the file:

```python
def set_thumbnail(platform_video_id: str, thumbnail_path: str | Path, credentials: dict) -> None:
    """Set a custom thumbnail on a YouTube video via the Data API v3.

    Does not raise on API failure — callers should catch and log warnings.
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise RuntimeError(
            "google-api-python-client not installed. "
            "Run: pip install google-api-python-client google-auth"
        )

    creds = Credentials(
        token=credentials.get("access_token"),
        refresh_token=credentials.get("refresh_token"),
        client_id=credentials.get("client_id"),
        client_secret=credentials.get("client_secret"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        logger.info("[YouTube] Token refreshed for thumbnail set")

    youtube = build("youtube", "v3", credentials=creds)
    media = MediaFileUpload(str(thumbnail_path), mimetype="image/png")
    youtube.thumbnails().set(videoId=platform_video_id, media_body=media).execute()
    logger.info("[YouTube] Thumbnail set for video %s", platform_video_id)
```

- [ ] **Step 4: Run all uploader tests**

```bash
python -m pytest tests/test_youtube_uploader.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add uploader/youtube_uploader.py tests/test_youtube_uploader.py
git commit -m "feat: add set_thumbnail() to youtube_uploader"
```

---

### Task 4: `_video_to_dict` update + 4 router endpoints

**Files:**
- Modify: `console/backend/services/youtube_video_service.py`
- Modify: `console/backend/routers/youtube_videos.py`
- Create: `tests/test_youtube_video_service_thumbnail.py`

- [ ] **Step 1: Write failing service tests**

```python
# tests/test_youtube_video_service_thumbnail.py
from unittest.mock import MagicMock


def _make_video(**kwargs):
    v = MagicMock()
    defaults = dict(
        id=1, title="Test", template_id=1, theme=None, status="draft",
        music_track_id=None, visual_asset_id=None, parent_youtube_video_id=None,
        sfx_overrides=None, target_duration_h=1.0, output_quality="1080p",
        seo_title=None, seo_description=None, seo_tags=None, celery_task_id=None,
        output_path=None, music_track_ids=[], sfx_pool=[], sfx_density_seconds=None,
        sfx_seed=None, black_from_seconds=None, skip_previews=True, render_parts=[],
        audio_preview_path=None, video_preview_path=None, visual_asset_ids=[],
        visual_clip_durations_s=[], visual_loop_mode="concat_loop",
        thumbnail_asset_id=None, thumbnail_text=None, thumbnail_path=None,
        created_at=None, updated_at=None,
    )
    defaults.update(kwargs)
    for k, val in defaults.items():
        setattr(v, k, val)
    return v


def test_video_to_dict_includes_thumbnail_fields():
    from console.backend.services.youtube_video_service import _video_to_dict
    v = _make_video(
        thumbnail_asset_id=5,
        thumbnail_text="DEEP FOCUS",
        thumbnail_path="/assets/thumbnails/generated/yt_1.png",
    )
    d = _video_to_dict(v)
    assert d["thumbnail_asset_id"] == 5
    assert d["thumbnail_text"] == "DEEP FOCUS"
    assert d["thumbnail_path"] == "/assets/thumbnails/generated/yt_1.png"


def test_video_to_dict_thumbnail_fields_default_none():
    from console.backend.services.youtube_video_service import _video_to_dict
    v = _make_video()
    d = _video_to_dict(v)
    assert d["thumbnail_asset_id"] is None
    assert d["thumbnail_text"] is None
    assert d["thumbnail_path"] is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python -m pytest tests/test_youtube_video_service_thumbnail.py -v
```

Expected: `KeyError: 'thumbnail_asset_id'`

- [ ] **Step 3: Update `_video_to_dict` in `console/backend/services/youtube_video_service.py`**

Inside `_video_to_dict`, add these three lines immediately before the `"uploads"` key (around line 85):

```python
        "thumbnail_asset_id":  v.thumbnail_asset_id,
        "thumbnail_text":      v.thumbnail_text,
        "thumbnail_path":      v.thumbnail_path,
```

- [ ] **Step 4: Run service tests — verify they pass**

```bash
python -m pytest tests/test_youtube_video_service_thumbnail.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Add imports and schema to `console/backend/routers/youtube_videos.py`**

Change the existing FastAPI import line to add `File` and `UploadFile`:

```python
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
```

Add `import time` to the stdlib imports at the top of the file (after `from pathlib import Path`):

```python
import time
```

Add `ThumbnailGenerateRequest` after the existing `StatusUpdate` schema:

```python
class ThumbnailGenerateRequest(BaseModel):
    text: str | None = None
```

- [ ] **Step 6: Add the four thumbnail endpoints to `console/backend/routers/youtube_videos.py`**

Append all four endpoints at the end of the file:

```python
@router.post("/{video_id}/thumbnail-image", status_code=201)
async def upload_thumbnail_image(
    video_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Upload a Midjourney source image; saves as VideoAsset(source='midjourney')."""
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_asset import VideoAsset

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"YoutubeVideo {video_id} not found")
    if video.status == "published":
        raise HTTPException(status_code=400, detail="Cannot update thumbnail of a published video")

    content = await image.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

    filename = image.filename or "thumbnail.jpg"
    ext = Path(filename).suffix.lower() or ".jpg"
    save_dir = Path("assets/thumbnails/source")
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"yt_{video_id}_{int(time.time())}{ext}"
    save_path.write_bytes(content)

    asset = VideoAsset(
        file_path=str(save_path),
        source="midjourney",
        asset_type="still_image",
        description=f"Thumbnail source for YouTube video {video_id}",
    )
    db.add(asset)
    db.flush()
    video.thumbnail_asset_id = asset.id
    db.commit()
    db.refresh(asset)

    return {"asset_id": asset.id, "source_url": f"/api/youtube-videos/{video_id}/thumbnail-source"}


@router.post("/{video_id}/thumbnail-generate")
def generate_thumbnail_endpoint(
    video_id: int,
    body: ThumbnailGenerateRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    """Generate (or regenerate) the thumbnail PNG from the uploaded source image."""
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_asset import VideoAsset
    from pipeline.youtube_thumbnail import generate_thumbnail

    video = db.get(YoutubeVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"YoutubeVideo {video_id} not found")
    if not video.thumbnail_asset_id:
        raise HTTPException(status_code=400, detail="No thumbnail image uploaded yet")

    text = body.text
    if text and len(text.strip().split()) > 5:
        raise HTTPException(status_code=400, detail="Thumbnail text must be 5 words or fewer")

    asset = db.get(VideoAsset, video.thumbnail_asset_id)
    if not asset:
        raise HTTPException(status_code=400, detail="Thumbnail source asset not found")

    output_path = Path(f"assets/thumbnails/generated/yt_{video_id}.png")
    try:
        generate_thumbnail(source_path=asset.file_path, output_path=output_path, text=text or None)
    except Exception as exc:
        video.thumbnail_path = None
        db.commit()
        raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {exc}")

    video.thumbnail_path = str(output_path)
    video.thumbnail_text = text or None
    db.commit()

    return {"thumbnail_url": f"/api/youtube-videos/{video_id}/thumbnail"}


@router.get("/{video_id}/thumbnail")
def get_thumbnail(video_id: int, db: Session = Depends(get_db)):
    """Serve the generated thumbnail PNG."""
    from console.backend.models.youtube_video import YoutubeVideo

    video = db.get(YoutubeVideo, video_id)
    if not video or not video.thumbnail_path:
        raise HTTPException(status_code=404, detail="No thumbnail available")
    p = Path(video.thumbnail_path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail file not found on disk")
    return FileResponse(str(p), media_type="image/png")


@router.get("/{video_id}/thumbnail-source")
def get_thumbnail_source(video_id: int, db: Session = Depends(get_db)):
    """Serve the original Midjourney source image."""
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_asset import VideoAsset

    video = db.get(YoutubeVideo, video_id)
    if not video or not video.thumbnail_asset_id:
        raise HTTPException(status_code=404, detail="No thumbnail source available")
    asset = db.get(VideoAsset, video.thumbnail_asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Thumbnail source asset not found")
    p = Path(asset.file_path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail source file not found on disk")
    ext = p.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "image/jpeg")
    return FileResponse(str(p), media_type=media_type)
```

- [ ] **Step 7: Run service + uploader tests**

```bash
python -m pytest tests/test_youtube_video_service_thumbnail.py tests/test_youtube_uploader.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add console/backend/services/youtube_video_service.py \
        console/backend/routers/youtube_videos.py \
        tests/test_youtube_video_service_thumbnail.py
git commit -m "feat: add thumbnail endpoints and expose thumbnail fields in _video_to_dict"
```

---

### Task 5: Upload task calls `set_thumbnail`

**Files:**
- Modify: `console/backend/tasks/youtube_upload_task.py`
- Modify: `tests/test_youtube_upload_task.py`

- [ ] **Step 1: Patch `_make_db` to set `thumbnail_path = None` by default**

In `tests/test_youtube_upload_task.py`, inside `_make_db()`, add after `video.title = "My Video"`:

```python
    video.thumbnail_path = None
```

(Without this, `MagicMock()` returns a truthy mock for any unset attribute, which would make the `if video.thumbnail_path:` guard always True.)

- [ ] **Step 2: Write the three new failing tests**

Append to `tests/test_youtube_upload_task.py`:

```python
def test_upload_task_calls_set_thumbnail_when_path_set():
    db, video, channel, cred, upload = _make_db()
    video.thumbnail_path = "/assets/thumbnails/generated/yt_1.png"

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", return_value="yt_xyz"), \
         patch("console.backend.tasks.youtube_upload_task.set_thumbnail") as mock_set_thumb:
        mock_settings.FERNET_KEY = "a" * 44
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
        upload_youtube_video_task.run(1, 3, 99)

    args = mock_set_thumb.call_args[0]
    assert args[0] == "yt_xyz"
    assert args[1] == "/assets/thumbnails/generated/yt_1.png"
    assert isinstance(args[2], dict)


def test_upload_task_skips_set_thumbnail_when_no_path():
    db, video, channel, cred, upload = _make_db()
    video.thumbnail_path = None

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", return_value="yt_xyz"), \
         patch("console.backend.tasks.youtube_upload_task.set_thumbnail") as mock_set_thumb:
        mock_settings.FERNET_KEY = "a" * 44
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
        upload_youtube_video_task.run(1, 3, 99)

    mock_set_thumb.assert_not_called()


def test_upload_task_thumbnail_failure_does_not_fail_upload():
    db, video, channel, cred, upload = _make_db()
    video.thumbnail_path = "/assets/thumbnails/generated/yt_1.png"

    with patch("console.backend.tasks.youtube_upload_task.SessionLocal", return_value=db), \
         patch("console.backend.config.settings") as mock_settings, \
         patch("console.backend.tasks.youtube_upload_task.Fernet") as mock_fernet_cls, \
         patch("console.backend.tasks.youtube_upload_task.upload_to_youtube", return_value="yt_xyz"), \
         patch("console.backend.tasks.youtube_upload_task.set_thumbnail", side_effect=RuntimeError("API error")):
        mock_settings.FERNET_KEY = "a" * 44
        mock_fernet_cls.return_value.decrypt.return_value = b"decrypted"

        from console.backend.tasks.youtube_upload_task import upload_youtube_video_task
        result = upload_youtube_video_task.run(1, 3, 99)

    assert upload.status == "done"
    assert result["platform_id"] == "yt_xyz"
```

- [ ] **Step 3: Run new tests — verify they fail**

```bash
python -m pytest tests/test_youtube_upload_task.py::test_upload_task_calls_set_thumbnail_when_path_set -v
```

Expected: `AssertionError` — `set_thumbnail` is not yet called.

- [ ] **Step 4: Update `console/backend/tasks/youtube_upload_task.py`**

Change line 16 from:

```python
from uploader.youtube_uploader import upload_to_youtube
```

To:

```python
from uploader.youtube_uploader import set_thumbnail, upload_to_youtube
```

Then, after `platform_id = upload_to_youtube(video.output_path, video_meta, credentials_dict)`, add:

```python
        if video.thumbnail_path:
            try:
                set_thumbnail(platform_id, video.thumbnail_path, credentials_dict)
            except Exception as thumb_exc:
                logger.warning(
                    "Thumbnail set failed for YoutubeVideo %s → %s: %s",
                    youtube_video_id, platform_id, thumb_exc,
                )
```

- [ ] **Step 5: Run all upload task tests**

```bash
python -m pytest tests/test_youtube_upload_task.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add console/backend/tasks/youtube_upload_task.py tests/test_youtube_upload_task.py
git commit -m "feat: set YouTube thumbnail after upload when thumbnail_path is present"
```

---

### Task 6: Frontend — API client + form section + card display

**Files:**
- Modify: `console/frontend/src/api/client.js`
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

- [ ] **Step 1: Add thumbnail methods to `youtubeVideosApi` in `client.js`**

Inside the `youtubeVideosApi` object, after the `videoPreviewUrl` line (~line 251), add:

```javascript
  uploadThumbnailImage: (id, file) => {
    const form = new FormData()
    form.append('image', file)
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch(`/api/youtube-videos/${id}/thumbnail-image`, { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
  generateThumbnail: (id, text) => fetchApi(`/api/youtube-videos/${id}/thumbnail-generate`, {
    method: 'POST',
    body: JSON.stringify({ text: text || null }),
  }),
  thumbnailUrl: (id) => `/api/youtube-videos/${id}/thumbnail`,
```

- [ ] **Step 2: Add thumbnail state to `CreationPanel` in `YouTubeVideosPage.jsx`**

Inside `CreationPanel`, after the `skipPreviews` state line (~line 142), add:

```javascript
  const [thumbnailFile, setThumbnailFile] = useState(null)
  const [thumbnailText, setThumbnailText] = useState(isEdit ? (existingVideo.thumbnail_text || '') : '')
  const [thumbnailPreviewKey, setThumbnailPreviewKey] = useState(0)
  const [hasThumbnail, setHasThumbnail] = useState(isEdit ? !!existingVideo.thumbnail_path : false)
  const [thumbnailGenerating, setThumbnailGenerating] = useState(false)
```

- [ ] **Step 3: Add `handleGenerateThumbnail` to `CreationPanel`**

After the `handleVisualUpload` function (~line 232), add:

```javascript
  const handleGenerateThumbnail = async () => {
    if (!thumbnailFile && !hasThumbnail) return
    const wordCount = thumbnailText.trim()
      ? thumbnailText.trim().split(/\s+/).filter(Boolean).length
      : 0
    if (wordCount > 5) { showToast('Thumbnail text must be 5 words or fewer', 'error'); return }
    const id = existingVideo?.id
    if (!id) { showToast('Save the video first before generating a thumbnail preview', 'info'); return }
    setThumbnailGenerating(true)
    try {
      if (thumbnailFile) {
        await youtubeVideosApi.uploadThumbnailImage(id, thumbnailFile)
        setThumbnailFile(null)
        setHasThumbnail(true)
      }
      await youtubeVideosApi.generateThumbnail(id, thumbnailText.trim() || null)
      setThumbnailPreviewKey(k => k + 1)
      showToast('Thumbnail generated', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setThumbnailGenerating(false)
    }
  }
```

- [ ] **Step 4: Update `handleSubmit` to chain thumbnail ops after video create**

In `handleSubmit`, replace:

```javascript
      if (isEdit) {
        await youtubeVideosApi.update(existingVideo.id, body)
      } else {
        await youtubeVideosApi.create(body)
      }
      onCreated()
      onClose()
```

With:

```javascript
      let videoId = existingVideo?.id
      if (isEdit) {
        await youtubeVideosApi.update(videoId, body)
      } else {
        const created = await youtubeVideosApi.create(body)
        videoId = created.id
      }
      if (!isEdit && thumbnailFile && videoId) {
        try {
          await youtubeVideosApi.uploadThumbnailImage(videoId, thumbnailFile)
          await youtubeVideosApi.generateThumbnail(videoId, thumbnailText.trim() || null)
        } catch (e) {
          showToast(`Thumbnail could not be generated — retry from the edit form. (${e.message})`, 'warning')
        }
      }
      onCreated()
      onClose()
```

- [ ] **Step 5: Add THUMBNAIL section to form JSX**

After the closing `</section>` of the `{/* ① THEME & SEO */}` block and before `{/* ② MUSIC */}`, insert:

```jsx
          {/* THUMBNAIL */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">THUMBNAIL</div>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">
                  Midjourney Image (optional)
                </label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={e => setThumbnailFile(e.target.files?.[0] || null)}
                  className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
                />
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs text-[#9090a8] font-medium">
                    Thumbnail Text (optional, ≤5 words)
                  </label>
                  <span className={`text-xs font-mono ${
                    thumbnailText.trim().split(/\s+/).filter(Boolean).length > 5
                      ? 'text-[#f87171]'
                      : 'text-[#5a5a70]'
                  }`}>
                    {thumbnailText.trim() ? thumbnailText.trim().split(/\s+/).filter(Boolean).length : 0}/5
                  </span>
                </div>
                <Input
                  value={thumbnailText}
                  onChange={e => setThumbnailText(e.target.value)}
                  placeholder="e.g. DEEP FOCUS"
                />
              </div>
              {isEdit && (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={thumbnailGenerating}
                  disabled={
                    (!thumbnailFile && !hasThumbnail) ||
                    thumbnailText.trim().split(/\s+/).filter(Boolean).length > 5
                  }
                  onClick={handleGenerateThumbnail}
                >
                  Generate Preview
                </Button>
              )}
              {isEdit && hasThumbnail && (
                <img
                  key={thumbnailPreviewKey}
                  src={`${youtubeVideosApi.thumbnailUrl(existingVideo.id)}?t=${thumbnailPreviewKey}`}
                  alt="Thumbnail preview"
                  className="w-full rounded-lg border border-[#2a2a32]"
                  style={{ aspectRatio: '16/9', objectFit: 'cover' }}
                  onError={() => setHasThumbnail(false)}
                />
              )}
            </div>
          </section>
```

- [ ] **Step 6: Add thumbnail display to video list cards**

Find the video card rendering in `YouTubeVideosPage.jsx` — look for the JSX element that renders `video.title`. Inside that card, before the card body text content, add:

```jsx
{video.thumbnail_path && (
  <img
    src={`/api/youtube-videos/${video.id}/thumbnail`}
    alt="thumbnail"
    className="w-full rounded-t-lg"
    style={{ aspectRatio: '16/9', objectFit: 'cover' }}
    onError={e => { e.target.style.display = 'none' }}
  />
)}
```

- [ ] **Step 7: Start the dev server and verify manually**

```bash
# Terminal 1 — backend
cd /Volumes/SSD/Workspace/ai-media-automation
./console/start.sh

# Terminal 2 — frontend
cd console/frontend && npm run dev
```

Navigate to http://localhost:5173 and go to the YouTube page. Verify:
1. New video form shows **THUMBNAIL** section below ① THEME & SEO.
2. Edit modal shows "Generate Preview" button; clicking it after uploading an image shows the 1280×720 preview.
3. Changing text and clicking "Generate Preview" again updates the preview.
4. Word counter turns red when >5 words; button is disabled.
5. Video cards with `thumbnail_path` show the image; cards without show unchanged layout.

- [ ] **Step 8: Commit**

```bash
git add console/frontend/src/api/client.js console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: YouTube thumbnail UI — upload field, generate preview, card display"
```

---

## Full test run

After all tasks:

```bash
python -m pytest tests/test_youtube_thumbnail.py \
                 tests/test_youtube_uploader.py \
                 tests/test_youtube_upload_task.py \
                 tests/test_youtube_video_service_thumbnail.py \
                 -v
```

Expected: all tests pass.
