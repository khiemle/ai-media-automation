# YouTube Portrait Short Render — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render portrait 9:16 YouTube Shorts from the same source materials as long-form landscape videos, with a CTA subtitle overlay in the last 10 seconds, and upload them as YouTube Shorts.

**Architecture:** Extract shared ffmpeg helpers from `youtube_render_task.py` into `pipeline/youtube_ffmpeg.py`, add `render_portrait_short` there, then create a thin `youtube_short_render_task.py` Celery task that calls it. The `start_render` router endpoint is updated to route by `template.output_format`. Two new columns (`short_cta_text`, `short_duration_s`) are added to `video_templates`.

**Tech Stack:** Python 3.11+, ffmpeg (subprocess), SQLAlchemy mapped models, Celery, Alembic, React 18 / JSX

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pipeline/youtube_ffmpeg.py` | **Create** | Shared resolve helpers + `render_landscape` + `render_portrait_short` |
| `console/backend/tasks/youtube_render_task.py` | **Refactor** | Thin wrapper → calls `render_landscape` from shared module |
| `console/backend/tasks/youtube_short_render_task.py` | **Create** | Dedicated Celery task for portrait short renders |
| `console/backend/models/video_template.py` | **Extend** | Add `short_cta_text`, `short_duration_s` columns |
| `console/backend/alembic/versions/010_template_short_fields.py` | **Create** | Migration for the two new template columns |
| `console/backend/services/youtube_video_service.py` | **Extend** | Add `dispatch_render()`, expose new template fields in `_template_to_dict` |
| `console/backend/routers/youtube_videos.py` | **Update** | `start_render` uses `svc.dispatch_render()` instead of hardcoded task import |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | **Update** | `MakeShortModal` pre-fills CTA + duration from template fields |
| `tests/test_youtube_ffmpeg.py` | **Create** | Unit tests for all helpers and both render functions |
| `tests/test_dispatch_render.py` | **Create** | Unit tests for `dispatch_render` routing |

---

## Task 1: Create `pipeline/youtube_ffmpeg.py` — shared resolve helpers

**Files:**
- Create: `pipeline/youtube_ffmpeg.py`
- Create: `tests/test_youtube_ffmpeg.py`

- [ ] **Step 1: Write failing tests for resolve helpers**

Create `tests/test_youtube_ffmpeg.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def _make_video(sfx_overrides=None, visual_asset_id=None, music_track_id=None,
                target_duration_h=3.0, output_quality="1080p"):
    v = MagicMock()
    v.visual_asset_id = visual_asset_id
    v.music_track_id = music_track_id
    v.sfx_overrides = sfx_overrides
    v.target_duration_h = target_duration_h
    v.output_quality = output_quality
    return v


def _make_template(short_duration_s=58, short_cta_text=None):
    t = MagicMock()
    t.short_duration_s = short_duration_s
    t.short_cta_text = short_cta_text
    return t


# ── resolve_visual ────────────────────────────────────────────────────────────

def test_resolve_visual_returns_none_when_no_asset_id():
    from pipeline.youtube_ffmpeg import resolve_visual
    assert resolve_visual(_make_video(visual_asset_id=None), MagicMock()) is None


def test_resolve_visual_returns_file_path():
    fake_asset = MagicMock()
    fake_asset.file_path = "/videos/forest.mp4"
    db = MagicMock()
    db.get.return_value = fake_asset
    from pipeline.youtube_ffmpeg import resolve_visual
    assert resolve_visual(_make_video(visual_asset_id=42), db) == "/videos/forest.mp4"


def test_resolve_visual_returns_none_when_asset_not_found():
    db = MagicMock()
    db.get.return_value = None
    from pipeline.youtube_ffmpeg import resolve_visual
    assert resolve_visual(_make_video(visual_asset_id=99), db) is None


# ── resolve_audio ─────────────────────────────────────────────────────────────

def test_resolve_audio_returns_none_when_no_track_id():
    from pipeline.youtube_ffmpeg import resolve_audio
    assert resolve_audio(_make_video(music_track_id=None), MagicMock()) is None


def test_resolve_audio_returns_file_path():
    fake_track = MagicMock()
    fake_track.file_path = "/music/ambient.mp3"
    db = MagicMock()
    db.get.return_value = fake_track
    from pipeline.youtube_ffmpeg import resolve_audio
    assert resolve_audio(_make_video(music_track_id=7), db) == "/music/ambient.mp3"


# ── resolve_sfx_layers ────────────────────────────────────────────────────────

def test_resolve_sfx_layers_empty_when_no_overrides():
    from pipeline.youtube_ffmpeg import resolve_sfx_layers
    assert resolve_sfx_layers(_make_video(sfx_overrides=None), MagicMock()) == []


def test_resolve_sfx_layers_skips_layer_with_no_asset_id():
    from pipeline.youtube_ffmpeg import resolve_sfx_layers
    video = _make_video(sfx_overrides={"foreground": {"volume": 0.5}})
    assert resolve_sfx_layers(video, MagicMock()) == []


# ── _escape_drawtext ──────────────────────────────────────────────────────────

def test_escape_drawtext_escapes_colon():
    from pipeline.youtube_ffmpeg import _escape_drawtext
    assert _escape_drawtext("Watch: full video") == "Watch\\: full video"


def test_escape_drawtext_escapes_backslash():
    from pipeline.youtube_ffmpeg import _escape_drawtext
    assert _escape_drawtext("Watch\\video") == "Watch\\\\video"
```

- [ ] **Step 2: Run the tests — confirm they all fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_youtube_ffmpeg.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'pipeline.youtube_ffmpeg'`

- [ ] **Step 3: Create `pipeline/youtube_ffmpeg.py` with resolve helpers and `_escape_drawtext`**

Create `/Volumes/SSD/Workspace/ai-media-automation/pipeline/youtube_ffmpeg.py`:

```python
"""Shared ffmpeg helpers for YouTube long-form and portrait-short rendering."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

QUALITY_SCALE = {
    "4K":    "3840:2160",
    "1080p": "1920:1080",
}
DEFAULT_SCALE = "1920:1080"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def resolve_visual(video, db) -> str | None:
    """Return the file path of the linked visual asset, or None."""
    if not video.visual_asset_id:
        return None
    try:
        from console.backend.models.video_asset import VideoAsset
        asset = db.get(VideoAsset, video.visual_asset_id)
        if asset and asset.file_path:
            return asset.file_path
    except Exception as exc:
        logger.warning("Could not load visual asset %s: %s", video.visual_asset_id, exc)
    return None


def resolve_audio(video, db) -> str | None:
    """Return the file path of the linked music track, or None."""
    if not video.music_track_id:
        return None
    try:
        from database.models import MusicTrack
        track = db.get(MusicTrack, video.music_track_id)
        if track and track.file_path:
            return track.file_path
    except Exception as exc:
        logger.warning("Could not load music track %s: %s", video.music_track_id, exc)
    return None


def resolve_sfx_layers(video, db) -> list[tuple[str, float]]:
    """Resolve SFX layer file paths from sfx_overrides (foreground/midground/background keys)."""
    from console.backend.models.sfx_asset import SfxAsset

    overrides = video.sfx_overrides or {}
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
            asset = db.get(SfxAsset, int(asset_id))
            if asset and asset.file_path and Path(asset.file_path).is_file():
                results.append((asset.file_path, volume))
            else:
                logger.warning("SFX asset %s not found or missing file on disk", asset_id)
        except Exception as exc:
            logger.warning("Could not resolve SFX asset %s: %s", asset_id, exc)
    return results


def _escape_drawtext(text: str) -> str:
    """Escape text for use in an ffmpeg drawtext filter value."""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _build_audio_filter(audio_inputs: list[tuple[str, float]], vf: str) -> tuple[list[str], list[str]]:
    """Return (filter_complex_parts, map_args) for the given audio inputs and video filter chain."""
    parts: list[str] = []
    audio_labels: list[str] = []
    for i, (_, vol) in enumerate(audio_inputs):
        parts.append(f"[{i + 1}:a]volume={vol}[a{i}]")
        audio_labels.append(f"[a{i}]")
    parts.append(f"[0:v]{vf}[vout]")

    if len(audio_inputs) == 1:
        return parts, ["-map", "[vout]", "-map", "[a0]"]

    mix_in = "".join(audio_labels)
    parts.append(
        f"{mix_in}amix=inputs={len(audio_inputs)}:duration=first:normalize=0[aout]"
    )
    return parts, ["-map", "[vout]", "-map", "[aout]"]


def _run_ffmpeg(cmd: list[str], timeout: float) -> None:
    timeout = max(timeout, 120)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg timed out after {timeout}s")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(result.stderr or '')[-800:]}")
```

- [ ] **Step 4: Run the tests — confirm they pass**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v 2>&1 | tail -20
```

Expected: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "feat: add pipeline/youtube_ffmpeg.py with shared resolve helpers and escape util"
```

---

## Task 2: Add `render_landscape` to shared module, refactor render task

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Modify: `console/backend/tasks/youtube_render_task.py`
- Modify: `tests/test_youtube_ffmpeg.py`

- [ ] **Step 1: Add `render_landscape` tests to `tests/test_youtube_ffmpeg.py`**

Append to `tests/test_youtube_ffmpeg.py`:

```python
# ── render_landscape ──────────────────────────────────────────────────────────

def test_render_landscape_raises_when_ffmpeg_missing():
    from pipeline.youtube_ffmpeg import render_landscape
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            render_landscape(_make_video(), Path("/tmp/out.mp4"), MagicMock())


def test_render_landscape_calls_ffmpeg_with_landscape_scale(tmp_path):
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(), output, MagicMock())

    cmd = " ".join(mock_run.call_args[0][0])
    assert "1920:1080" in cmd or "1920x1080" in cmd


def test_render_landscape_uses_duration_from_video(tmp_path):
    output = tmp_path / "out.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(_make_video(target_duration_h=1.0), output, MagicMock())

    cmd_list = mock_run.call_args[0][0]
    t_idx = cmd_list.index("-t")
    assert cmd_list[t_idx + 1] == "3600"
```

- [ ] **Step 2: Run the new tests — confirm they fail**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_render_landscape_raises_when_ffmpeg_missing -v
```

Expected: `ImportError` or `AttributeError` — `render_landscape` not yet defined.

- [ ] **Step 3: Add `render_landscape` to `pipeline/youtube_ffmpeg.py`**

Append to the bottom of `/Volumes/SSD/Workspace/ai-media-automation/pipeline/youtube_ffmpeg.py`:

```python
def render_landscape(video, output_path: Path, db) -> None:
    """Render a landscape long-form YouTube video."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    duration_s = int((video.target_duration_h or 3.0) * 3600)
    scale = QUALITY_SCALE.get(getattr(video, "output_quality", None) or "1080p", DEFAULT_SCALE)
    w, h = scale.split(":")

    visual_path = resolve_visual(video, db)
    music_path = resolve_audio(video, db)
    sfx_layers = resolve_sfx_layers(video, db)
    is_image = visual_path is not None and Path(visual_path).suffix.lower() in IMAGE_EXTS

    audio_inputs: list[tuple[str, float]] = []
    if music_path and Path(music_path).is_file():
        audio_inputs.append((music_path, 1.0))
    audio_inputs.extend(sfx_layers)

    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
    )

    cmd = ["ffmpeg", "-y"]

    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]

    if audio_inputs:
        for path, _ in audio_inputs:
            cmd += ["-stream_loop", "-1", "-i", path]
        parts, map_args = _build_audio_filter(audio_inputs, vf)
        cmd += ["-filter_complex", ";".join(parts)] + map_args
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-vf", vf]

    cmd += ["-t", str(duration_s)]

    if is_image:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "18"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]

    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart",
            str(output_path)]

    logger.info("ffmpeg landscape cmd: %s", " ".join(cmd))
    _run_ffmpeg(cmd, duration_s * 4)
```

- [ ] **Step 4: Run the new tests — confirm they pass**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v 2>&1 | tail -20
```

Expected: all 13 tests pass.

- [ ] **Step 5: Refactor `console/backend/tasks/youtube_render_task.py`**

Replace the entire file content of `/Volumes/SSD/Workspace/ai-media-automation/console/backend/tasks/youtube_render_task.py`:

```python
"""Celery task: orchestrate full YouTube long-form video rendering."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.environ.get("RENDER_OUTPUT_PATH", "./renders/youtube"))


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_video",
    queue="render_q",
    max_retries=2,
    default_retry_delay=60,
)
def render_youtube_video_task(self, youtube_video_id: int):
    """Render a long-form landscape YouTube video."""
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_template import VideoTemplate  # noqa: F401 — registers FK target
    from pipeline.youtube_ffmpeg import render_landscape

    db = SessionLocal()
    video = None
    render_completed = False
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            logger.error("YoutubeVideo %s not found", youtube_video_id)
            return {"status": "failed", "reason": "video not found"}

        if video.status not in {"draft", "queued"}:
            logger.warning(
                "YoutubeVideo %s is already %s; skipping render",
                youtube_video_id, video.status,
            )
            return {"status": "skipped", "reason": f"already {video.status}"}

        video.status = "rendering"
        db.commit()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"youtube_{youtube_video_id}_v{int(time.time())}.mp4"

        render_landscape(video, output_path, db)
        render_completed = True

        video.status = "done"
        video.output_path = str(output_path)
        db.commit()

        logger.info("YoutubeVideo %s rendered to %s", youtube_video_id, output_path)
        return {"status": "done", "output_path": str(output_path)}

    except Exception as exc:
        logger.exception("YoutubeVideo %s render failed: %s", youtube_video_id, exc)
        if video is not None and not render_completed:
            try:
                video.status = "failed"
                db.commit()
            except Exception as db_exc:
                db.rollback()
                logger.error(
                    "Failed to persist 'failed' status for YoutubeVideo %s: %s",
                    youtube_video_id, db_exc,
                )
        raise self.retry(exc=exc)
    finally:
        db.close()
```

- [ ] **Step 6: Verify the import still works**

```bash
python -c "from console.backend.tasks.youtube_render_task import render_youtube_video_task; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Run all existing tests — confirm nothing broke**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add pipeline/youtube_ffmpeg.py console/backend/tasks/youtube_render_task.py tests/test_youtube_ffmpeg.py
git commit -m "refactor: move render_landscape and resolve helpers to pipeline/youtube_ffmpeg.py"
```

---

## Task 3: Add `short_cta_text` + `short_duration_s` to `VideoTemplate` model + migration

**Files:**
- Modify: `console/backend/models/video_template.py`
- Create: `console/backend/alembic/versions/010_template_short_fields.py`
- Modify: `console/backend/services/youtube_video_service.py` (lines 56–70, `_template_to_dict`)

- [ ] **Step 1: Add columns to `VideoTemplate` model**

In `/Volumes/SSD/Workspace/ai-media-automation/console/backend/models/video_template.py`, add two lines after the existing `seo_description_template` column (current last column):

```python
    short_cta_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True, default=58, server_default="58")
```

Make sure `Integer` is imported — it's already in the existing imports at the top of the file.

- [ ] **Step 2: Create the migration**

Create `/Volumes/SSD/Workspace/ai-media-automation/console/backend/alembic/versions/010_template_short_fields.py`:

```python
"""video_templates — add short_cta_text and short_duration_s

Revision ID: 010
Revises: 009
Create Date: 2026-05-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("video_templates", sa.Column("short_cta_text", sa.Text, nullable=True))
    op.add_column(
        "video_templates",
        sa.Column("short_duration_s", sa.Integer, nullable=True, server_default="58"),
    )


def downgrade() -> None:
    op.drop_column("video_templates", "short_duration_s")
    op.drop_column("video_templates", "short_cta_text")
```

- [ ] **Step 3: Run the migration**

```bash
cd console/backend && alembic upgrade head && cd ../..
```

Expected: `Running upgrade 009 -> 010, video_templates — add short_cta_text and short_duration_s`

- [ ] **Step 4: Update `_template_to_dict` in the service**

In `/Volumes/SSD/Workspace/ai-media-automation/console/backend/services/youtube_video_service.py`, in the `_template_to_dict` function, add two keys at the end of the returned dict (after `"seo_description_template"`):

```python
        "short_cta_text": t.short_cta_text,
        "short_duration_s": t.short_duration_s if t.short_duration_s is not None else 58,
```

- [ ] **Step 5: Verify the new fields appear in the API response**

```bash
python -c "
from console.backend.services.youtube_video_service import _template_to_dict
from unittest.mock import MagicMock
t = MagicMock()
t.short_cta_text = 'Watch the full video!'
t.short_duration_s = 45
result = _template_to_dict(t)
print('short_cta_text:', result['short_cta_text'])
print('short_duration_s:', result['short_duration_s'])
"
```

Expected:
```
short_cta_text: Watch the full video!
short_duration_s: 45
```

- [ ] **Step 6: Commit**

```bash
git add console/backend/models/video_template.py \
        console/backend/alembic/versions/010_template_short_fields.py \
        console/backend/services/youtube_video_service.py
git commit -m "feat: add short_cta_text and short_duration_s to VideoTemplate model"
```

---

## Task 4: Add `render_portrait_short` to `pipeline/youtube_ffmpeg.py`

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Modify: `tests/test_youtube_ffmpeg.py`

- [ ] **Step 1: Add `render_portrait_short` tests to `tests/test_youtube_ffmpeg.py`**

Append to `tests/test_youtube_ffmpeg.py`:

```python
# ── render_portrait_short ─────────────────────────────────────────────────────

def test_render_portrait_short_raises_when_ffmpeg_missing():
    from pipeline.youtube_ffmpeg import render_portrait_short
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            render_portrait_short(
                _make_video(), _make_template(), Path("/tmp/out.mp4"), MagicMock()
            )


def test_render_portrait_short_uses_portrait_resolution(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch full video!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "1080:1920" in cmd


def test_render_portrait_short_includes_center_crop_filter(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Subscribe!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "crop=ih*9/16:ih:(iw-ih*9/16)/2:0" in cmd


def test_render_portrait_short_includes_drawtext_with_cta_text(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch full video!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(short_duration_s=58), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    assert "drawtext=text=" in cmd
    assert "Watch full video" in cmd


def test_render_portrait_short_cta_enabled_in_last_10s(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(short_duration_s=30), output, MagicMock())
    cmd = " ".join(mock_run.call_args[0][0])
    # duration=30, so CTA starts at 30-10=20
    assert "between(t,20,30)" in cmd


def test_render_portrait_short_uses_template_duration(tmp_path):
    video = _make_video(sfx_overrides={"cta": {"text": "Watch!"}})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(video, _make_template(short_duration_s=45), output, MagicMock())
    cmd_list = mock_run.call_args[0][0]
    t_idx = cmd_list.index("-t")
    assert cmd_list[t_idx + 1] == "45"


def test_render_portrait_short_falls_back_to_template_cta_text(tmp_path):
    video = _make_video(sfx_overrides={})  # no cta key
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(
            video, _make_template(short_cta_text="See link in description!"), output, MagicMock()
        )
    cmd = " ".join(mock_run.call_args[0][0])
    assert "See link in description" in cmd


def test_render_portrait_short_falls_back_to_hardcoded_default_when_no_cta(tmp_path):
    video = _make_video(sfx_overrides={})
    output = tmp_path / "short.mp4"
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_portrait_short
        render_portrait_short(
            video, _make_template(short_cta_text=None), output, MagicMock()
        )
    cmd = " ".join(mock_run.call_args[0][0])
    assert "Watch the full video" in cmd
```

- [ ] **Step 2: Run the new tests — confirm they fail**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -k "portrait" -v 2>&1 | head -20
```

Expected: `AttributeError: module 'pipeline.youtube_ffmpeg' has no attribute 'render_portrait_short'`

- [ ] **Step 3: Add `render_portrait_short` and `_get_cta_text` to `pipeline/youtube_ffmpeg.py`**

Append to the bottom of `/Volumes/SSD/Workspace/ai-media-automation/pipeline/youtube_ffmpeg.py`:

```python
def render_portrait_short(video, template, output_path: Path, db) -> None:
    """Render a portrait 9:16 YouTube Short with CTA drawtext overlay in the last 10 seconds."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    duration_s = template.short_duration_s or 58

    visual_path = resolve_visual(video, db)
    music_path = resolve_audio(video, db)
    sfx_layers = resolve_sfx_layers(video, db)
    is_image = visual_path is not None and Path(visual_path).suffix.lower() in IMAGE_EXTS

    audio_inputs: list[tuple[str, float]] = []
    if music_path and Path(music_path).is_file():
        audio_inputs.append((music_path, 1.0))
    audio_inputs.extend(sfx_layers)

    cta_text = _get_cta_text(video, template)
    cta_start = max(0, duration_s - 10)
    escaped = _escape_drawtext(cta_text)
    drawtext = (
        f"drawtext=text='{escaped}'"
        f":fontcolor=white:fontsize=52"
        f":x=(w-tw)/2:y=h*0.80"
        f":box=1:boxcolor=black@0.5:boxborderw=10"
        f":enable='between(t,{cta_start},{duration_s})'"
    )

    portrait_crop = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920,fps=30"
    vf_chain = f"{portrait_crop},{drawtext}"

    cmd = ["ffmpeg", "-y"]

    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30"]

    if audio_inputs:
        for path, _ in audio_inputs:
            cmd += ["-stream_loop", "-1", "-i", path]
        parts, map_args = _build_audio_filter(audio_inputs, vf_chain)
        cmd += ["-filter_complex", ";".join(parts)] + map_args
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-vf", vf_chain]

    cmd += ["-t", str(duration_s)]

    if is_image:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "18"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18"]

    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart",
            str(output_path)]

    logger.info("ffmpeg portrait short cmd: %s", " ".join(cmd))
    _run_ffmpeg(cmd, max(duration_s * 4, 120))


def _get_cta_text(video, template) -> str:
    overrides = video.sfx_overrides or {}
    cta = overrides.get("cta") or {}
    return (
        cta.get("text")
        or getattr(template, "short_cta_text", None)
        or "Watch the full video — link in description!"
    )
```

- [ ] **Step 4: Run all tests — confirm everything passes**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v 2>&1 | tail -25
```

Expected: all 21 tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "feat: add render_portrait_short to pipeline/youtube_ffmpeg.py"
```

---

## Task 5: Create `console/backend/tasks/youtube_short_render_task.py`

**Files:**
- Create: `console/backend/tasks/youtube_short_render_task.py`

- [ ] **Step 1: Create the task file**

Create `/Volumes/SSD/Workspace/ai-media-automation/console/backend/tasks/youtube_short_render_task.py`:

```python
"""Celery task: render a portrait 9:16 YouTube Short."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.environ.get("RENDER_OUTPUT_PATH", "./renders/youtube"))


@celery_app.task(
    bind=True,
    name="tasks.render_youtube_short",
    queue="render_q",
    max_retries=2,
    default_retry_delay=60,
)
def render_youtube_short_task(self, youtube_video_id: int):
    """Render a portrait 9:16 YouTube Short from the video's source materials."""
    from console.backend.database import SessionLocal
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import render_portrait_short

    db = SessionLocal()
    video = None
    render_completed = False
    try:
        video = db.get(YoutubeVideo, youtube_video_id)
        if not video:
            logger.error("YoutubeVideo %s not found", youtube_video_id)
            return {"status": "failed", "reason": "video not found"}

        if video.status not in {"draft", "queued"}:
            logger.warning(
                "YoutubeVideo %s is already %s; skipping short render",
                youtube_video_id, video.status,
            )
            return {"status": "skipped", "reason": f"already {video.status}"}

        template = db.get(VideoTemplate, video.template_id)
        if not template:
            raise ValueError(f"VideoTemplate {video.template_id} not found")

        video.status = "rendering"
        db.commit()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"short_{youtube_video_id}_v{int(time.time())}.mp4"

        render_portrait_short(video, template, output_path, db)
        render_completed = True

        video.status = "done"
        video.output_path = str(output_path)
        db.commit()

        logger.info("YoutubeVideo %s (short) rendered to %s", youtube_video_id, output_path)
        return {"status": "done", "output_path": str(output_path)}

    except Exception as exc:
        logger.exception("YoutubeVideo %s short render failed: %s", youtube_video_id, exc)
        if video is not None and not render_completed:
            try:
                video.status = "failed"
                db.commit()
            except Exception as db_exc:
                db.rollback()
                logger.error(
                    "Failed to persist 'failed' status for YoutubeVideo %s: %s",
                    youtube_video_id, db_exc,
                )
        raise self.retry(exc=exc)
    finally:
        db.close()
```

- [ ] **Step 2: Verify the import works**

```bash
python -c "from console.backend.tasks.youtube_short_render_task import render_youtube_short_task; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add console/backend/tasks/youtube_short_render_task.py
git commit -m "feat: add youtube_short_render_task Celery task for portrait short rendering"
```

---

## Task 6: Add `dispatch_render` to service, update router — with routing tests

**Files:**
- Create: `tests/test_dispatch_render.py`
- Modify: `console/backend/services/youtube_video_service.py`
- Modify: `console/backend/routers/youtube_videos.py` (lines 157–182)

- [ ] **Step 1: Write failing tests for `dispatch_render` routing**

Create `/Volumes/SSD/Workspace/ai-media-automation/tests/test_dispatch_render.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def _setup_db(output_format: str):
    """Return a mock db that returns a video and template with the given output_format."""
    video = MagicMock()
    video.id = 1
    video.template_id = 10
    video.celery_task_id = None

    template = MagicMock()
    template.output_format = output_format

    db = MagicMock()

    def _get(cls, _id):
        name = cls.__name__ if hasattr(cls, "__name__") else str(cls)
        return video if "YoutubeVideo" in name else template

    db.get.side_effect = _get
    return db, video, template


def test_dispatch_render_routes_landscape_long_to_landscape_task():
    db, video, _ = _setup_db("landscape_long")

    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="task-landscape")

    with patch(
        "console.backend.tasks.youtube_render_task.render_youtube_video_task",
        mock_task,
    ):
        from console.backend.services.youtube_video_service import YoutubeVideoService
        svc = YoutubeVideoService(db)
        task_id = svc.dispatch_render(1)

    mock_task.delay.assert_called_once_with(1)
    assert task_id == "task-landscape"


def test_dispatch_render_routes_portrait_short_to_short_task():
    db, video, _ = _setup_db("portrait_short")

    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="task-short")

    with patch(
        "console.backend.tasks.youtube_short_render_task.render_youtube_short_task",
        mock_task,
    ):
        from console.backend.services.youtube_video_service import YoutubeVideoService
        svc = YoutubeVideoService(db)
        task_id = svc.dispatch_render(1)

    mock_task.delay.assert_called_once_with(1)
    assert task_id == "task-short"


def test_dispatch_render_raises_when_video_not_found():
    db = MagicMock()
    db.get.return_value = None

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(KeyError, match="not found"):
        svc.dispatch_render(999)


def test_dispatch_render_raises_when_template_not_found():
    video = MagicMock()
    video.id = 1
    video.template_id = 10

    db = MagicMock()
    call_count = {"n": 0}

    def _get(cls, _id):
        call_count["n"] += 1
        return video if call_count["n"] == 1 else None

    db.get.side_effect = _get

    from console.backend.services.youtube_video_service import YoutubeVideoService
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="not found"):
        svc.dispatch_render(1)
```

- [ ] **Step 2: Run the tests — confirm they fail**

```bash
python -m pytest tests/test_dispatch_render.py -v 2>&1 | head -20
```

Expected: `AttributeError: 'YoutubeVideoService' object has no attribute 'dispatch_render'`

- [ ] **Step 3: Add `dispatch_render` to `YoutubeVideoService`**

In `/Volumes/SSD/Workspace/ai-media-automation/console/backend/services/youtube_video_service.py`, add this method inside the `YoutubeVideoService` class, after `delete_video`:

```python
    def dispatch_render(self, video_id: int) -> str:
        """Queue the correct render task based on template.output_format. Returns Celery task_id."""
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")

        template = self.db.get(VideoTemplate, v.template_id)
        if not template:
            raise ValueError(f"VideoTemplate {v.template_id} not found")

        if template.output_format == "portrait_short":
            from console.backend.tasks.youtube_short_render_task import render_youtube_short_task
            task = render_youtube_short_task.delay(video_id)
        else:
            from console.backend.tasks.youtube_render_task import render_youtube_video_task
            task = render_youtube_video_task.delay(video_id)

        v.celery_task_id = task.id
        self.db.commit()
        return task.id
```

- [ ] **Step 4: Run the routing tests — confirm they pass**

```bash
python -m pytest tests/test_dispatch_render.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Update `start_render` in the router**

In `/Volumes/SSD/Workspace/ai-media-automation/console/backend/routers/youtube_videos.py`, replace the `start_render` function body (lines 158–182) with:

```python
@router.post("/{video_id}/render")
def start_render(
    video_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    """Queue a YouTube video for rendering via Celery."""
    svc = YoutubeVideoService(db)
    try:
        video = svc.get_video(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if video["status"] not in ("draft", "queued"):
        raise HTTPException(status_code=400, detail=f"Cannot render video in status '{video['status']}'")

    svc.update_status(video_id, "queued", user_id=user.id)

    try:
        task_id = svc.dispatch_render(video_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {"task_id": task_id, "status": "queued"}
```

- [ ] **Step 6: Verify the import is clean (no leftover hardcoded task import)**

```bash
grep -n "render_youtube_video_task\|render_youtube_short_task" console/backend/routers/youtube_videos.py
```

Expected: no output (both imports now live inside `dispatch_render` in the service).

- [ ] **Step 7: Run all tests**

```bash
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add console/backend/services/youtube_video_service.py \
        console/backend/routers/youtube_videos.py \
        tests/test_dispatch_render.py
git commit -m "feat: add dispatch_render routing to YoutubeVideoService, update start_render endpoint"
```

---

## Task 7: Update `MakeShortModal` to read from template

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (lines 551–556, 572, 627)

- [ ] **Step 1: Move `shortTemplate` assignment above `useState`**

In `YouTubeVideosPage.jsx` inside `MakeShortModal`, the current code has `shortTemplate` declared on line 561 (after the `useState` call). Move it above the `useState`:

Replace (lines 550–561):
```jsx
function MakeShortModal({ video, shortTemplates, onClose, onCreated }) {
  const [form, setForm] = useState({
    sameMusic: true,
    sameVisual: true,
    ctaText: `Full ${video.target_duration_h ? video.target_duration_h + 'h' : ''} version on channel ↑`,
    ctaPosition: 'last_10s',
  })
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const shortTemplate = shortTemplates[0]
```

With:
```jsx
function MakeShortModal({ video, shortTemplates, onClose, onCreated }) {
  const shortTemplate = shortTemplates[0]
  const [form, setForm] = useState({
    sameMusic: true,
    sameVisual: true,
    ctaText: shortTemplate?.short_cta_text || `Full ${video.target_duration_h ? video.target_duration_h + 'h' : ''} version on channel ↑`,
    ctaPosition: 'last_10s',
  })
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }
```

- [ ] **Step 2: Update `target_duration_h` in `handleSubmit` to use template value**

In the same function, find line 572:
```jsx
        target_duration_h: 58 / 3600,
```

Replace with:
```jsx
        target_duration_h: (shortTemplate?.short_duration_s ?? 58) / 3600,
```

- [ ] **Step 3: Update the duration display line**

Find line 627:
```jsx
        <div className="text-xs text-[#9090a8]">Duration: <strong className="text-[#e8e8f0]">58 seconds</strong> (fixed)</div>
```

Replace with:
```jsx
        <div className="text-xs text-[#9090a8]">Duration: <strong className="text-[#e8e8f0]">{shortTemplate?.short_duration_s ?? 58} seconds</strong> (fixed)</div>
```

- [ ] **Step 4: Verify the frontend compiles without errors**

```bash
cd console/frontend && npm run build 2>&1 | tail -10 && cd ../..
```

Expected: build succeeds with no errors.

- [ ] **Step 5: Start the dev server and manually test the Make Short modal**

```bash
cd console/frontend && npm run dev
```

Open `http://localhost:5173`, log in, navigate to the YouTube Videos tab, find a long-form video, click "+ Make Short". Verify:
- CTA text is pre-filled from the template's `short_cta_text` (or the fallback generic string if null)
- Duration shows the template's `short_duration_s` (default 58)

- [ ] **Step 6: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: MakeShortModal pre-fills CTA text and duration from portrait_short template"
```

---

## Task 8: Final integration check

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass. Note the count — should be at least 25 more than before this feature.

- [ ] **Step 2: Verify the Celery task registry sees both tasks**

```bash
python -c "
from console.backend.celery_app import celery_app
import console.backend.tasks.youtube_render_task
import console.backend.tasks.youtube_short_render_task
tasks = [k for k in celery_app.tasks if 'youtube' in k]
for t in sorted(tasks): print(t)
"
```

Expected output includes:
```
tasks.render_youtube_short
tasks.render_youtube_video
```

- [ ] **Step 3: Verify migration chain is intact**

```bash
cd console/backend && alembic history | head -5 && cd ../..
```

Expected: shows `010 -> (head)` as the latest revision.

- [ ] **Step 4: Final commit if any loose files**

```bash
git status
```

If clean, done. If any untracked changes, stage and commit them.
