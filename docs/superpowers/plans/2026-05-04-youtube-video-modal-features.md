# YouTube Video Modal — Feature Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five features to the Create YouTube Video modal in the Management Console: edit-existing flow with status reset, modal-style SFX layer pickers, listen-before-select on SFX/music modals, multi-visual playlist editor, and renderer loop modes (concat-then-loop and per-clip duration).

**Architecture:** Backend gets one additive Alembic migration, three new optional fields on the create/update schemas, an extended `update_video` service path with validation + artifact cleanup, and a new visual-playlist segment builder in the landscape renderer. Frontend gets one shared `PreviewPlayer` primitive plus three new modal/editor components, swapped into the existing `CreationPanel` while reusing it for both create and edit modes via a `mode` prop.

**Tech Stack:** FastAPI · SQLAlchemy 2.x typed ORM · Alembic · pytest · React 18 · Vite · Tailwind CSS · ffmpeg.

**Spec:** `docs/superpowers/specs/2026-05-04-youtube-video-modal-features-design.md`

> **Note on line numbers.** All line-number references in this plan refer to the *original* file state (before any task in this plan has been applied). Later tasks shift line counts in `YouTubeVideosPage.jsx` — when reading a step from a later task, use the surrounding code snippet (always shown in the step) as the actual anchor, not the line number.

---

## File Structure

### New files

| Path | Responsibility |
|---|---|
| `console/backend/alembic/versions/015_youtube_video_visual_playlist.py` | Migration: adds `visual_asset_ids INTEGER[]`, `visual_clip_durations_s FLOAT[]`, `visual_loop_mode VARCHAR(20)` to `youtube_videos`. |
| `console/frontend/src/components/PreviewPlayer.jsx` | Shared primitive: small ▶/⏸ button (or thumbnail-with-overlay-play) for `audio` / `video` / `image`. Single-track-at-a-time semantics via module-level `currentlyPlaying` ref. |
| `console/frontend/src/components/SfxPickerModal.jsx` | Single-select SFX picker modal with search and per-row preview. Used by ④ FG/MG/BG layer cards. |
| `console/frontend/src/components/VisualPickerModal.jsx` | Single-select visual asset picker modal with thumbnail grid, source/keywords filters, and click-to-play preview per tile. Returns one `{ id, asset_type, file_path, … }`. |
| `console/frontend/src/components/VisualPlaylistEditor.jsx` | Inline ordered list mirroring `MusicPlaylistEditor`: thumbnail + title + per-clip duration field + ↑↓×; **+ Add Visual** opens `VisualPickerModal`. |
| `tests/test_youtube_video_service_update.py` | Pytest module: edit-reset path validation, artifact cleanup, status guards. |
| `tests/test_youtube_video_service_visual_playlist.py` | Pytest module: round-trip the three new fields through `create_video`/`update_video`. |
| `tests/test_youtube_ffmpeg_visual_playlist.py` | Pytest module: visual-playlist resolver and segment-builder helpers. |

### Modified files

| Path | Change |
|---|---|
| `console/backend/models/youtube_video.py` | Add three columns: `visual_asset_ids`, `visual_clip_durations_s`, `visual_loop_mode`. |
| `console/backend/routers/youtube_videos.py` | Add three optional fields (with `Literal` for `visual_loop_mode`) to `YoutubeVideoCreate` and `YoutubeVideoUpdate` schemas. |
| `console/backend/services/youtube_video_service.py` | Extend `_video_to_dict` to surface new fields; extend `create_video` to persist them; rewrite `update_video` to enforce status whitelist, validate playlist, force `status='draft'`, delete orphaned preview/output files, audit-log. |
| `pipeline/youtube_ffmpeg.py` | Add `resolve_visual_playlist(video, db)` and `_build_visual_segment(...)` helpers; modify `render_landscape` to use the playlist when non-empty (fallback to existing single-asset path). |
| `console/frontend/src/components/SfxPoolEditor.jsx` | Embed `<PreviewPlayer kind="audio" />` per row in the picker grid and per row in the selected-pool list. |
| `console/frontend/src/components/MusicPlaylistEditor.jsx` | Embed `<PreviewPlayer kind="audio" />` per row in the picker modal and per row in the selected playlist. |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | (a) Replace ③ VISUAL `<Select>` with loop-mode toggle + `<VisualPlaylistEditor>`. (b) Replace ④ SFX LAYERS three `<select>`s with three `<SfxPickerModal>` triggers. (c) Add `mode: 'create' \| 'edit'` and `existingVideo` props on `CreationPanel`; prefill from `existingVideo`; guard ✦ AI Autofill button and theme→SEO autofill `useEffect` on `mode==='create'`; submit calls `youtubeVideosApi.update(id, …)` in edit mode. (d) Add ✎ Edit button on list rows when `v.status` is in `{draft, failed, audio_preview_ready, video_preview_ready}`. |

`console/frontend/src/api/client.js` already exposes `youtubeVideosApi.update(id, data)` — no client wrapper changes needed (the spec mentioned adding it; that turned out to be already present).

---

## Task 1: Migration — add three new visual-playlist columns

**Files:**
- Create: `console/backend/alembic/versions/015_youtube_video_visual_playlist.py`

- [ ] **Step 1: Write the migration**

Mirror the patterns in `013_asmr_youtube_fields.py`:

```python
"""Add visual playlist + loop mode fields to youtube_videos

Revision ID: 015
Revises: 014
Create Date: 2026-05-04
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column("visual_asset_ids", ARRAY(sa.Integer), server_default="{}", nullable=False),
    )
    op.add_column(
        "youtube_videos",
        sa.Column("visual_clip_durations_s", ARRAY(sa.Float), server_default="{}", nullable=False),
    )
    op.add_column(
        "youtube_videos",
        sa.Column(
            "visual_loop_mode",
            sa.String(20),
            server_default="concat_loop",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("youtube_videos", "visual_loop_mode")
    op.drop_column("youtube_videos", "visual_clip_durations_s")
    op.drop_column("youtube_videos", "visual_asset_ids")
```

- [ ] **Step 2: Run the migration against your dev DB**

```bash
cd console/backend
alembic upgrade head
```

Expected: alembic prints `Running upgrade 014 -> 015, ...`. No errors.

- [ ] **Step 3: Verify columns are present**

```bash
psql $DATABASE_URL -c "\d youtube_videos" | grep -E 'visual_asset_ids|visual_clip_durations_s|visual_loop_mode'
```

Expected output: three lines showing each new column with the correct type and `not null default ...`.

- [ ] **Step 4: Roll back and re-apply to confirm `downgrade()` works**

```bash
cd console/backend
alembic downgrade -1
alembic upgrade head
```

Expected: both commands succeed; the post-upgrade `\d youtube_videos` again shows all three columns.

- [ ] **Step 5: Commit**

```bash
git add console/backend/alembic/versions/015_youtube_video_visual_playlist.py
git commit -m "feat(youtube-videos): migration 015 — add visual playlist + loop mode columns"
```

---

## Task 2: Extend `YoutubeVideo` SQLAlchemy model

**Files:**
- Modify: `console/backend/models/youtube_video.py` (after line 56)

- [ ] **Step 1: Write a failing test**

Create `tests/test_youtube_video_service_visual_playlist.py`:

```python
import uuid

from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo


def _seed_template(db, output_format: str = "landscape_long") -> VideoTemplate:
    """Insert a fresh VideoTemplate with a unique slug (DB session is per-test)."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    t = VideoTemplate(slug=slug, label="Test", output_format=output_format)
    db.add(t)
    db.flush()
    return t


def test_youtube_video_model_has_visual_playlist_columns(db):
    """The new playlist columns are exposed as Mapped attrs with correct defaults."""
    template = _seed_template(db)
    v = YoutubeVideo(title="t", template_id=template.id)
    db.add(v)
    db.flush()

    assert v.visual_asset_ids == []
    assert v.visual_clip_durations_s == []
    assert v.visual_loop_mode == "concat_loop"
```

- [ ] **Step 2: Run it and confirm failure**

```bash
pytest tests/test_youtube_video_service_visual_playlist.py::test_youtube_video_model_has_visual_playlist_columns -v
```

Expected: `AttributeError` (or similar) — those attributes don't exist on the model yet.

- [ ] **Step 3: Add the three Mapped columns**

Edit `console/backend/models/youtube_video.py` — append after the existing `video_preview_path` line (after line 56):

```python
    # Visual playlist + loop mode (added by migration 015)
    visual_asset_ids:        Mapped[list[int]]   = mapped_column(ARRAY(Integer), default=list, server_default="{}", nullable=False)
    visual_clip_durations_s: Mapped[list[float]] = mapped_column(ARRAY(Float),   default=list, server_default="{}", nullable=False)
    visual_loop_mode:        Mapped[str]         = mapped_column(String(20), default="concat_loop", server_default="concat_loop", nullable=False)
```

- [ ] **Step 4: Re-run the test**

```bash
pytest tests/test_youtube_video_service_visual_playlist.py::test_youtube_video_model_has_visual_playlist_columns -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add console/backend/models/youtube_video.py tests/test_youtube_video_service_visual_playlist.py
git commit -m "feat(youtube-videos): expose visual playlist columns on YoutubeVideo model"
```

---

## Task 3: Surface and persist new fields through service + schemas

**Files:**
- Modify: `console/backend/routers/youtube_videos.py` (lines 19-54)
- Modify: `console/backend/services/youtube_video_service.py` (`_video_to_dict`, `create_video`)
- Modify: `tests/test_youtube_video_service_visual_playlist.py`

- [ ] **Step 1: Append a failing test for create round-trip**

Add to `tests/test_youtube_video_service_visual_playlist.py`:

```python
def test_create_video_persists_visual_playlist_fields(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    from console.backend.models.video_asset import VideoAsset

    template = _seed_template(db)
    a1 = VideoAsset(file_path="/tmp/a1.mp4", source="manual", asset_type="video_clip")
    a2 = VideoAsset(file_path="/tmp/a2.jpg", source="manual", asset_type="still_image")
    db.add_all([a1, a2])
    db.flush()

    svc = YoutubeVideoService(db)
    out = svc.create_video({
        "title": "t",
        "template_id": template.id,
        "visual_asset_ids":        [a1.id, a2.id],
        "visual_clip_durations_s": [0.0, 3.0],
        "visual_loop_mode":        "per_clip",
    })

    assert out["visual_asset_ids"]        == [a1.id, a2.id]
    assert out["visual_clip_durations_s"] == [0.0, 3.0]
    assert out["visual_loop_mode"]        == "per_clip"
```

- [ ] **Step 2: Run it and confirm failure**

```bash
pytest tests/test_youtube_video_service_visual_playlist.py::test_create_video_persists_visual_playlist_fields -v
```

Expected: `KeyError` on `out["visual_asset_ids"]` — `_video_to_dict` doesn't surface those keys yet, and `create_video` ignores them.

- [ ] **Step 3: Extend `_video_to_dict`**

In `console/backend/services/youtube_video_service.py`, inside the `_video_to_dict` return dict (after the `"video_preview_path": v.video_preview_path,` line), add:

```python
        "visual_asset_ids":        list(v.visual_asset_ids or []),
        "visual_clip_durations_s": list(v.visual_clip_durations_s or []),
        "visual_loop_mode":        v.visual_loop_mode or "concat_loop",
```

- [ ] **Step 4: Extend `create_video` to persist them**

In `create_video`, append three kwargs to the `YoutubeVideo(...)` constructor call (after the `seo_tags=data.get("seo_tags"),` line — keep it ABOVE `status="draft"`):

```python
            visual_asset_ids=data.get("visual_asset_ids") or [],
            visual_clip_durations_s=data.get("visual_clip_durations_s") or [],
            visual_loop_mode=data.get("visual_loop_mode") or "concat_loop",
```

- [ ] **Step 5: Add the three fields to both Pydantic schemas**

In `console/backend/routers/youtube_videos.py`, change the imports at the top to include `Literal`:

```python
from typing import Literal
```

Then append to `YoutubeVideoCreate` (after `parent_youtube_video_id: int | None = None`):

```python
    visual_asset_ids:        list[int] | None = None
    visual_clip_durations_s: list[float] | None = None
    visual_loop_mode:        Literal["concat_loop", "per_clip"] | None = None
```

And append to `YoutubeVideoUpdate` (after `seo_tags: list[str] | None = None`):

```python
    visual_asset_ids:        list[int] | None = None
    visual_clip_durations_s: list[float] | None = None
    visual_loop_mode:        Literal["concat_loop", "per_clip"] | None = None
```

- [ ] **Step 6: Re-run the test**

```bash
pytest tests/test_youtube_video_service_visual_playlist.py -v
```

Expected: both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add console/backend/services/youtube_video_service.py \
        console/backend/routers/youtube_videos.py \
        tests/test_youtube_video_service_visual_playlist.py
git commit -m "feat(youtube-videos): create-time round-trip for visual playlist fields"
```

---

## Task 4: `update_video` — edit-reset path with status guard, validation, and artifact cleanup

**Files:**
- Modify: `console/backend/services/youtube_video_service.py` (`update_video`)
- Create: `tests/test_youtube_video_service_update.py`

This is the core of the "edit existing video" feature. After this task, the existing `PUT /api/youtube-videos/{id}` endpoint (already wired) will perform the reset behaviour described in §5.2 of the spec.

- [ ] **Step 1: Write a failing test for the status whitelist**

Create `tests/test_youtube_video_service_update.py`:

```python
import uuid

import pytest
from pathlib import Path

from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.services.youtube_video_service import YoutubeVideoService


def _seed_template(db) -> VideoTemplate:
    slug = f"test-{uuid.uuid4().hex[:8]}"
    t = VideoTemplate(slug=slug, label="Test", output_format="landscape_long")
    db.add(t)
    db.flush()
    return t


def _seed_video(db, **overrides):
    template = _seed_template(db)
    v = YoutubeVideo(title="t", template_id=template.id, **overrides)
    db.add(v)
    db.flush()
    return v


def test_update_video_rejects_done_status(db):
    v = _seed_video(db, status="done")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="cannot be edited"):
        svc.update_video(v.id, {"title": "new"}, user_id=None)


def test_update_video_rejects_published_status(db):
    v = _seed_video(db, status="published")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="cannot be edited"):
        svc.update_video(v.id, {"title": "new"}, user_id=None)


def test_update_video_rejects_actively_running_statuses(db):
    svc = YoutubeVideoService(db)
    for status in ("queued", "rendering", "audio_preview_rendering", "video_preview_rendering"):
        v = _seed_video(db, status=status)
        with pytest.raises(ValueError, match="cannot be edited"):
            svc.update_video(v.id, {"title": "new"}, user_id=None)
```

- [ ] **Step 2: Run and confirm failure**

```bash
pytest tests/test_youtube_video_service_update.py -v
```

Expected: tests fail because the current `update_video` accepts any status.

- [ ] **Step 3: Add the status guard at the top of `update_video`**

Open `console/backend/services/youtube_video_service.py` and replace the body of `update_video` (currently lines 238-261) with:

```python
    EDITABLE_STATUSES = {"draft", "failed", "audio_preview_ready", "video_preview_ready"}

    def update_video(self, video_id: int, data: dict, user_id: int | None = None) -> dict:
        """Edit fields on a YouTube video and reset to draft, discarding any preview/output artifacts."""
        v = self.db.get(YoutubeVideo, video_id)
        if not v:
            raise KeyError(f"YoutubeVideo {video_id} not found")
        if v.status not in self.EDITABLE_STATUSES:
            raise ValueError(
                f"Video in status {v.status!r} cannot be edited "
                f"(allowed: {sorted(self.EDITABLE_STATUSES)})"
            )

        # Validate visual playlist BEFORE any writes
        playlist_validation = self._validate_visual_playlist(data)

        editable_fields = [
            "title", "theme", "music_track_id", "music_track_ids", "visual_asset_id",
            "sfx_overrides", "sfx_pool", "sfx_density_seconds", "black_from_seconds",
            "skip_previews", "target_duration_h", "output_quality",
            "seo_title", "seo_description", "seo_tags",
            "visual_asset_ids", "visual_clip_durations_s", "visual_loop_mode",
        ]
        changed = {f: data[f] for f in editable_fields if f in data}

        # Apply normalized durations array if validation rewrote it
        if playlist_validation is not None:
            changed["visual_clip_durations_s"] = playlist_validation

        for field, value in changed.items():
            setattr(v, field, value)

        # Reset to draft + discard orphaned artifacts
        discarded = self._discard_render_artifacts(v)
        v.status = "draft"
        v.celery_task_id = None

        try:
            _audit(
                self.db,
                user_id,
                "video_edit_reset",
                "youtube_video",
                str(video_id),
                {"changed_fields": sorted(changed.keys()), "discarded_artifacts": discarded},
            )
            self.db.commit()
            self.db.refresh(v)
        except Exception:
            self.db.rollback()
            raise
        return _video_to_dict(v)
```

Also add the class attribute and the two helper methods (right above `update_video`):

```python
    EDITABLE_STATUSES = {"draft", "failed", "audio_preview_ready", "video_preview_ready"}

    def _validate_visual_playlist(self, data: dict) -> list[float] | None:
        """Validate visual playlist fields. Returns the normalized durations array if rewritten, else None.

        Raises ValueError on invalid combinations.
        """
        if "visual_asset_ids" not in data:
            return None
        asset_ids = data.get("visual_asset_ids") or []
        if not asset_ids:
            return None

        from console.backend.models.video_asset import VideoAsset
        rows = self.db.query(VideoAsset).filter(VideoAsset.id.in_(asset_ids)).all()
        rows_by_id = {r.id: r for r in rows}
        for aid in asset_ids:
            if aid not in rows_by_id:
                raise ValueError(f"visual_asset_ids includes unknown asset {aid}")

        durations = list(data.get("visual_clip_durations_s") or [])
        if durations and len(durations) != len(asset_ids):
            raise ValueError(
                f"visual_clip_durations_s length ({len(durations)}) "
                f"must match visual_asset_ids length ({len(asset_ids)})"
            )
        if not durations:
            durations = [0.0] * len(asset_ids)

        loop_mode = data.get("visual_loop_mode") or "concat_loop"
        if loop_mode not in ("concat_loop", "per_clip"):
            raise ValueError(f"visual_loop_mode must be 'concat_loop' or 'per_clip', got {loop_mode!r}")

        # Per-mode duration rules
        for i, aid in enumerate(asset_ids):
            asset = rows_by_id[aid]
            is_still = asset.asset_type == "still_image"
            if loop_mode == "concat_loop":
                if is_still and durations[i] <= 0:
                    durations[i] = 3.0
            else:  # per_clip
                if is_still and durations[i] <= 0:
                    durations[i] = 3.0
                elif not is_still and durations[i] <= 0:
                    raise ValueError(
                        f"per_clip mode requires duration > 0 for video at index {i} (asset {aid})"
                    )
        return durations

    def _discard_render_artifacts(self, v: YoutubeVideo) -> list[str]:
        """Delete preview + output files from disk; null the path columns. Return list of discarded paths."""
        from pathlib import Path

        discarded: list[str] = []
        for attr in ("audio_preview_path", "video_preview_path", "output_path"):
            path_str = getattr(v, attr, None)
            if path_str:
                p = Path(path_str)
                if p.is_file():
                    try:
                        p.unlink()
                        discarded.append(path_str)
                    except OSError:
                        pass  # best-effort; we still null the column
                setattr(v, attr, None)
        return discarded
```

- [ ] **Step 4: Re-run the status-guard tests**

```bash
pytest tests/test_youtube_video_service_update.py -v
```

Expected: the three status-rejection tests PASS.

- [ ] **Step 5: Add tests for the happy-path reset behaviour**

Append to `tests/test_youtube_video_service_update.py`:

```python
def test_update_video_resets_to_draft_and_clears_celery_task(db):
    v = _seed_video(db, status="failed", celery_task_id="some-task-id")
    out = YoutubeVideoService(db).update_video(v.id, {"title": "new"}, user_id=None)
    assert out["status"] == "draft"
    assert out["celery_task_id"] is None
    assert out["title"] == "new"


def test_update_video_deletes_preview_files(tmp_path, db):
    audio = tmp_path / "audio.wav"
    video = tmp_path / "video.mp4"
    audio.write_bytes(b"fake")
    video.write_bytes(b"fake")
    v = _seed_video(
        db,
        status="video_preview_ready",
        audio_preview_path=str(audio),
        video_preview_path=str(video),
    )
    out = YoutubeVideoService(db).update_video(v.id, {"title": "new"}, user_id=None)
    assert not audio.exists()
    assert not video.exists()
    assert out["audio_preview_path"] is None
    assert out["video_preview_path"] is None


def test_update_video_validates_unknown_asset_ids(db):
    v = _seed_video(db, status="draft")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="unknown asset"):
        svc.update_video(v.id, {"visual_asset_ids": [99999]}, user_id=None)


def test_update_video_validates_per_clip_video_requires_positive_duration(db):
    from console.backend.models.video_asset import VideoAsset
    a = VideoAsset(file_path="/tmp/a.mp4", source="manual", asset_type="video_clip")
    db.add(a); db.flush()
    v = _seed_video(db, status="draft")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="per_clip mode requires duration > 0"):
        svc.update_video(v.id, {
            "visual_asset_ids": [a.id],
            "visual_clip_durations_s": [0.0],
            "visual_loop_mode": "per_clip",
        }, user_id=None)


def test_update_video_autofills_still_duration(db):
    from console.backend.models.video_asset import VideoAsset
    img = VideoAsset(file_path="/tmp/a.jpg", source="manual", asset_type="still_image")
    db.add(img); db.flush()
    v = _seed_video(db, status="draft")
    out = YoutubeVideoService(db).update_video(v.id, {
        "visual_asset_ids": [img.id],
        "visual_clip_durations_s": [0.0],
        "visual_loop_mode": "concat_loop",
    }, user_id=None)
    assert out["visual_clip_durations_s"] == [3.0]


def test_update_video_rejects_durations_length_mismatch(db):
    from console.backend.models.video_asset import VideoAsset
    a = VideoAsset(file_path="/tmp/a.mp4", source="manual", asset_type="video_clip")
    db.add(a); db.flush()
    v = _seed_video(db, status="draft")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="length .* must match"):
        svc.update_video(v.id, {
            "visual_asset_ids": [a.id],
            "visual_clip_durations_s": [1.0, 2.0],
        }, user_id=None)
```

- [ ] **Step 6: Run all the update tests**

```bash
pytest tests/test_youtube_video_service_update.py -v
```

Expected: all eight tests PASS.

- [ ] **Step 7: Commit**

```bash
git add console/backend/services/youtube_video_service.py \
        tests/test_youtube_video_service_update.py
git commit -m "feat(youtube-videos): edit-reset semantics on update_video"
```

---

## Task 5: Renderer — visual playlist support in `render_landscape`

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Create: `tests/test_youtube_ffmpeg_visual_playlist.py`

The renderer must understand the new `visual_asset_ids` array and `visual_loop_mode` so a multi-visual video actually renders. Per the spec's rollout order, this **must precede** any frontend UI that lets users save such videos.

- [ ] **Step 1: Write failing tests for the resolver**

Create `tests/test_youtube_ffmpeg_visual_playlist.py`:

```python
from unittest.mock import MagicMock


def _make_video(visual_asset_ids=None, visual_clip_durations_s=None,
                visual_loop_mode="concat_loop", visual_asset_id=None):
    v = MagicMock()
    v.visual_asset_ids = visual_asset_ids if visual_asset_ids is not None else []
    v.visual_clip_durations_s = visual_clip_durations_s if visual_clip_durations_s is not None else []
    v.visual_loop_mode = visual_loop_mode
    v.visual_asset_id = visual_asset_id
    return v


def test_resolve_visual_playlist_returns_empty_when_no_ids():
    from pipeline.youtube_ffmpeg import resolve_visual_playlist
    assert resolve_visual_playlist(_make_video(), MagicMock()) == []


def test_resolve_visual_playlist_returns_assets_in_order():
    a1 = MagicMock(); a1.id = 1; a1.file_path = "/tmp/a1.mp4"; a1.asset_type = "video_clip"
    a2 = MagicMock(); a2.id = 2; a2.file_path = "/tmp/a2.jpg"; a2.asset_type = "still_image"
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [a2, a1]  # DB order != playlist order

    from pipeline.youtube_ffmpeg import resolve_visual_playlist
    result = resolve_visual_playlist(_make_video(visual_asset_ids=[1, 2]), db)
    assert [r.id for r in result] == [1, 2]  # preserves playlist order, not DB order


def test_resolve_visual_playlist_drops_assets_with_missing_files(tmp_path):
    real = tmp_path / "real.mp4"
    real.write_bytes(b"x")  # ensures Path.is_file() is True for the first asset
    a1 = MagicMock(); a1.id = 1; a1.file_path = str(real); a1.asset_type = "video_clip"
    a2 = MagicMock(); a2.id = 2; a2.file_path = str(tmp_path / "definitely_missing.mp4"); a2.asset_type = "video_clip"
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [a1, a2]

    from pipeline.youtube_ffmpeg import resolve_visual_playlist
    result = resolve_visual_playlist(_make_video(visual_asset_ids=[1, 2]), db)
    assert [r.id for r in result] == [1]
```

- [ ] **Step 2: Run and confirm failure**

```bash
pytest tests/test_youtube_ffmpeg_visual_playlist.py -v
```

Expected: ImportError — `resolve_visual_playlist` doesn't exist yet.

- [ ] **Step 3: Implement `resolve_visual_playlist`**

In `pipeline/youtube_ffmpeg.py`, after `resolve_visual` (after line 30), add:

```python
def resolve_visual_playlist(video, db):
    """Return the ordered list of VideoAsset rows whose files exist on disk.

    Empty list means "use legacy single-asset path" (caller falls back to resolve_visual).
    """
    ids = list(getattr(video, "visual_asset_ids", None) or [])
    if not ids:
        return []
    from console.backend.models.video_asset import VideoAsset

    rows = db.query(VideoAsset).filter(VideoAsset.id.in_(ids)).all()
    by_id = {r.id: r for r in rows}
    out = []
    for aid in ids:
        a = by_id.get(aid)
        if a and a.file_path and Path(a.file_path).is_file():
            out.append(a)
        else:
            logger.warning("Visual asset %s missing or file not on disk; skipping in playlist", aid)
    return out
```

- [ ] **Step 4: Re-run and confirm the resolver tests pass**

```bash
pytest tests/test_youtube_ffmpeg_visual_playlist.py -v
```

Expected: PASS.

- [ ] **Step 5: Add a failing test for the segment builder**

Append to `tests/test_youtube_ffmpeg_visual_playlist.py`:

```python
def test_build_visual_segment_uses_native_length_for_videos_in_concat_loop(monkeypatch, tmp_path):
    """In concat_loop mode, video items with duration=0 should use -i without -t (native length)."""
    a = MagicMock(); a.file_path = str(tmp_path / "v.mp4"); a.asset_type = "video_clip"
    (tmp_path / "v.mp4").write_bytes(b"fake")

    captured = {}
    def fake_run(cmd, timeout):
        captured["cmd"] = cmd
    monkeypatch.setattr("pipeline.youtube_ffmpeg._run_ffmpeg", fake_run)

    from pipeline.youtube_ffmpeg import _build_visual_segment
    out = _build_visual_segment(
        playlist=[a],
        durations=[0.0],
        loop_mode="concat_loop",
        w=1920, h=1080, target_dur_s=60,
        output_dir=tmp_path,
    )
    assert out is not None
    cmd = " ".join(captured["cmd"])
    # Sanity: ffmpeg should be invoked with the input path and produce an mp4 in output_dir
    assert "v.mp4" in cmd
    assert str(out).endswith(".mp4")


def test_build_visual_segment_per_clip_mode_uses_per_item_duration(monkeypatch, tmp_path):
    a1 = MagicMock(); a1.file_path = str(tmp_path / "v1.mp4"); a1.asset_type = "video_clip"
    a2 = MagicMock(); a2.file_path = str(tmp_path / "img.jpg"); a2.asset_type = "still_image"
    (tmp_path / "v1.mp4").write_bytes(b"fake")
    (tmp_path / "img.jpg").write_bytes(b"fake")

    captured = {}
    def fake_run(cmd, timeout):
        captured["cmd"] = cmd
    monkeypatch.setattr("pipeline.youtube_ffmpeg._run_ffmpeg", fake_run)

    from pipeline.youtube_ffmpeg import _build_visual_segment
    out = _build_visual_segment(
        playlist=[a1, a2],
        durations=[10.0, 3.0],
        loop_mode="per_clip",
        w=1920, h=1080, target_dur_s=60,
        output_dir=tmp_path,
    )
    cmd = " ".join(captured["cmd"])
    # Both per-item durations should appear in the filter graph
    assert "10" in cmd
    assert "3" in cmd
```

- [ ] **Step 6: Run and confirm failure**

```bash
pytest tests/test_youtube_ffmpeg_visual_playlist.py -v
```

Expected: ImportError on `_build_visual_segment`.

- [ ] **Step 7: Implement `_build_visual_segment`**

In `pipeline/youtube_ffmpeg.py`, after `resolve_visual_playlist`, add:

```python
def _build_visual_segment(
    playlist,
    durations: list[float],
    loop_mode: str,
    w: int,
    h: int,
    target_dur_s: int,
    output_dir: Path,
) -> Path | None:
    """Render the visual playlist to a single concatenated MP4 (no audio), then loop to target_dur_s.

    Returns the file path of the looped concat, or None if playlist was empty.
    """
    if not playlist:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: render each item to a normalized clip (same scale, fps, codec, no audio)
    item_paths: list[Path] = []
    for i, asset in enumerate(playlist):
        is_image = asset.asset_type == "still_image"
        # Resolve per-item duration: 0 in concat_loop+video means "native length"
        item_dur = durations[i] if i < len(durations) else 0.0
        out = output_dir / f"vseg_{i}.mp4"

        cmd = ["ffmpeg", "-y"]
        if is_image:
            cmd += ["-loop", "1", "-t", str(item_dur or 3.0), "-i", asset.file_path]
        elif loop_mode == "per_clip" and item_dur > 0:
            # Loop the video so it fills the slot; -t bounds it
            cmd += ["-stream_loop", "-1", "-t", str(item_dur), "-i", asset.file_path]
        elif loop_mode == "concat_loop" and item_dur > 0:
            # Trim to user-specified duration
            cmd += ["-t", str(item_dur), "-i", asset.file_path]
        else:
            # concat_loop + video + duration=0 → native length
            cmd += ["-i", asset.file_path]

        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps=30"
        )
        cmd += ["-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-pix_fmt", "yuv420p", str(out)]
        _run_ffmpeg(cmd, max(120, int(item_dur or 60) * 4))
        item_paths.append(out)

    # Step 2: concat the items with the concat demuxer
    list_file = output_dir / "vseg_list.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in item_paths))
    concat_path = output_dir / "vseg_concat.mp4"
    _run_ffmpeg(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(concat_path)],
        timeout=300,
    )

    # Step 3: loop the concat segment to target_dur_s (using -stream_loop on the demuxer side)
    looped_path = output_dir / "vseg_looped.mp4"
    _run_ffmpeg(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(concat_path),
         "-t", str(target_dur_s), "-c", "copy", str(looped_path)],
        timeout=max(300, target_dur_s + 60),
    )
    return looped_path
```

- [ ] **Step 8: Wire the playlist into `render_landscape`**

In `render_landscape` (lines 280-409), find the section starting `visual_path = resolve_visual(video, db)` (around line 306) and replace through the `# Visual input` block (around line 343) with:

```python
    # Try the new playlist path first; fall back to legacy single-asset
    playlist = resolve_visual_playlist(video, db)
    playlist_segment_path: Path | None = None
    if playlist:
        playlist_segment_path = _build_visual_segment(
            playlist=playlist,
            durations=list(getattr(video, "visual_clip_durations_s", None) or []),
            loop_mode=getattr(video, "visual_loop_mode", None) or "concat_loop",
            w=w, h=h, target_dur_s=target_dur,
            output_dir=output_dir,
        )

    if playlist_segment_path is not None:
        visual_path = str(playlist_segment_path)
        is_image = False  # the segment is always an mp4
    else:
        visual_path = resolve_visual(video, db)
        is_image = visual_path is not None and Path(visual_path).suffix.lower() in IMAGE_EXTS
```

Then, in the existing `# Visual input` block, when `playlist_segment_path` is set, the visual is already exact-duration so we should NOT add `-stream_loop`. Update the visual-input branch (currently around line 337-343) to:

```python
    # Visual input
    if visual_path and Path(visual_path).is_file():
        if is_image:
            cmd += ["-loop", "1", "-i", visual_path]
        elif playlist_segment_path is not None:
            # Pre-rendered playlist segment: exact duration, no looping needed
            cmd += ["-i", visual_path]
        else:
            cmd += ["-stream_loop", "-1", "-i", visual_path]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r=30"]
```

- [ ] **Step 9: Run all the renderer tests, both new and existing, to ensure nothing regressed**

```bash
pytest tests/test_youtube_ffmpeg.py tests/test_youtube_ffmpeg_visual_playlist.py -v
```

Expected: all tests PASS. The existing tests use `visual_asset_ids=[]` by default in `_make_video`, so they hit the legacy fallback path.

- [ ] **Step 10: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg_visual_playlist.py
git commit -m "feat(renderer): visual playlist + concat-loop / per-clip modes for landscape render"
```

---

## Task 6: `PreviewPlayer` shared component

**Files:**
- Create: `console/frontend/src/components/PreviewPlayer.jsx`

No frontend test framework is configured in this repo (no `vitest`/`jest` in `package.json`), so frontend tasks are verified manually after implementation. Each task has a verification step that exercises the change in the running dev server.

- [ ] **Step 1: Create the component**

Write `console/frontend/src/components/PreviewPlayer.jsx`:

```jsx
import { useEffect, useRef, useState } from 'react'

// Module-level "currently playing" reference so starting one preview stops any other.
let _activeStop = null

/**
 * PreviewPlayer
 * Props:
 *   src   — URL of the audio or video file
 *   kind  — 'audio' | 'video' | 'image'
 *   size  — 'sm' (default) | 'md' for thumbnail rendering
 *   className — extra classes for the wrapper
 *
 * For 'image', renders a small static preview tile (no play button).
 * For 'audio'/'video', renders a play/pause button. Clicking play stops any other
 * PreviewPlayer that is currently playing.
 */
export default function PreviewPlayer({ src, kind, size = 'sm', className = '' }) {
  const mediaRef = useRef(null)
  const [playing, setPlaying] = useState(false)

  useEffect(() => () => {
    // On unmount, stop playback and clear the active-stop ref if it points at us
    if (mediaRef.current) mediaRef.current.pause()
    if (_activeStop && _activeStop === stop) _activeStop = null
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const stop = () => {
    if (mediaRef.current) {
      mediaRef.current.pause()
      mediaRef.current.currentTime = 0
    }
    setPlaying(false)
  }

  const handleToggle = (e) => {
    e.stopPropagation()
    if (playing) {
      stop()
      _activeStop = null
      return
    }
    if (_activeStop && _activeStop !== stop) _activeStop()
    _activeStop = stop
    if (mediaRef.current) {
      mediaRef.current.play().catch(() => {})
      setPlaying(true)
    }
  }

  if (kind === 'image') {
    return (
      <img
        src={src}
        alt=""
        className={`object-cover bg-[#0d0d0f] ${size === 'md' ? 'w-24 h-24' : 'w-12 h-12'} ${className}`}
      />
    )
  }

  return (
    <div className={`inline-flex items-center ${className}`}>
      <button
        type="button"
        onClick={handleToggle}
        aria-label={playing ? 'Pause preview' : 'Play preview'}
        className="w-7 h-7 flex items-center justify-center rounded bg-[#1c1c22] border border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0] hover:border-[#7c6af7] transition-colors"
      >
        {playing ? '⏸' : '▶'}
      </button>
      {kind === 'audio' ? (
        <audio ref={mediaRef} src={src} preload="none" onEnded={() => { setPlaying(false); if (_activeStop === stop) _activeStop = null }} />
      ) : (
        <video ref={mediaRef} src={src} preload="none" muted={false} className="hidden" onEnded={() => { setPlaying(false); if (_activeStop === stop) _activeStop = null }} />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build doesn't break**

```bash
cd console/frontend
npm run build
```

Expected: `vite build` completes without errors. The new component is unused so far, so this only proves it parses.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/components/PreviewPlayer.jsx
git commit -m "feat(console): add PreviewPlayer shared primitive for audio/video/image previews"
```

---

## Task 7: Add `PreviewPlayer` to `SfxPoolEditor`

**Files:**
- Modify: `console/frontend/src/components/SfxPoolEditor.jsx`

- [ ] **Step 1: Add the import**

In `console/frontend/src/components/SfxPoolEditor.jsx`, after the existing imports (line 3):

```jsx
import PreviewPlayer from './PreviewPlayer.jsx'
```

- [ ] **Step 2: Add a play button in the selected-pool row**

Replace the row markup inside the `pool.map(...)` block (lines 79-107) with:

```jsx
            return (
              <div
                key={asset_id}
                className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded"
              >
                <PreviewPlayer src={`/api/sfx/${asset_id}/stream`} kind="audio" />
                <span className="text-sm text-[#e8e8f0] flex-1 truncate">
                  {s?.title || `SFX #${asset_id}`}
                </span>
                <input
                  type="range"
                  min={0} max={1} step={0.05}
                  value={volume ?? 1.0}
                  onChange={e => setVolume(asset_id, parseFloat(e.target.value))}
                  className="w-24 accent-[#7c6af7]"
                  aria-label={`Volume for ${s?.title || `SFX ${asset_id}`}`}
                />
                <span className="text-xs font-mono text-[#9090a8] w-10 text-right">
                  {Math.round((volume ?? 1.0) * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => remove(asset_id)}
                  className="text-[#f87171] text-xs px-1"
                  aria-label={`Remove ${s?.title || `SFX ${asset_id}`}`}
                >×</button>
              </div>
            )
```

- [ ] **Step 3: Add a play button in the picker grid tile**

Replace the picker `<button>` markup inside `filtered.map(...)` (lines 140-152) with:

```jsx
            return (
              <div
                key={s.id}
                className={`flex items-stretch gap-2 px-3 py-2 rounded border ${
                  active ? 'border-[#7c6af7] bg-[#7c6af7]/10' : 'border-[#2a2a32] hover:bg-[#1c1c22]'
                }`}
              >
                <PreviewPlayer src={`/api/sfx/${s.id}/stream`} kind="audio" />
                <button
                  type="button"
                  onClick={() => togglePick(s.id)}
                  className="flex-1 text-left min-w-0"
                >
                  <div className="text-sm text-[#e8e8f0] truncate">{s.title}</div>
                  {s.sound_type && <div className="text-[10px] text-[#5a5a70]">{s.sound_type}</div>}
                </button>
              </div>
            )
```

- [ ] **Step 4: Verify in the running app**

```bash
./console/start.sh   # if not already running
# in another terminal:
cd console/frontend && npm run dev
```

Open <http://localhost:5173>, navigate to **YouTube Videos** → **+ New Video** with an asmr/soundscape template. Scroll to **④b RANDOM SFX POOL** → click **+ Pick SFX**. Confirm:
- Each row in the picker has a ▶ button.
- Clicking ▶ on one row plays the SFX. Clicking ▶ on another row stops the first and plays the second.
- Selecting an SFX adds it to the pool list — that row also has a ▶ button that works the same way.

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/components/SfxPoolEditor.jsx
git commit -m "feat(console): listen-before-select preview button in SFX pool editor"
```

---

## Task 8: Add `PreviewPlayer` to `MusicPlaylistEditor`

**Files:**
- Modify: `console/frontend/src/components/MusicPlaylistEditor.jsx`

- [ ] **Step 1: Add the import**

After the existing imports (line 3):

```jsx
import PreviewPlayer from './PreviewPlayer.jsx'
```

- [ ] **Step 2: Add a play button in the selected playlist row**

Replace the `tracks.map(...)` block (lines 51-77) with:

```jsx
      {tracks.map((t, i) => (
        <div key={`${t.id}-${i}`} className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
          <span className="text-xs font-mono text-[#5a5a70] w-6">{i + 1}</span>
          <PreviewPlayer src={`/api/music/${t.id}/stream`} kind="audio" />
          <span className="text-sm text-[#e8e8f0] flex-1 truncate">{t.title}</span>
          <span className="text-xs font-mono text-[#9090a8]">{Math.round(t.duration_s || 0)}s</span>
          <button
            type="button"
            onClick={() => move(i, -1)}
            disabled={i === 0}
            className="text-xs text-[#9090a8] disabled:opacity-30 px-1"
            aria-label="Move up"
          >↑</button>
          <button
            type="button"
            onClick={() => move(i, +1)}
            disabled={i === tracks.length - 1}
            className="text-xs text-[#9090a8] disabled:opacity-30 px-1"
            aria-label="Move down"
          >↓</button>
          <button
            type="button"
            onClick={() => remove(i)}
            className="text-xs text-[#f87171] px-1"
            aria-label="Remove track"
          >×</button>
        </div>
      ))}
```

- [ ] **Step 3: Add a play button in the picker rows**

Replace the `filtered.map(...)` block inside the modal (lines 90-106) with:

```jsx
          {filtered.map(t => {
            const already = trackIds.includes(t.id)
            return (
              <div
                key={t.id}
                className="flex items-center gap-2 px-3 py-2 hover:bg-[#1c1c22] rounded"
              >
                <PreviewPlayer src={`/api/music/${t.id}/stream`} kind="audio" />
                <button
                  type="button"
                  onClick={() => add(t.id)}
                  className="flex-1 text-left text-sm text-[#e8e8f0] flex items-center justify-between gap-2"
                >
                  <span className="truncate">
                    {t.title}{' '}
                    <span className="text-[#5a5a70] text-xs">({Math.round(t.duration_s || 0)}s)</span>
                  </span>
                  {already && <span className="text-[10px] text-[#7c6af7]">in playlist</span>}
                </button>
              </div>
            )
          })}
```

- [ ] **Step 4: Verify**

In the running app, open the YouTube Videos modal for an ASMR/Soundscape template. In **② MUSIC** → **+ Add Track**, confirm each row has a working ▶ button and the single-track-at-a-time behaviour works across SFX-pool and music-playlist pickers (clicking a music ▶ stops a playing SFX preview and vice versa).

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/components/MusicPlaylistEditor.jsx
git commit -m "feat(console): listen-before-select preview button in music playlist editor"
```

---

## Task 9: `SfxPickerModal` — single-select modal with preview

**Files:**
- Create: `console/frontend/src/components/SfxPickerModal.jsx`

- [ ] **Step 1: Write the component**

```jsx
import { useEffect, useMemo, useState } from 'react'
import { Modal, Button } from './index.jsx'
import { fetchApi } from '../api/client.js'
import PreviewPlayer from './PreviewPlayer.jsx'

const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

/**
 * SfxPickerModal — single-select SFX picker with per-row preview.
 *
 * Props:
 *   open           — boolean, controls visibility
 *   onClose()      — close without selection
 *   onSelect(asset)— called with the chosen { id, title, sound_type, ... }
 *   selectedId     — currently selected asset id (highlighted)
 */
export default function SfxPickerModal({ open, onClose, onSelect, selectedId = null }) {
  const [library, setLibrary] = useState([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    if (!open) return
    fetchApi('/api/sfx?per_page=500')
      .then(r => setLibrary(unwrap(r)))
      .catch(() => setLibrary([]))
  }, [open])

  const filtered = useMemo(() => {
    if (!search) return library
    const q = search.toLowerCase()
    return library.filter(s =>
      (s.title || '').toLowerCase().includes(q) ||
      (s.sound_type || '').toLowerCase().includes(q)
    )
  }, [library, search])

  const handlePick = (s) => {
    onSelect(s)
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="Pick SFX">
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search by title or sound type…"
        className="w-full mb-3 bg-[#16161a] border border-[#2a2a32] rounded-lg px-3 py-1.5 text-sm text-[#e8e8f0] placeholder:text-[#5a5a70] focus:outline-none focus:border-[#7c6af7] transition-colors"
      />
      <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
        {filtered.length === 0 && (
          <p className="col-span-2 text-xs text-[#5a5a70] px-2 py-3">No SFX assets.</p>
        )}
        {filtered.map(s => {
          const active = s.id === selectedId
          return (
            <div
              key={s.id}
              className={`flex items-center gap-2 px-3 py-2 rounded border ${
                active ? 'border-[#7c6af7] bg-[#7c6af7]/10' : 'border-[#2a2a32] hover:bg-[#1c1c22]'
              }`}
            >
              <PreviewPlayer src={`/api/sfx/${s.id}/stream`} kind="audio" />
              <button
                type="button"
                onClick={() => handlePick(s)}
                className="flex-1 text-left min-w-0"
              >
                <div className="text-sm text-[#e8e8f0] truncate">{s.title}</div>
                {s.sound_type && <div className="text-[10px] text-[#5a5a70]">{s.sound_type}</div>}
              </button>
            </div>
          )
        })}
      </div>
      <div className="flex justify-end mt-3">
        <Button variant="ghost" onClick={onClose}>Close</Button>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 2: Confirm build still passes**

```bash
cd console/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/components/SfxPickerModal.jsx
git commit -m "feat(console): add SfxPickerModal — single-select picker with preview"
```

---

## Task 10: Wire `SfxPickerModal` into ④ SFX LAYERS

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (the ④ SFX LAYERS section, lines 633-685)

- [ ] **Step 1: Add the import**

At the top of `YouTubeVideosPage.jsx` (after line 8), add:

```jsx
import SfxPickerModal from '../components/SfxPickerModal.jsx'
```

- [ ] **Step 2: Add picker-open state inside `CreationPanel`**

Inside `CreationPanel` (right after the `[sfxLayers, setSfxLayers]` declaration around line 122-126), add:

```jsx
  const [sfxPickerLayer, setSfxPickerLayer] = useState(null)  // 'foreground' | 'midground' | 'background' | null
```

- [ ] **Step 3: Replace the layer card body**

Find the ④ SFX LAYERS section (lines 633-685) and replace the entire `[{...}, {...}, {...}].map(...)` block with:

```jsx
              {[
                { key: 'foreground', label: 'Foreground', defaultVol: 0.6 },
                { key: 'midground',  label: 'Midground',  defaultVol: 0.3 },
                { key: 'background', label: 'Background', defaultVol: 0.1 },
              ].map(({ key, label }) => {
                const sfxPack = template?.sfx_pack?.[key]
                const layerDefault = sfxList.find(s => s.id === sfxPack?.asset_id)
                const pickedId = sfxLayers[key].asset_id
                const pickedSfx = sfxList.find(s => String(s.id) === String(pickedId))
                return (
                  <div key={key} className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 flex flex-col gap-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-[#9090a8]">{label}</span>
                      {layerDefault && !pickedId && (
                        <span className="text-[10px] text-[#5a5a70] font-mono">template default: {layerDefault.title}</span>
                      )}
                    </div>
                    {pickedId ? (
                      <div className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
                        <PreviewPlayer src={`/api/sfx/${pickedId}/stream`} kind="audio" />
                        <button
                          type="button"
                          onClick={() => setSfxPickerLayer(key)}
                          className="flex-1 text-left text-sm text-[#e8e8f0] truncate"
                        >
                          {pickedSfx?.title || `SFX #${pickedId}`}
                        </button>
                        <button
                          type="button"
                          onClick={() => setSfxLayers(prev => ({ ...prev, [key]: { ...prev[key], asset_id: '' } }))}
                          className="text-[#f87171] text-xs px-1"
                          aria-label={`Clear ${label}`}
                        >×</button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setSfxPickerLayer(key)}
                        className="px-3 py-1.5 rounded border border-dashed border-[#2a2a32] text-xs text-[#9090a8] hover:text-[#e8e8f0] hover:border-[#7c6af7] transition-colors"
                      >
                        + Pick SFX
                      </button>
                    )}
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-[#5a5a70] w-16 shrink-0">Volume</span>
                      <input
                        type="range"
                        min={0} max={1} step={0.05}
                        value={sfxLayers[key].volume}
                        onChange={e => setSfxLayers(prev => ({
                          ...prev,
                          [key]: { ...prev[key], volume: parseFloat(e.target.value) },
                        }))}
                        className="flex-1 accent-[#7c6af7]"
                      />
                      <span className="text-xs text-[#9090a8] font-mono w-8 text-right">
                        {Math.round(sfxLayers[key].volume * 100)}%
                      </span>
                    </div>
                  </div>
                )
              })}
```

Note: this also requires importing `PreviewPlayer` inside the page. Add at the top of `YouTubeVideosPage.jsx` (alongside the SfxPickerModal import):

```jsx
import PreviewPlayer from '../components/PreviewPlayer.jsx'
```

- [ ] **Step 4: Render the picker modal at the bottom of `CreationPanel`**

Just before the closing `</div>` of the panel container (right before the **/* Footer */** comment at line 733), insert:

```jsx
        <SfxPickerModal
          open={sfxPickerLayer !== null}
          onClose={() => setSfxPickerLayer(null)}
          selectedId={sfxPickerLayer ? sfxLayers[sfxPickerLayer].asset_id : null}
          onSelect={(s) => {
            setSfxLayers(prev => ({
              ...prev,
              [sfxPickerLayer]: { ...prev[sfxPickerLayer], asset_id: String(s.id) },
            }))
          }}
        />
```

- [ ] **Step 5: Verify**

In the running app, open **+ New Video** with an ASMR/Soundscape template. In **④ SFX LAYERS**, confirm:
- Each layer initially shows **+ Pick SFX**.
- Clicking it opens the picker modal.
- Each row in the picker has a ▶ that previews the sound.
- Selecting one closes the modal and the layer card now shows the picked SFX as a chip with a ▶ + ✕.
- Clicking ✕ clears it back to **+ Pick SFX**.
- Clicking the chip body re-opens the picker.
- Existing volume slider still works.

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(console): replace SFX layer dropdowns with modal picker (preview-enabled)"
```

---

## Task 11: `VisualPickerModal` — single-select visual picker with preview

**Files:**
- Create: `console/frontend/src/components/VisualPickerModal.jsx`

- [ ] **Step 1: Write the component**

```jsx
import { useEffect, useMemo, useState } from 'react'
import { Modal, Button, Input, Select } from './index.jsx'
import { fetchApi } from '../api/client.js'
import PreviewPlayer from './PreviewPlayer.jsx'

const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

const SOURCES = ['', 'midjourney', 'runway', 'veo', 'manual', 'pexels', 'stock']

/**
 * VisualPickerModal — single-select visual asset picker with thumbnail grid + preview.
 *
 * Props:
 *   open           — boolean
 *   onClose()      — dismiss without choosing
 *   onSelect(asset)— called with the chosen asset { id, file_path, asset_type, source, ... }
 */
export default function VisualPickerModal({ open, onClose, onSelect }) {
  const [assets, setAssets] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')

  useEffect(() => {
    if (!open) return
    setLoading(true)
    const params = new URLSearchParams({ per_page: '200' })
    if (source) params.set('source', source)
    fetchApi(`/api/production/assets?${params}`)
      .then(r => setAssets(unwrap(r)))
      .catch(() => setAssets([]))
      .finally(() => setLoading(false))
  }, [open, source])

  const filtered = useMemo(() => {
    if (!search) return assets
    const q = search.toLowerCase()
    return assets.filter(a =>
      (a.description || '').toLowerCase().includes(q) ||
      (a.keywords || []).some(k => (k || '').toLowerCase().includes(q))
    )
  }, [assets, search])

  return (
    <Modal open={open} onClose={onClose} title="Pick Visual" width="max-w-4xl">
      <div className="flex gap-2 mb-3">
        <Input
          placeholder="Search keywords or description…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1"
        />
        <Select value={source} onChange={e => setSource(e.target.value)} className="w-40">
          {SOURCES.map(s => (
            <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All Sources'}</option>
          ))}
        </Select>
      </div>
      {loading ? (
        <p className="text-xs text-[#5a5a70] py-6 text-center">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-xs text-[#5a5a70] py-6 text-center">No assets found.</p>
      ) : (
        <div className="grid grid-cols-3 gap-3 max-h-[60vh] overflow-y-auto">
          {filtered.map(a => {
            const isImage = a.asset_type === 'still_image'
            const streamUrl = `/api/production/assets/${a.id}/stream`
            return (
              <div
                key={a.id}
                className="border border-[#2a2a32] rounded-lg overflow-hidden bg-[#0d0d0f] flex flex-col"
              >
                <div className="aspect-video relative bg-black flex items-center justify-center">
                  {isImage ? (
                    <img src={streamUrl} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <video
                      src={streamUrl}
                      preload="metadata"
                      controls
                      className="w-full h-full object-contain bg-black"
                    />
                  )}
                </div>
                <div className="p-2 flex items-center gap-2">
                  <span className="text-xs text-[#9090a8] flex-1 truncate">
                    {a.description || `Asset #${a.id}`}
                    <span className="text-[10px] text-[#5a5a70] ml-1">· {a.source}</span>
                  </span>
                  <Button variant="primary" size="sm" onClick={() => { onSelect(a); onClose() }}>
                    Pick
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
      <div className="flex justify-end mt-3">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd console/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/components/VisualPickerModal.jsx
git commit -m "feat(console): add VisualPickerModal — single-select asset picker with previews"
```

---

## Task 12: `VisualPlaylistEditor` — inline ordered list with per-clip duration

**Files:**
- Create: `console/frontend/src/components/VisualPlaylistEditor.jsx`

- [ ] **Step 1: Write the component**

```jsx
import { useEffect, useState } from 'react'
import { Button } from './index.jsx'
import { fetchApi } from '../api/client.js'
import VisualPickerModal from './VisualPickerModal.jsx'

const unwrap = (r) => Array.isArray(r) ? r : (r?.items || [])

/**
 * VisualPlaylistEditor — ordered list of visual assets with per-clip durations.
 *
 * Props:
 *   assetIds      — list of integer asset ids (order matters)
 *   durations     — list of floats parallel to assetIds (0 = native length for videos in concat_loop)
 *   loopMode      — 'concat_loop' | 'per_clip'
 *   onChange({ assetIds, durations }) — emitted on every mutation
 */
export default function VisualPlaylistEditor({ assetIds = [], durations = [], loopMode, onChange }) {
  const [details, setDetails] = useState([])
  const [picker, setPicker] = useState(false)

  useEffect(() => {
    if (assetIds.length === 0) { setDetails([]); return }
    Promise.all(assetIds.map(id =>
      fetchApi(`/api/production/assets/${id}`).catch(() => null)
    )).then(rows => setDetails(rows.filter(Boolean)))
  }, [assetIds.join(',')])

  const detailsById = Object.fromEntries(details.map(a => [a.id, a]))

  const move = (i, dir) => {
    const j = i + dir
    if (j < 0 || j >= assetIds.length) return
    const ids = [...assetIds]
    const durs = [...durations, ...Array(Math.max(0, assetIds.length - durations.length)).fill(0)]
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
    ;[durs[i], durs[j]] = [durs[j], durs[i]]
    onChange({ assetIds: ids, durations: durs })
  }

  const remove = (i) => {
    onChange({
      assetIds: assetIds.filter((_, k) => k !== i),
      durations: durations.filter((_, k) => k !== i),
    })
  }

  const setDuration = (i, value) => {
    const durs = [...durations, ...Array(Math.max(0, assetIds.length - durations.length)).fill(0)]
    durs[i] = value === '' ? 0 : parseFloat(value)
    onChange({ assetIds, durations: durs })
  }

  const add = (asset) => {
    onChange({
      assetIds: [...assetIds, asset.id],
      durations: [...durations, asset.asset_type === 'still_image' ? 3.0 : 0.0],
    })
  }

  return (
    <div className="space-y-2">
      {assetIds.length === 0 && (
        <p className="text-xs text-[#5a5a70]">No visuals selected.</p>
      )}
      {assetIds.map((id, i) => {
        const a = detailsById[id]
        const isImage = a?.asset_type === 'still_image'
        const dur = durations[i] ?? 0
        const placeholder = (loopMode === 'concat_loop' && !isImage)
          ? 'native'
          : '3.0'
        return (
          <div key={`${id}-${i}`} className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
            <span className="text-xs font-mono text-[#5a5a70] w-6">{i + 1}</span>
            <div className="w-16 h-9 bg-[#0d0d0f] rounded overflow-hidden flex items-center justify-center flex-shrink-0">
              {a ? (
                isImage
                  ? <img src={`/api/production/assets/${id}/stream`} alt="" className="w-full h-full object-cover" />
                  : <video src={`/api/production/assets/${id}/stream`} muted preload="metadata" className="w-full h-full object-cover" />
              ) : (
                <span className="text-[9px] text-[#5a5a70]">…</span>
              )}
            </div>
            <span className="text-sm text-[#e8e8f0] flex-1 truncate">
              {a?.description || `Asset #${id}`}
              {isImage && <span className="text-[10px] text-[#5a5a70] ml-1">[still]</span>}
            </span>
            <input
              type="number"
              min="0"
              step="0.5"
              value={dur || ''}
              onChange={e => setDuration(i, e.target.value)}
              placeholder={placeholder}
              className="w-16 bg-[#0d0d0f] border border-[#2a2a32] rounded px-1.5 py-1 text-xs text-[#e8e8f0] text-right"
              aria-label={`Duration for item ${i + 1} (seconds)`}
            />
            <span className="text-[10px] text-[#5a5a70]">s</span>
            <button type="button" onClick={() => move(i, -1)} disabled={i === 0}
              className="text-xs text-[#9090a8] disabled:opacity-30 px-1" aria-label="Move up">↑</button>
            <button type="button" onClick={() => move(i, +1)} disabled={i === assetIds.length - 1}
              className="text-xs text-[#9090a8] disabled:opacity-30 px-1" aria-label="Move down">↓</button>
            <button type="button" onClick={() => remove(i)}
              className="text-xs text-[#f87171] px-1" aria-label="Remove visual">×</button>
          </div>
        )
      })}
      <Button variant="default" onClick={() => setPicker(true)}>+ Add Visual</Button>
      <VisualPickerModal open={picker} onClose={() => setPicker(false)} onSelect={add} />
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd console/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/components/VisualPlaylistEditor.jsx
git commit -m "feat(console): add VisualPlaylistEditor with per-clip duration + reorder"
```

---

## Task 13: Wire `VisualPlaylistEditor` into ③ VISUAL section of `CreationPanel`

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` — `CreationPanel`'s ③ VISUAL section (lines 547-631) and submit body (lines 273-317)

- [ ] **Step 1: Add the import**

At the top of `YouTubeVideosPage.jsx`, add:

```jsx
import VisualPlaylistEditor from '../components/VisualPlaylistEditor.jsx'
```

- [ ] **Step 2: Add new local state for the playlist + loop mode**

Inside `CreationPanel`, after the existing `[sfxLayers, setSfxLayers]` block (around line 126), add:

```jsx
  const [visualAssetIds, setVisualAssetIds]       = useState([])
  const [visualDurations, setVisualDurations]     = useState([])
  const [visualLoopMode, setVisualLoopMode]       = useState('concat_loop')
```

- [ ] **Step 3: Replace the entire ③ VISUAL section**

Replace the section ③ VISUAL (currently lines 547-631) with:

```jsx
          {/* ③ VISUAL */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold text-[#5a5a70] tracking-widest">③ VISUAL</div>
              <button
                type="button"
                onClick={() => setShowVisualUpload(v => !v)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  showVisualUpload
                    ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                    : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                }`}
              >
                ↑ Upload
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex gap-2">
                {[
                  { value: 'concat_loop', label: 'Concat-then-loop' },
                  { value: 'per_clip',    label: 'Per-clip duration' },
                ].map(opt => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setVisualLoopMode(opt.value)}
                    className={`flex-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                      visualLoopMode === opt.value
                        ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                        : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <VisualPlaylistEditor
                assetIds={visualAssetIds}
                durations={visualDurations}
                loopMode={visualLoopMode}
                onChange={({ assetIds, durations }) => {
                  setVisualAssetIds(assetIds)
                  setVisualDurations(durations)
                }}
              />
              {showVisualUpload && (
                <div className="flex flex-col gap-2 bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
                  <div className="text-xs text-[#5a5a70] font-medium">Upload Visual Asset</div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-[#9090a8] font-medium">File (image or video)</label>
                    <input
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm"
                      onChange={e => setVisualUploadFile(e.target.files?.[0] || null)}
                      className="text-sm text-[#9090a8] file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
                    />
                  </div>
                  <Select label="Source" value={visualUploadSource} onChange={e => setVisualUploadSource(e.target.value)}>
                    {['manual', 'midjourney', 'runway', 'pexels', 'veo', 'stock'].map(s => (
                      <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                    ))}
                  </Select>
                  <Input
                    label="Description (optional)"
                    value={visualUploadDesc}
                    onChange={e => setVisualUploadDesc(e.target.value)}
                    placeholder="e.g. Rainy window close-up"
                  />
                  <div className="flex gap-2 justify-end">
                    <Button variant="ghost" size="sm" onClick={() => {
                      setShowVisualUpload(false)
                      setVisualUploadFile(null)
                      setVisualUploadDesc('')
                      setVisualUploadSource('manual')
                    }}>
                      Cancel
                    </Button>
                    <Button variant="primary" size="sm" loading={visualUploading} onClick={handleVisualUpload}>
                      Upload
                    </Button>
                  </div>
                </div>
              )}
              {(template?.runway_prompt_template || autofillRunway) && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">
                    Runway Prompt {autofillRunway ? '(AI generated)' : '(reference)'}
                  </div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">
                    {autofillRunway || template.runway_prompt_template}
                  </p>
                  <button
                    onClick={() => navigator.clipboard.writeText(autofillRunway || template.runway_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded"
                  >
                    Copy
                  </button>
                </div>
              )}
            </div>
          </section>
```

- [ ] **Step 4: Update the upload-on-success handler to push into the playlist**

Find `handleVisualUpload` (lines 183-206) and replace its success block to push into the new playlist instead of writing the legacy `visual_asset_id`:

```jsx
  const handleVisualUpload = async () => {
    if (!visualUploadFile) { showToast('Select a file', 'error'); return }
    setVisualUploading(true)
    try {
      const ext = (visualUploadFile.name.split('.').pop() || '').toLowerCase()
      const asset_type = ['mp4', 'mov', 'webm'].includes(ext) ? 'video_clip' : 'still_image'
      const newAsset = await assetsApi.upload(visualUploadFile, {
        source: visualUploadSource,
        description: visualUploadDesc,
        asset_type,
      })
      setAssetList(prev => [...prev, newAsset])
      setVisualAssetIds(prev => [...prev, newAsset.id])
      setVisualDurations(prev => [...prev, asset_type === 'still_image' ? 3.0 : 0.0])
      setShowVisualUpload(false)
      setVisualUploadFile(null)
      setVisualUploadDesc('')
      setVisualUploadSource('manual')
      showToast('Asset uploaded', 'success')
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setVisualUploading(false)
    }
  }
```

- [ ] **Step 5: Update the submit body in `handleSubmit`**

In `handleSubmit` (lines 273-317), find the `await youtubeVideosApi.create({ ... })` call. Replace `visual_asset_id: form.visual_asset_id || null,` with:

```jsx
        visual_asset_id: null,
        visual_asset_ids: visualAssetIds,
        visual_clip_durations_s: visualDurations,
        visual_loop_mode: visualLoopMode,
```

(Leaving `visual_asset_id: null` makes the new server-side fallback unambiguously prefer the array.)

- [ ] **Step 6: Verify in the running app**

In the running console, **+ New Video** with any template:
- The ③ VISUAL section now shows a segmented toggle (Concat-then-loop / Per-clip duration) above the visual playlist editor.
- Click **+ Add Visual** — picker modal opens with thumbnails. Click a video — it appears as row #1 with `[native]` placeholder and 0s duration field. Click an image — it appears with default 3s.
- Toggle to **Per-clip duration**; row placeholders change to `3.0`.
- Reorder with ↑↓; remove with ×.
- Save the video, refresh the list, then GET `/api/youtube-videos/{id}` — confirm `visual_asset_ids`, `visual_clip_durations_s`, `visual_loop_mode` round-trip with the values you set.

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(console): visual playlist editor with loop-mode toggle in CreationPanel"
```

---

## Task 14: `CreationPanel` — `mode` prop and edit prefill

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` — `CreationPanel` (line 96 onward)

- [ ] **Step 1: Add `mode` and `existingVideo` props**

Change the function signature (line 96) from:

```jsx
function CreationPanel({ template, channelPlan, channelPlans = [], onClose, onCreated }) {
```

to:

```jsx
function CreationPanel({ template, channelPlan, channelPlans = [], onClose, onCreated, mode = 'create', existingVideo = null }) {
```

- [ ] **Step 2: Prefill state from `existingVideo` when in edit mode**

Replace the initial `useState` block for `form` and the SFX/playlist defaults (currently lines 98-133) with:

```jsx
  const isEdit = mode === 'edit' && existingVideo
  const [selectedPlan, setSelectedPlan] = useState(channelPlan)
  const [form, setForm] = useState({
    theme:                 isEdit ? (existingVideo.theme || '')                  : '',
    target_duration_h:     isEdit ? (existingVideo.target_duration_h || 8)       : (template?.target_duration_h || 8),
    customDuration:        '',
    isCustomDuration:      false,
    music_track_id:        isEdit ? existingVideo.music_track_id                 : null,
    visual_asset_id:       isEdit ? existingVideo.visual_asset_id                : null,
    sfx_overrides:         null,
    seo_title:             isEdit ? (existingVideo.seo_title || '')              : '',
    seo_description:       isEdit ? (existingVideo.seo_description || '')        : '',
    seo_tags:              isEdit ? (existingVideo.seo_tags || []).join(', ')    : '',
    output_quality:        isEdit ? (existingVideo.output_quality || '1080p')    : '1080p',
  })
  const [musicList, setMusicList]   = useState([])
  const [assetList, setAssetList]   = useState([])
  const [sfxList,   setSfxList]     = useState([])
  const [loading, setLoading]       = useState(false)
  const [toast, setToast]           = useState(null)
  const [autofilling, setAutofilling] = useState(false)
  const [autofillError, setAutofillError] = useState(null)
  const [autofillSuno, setAutofillSuno] = useState(null)
  const [autofillRunway, setAutofillRunway] = useState(null)
  const [autofilled, setAutofilled] = useState(isEdit)  // skip the auto-SEO useEffect on edit

  const [sfxLayers, setSfxLayers] = useState(() => {
    const overrides = isEdit ? (existingVideo.sfx_overrides || {}) : {}
    return {
      foreground: { asset_id: overrides.foreground?.asset_id ? String(overrides.foreground.asset_id) : '', volume: overrides.foreground?.volume ?? 0.6 },
      midground:  { asset_id: overrides.midground?.asset_id  ? String(overrides.midground.asset_id)  : '', volume: overrides.midground?.volume  ?? 0.3 },
      background: { asset_id: overrides.background?.asset_id ? String(overrides.background.asset_id) : '', volume: overrides.background?.volume ?? 0.1 },
    }
  })

  const [sfxPickerLayer, setSfxPickerLayer] = useState(null)

  // ASMR / Soundscape extras
  const [musicTrackIds, setMusicTrackIds]       = useState(isEdit ? (existingVideo.music_track_ids || []) : [])
  const [sfxPool, setSfxPool]                   = useState(isEdit ? (existingVideo.sfx_pool || [])       : [])
  const [sfxDensity, setSfxDensity]             = useState(isEdit ? (existingVideo.sfx_density_seconds || 60) : 60)
  const [blackFromSeconds, setBlackFromSeconds] = useState(isEdit && existingVideo.black_from_seconds != null ? String(existingVideo.black_from_seconds) : '')
  const [skipPreviews, setSkipPreviews]         = useState(isEdit ? !!existingVideo.skip_previews : false)
  const isAsmrLike = ['asmr', 'soundscape'].includes(template?.slug)

  // Visual playlist — fall back to legacy single visual_asset_id when array is empty
  // so editing a pre-feature video doesn't drop the existing visual.
  const [visualAssetIds, setVisualAssetIds]   = useState(() => {
    if (!isEdit) return []
    if (existingVideo.visual_asset_ids?.length > 0) return existingVideo.visual_asset_ids
    if (existingVideo.visual_asset_id) return [existingVideo.visual_asset_id]
    return []
  })
  const [visualDurations, setVisualDurations] = useState(() => {
    if (!isEdit) return []
    if (existingVideo.visual_clip_durations_s?.length > 0) return existingVideo.visual_clip_durations_s
    if (existingVideo.visual_asset_id) return [0.0]  // 0 = use native length in concat_loop
    return []
  })
  const [visualLoopMode, setVisualLoopMode]   = useState(isEdit ? (existingVideo.visual_loop_mode || 'concat_loop') : 'concat_loop')
```

- [ ] **Step 3: Guard the AI Autofill button on `mode==='create'`**

In the panel header (around lines 332-343), wrap the **✦ AI Autofill** Button with `{!isEdit && (...)}`:

```jsx
            {!isEdit && (selectedPlan || channelPlans.length > 0) && (
              <Button
                variant="accent"
                size="sm"
                ...
              >
                ✦ AI Autofill
              </Button>
            )}
```

- [ ] **Step 4: Guard the theme→SEO autofill `useEffect` on create mode**

The existing `useEffect` (lines 224-240) auto-rewrites SEO when theme changes. In edit mode this would clobber the editor's saved SEO. Wrap the inner body in `if (isEdit) return`:

```jsx
  useEffect(() => {
    if (isEdit) return  // edit mode: never auto-rewrite SEO from theme
    if (form.theme && template && !autofilled) {
      const h = form.isCustomDuration
        ? (parseFloat(form.customDuration) || 8)
        : form.target_duration_h
      const durationDisplay = h < 1 ? `${Math.round(h * 60)}min` : h
      setForm(f => ({
        ...f,
        seo_title: (template.seo_title_formula || '{theme} — {duration}h')
          .replace('{theme}', form.theme)
          .replace('{duration}', durationDisplay),
        seo_description: (template.seo_description_template || '')
          .replace('{theme}', form.theme)
          .replace('{duration}', durationDisplay),
      }))
    }
  }, [form.theme, form.target_duration_h, form.customDuration, form.isCustomDuration, autofilled, isEdit])
```

- [ ] **Step 5: Update the panel header label**

In the panel header (line 326), change:

```jsx
            <h2 className="text-base font-semibold text-[#e8e8f0]">New {template?.label}</h2>
```

to:

```jsx
            <h2 className="text-base font-semibold text-[#e8e8f0]">
              {isEdit ? 'Edit' : 'New'} {template?.label}
            </h2>
```

- [ ] **Step 6: Switch `handleSubmit` to call `update` in edit mode**

Inside `handleSubmit` (lines 273-317), replace the `await youtubeVideosApi.create({...})` call with:

```jsx
      const body = {
        title,
        template_id: template.id,
        theme: form.theme,
        target_duration_h: duration,
        music_track_id: form.music_track_id || null,
        visual_asset_id: null,
        visual_asset_ids: visualAssetIds,
        visual_clip_durations_s: visualDurations,
        visual_loop_mode: visualLoopMode,
        sfx_overrides: (sfxLayers.foreground.asset_id || sfxLayers.midground.asset_id || sfxLayers.background.asset_id)
          ? {
              foreground: sfxLayers.foreground.asset_id ? sfxLayers.foreground : null,
              midground:  sfxLayers.midground.asset_id  ? sfxLayers.midground  : null,
              background: sfxLayers.background.asset_id ? sfxLayers.background : null,
            }
          : null,
        seo_title: form.seo_title,
        seo_description: form.seo_description,
        seo_tags: form.seo_tags
          ? form.seo_tags.split(',').map(t => t.trim()).filter(Boolean)
          : [],
        output_quality: form.output_quality,
        ...(isAsmrLike ? {
          music_track_ids: musicTrackIds,
          sfx_pool: sfxPool,
          sfx_density_seconds: sfxPool.length > 0 ? sfxDensity : null,
          black_from_seconds: blackFromSeconds ? parseInt(blackFromSeconds, 10) : null,
          skip_previews: skipPreviews,
        } : {}),
      }
      if (isEdit) {
        await youtubeVideosApi.update(existingVideo.id, body)
      } else {
        await youtubeVideosApi.create(body)
      }
```

- [ ] **Step 7: Update the submit button label**

In the panel footer (line 736), change:

```jsx
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Queue Render →</Button>
```

to:

```jsx
          <Button variant="primary" loading={loading} onClick={handleSubmit}>
            {isEdit ? 'Save changes →' : 'Queue Render →'}
          </Button>
```

- [ ] **Step 8: Verify build**

```bash
cd console/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(console): CreationPanel supports mode='edit' with prefill from existing video"
```

---

## Task 15: ✎ Edit button on `YouTubeVideosPage` list rows

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` — list rows + page state

- [ ] **Step 1: Add `editingVideo` state in `YouTubeVideosPage`**

Inside `YouTubeVideosPage` (after the existing `[previewVideo, setPreviewVideo]` line around line 837), add:

```jsx
  const [editingVideo, setEditingVideo] = useState(null)
```

- [ ] **Step 2: Add the Edit button to the list row actions**

Find the action button block in the video card (around lines 1055-1080). Replace it with:

```jsx
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs font-medium" style={{ color: STATUS_COLORS[v.status] }}>
                      ● {v.status}
                    </span>
                    {['draft', 'failed', 'audio_preview_ready', 'video_preview_ready'].includes(v.status) && (
                      <Button variant="ghost" size="sm" onClick={() => setEditingVideo(v)}>
                        ✎ Edit
                      </Button>
                    )}
                    {v.status === 'draft' && (
                      <Button variant="ghost" size="sm" onClick={() => handleRender(v)}>
                        Render →
                      </Button>
                    )}
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
                    <button
                      onClick={() => handleDelete(v)}
                      className="text-[#5a5a70] hover:text-[#f87171] text-xs ml-1"
                    >
                      ✕
                    </button>
                  </div>
```

- [ ] **Step 3: Render the edit slide-over in the same place as the create panel**

Find the existing `{activeTemplate && <CreationPanel ... />}` block (lines 1094-1102). Append a sibling block right after it for the edit slide-over:

```jsx
      {editingVideo && (() => {
        const tmpl = templates.find(t => t.id === editingVideo.template_id)
        return (
          <CreationPanel
            template={tmpl}
            channelPlan={null}
            channelPlans={[]}
            mode="edit"
            existingVideo={editingVideo}
            onClose={() => setEditingVideo(null)}
            onCreated={() => { setEditingVideo(null); load() }}
          />
        )
      })()}
```

- [ ] **Step 4: Verify in the running app**

In the running console, on the YouTube Videos page:
- A `draft` row shows the **✎ Edit** button. Click it. The slide-over opens with the same form, prefilled (theme, duration, SEO, music playlist, visual playlist, SFX layers, SFX pool — all values match the existing video).
- The header reads **Edit ASMR** (or whichever template). The footer button reads **Save changes →**. The **✦ AI Autofill** button is hidden.
- Change the title; click **Save changes →**. The slide-over closes; the list refreshes; the row's status is now **draft** (was previously whatever status it was in).
- A `done` row shows **▶ Preview** and **+ Make Short** but does NOT show **✎ Edit**.
- A `published` row does NOT show **✎ Edit**.
- A `rendering` row does NOT show **✎ Edit**.
- A `video_preview_ready` row DOES show **✎ Edit**. Editing it deletes the on-disk video preview file and resets to draft.

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(console): ✎ Edit button on YouTube videos list rows"
```

---

## Final verification

- [ ] **Step 1: Run the full backend test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests PASS — none of the renderer / dispatch / upload existing tests should regress.

- [ ] **Step 2: Manual end-to-end (multi-visual)**

In the running console, create a 10-minute (`10 / 60` hours) ASMR video with:
- Three visuals in this order: a 5s video clip, a still image (3s), another 12s video clip.
- Loop mode: **Concat-then-loop**.
- One music track, no SFX pool.

Render it (skip previews on, for speed). Once `done`, open the rendered MP4 in a player and verify:
- Total duration ≈ 600 seconds (the visual playlist loops to fill).
- Sequence visible: clip 1 (5s) → image (3s) → clip 2 (12s) → clip 1 → image → clip 2 → … until 600s.

Edit the same video, switch to **Per-clip duration**, set durations [10, 5, 8], save. The video resets to `draft`. Render again. Verify the new sequence and total length still ≈ 600 seconds.

- [ ] **Step 3: Manual end-to-end (edit-reset of preview)**

Create a fresh ASMR video (don't tick "skip previews"). Render → audio preview → reject and re-render → video preview ready. With status `video_preview_ready`, click **✎ Edit**, change the SEO title, save. Confirm:
- The preview file is no longer on disk (`ls $RENDER_OUTPUT_PATH/asmr/...`).
- The DB row's `audio_preview_path`, `video_preview_path`, `output_path` are all NULL.
- Status is `draft`.
- An `audit_log` entry exists with `action='video_edit_reset'` and `details.discarded_artifacts` listing the deleted file paths.

- [ ] **Step 4: Final commit / push**

If any of the above verifications surfaces a fix, commit it as `fix(...)`. Otherwise the implementation is complete. The plan author or reviewer can decide whether to push to a branch / open a PR.
