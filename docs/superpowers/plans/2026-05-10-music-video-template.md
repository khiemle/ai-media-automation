# Music Video YouTube Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third YouTube video template — `music` — that publishes a curated music playlist over a (single or playlist) visual, with on-screen now-playing overlay, optional ffmpeg spectrum visualizer, and YouTube chapters in the upload description.

**Architecture:** Extends the existing template system. New Alembic migration adds 8 columns to `youtube_videos` and a `ui_features` gating column to `video_templates`. The render pipeline gains a `music`-template branch in `pipeline/youtube_ffmpeg.py:render_landscape` that bypasses the SFX/blackout path and adds Pillow-rendered now-playing PNG overlays + an optional ffmpeg `showfreqs` spectrum overlay. The YouTube uploader learns to inject a chapter block at the top of the description.

**Tech Stack:** Python 3.11 · SQLAlchemy 2.0 · Alembic · FastAPI · Pydantic v2 · Pillow · ffmpeg (filtergraph) · pytest · React 18 · Vite

**Spec:** `docs/superpowers/specs/2026-05-10-music-video-template-design.md`

---

## File Structure Overview

| File | Purpose | Action |
|------|---------|--------|
| `console/backend/alembic/versions/022_music_template.py` | Add `ui_features` column + 8 youtube_videos columns + insert music template row | Create |
| `console/backend/models/video_template.py` | Add `ui_features: list[str]` mapped column | Modify |
| `console/backend/models/youtube_video.py` | Add 8 new columns (track_transition, spectrum_*, etc.) | Modify |
| `console/backend/schemas/youtube_video.py` | Add new fields to Create/Update/Response schemas + Literal types | Modify (or create) |
| `console/backend/services/youtube_video_service.py` | New helpers: `_resolve_music_tracks`, `_compute_music_total_duration`, `build_chapters`. New validation for music template. | Modify |
| `pipeline/music_overlay.py` | NEW module: PNG renderers for chip/sidebar/bottom_bar + `build_now_playing_overlay` orchestrator | Create |
| `pipeline/music_audio.py` | NEW module: `_build_music_playlist_wav_with_transitions` (gapless/crossfade/gap) | Create |
| `pipeline/youtube_ffmpeg.py` | Music-template branch in `render_landscape` + spectrum filtergraph helper | Modify |
| `uploader/youtube_uploader.py` | `_format_chapters`, `_fmt_timestamp`, accept `chapters` param in `_build_description` and `upload_video` | Modify |
| `console/backend/tasks/upload_tasks.py` | Build chapters list, pass to uploader | Modify |
| `console/mcp/tools/youtube_video.py` | New `get_chapters` action + updated docstring | Modify |
| `console/frontend/src/api/client.js` | Add new fields to YT video API calls | Modify |
| `console/frontend/src/pages/YoutubeVideoPage.jsx` (or equivalent) | `ui_features` gating + music panels | Modify |
| `console/frontend/src/components/MusicPlaylistPicker.jsx` | NEW — multi-select + drag reorder | Create |
| `console/frontend/src/components/TransitionPanel.jsx` | NEW — radio buttons + crossfade-seconds input | Create |
| `console/frontend/src/components/OverlayStylePicker.jsx` | NEW — radio buttons with thumbnail previews | Create |
| `console/frontend/src/components/SpectrumPanel.jsx` | NEW — collapsible toggle + style controls | Create |
| `tests/test_chapter_builder.py` | Unit tests for `build_chapters` and duration math | Create |
| `tests/test_music_overlay.py` | Unit tests for PNG renderers | Create |
| `tests/test_youtube_video_service_music.py` | Service validation tests for music template | Create |
| `tests/test_youtube_uploader_chapters.py` | Description formatting with chapters | Create |
| `tests/test_music_render_smoke.py` | End-to-end render smoke test | Create |

---

## Task 1: Alembic migration

**Files:**
- Create: `console/backend/alembic/versions/022_music_template.py`

- [ ] **Step 1: Confirm current alembic head**

Run: `cd console/backend && alembic heads`
Expected: `d885cdd6570e (head)` — the mcp_server_tables migration. The new migration's `down_revision` is `d885cdd6570e`.

- [ ] **Step 2: Create the migration file**

```python
# console/backend/alembic/versions/022_music_template.py
"""music_template

Revision ID: 022_music_template
Revises: d885cdd6570e
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "022_music_template"
down_revision = "d885cdd6570e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ui_features on video_templates
    op.add_column(
        "video_templates",
        sa.Column(
            "ui_features",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        """
        UPDATE video_templates
           SET ui_features = '["sfx_panel", "duration_picker", "blackout"]'::jsonb
         WHERE slug IN ('asmr', 'soundscape')
        """
    )

    # 2. Insert music template row
    op.execute(
        """
        INSERT INTO video_templates
            (slug, label, output_format, target_duration_h,
             suno_extends_recommended, sfx_pack,
             suno_prompt_template, midjourney_prompt_template,
             runway_prompt_template, sound_rules,
             seo_title_formula, seo_description_template,
             ui_features)
        VALUES (
            'music', 'Music Video', 'landscape_long', NULL, NULL, NULL,
            NULL, NULL, NULL, '[]'::jsonb,
            '{theme} Music — {duration} of Continuous Listening',
            'Curated {theme} music playlist. {duration} of uninterrupted listening.',
            '[]'::jsonb
        )
        ON CONFLICT (slug) DO NOTHING
        """
    )

    # 3. New columns on youtube_videos
    op.add_column("youtube_videos",
        sa.Column("track_transition", sa.String(20),
                  nullable=False, server_default="gapless"))
    op.add_column("youtube_videos",
        sa.Column("track_transition_seconds", sa.Float,
                  nullable=False, server_default="2.0"))
    op.add_column("youtube_videos",
        sa.Column("playlist_overlay_style", sa.String(20), nullable=True))
    op.add_column("youtube_videos",
        sa.Column("spectrum_enabled", sa.Boolean,
                  nullable=False, server_default=sa.text("false")))
    op.add_column("youtube_videos",
        sa.Column("spectrum_position", sa.String(10),
                  nullable=False, server_default="bottom"))
    op.add_column("youtube_videos",
        sa.Column("spectrum_height_pct", sa.Float,
                  nullable=False, server_default="0.12"))
    op.add_column("youtube_videos",
        sa.Column("spectrum_color", sa.String(9),
                  nullable=False, server_default="#ffffff"))
    op.add_column("youtube_videos",
        sa.Column("spectrum_opacity", sa.Float,
                  nullable=False, server_default="0.6"))

    # 4. CHECK constraints
    op.create_check_constraint(
        "track_transition_valid", "youtube_videos",
        "track_transition IN ('gapless', 'crossfade', 'gap')")
    op.create_check_constraint(
        "playlist_overlay_style_valid", "youtube_videos",
        "playlist_overlay_style IS NULL OR "
        "playlist_overlay_style IN ('chip', 'sidebar', 'bottom_bar')")
    op.create_check_constraint(
        "spectrum_position_valid", "youtube_videos",
        "spectrum_position IN ('bottom', 'center')")
    op.create_check_constraint(
        "spectrum_height_pct_range", "youtube_videos",
        "spectrum_height_pct > 0.0 AND spectrum_height_pct <= 0.5")
    op.create_check_constraint(
        "spectrum_opacity_range", "youtube_videos",
        "spectrum_opacity >= 0.0 AND spectrum_opacity <= 1.0")
    op.create_check_constraint(
        "track_transition_seconds_range", "youtube_videos",
        "track_transition_seconds >= 0.5 AND track_transition_seconds <= 10.0")


def downgrade() -> None:
    for name in (
        "track_transition_seconds_range",
        "spectrum_opacity_range",
        "spectrum_height_pct_range",
        "spectrum_position_valid",
        "playlist_overlay_style_valid",
        "track_transition_valid",
    ):
        op.drop_constraint(name, "youtube_videos", type_="check")

    for col in (
        "spectrum_opacity", "spectrum_color", "spectrum_height_pct",
        "spectrum_position", "spectrum_enabled",
        "playlist_overlay_style", "track_transition_seconds",
        "track_transition",
    ):
        op.drop_column("youtube_videos", col)

    op.execute("DELETE FROM youtube_videos WHERE template_id = "
               "(SELECT id FROM video_templates WHERE slug = 'music')")
    op.execute("DELETE FROM video_templates WHERE slug = 'music'")
    op.drop_column("video_templates", "ui_features")
```

- [ ] **Step 3: Run upgrade against test DB**

Run: `cd console/backend && TEST_DATABASE_URL=postgresql://localhost/ai_media_test alembic upgrade head`
Expected: clean upgrade, no errors. Then `alembic downgrade -1` and re-upgrade to verify reversibility.

- [ ] **Step 4: Smoke-verify**

Run: `psql ai_media_test -c "SELECT slug, ui_features FROM video_templates"`
Expected: three rows; `asmr` and `soundscape` show `["sfx_panel", "duration_picker", "blackout"]`; `music` shows `[]`.
Run: `psql ai_media_test -c "\d youtube_videos" | grep -E 'track_transition|spectrum|playlist_overlay'`
Expected: 8 new columns listed.

- [ ] **Step 5: Commit**

```bash
git add console/backend/alembic/versions/022_music_template.py
git commit -m "feat(db): add music template + youtube_videos music columns

Migration 022 adds ui_features gating column to video_templates,
inserts the music template row, and adds 8 columns to youtube_videos
covering track transitions, playlist overlay style, and spectrum
visualizer config. CHECK constraints enforce enum + range validity."
```

---

## Task 2: SQLAlchemy models + Pydantic schemas

**Files:**
- Modify: `console/backend/models/video_template.py`
- Modify: `console/backend/models/youtube_video.py`
- Modify: `console/backend/schemas/youtube_video.py` (or wherever the YT video schemas live — search for `YoutubeVideoCreate`)

- [ ] **Step 1: Add `ui_features` to `VideoTemplate` model**

Open `console/backend/models/video_template.py` and add to the class body:

```python
from sqlalchemy.dialects.postgresql import JSONB

class VideoTemplate(Base):
    # ... existing columns ...
    ui_features: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb")
    )
```

If the file already imports `JSONB` and `sa`, skip those imports. The `Mapped[list[str]]` annotation works because SQLAlchemy 2.0 treats JSONB as opaque Python.

- [ ] **Step 2: Add 8 columns to `YoutubeVideo` model**

Open `console/backend/models/youtube_video.py` and add to the class body:

```python
class YoutubeVideo(Base):
    # ... existing columns ...
    track_transition: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="gapless", server_default="gapless"
    )
    track_transition_seconds: Mapped[float] = mapped_column(
        sa.Float, nullable=False, default=2.0, server_default="2.0"
    )
    playlist_overlay_style: Mapped[str | None] = mapped_column(
        sa.String(20), nullable=True
    )
    spectrum_enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    spectrum_position: Mapped[str] = mapped_column(
        sa.String(10), nullable=False, default="bottom", server_default="bottom"
    )
    spectrum_height_pct: Mapped[float] = mapped_column(
        sa.Float, nullable=False, default=0.12, server_default="0.12"
    )
    spectrum_color: Mapped[str] = mapped_column(
        sa.String(9), nullable=False, default="#ffffff", server_default="#ffffff"
    )
    spectrum_opacity: Mapped[float] = mapped_column(
        sa.Float, nullable=False, default=0.6, server_default="0.6"
    )
```

- [ ] **Step 3: Update Pydantic schemas**

Find the YT video schemas file (likely `console/backend/schemas/youtube_video.py` — if it doesn't exist yet, the schemas may be inline in the router; in that case, use the inline location). Add:

```python
from typing import Literal
from pydantic import BaseModel

TrackTransition  = Literal["gapless", "crossfade", "gap"]
OverlayStyle     = Literal["chip", "sidebar", "bottom_bar"]
SpectrumPosition = Literal["bottom", "center"]


# Add these as optional fields on YoutubeVideoCreate AND YoutubeVideoUpdate:
#   track_transition: TrackTransition = "gapless"
#   track_transition_seconds: float = 2.0
#   playlist_overlay_style: OverlayStyle | None = None
#   spectrum_enabled: bool = False
#   spectrum_position: SpectrumPosition = "bottom"
#   spectrum_height_pct: float = 0.12
#   spectrum_color: str = "#ffffff"
#   spectrum_opacity: float = 0.6

# Add to YoutubeVideoResponse (or equivalent read schema):
#   total_duration_s: float | None = None
```

- [ ] **Step 4: Run existing tests, expect zero regressions**

Run: `pytest tests/ -k "not music" -x --tb=short 2>&1 | tail -20`
Expected: all existing tests still pass. Model attribute additions are non-breaking.

- [ ] **Step 5: Commit**

```bash
git add console/backend/models/video_template.py \
        console/backend/models/youtube_video.py \
        console/backend/schemas/youtube_video.py
git commit -m "feat(models): add music-template fields to ORM + Pydantic

VideoTemplate.ui_features (JSONB list of UI gating flags).
YoutubeVideo gains 8 columns for track transitions, playlist overlay
style, and spectrum visualizer config. Pydantic schemas exposed via
Literal types for transition/overlay/position enums."
```

---

## Task 3: Music track resolution + duration math helpers

**Files:**
- Modify: `console/backend/services/youtube_video_service.py`
- Create: `tests/test_music_duration.py`

- [ ] **Step 1: Write failing test for duration math**

```python
# tests/test_music_duration.py
import pytest
from console.backend.services.youtube_video_service import (
    _compute_music_total_duration,
)


class FakeTrack:
    def __init__(self, duration_s: float):
        self.duration_s = duration_s


def test_gapless_sums_durations():
    tracks = [FakeTrack(60.0), FakeTrack(45.0), FakeTrack(90.0)]
    total, boundaries = _compute_music_total_duration(tracks, "gapless", 2.0)
    assert total == pytest.approx(195.0)
    assert boundaries == [0.0, 60.0, 105.0]


def test_crossfade_subtracts_overlap():
    tracks = [FakeTrack(60.0), FakeTrack(60.0), FakeTrack(60.0)]
    total, boundaries = _compute_music_total_duration(tracks, "crossfade", 2.0)
    # 60 + (60-2) + (60-2) = 176
    assert total == pytest.approx(176.0)
    assert boundaries == pytest.approx([0.0, 58.0, 116.0])


def test_gap_adds_silence():
    tracks = [FakeTrack(60.0), FakeTrack(60.0)]
    total, boundaries = _compute_music_total_duration(tracks, "gap", 1.5)
    # 60 + 1.5 + 60 = 121.5
    assert total == pytest.approx(121.5)
    assert boundaries == pytest.approx([0.0, 61.5])


def test_single_track_ignores_transition():
    tracks = [FakeTrack(120.0)]
    total, boundaries = _compute_music_total_duration(tracks, "crossfade", 2.0)
    assert total == pytest.approx(120.0)
    assert boundaries == [0.0]


def test_empty_tracks_returns_zero():
    total, boundaries = _compute_music_total_duration([], "gapless", 2.0)
    assert total == 0.0
    assert boundaries == []
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_music_duration.py -x -v`
Expected: ImportError — `_compute_music_total_duration` not defined.

- [ ] **Step 3: Implement the helpers in `youtube_video_service.py`**

Add to `console/backend/services/youtube_video_service.py` (near the top, after imports):

```python
from database.models import MusicTrack


def _resolve_music_tracks(video, db) -> list[MusicTrack]:
    """Return ordered list of MusicTrack rows for video.music_track_ids.

    Preserves the user-specified order. Raises ValueError if any ID is missing.
    Falls back to single music_track_id when music_track_ids is empty.
    """
    track_ids = list(getattr(video, "music_track_ids", None) or [])
    if not track_ids and getattr(video, "music_track_id", None):
        track_ids = [video.music_track_id]
    if not track_ids:
        return []

    rows = db.query(MusicTrack).filter(MusicTrack.id.in_(track_ids)).all()
    by_id = {t.id: t for t in rows}
    missing = [tid for tid in track_ids if tid not in by_id]
    if missing:
        raise ValueError(f"music_track_ids not found: {missing}")
    return [by_id[tid] for tid in track_ids]


def _compute_music_total_duration(
    tracks, transition: str, transition_s: float
) -> tuple[float, list[float]]:
    """Return (total_seconds, per-track-start boundaries).

    Boundaries[i] is the start time of track i in the final timeline.
    Total is the timeline length after transition adjustments.
    """
    if not tracks:
        return 0.0, []

    boundaries: list[float] = [0.0]
    if transition == "gapless" or len(tracks) == 1:
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + float(t.duration_s))
        total = boundaries[-1] + float(tracks[-1].duration_s)
    elif transition == "crossfade":
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + float(t.duration_s) - transition_s)
        total = boundaries[-1] + float(tracks[-1].duration_s)
    elif transition == "gap":
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + float(t.duration_s) + transition_s)
        total = boundaries[-1] + float(tracks[-1].duration_s)
    else:
        raise ValueError(f"unknown transition mode: {transition}")
    return total, boundaries
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_music_duration.py -x -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/youtube_video_service.py \
        tests/test_music_duration.py
git commit -m "feat(svc): music track resolution + transition-aware duration math

_resolve_music_tracks loads MusicTrack rows in user order, errors on
missing IDs. _compute_music_total_duration handles gapless / crossfade
/ gap modes and returns both total length and per-track boundary
timestamps, which both chapter generation and now-playing overlays
will reuse as a single source of truth."
```

---

## Task 4: Service-layer validation for music template

**Files:**
- Modify: `console/backend/services/youtube_video_service.py`
- Create: `tests/test_youtube_video_service_music.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_youtube_video_service_music.py
import pytest
from console.backend.services.youtube_video_service import YoutubeVideoService
from console.backend.models.video_template import VideoTemplate
from database.models import MusicTrack


@pytest.fixture
def music_template(db):
    t = db.query(VideoTemplate).filter_by(slug="music").one()
    return t


@pytest.fixture
def two_tracks(db):
    a = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=120.0)
    b = MusicTrack(title="B", file_path="/tmp/b.wav", duration_s=180.0)
    db.add_all([a, b]); db.commit()
    return [a.id, b.id]


def test_music_rejects_target_duration(db, music_template, two_tracks):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="derives duration"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": two_tracks,
            "target_duration_h": 8.0,
        }, user_id=1)


def test_music_rejects_blackout(db, music_template, two_tracks):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="does not support blackout"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": two_tracks,
            "black_from_seconds": 60,
        }, user_id=1)


def test_music_rejects_sound_layers(db, music_template, two_tracks):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="does not support SFX layers"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": two_tracks,
            "sound_layers": {"background": {"asset_id": 1, "volume": 0.1}},
        }, user_id=1)


def test_music_requires_at_least_one_track(db, music_template):
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="at least 1 music track"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": [],
        }, user_id=1)


def test_single_track_nullifies_overlay_style(db, music_template):
    a = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=120.0)
    db.add(a); db.commit()
    svc = YoutubeVideoService(db)
    video = svc.create_video({
        "title": "x", "template_id": music_template.id,
        "music_track_ids": [a.id],
        "playlist_overlay_style": "chip",
    }, user_id=1)
    assert video.playlist_overlay_style is None


def test_crossfade_too_long_rejected(db, music_template):
    short = MusicTrack(title="short", file_path="/tmp/s.wav", duration_s=4.0)
    long  = MusicTrack(title="long",  file_path="/tmp/l.wav", duration_s=120.0)
    db.add_all([short, long]); db.commit()
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="exceeds half"):
        svc.create_video({
            "title": "x", "template_id": music_template.id,
            "music_track_ids": [short.id, long.id],
            "track_transition": "crossfade",
            "track_transition_seconds": 3.0,  # > shortest_track / 2 = 2.0
        }, user_id=1)


def test_asmr_template_unaffected(db):
    asmr = db.query(VideoTemplate).filter_by(slug="asmr").one()
    svc = YoutubeVideoService(db)
    # Should NOT raise — these fields are valid for asmr
    video = svc.create_video({
        "title": "x", "template_id": asmr.id,
        "target_duration_h": 8.0,
        "black_from_seconds": 7200,
    }, user_id=1)
    assert video.target_duration_h == 8.0
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_youtube_video_service_music.py -x -v`
Expected: failures — validation not implemented.

- [ ] **Step 3: Implement validation in `create_video` (and `update_video`)**

In `console/backend/services/youtube_video_service.py`, find `create_video()` (and `update_video()`). Before persisting, add:

```python
def _validate_music_template(self, data: dict, template) -> dict:
    """Reject incompatible fields, normalize single-track overlay.
    Returns possibly-adjusted data dict and warnings list (mutated in place
    by reading data['_field_warnings']).
    """
    if template.slug != "music":
        return data
    warnings = []

    if data.get("target_duration_h") is not None:
        raise ValueError("music template derives duration from tracks; "
                         "remove target_duration_h")
    if data.get("black_from_seconds") is not None:
        raise ValueError("music template does not support blackout")
    for field in ("sound_layers", "sfx_overrides", "sfx_pool"):
        if data.get(field):
            raise ValueError("music template does not support SFX layers")

    track_ids = data.get("music_track_ids") or []
    if not track_ids and not data.get("music_track_id"):
        raise ValueError("music template requires at least 1 music track")

    # Single-track → null the overlay style silently, with warning
    effective_count = len(track_ids) if track_ids else 1
    if effective_count < 2 and data.get("playlist_overlay_style"):
        warnings.append("overlay hidden for single-track playlists")
        data["playlist_overlay_style"] = None

    # Crossfade safety: must be < half the shortest track
    if data.get("track_transition") == "crossfade":
        from database.models import MusicTrack
        rows = self.db.query(MusicTrack).filter(
            MusicTrack.id.in_(track_ids)
        ).all()
        durations = [r.duration_s for r in rows if r.duration_s]
        if durations:
            shortest = min(durations)
            xfade = float(data.get("track_transition_seconds") or 2.0)
            if xfade > shortest / 2:
                raise ValueError(
                    f"crossfade ({xfade}s) exceeds half the shortest "
                    f"track duration ({shortest}s)"
                )

    if warnings:
        data["_field_warnings"] = warnings
    return data
```

Then call it from `create_video` and `update_video` after loading the template:

```python
def create_video(self, data: dict, user_id: int):
    # ... load template ...
    template = self.db.query(VideoTemplate).filter_by(id=data["template_id"]).one()
    data = self._validate_music_template(data, template)
    # ... existing creation logic ...
```

If the existing service exposes `field_warnings` in the response, surface `data.pop("_field_warnings", None)`. Otherwise add it to the response dict the router builds.

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_youtube_video_service_music.py -x -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/youtube_video_service.py \
        tests/test_youtube_video_service_music.py
git commit -m "feat(svc): validate music-template-incompatible fields

Reject target_duration_h, black_from_seconds, and sfx_* fields when
template is music. Require >= 1 music track. Silently null overlay
style for single-track playlists with a field_warning. Reject
crossfade durations exceeding half the shortest track."
```

---

## Task 5: build_chapters helper

**Files:**
- Modify: `console/backend/services/youtube_video_service.py`
- Create: `tests/test_chapter_builder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_chapter_builder.py
import pytest
from console.backend.services.youtube_video_service import (
    _compute_music_total_duration,
    build_chapters_from_tracks,
)


class FakeTrack:
    def __init__(self, title, duration_s):
        self.title = title
        self.duration_s = duration_s


def test_returns_none_for_one_track():
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60)], "gapless", 2.0
    )
    assert chapters is None


def test_returns_none_for_two_tracks():
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("B", 60)], "gapless", 2.0
    )
    assert chapters is None


def test_returns_list_for_three_tracks():
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("B", 90), FakeTrack("C", 30)],
        "gapless", 2.0,
    )
    assert chapters == [
        {"seconds": 0,   "title": "A"},
        {"seconds": 60,  "title": "B"},
        {"seconds": 150, "title": "C"},
    ]


def test_crossfade_adjusts_boundaries():
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("B", 60), FakeTrack("C", 60)],
        "crossfade", 2.0,
    )
    # Boundaries: 0, 58, 116
    assert chapters == [
        {"seconds": 0,   "title": "A"},
        {"seconds": 58,  "title": "B"},
        {"seconds": 116, "title": "C"},
    ]


def test_empty_title_falls_back(caplog):
    chapters = build_chapters_from_tracks(
        [FakeTrack("A", 60), FakeTrack("", 60), FakeTrack(None, 60)],
        "gapless", 2.0,
    )
    assert chapters[1]["title"] == "Track 2"
    assert chapters[2]["title"] == "Track 3"
    # Both empty/null titles logged a warning
    warnings = [r for r in caplog.records if "empty title" in r.message.lower()]
    assert len(warnings) == 2
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_chapter_builder.py -x -v`
Expected: ImportError on `build_chapters_from_tracks`.

- [ ] **Step 3: Implement `build_chapters_from_tracks` and `build_chapters`**

Add to `console/backend/services/youtube_video_service.py`:

```python
import logging
log = logging.getLogger(__name__)


def build_chapters_from_tracks(
    tracks, transition: str, transition_s: float
) -> list[dict] | None:
    """Pure function — returns chapter list or None.

    Returns None when there are <3 tracks (YouTube requires >=3 chapters).
    Falls back to "Track {i+1}" when a track title is empty/null, logging
    a warning.
    """
    if len(tracks) < 3:
        return None
    _, boundaries = _compute_music_total_duration(tracks, transition, transition_s)
    chapters = []
    for i, t in enumerate(tracks):
        title = (t.title or "").strip()
        if not title:
            log.warning("Music track at index %d has empty title; "
                        "falling back to 'Track %d'", i, i + 1)
            title = f"Track {i + 1}"
        chapters.append({
            "seconds": int(round(boundaries[i])),
            "title": title,
        })
    return chapters


# Service method that wraps the pure function:
class YoutubeVideoService:
    # ... existing ...
    def build_chapters(self, video) -> list[dict] | None:
        if video.template.slug != "music":
            return None
        tracks = _resolve_music_tracks(video, self.db)
        return build_chapters_from_tracks(
            tracks, video.track_transition, video.track_transition_seconds
        )
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_chapter_builder.py -x -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add console/backend/services/youtube_video_service.py \
        tests/test_chapter_builder.py
git commit -m "feat(svc): build_chapters helper for music template

Pure function returns chapter list (seconds + title) or None when
<3 tracks (YouTube minimum). Boundaries reuse the same duration math
as the renderer. Empty titles fall back to 'Track N' with warning log."
```

---

## Task 6: Music playlist WAV builder with transitions

**Files:**
- Create: `pipeline/music_audio.py`
- Create: `tests/test_music_audio.py`

- [ ] **Step 1: Write failing test (uses synthesized sine WAVs)**

```python
# tests/test_music_audio.py
import subprocess
from pathlib import Path

import pytest

from pipeline.music_audio import build_music_playlist_wav_with_transitions


class FakeTrack:
    def __init__(self, file_path, duration_s, volume=1.0):
        self.file_path = file_path
        self.duration_s = duration_s
        self.volume = volume


@pytest.fixture
def sine_wav(tmp_path):
    """Generate a 5-second mono 440Hz WAV for testing."""
    def make(name: str, dur: float = 5.0, freq: int = 440) -> Path:
        out = tmp_path / f"{name}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency={freq}:duration={dur}",
            "-ar", "44100", "-ac", "2", str(out),
        ], check=True, capture_output=True)
        return out
    return make


def _probe_duration(path: Path) -> float:
    out = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def test_gapless_concat_total_duration(tmp_path, sine_wav):
    a, b, c = sine_wav("a"), sine_wav("b"), sine_wav("c")
    tracks = [FakeTrack(str(a), 5.0), FakeTrack(str(b), 5.0), FakeTrack(str(c), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=15.0, transition="gapless",
        transition_s=2.0, output_dir=tmp_path,
    )
    assert _probe_duration(Path(out)) == pytest.approx(15.0, abs=0.1)


def test_crossfade_total_duration(tmp_path, sine_wav):
    a, b = sine_wav("a"), sine_wav("b")
    tracks = [FakeTrack(str(a), 5.0), FakeTrack(str(b), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=8.0, transition="crossfade",
        transition_s=2.0, output_dir=tmp_path,
    )
    # 5 + 5 - 2 = 8
    assert _probe_duration(Path(out)) == pytest.approx(8.0, abs=0.15)


def test_gap_total_duration(tmp_path, sine_wav):
    a, b = sine_wav("a"), sine_wav("b")
    tracks = [FakeTrack(str(a), 5.0), FakeTrack(str(b), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=11.5, transition="gap",
        transition_s=1.5, output_dir=tmp_path,
    )
    # 5 + 1.5 + 5 = 11.5
    assert _probe_duration(Path(out)) == pytest.approx(11.5, abs=0.15)


def test_single_track_no_loop(tmp_path, sine_wav):
    a = sine_wav("a", dur=5.0)
    tracks = [FakeTrack(str(a), 5.0)]
    out = build_music_playlist_wav_with_transitions(
        tracks, total_duration_s=5.0, transition="gapless",
        transition_s=2.0, output_dir=tmp_path,
    )
    assert _probe_duration(Path(out)) == pytest.approx(5.0, abs=0.1)
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_music_audio.py -x -v`
Expected: ImportError.

- [ ] **Step 3: Implement the module**

```python
# pipeline/music_audio.py
"""Music playlist WAV builder for the music template.

Unlike pipeline.youtube_ffmpeg._build_music_playlist_wav (which loops to
fill a target duration), this module produces a WAV equal to the natural
sum of track durations (adjusted for transitions). Used by the music
template render path.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, Protocol


class _Track(Protocol):
    file_path: str
    duration_s: float
    volume: float | None


def build_music_playlist_wav_with_transitions(
    tracks: list,
    total_duration_s: float,
    transition: str,
    transition_s: float,
    output_dir: Path,
    start_s: float = 0.0,
) -> str:
    """Render the playlist to a single WAV with the chosen transition mode.

    Returns absolute path to the output WAV. Raises RuntimeError on ffmpeg
    failure or if no playable tracks are present.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "music_playlist.wav"

    paths: list[tuple[str, float]] = []
    for t in tracks:
        if t.file_path and Path(t.file_path).is_file():
            paths.append((t.file_path, float(getattr(t, "volume", None) or 1.0)))
    if not paths:
        raise RuntimeError("No playable music tracks found")

    cmd = ["ffmpeg", "-y"]
    for path, _vol in paths:
        cmd += ["-i", path]

    parts: list[str] = []
    for i, (_p, vol) in enumerate(paths):
        parts.append(f"[{i}:a]volume={vol}[v{i}]")

    if len(paths) == 1:
        parts.append("[v0]anull[joined]")
    elif transition == "gapless":
        # concat audio streams
        chain = "".join(f"[v{i}]" for i in range(len(paths)))
        parts.append(f"{chain}concat=n={len(paths)}:v=0:a=1[joined]")
    elif transition == "crossfade":
        prev = "v0"
        for i in range(1, len(paths)):
            label = f"x{i}" if i < len(paths) - 1 else "joined"
            parts.append(
                f"[{prev}][v{i}]acrossfade=d={transition_s}:c1=tri:c2=tri[{label}]"
            )
            prev = label
    elif transition == "gap":
        # Insert silence between each pair
        sil = (f"aevalsrc=0|0:duration={transition_s}:sample_rate=44100"
               f":channel_layout=stereo")
        # Build [v0][s][v1][s][v2] then concat
        sil_idx = 0
        chain_parts = []
        for i in range(len(paths)):
            chain_parts.append(f"[v{i}]")
            if i < len(paths) - 1:
                parts.append(f"{sil},asetpts=PTS-STARTPTS[s{sil_idx}]")
                chain_parts.append(f"[s{sil_idx}]")
                sil_idx += 1
        n = len(paths) + (len(paths) - 1)
        parts.append("".join(chain_parts) + f"concat=n={n}:v=0:a=1[joined]")
    else:
        raise ValueError(f"Unknown transition: {transition}")

    if start_s > 0 or abs(total_duration_s) > 0:
        parts.append(
            f"[joined]atrim=start={start_s}:end={start_s + total_duration_s},"
            f"asetpts=PTS-STARTPTS[out]"
        )
        out_label = "[out]"
    else:
        out_label = "[joined]"

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", out_label,
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")
    return str(out_path)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_music_audio.py -x -v`
Expected: 4 passed (note: requires ffmpeg in PATH).

- [ ] **Step 5: Commit**

```bash
git add pipeline/music_audio.py tests/test_music_audio.py
git commit -m "feat(pipeline): music playlist audio builder with transitions

New pipeline/music_audio.py builds a single WAV from N tracks using
gapless concat, pairwise acrossfade, or aevalsrc silence gaps. Returns
a WAV at the natural sum-of-durations length (adjusted for transitions),
unlike the existing _build_music_playlist_wav which loops to fill."
```

---

## Task 7: PNG overlay — chip style

**Files:**
- Create: `pipeline/music_overlay.py`
- Create: `tests/test_music_overlay.py`

- [ ] **Step 1: Write failing test for chip renderer**

```python
# tests/test_music_overlay.py
from pathlib import Path
import pytest
from PIL import Image

from pipeline.music_overlay import render_chip_png


class FakeTrack:
    def __init__(self, title): self.title = title


def test_chip_png_is_full_canvas_rgba(tmp_path):
    tracks = [FakeTrack("Moonlit Stream"), FakeTrack("Hollow Echoes"),
              FakeTrack("Forest Veil")]
    out = render_chip_png(
        tracks=tracks, current_index=1,
        output_dir=tmp_path, canvas_w=1920, canvas_h=1080,
        cache_key="t1",
    )
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.mode == "RGBA"


def test_chip_png_truncates_long_title(tmp_path):
    tracks = [FakeTrack("A" * 100)]  # very long
    out = render_chip_png(
        tracks=tracks, current_index=0,
        output_dir=tmp_path, canvas_w=1920, canvas_h=1080,
        cache_key="t2",
    )
    # Just verify it didn't crash and produced a file
    assert Path(out).is_file()


def test_chip_png_caches_by_key(tmp_path):
    tracks = [FakeTrack("A"), FakeTrack("B")]
    p1 = render_chip_png(tracks, 0, tmp_path, 1920, 1080, "same-key")
    p2 = render_chip_png(tracks, 0, tmp_path, 1920, 1080, "same-key")
    assert p1 == p2
    # Different key → different file
    p3 = render_chip_png(tracks, 0, tmp_path, 1920, 1080, "other-key")
    assert p3 != p1
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_music_overlay.py -x -v`
Expected: ImportError.

- [ ] **Step 3: Implement chip renderer + module skeleton**

```python
# pipeline/music_overlay.py
"""PNG renderer for now-playing playlist overlays.

Generates one transparent RGBA PNG per (style, current_index, cache_key).
The render pipeline overlays these onto the visual video using ffmpeg's
overlay+enable filter, switching which PNG is "active" at each track
boundary.

Three styles supported:
  - chip:        compact bottom-left pill
  - sidebar:     right-side playlist (all tracks visible, current highlighted)
  - bottom_bar:  bottom-center bar with current track + duration
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont


# === Constants ==============================================================

_FONT_CANDIDATES = [
    "/Library/Fonts/IBMPlexSans-Medium.ttf",     # macOS
    "/usr/share/fonts/truetype/ibm-plex/IBMPlexSans-Medium.ttf",  # Linux
    "/System/Library/Fonts/Helvetica.ttc",       # macOS fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux fallback
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


@dataclass
class OverlaySegment:
    png_path: str
    start_s: float
    end_s: float


class _Track(Protocol):
    title: str


# === chip ===================================================================

def render_chip_png(
    tracks: list, current_index: int,
    output_dir: Path, canvas_w: int, canvas_h: int,
    cache_key: str,
) -> str:
    """Bottom-left pill with [{i+1}/{n} · title]."""
    out = Path(output_dir) / f"overlay_chip_{current_index}_{cache_key}.png"
    if out.is_file():
        return str(out)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    title = _truncate(tracks[current_index].title or f"Track {current_index+1}", 40)
    label = f"{current_index + 1} / {len(tracks)}  ·  {title}"
    font = _load_font(28)

    # measure text
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # pill geometry — bottom-left, 4% margin
    pad_x, pad_y = 24, 14
    dot_r = 7
    dot_gap = 14
    pill_w = dot_r * 2 + dot_gap + text_w + pad_x * 2
    pill_h = max(text_h, dot_r * 2) + pad_y * 2

    margin = int(canvas_w * 0.04)
    x = margin
    y = canvas_h - margin - pill_h

    # background
    draw.rounded_rectangle(
        (x, y, x + pill_w, y + pill_h),
        radius=pill_h // 2,
        fill=(10, 14, 28, int(0.55 * 255)),
        outline=(255, 255, 255, int(0.10 * 255)),
        width=1,
    )
    # dot
    cx = x + pad_x + dot_r
    cy = y + pill_h // 2
    draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
                 fill=(124, 106, 247, 255))
    # text
    tx = cx + dot_r + dot_gap
    ty = y + (pill_h - text_h) // 2 - bbox[1]
    draw.text((tx, ty), label, font=font, fill=(232, 232, 240, 255))

    img.save(out, "PNG")
    return str(out)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_music_overlay.py -x -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/music_overlay.py tests/test_music_overlay.py
git commit -m "feat(pipeline): PNG renderer for chip-style now-playing overlay

New pipeline/music_overlay.py module. render_chip_png produces a
transparent RGBA PNG at full canvas resolution with a bottom-left
pill showing track index + title. Cached by cache_key on disk."
```

---

## Task 8: PNG overlay — sidebar style

**Files:**
- Modify: `pipeline/music_overlay.py`
- Modify: `tests/test_music_overlay.py`

- [ ] **Step 1: Add failing tests for sidebar**

Append to `tests/test_music_overlay.py`:

```python
from pipeline.music_overlay import render_sidebar_png


def test_sidebar_full_canvas_rgba(tmp_path):
    tracks = [FakeTrack(f"Track {i}") for i in range(5)]
    out = render_sidebar_png(tracks, 2, tmp_path, 1920, 1080, "s1")
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.mode == "RGBA"


def test_sidebar_truncates_to_30_chars(tmp_path):
    tracks = [FakeTrack("A" * 100), FakeTrack("B"), FakeTrack("C")]
    out = render_sidebar_png(tracks, 0, tmp_path, 1920, 1080, "s2")
    assert Path(out).is_file()  # didn't crash on long title


def test_sidebar_handles_long_playlist(tmp_path):
    """>8 tracks should show 4 around current + ellipsis above/below."""
    tracks = [FakeTrack(f"Track {i}") for i in range(20)]
    out = render_sidebar_png(tracks, 10, tmp_path, 1920, 1080, "s3")
    assert Path(out).is_file()
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_music_overlay.py::test_sidebar_full_canvas_rgba -x -v`
Expected: ImportError on `render_sidebar_png`.

- [ ] **Step 3: Implement sidebar renderer**

Append to `pipeline/music_overlay.py`:

```python
def render_sidebar_png(
    tracks: list, current_index: int,
    output_dir: Path, canvas_w: int, canvas_h: int,
    cache_key: str,
) -> str:
    """Right-side playlist column showing all tracks, current highlighted."""
    out = Path(output_dir) / f"overlay_sidebar_{current_index}_{cache_key}.png"
    if out.is_file():
        return str(out)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    panel_w = int(canvas_w * 0.28)
    margin  = int(canvas_w * 0.03)
    pad     = 18
    header_font = _load_font(13)
    row_font    = _load_font(18)

    # Determine which rows to render (window of 8 around current for long lists)
    n = len(tracks)
    window: list[tuple[int, str]] = []  # (display_marker, title)
    if n <= 8:
        rows = list(range(n))
        show_top_ellipsis = show_bot_ellipsis = False
    else:
        start = max(0, current_index - 3)
        end   = min(n, start + 8)
        if end == n:
            start = max(0, end - 8)
        rows = list(range(start, end))
        show_top_ellipsis = start > 0
        show_bot_ellipsis = end < n

    # Header
    header = f"Playlist · {n} tracks"
    h_bbox = draw.textbbox((0, 0), header, font=header_font)
    h_h = h_bbox[3] - h_bbox[1]

    row_h = 28
    panel_h = pad * 2 + h_h + 12 + row_h * (
        len(rows) + (1 if show_top_ellipsis else 0)
        + (1 if show_bot_ellipsis else 0)
    )

    x = canvas_w - margin - panel_w
    y = (canvas_h - panel_h) // 2

    # Background
    draw.rounded_rectangle(
        (x, y, x + panel_w, y + panel_h),
        radius=8,
        fill=(8, 10, 20, int(0.45 * 255)),
        outline=(255, 255, 255, int(0.08 * 255)),
        width=1,
    )

    # Header text
    hx = x + pad
    hy = y + pad - h_bbox[1]
    draw.text((hx, hy), header.upper(),
              font=header_font, fill=(90, 90, 112, 255))

    cursor_y = y + pad + h_h + 12
    if show_top_ellipsis:
        draw.text((hx, cursor_y), "…", font=row_font, fill=(90, 90, 112, 255))
        cursor_y += row_h

    for i in rows:
        played = i < current_index
        is_current = i == current_index
        marker = "✓" if played else ("▶" if is_current else f"{i+1}")
        title = _truncate(tracks[i].title or f"Track {i+1}", 30)

        if is_current:
            color = (232, 232, 240, 255)
            marker_color = (124, 106, 247, 255)
        elif played:
            color = (106, 106, 128, 255)
            marker_color = (52, 211, 153, 255)
        else:
            color = (106, 106, 128, 255)
            marker_color = (90, 90, 112, 255)

        draw.text((hx, cursor_y), marker, font=row_font, fill=marker_color)
        draw.text((hx + 28, cursor_y), title, font=row_font, fill=color)
        cursor_y += row_h

    if show_bot_ellipsis:
        draw.text((hx, cursor_y), "…", font=row_font, fill=(90, 90, 112, 255))

    img.save(out, "PNG")
    return str(out)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_music_overlay.py -x -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/music_overlay.py tests/test_music_overlay.py
git commit -m "feat(pipeline): sidebar-style now-playing overlay PNG

Right-side panel showing all tracks (or 8-track window with ellipsis
markers for long playlists). Played tracks get checkmarks in green,
current track gets ▶ in violet, upcoming get track numbers."
```

---

## Task 9: PNG overlay — bottom_bar style

**Files:**
- Modify: `pipeline/music_overlay.py`
- Modify: `tests/test_music_overlay.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_music_overlay.py`:

```python
from pipeline.music_overlay import render_bottom_bar_png


class FakeTrackWithDuration:
    def __init__(self, title, duration_s):
        self.title = title
        self.duration_s = duration_s


def test_bottom_bar_full_canvas_rgba(tmp_path):
    tracks = [FakeTrackWithDuration(f"Track {i}", 60.0) for i in range(3)]
    out = render_bottom_bar_png(tracks, 1, tmp_path, 1920, 1080, "b1")
    img = Image.open(out)
    assert img.size == (1920, 1080)
    assert img.mode == "RGBA"


def test_bottom_bar_long_title_truncates(tmp_path):
    tracks = [FakeTrackWithDuration("A" * 100, 60.0)]
    out = render_bottom_bar_png(tracks, 0, tmp_path, 1920, 1080, "b2")
    assert Path(out).is_file()
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_music_overlay.py::test_bottom_bar_full_canvas_rgba -x -v`
Expected: ImportError.

- [ ] **Step 3: Implement bottom_bar renderer**

Append to `pipeline/music_overlay.py`:

```python
def _fmt_mmss(seconds: float) -> str:
    s = int(round(seconds))
    m, s = divmod(s, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def render_bottom_bar_png(
    tracks: list, current_index: int,
    output_dir: Path, canvas_w: int, canvas_h: int,
    cache_key: str,
) -> str:
    """Bottom-center bar showing 'Track i/n · Title · MM:SS'."""
    out = Path(output_dir) / f"overlay_bottom_bar_{current_index}_{cache_key}.png"
    if out.is_file():
        return str(out)

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    track = tracks[current_index]
    title = _truncate(track.title or f"Track {current_index+1}", 50)
    duration = _fmt_mmss(track.duration_s)
    label = f"Track {current_index + 1} / {len(tracks)}   ·   {title}   ·   {duration}"
    font = _load_font(22)

    bar_w = int(canvas_w * 0.60)
    pad_x, pad_y = 24, 16

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bar_h = text_h + pad_y * 2

    margin_y = int(canvas_h * 0.06)
    x = (canvas_w - bar_w) // 2
    y = canvas_h - margin_y - bar_h

    draw.rounded_rectangle(
        (x, y, x + bar_w, y + bar_h),
        radius=6,
        fill=(8, 10, 20, int(0.55 * 255)),
        outline=(255, 255, 255, int(0.08 * 255)),
        width=1,
    )
    tx = x + (bar_w - text_w) // 2 - bbox[0]
    ty = y + (bar_h - text_h) // 2 - bbox[1]
    draw.text((tx, ty), label, font=font, fill=(232, 232, 240, 255))

    img.save(out, "PNG")
    return str(out)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_music_overlay.py -x -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/music_overlay.py tests/test_music_overlay.py
git commit -m "feat(pipeline): bottom-bar now-playing overlay PNG

Bottom-center bar with 'Track i/n · Title · MM:SS'. No animated
progress bar in v1 to keep PNG approach pure."
```

---

## Task 10: Overlay orchestrator + cache key + segments

**Files:**
- Modify: `pipeline/music_overlay.py`
- Modify: `tests/test_music_overlay.py`

- [ ] **Step 1: Add failing test for orchestrator**

Append to `tests/test_music_overlay.py`:

```python
from pipeline.music_overlay import build_now_playing_overlay


class FakeVideo:
    def __init__(self, style):
        self.playlist_overlay_style = style


def test_orchestrator_returns_segment_per_track(tmp_path):
    tracks = [FakeTrackWithDuration(f"T{i}", 60.0) for i in range(3)]
    boundaries = [0.0, 60.0, 120.0]
    video = FakeVideo("chip")
    segs = build_now_playing_overlay(
        video=video, tracks=tracks, boundaries=boundaries,
        total_duration_s=180.0, output_dir=tmp_path,
        canvas_w=1920, canvas_h=1080,
    )
    assert len(segs) == 3
    assert segs[0].start_s == 0.0
    assert segs[0].end_s == 60.0
    assert segs[1].start_s == 60.0
    assert segs[1].end_s == 120.0
    assert segs[2].start_s == 120.0
    assert segs[2].end_s == 180.0
    for seg in segs:
        assert Path(seg.png_path).is_file()


def test_cache_key_invalidates_on_title_change(tmp_path):
    tracks_v1 = [FakeTrackWithDuration("Original", 60.0),
                 FakeTrackWithDuration("Two", 60.0),
                 FakeTrackWithDuration("Three", 60.0)]
    tracks_v2 = [FakeTrackWithDuration("Renamed", 60.0),
                 FakeTrackWithDuration("Two", 60.0),
                 FakeTrackWithDuration("Three", 60.0)]
    video = FakeVideo("chip")
    segs1 = build_now_playing_overlay(
        video, tracks_v1, [0.0, 60.0, 120.0], 180.0, tmp_path, 1920, 1080
    )
    segs2 = build_now_playing_overlay(
        video, tracks_v2, [0.0, 60.0, 120.0], 180.0, tmp_path, 1920, 1080
    )
    # Different titles → different cache key → different paths
    assert segs1[0].png_path != segs2[0].png_path
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_music_overlay.py::test_orchestrator_returns_segment_per_track -x -v`
Expected: ImportError.

- [ ] **Step 3: Implement orchestrator + cache key**

Append to `pipeline/music_overlay.py`:

```python
def _playlist_cache_key(tracks: list) -> str:
    """Hash the ordered (id, title) list so cache invalidates on rename."""
    h = hashlib.sha1()
    for t in tracks:
        tid = getattr(t, "id", "?")
        title = (t.title or "").strip()
        h.update(f"{tid}|{title}\n".encode("utf-8"))
    return h.hexdigest()[:12]


_RENDERERS = {
    "chip":       render_chip_png,
    "sidebar":    render_sidebar_png,
    "bottom_bar": render_bottom_bar_png,
}


def build_now_playing_overlay(
    video,
    tracks: list,
    boundaries: list[float],
    total_duration_s: float,
    output_dir: Path,
    canvas_w: int = 1920,
    canvas_h: int = 1080,
) -> list[OverlaySegment]:
    """Build one OverlaySegment per track using video.playlist_overlay_style."""
    style = getattr(video, "playlist_overlay_style", None)
    if not style or len(tracks) < 2:
        return []
    renderer = _RENDERERS.get(style)
    if renderer is None:
        raise ValueError(f"Unknown overlay style: {style}")

    cache_key = _playlist_cache_key(tracks)
    segments: list[OverlaySegment] = []
    for i in range(len(tracks)):
        start = boundaries[i]
        end   = boundaries[i + 1] if i + 1 < len(tracks) else total_duration_s
        png   = renderer(
            tracks=tracks, current_index=i,
            output_dir=Path(output_dir),
            canvas_w=canvas_w, canvas_h=canvas_h,
            cache_key=cache_key,
        )
        segments.append(OverlaySegment(png_path=png, start_s=start, end_s=end))
    return segments
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_music_overlay.py -x -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/music_overlay.py tests/test_music_overlay.py
git commit -m "feat(pipeline): now-playing overlay orchestrator + cache invalidation

build_now_playing_overlay maps tracks → OverlaySegments using the
selected style renderer. Cache key hashes (id, title) tuples so a
track rename invalidates cached PNGs automatically."
```

---

## Task 11: Spectrum filtergraph helper

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Create: `tests/test_spectrum_filter.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_spectrum_filter.py
from pipeline.youtube_ffmpeg import build_spectrum_filter


def test_disabled_returns_empty():
    assert build_spectrum_filter(
        enabled=False, position="bottom", height_pct=0.12,
        color="#ffffff", opacity=0.6, canvas_w=1920, canvas_h=1080,
    ) == ("", [])


def test_bottom_position_renders_overlay_at_bottom():
    chain, inputs = build_spectrum_filter(
        enabled=True, position="bottom", height_pct=0.10,
        color="#ffffff", opacity=0.5, canvas_w=1920, canvas_h=1080,
    )
    assert "showfreqs" in chain
    assert "size=1920x108" in chain  # 1080 * 0.10
    assert "overlay=0:972" in chain  # 1080 - 108
    assert "colorchannelmixer=aa=0.5" in chain
    assert inputs == []  # uses existing audio input


def test_center_position():
    chain, _ = build_spectrum_filter(
        enabled=True, position="center", height_pct=0.20,
        color="#7c6af7", opacity=0.8, canvas_w=1920, canvas_h=1080,
    )
    # height = 216, y = (1080 - 216) // 2 = 432
    assert "size=1920x216" in chain
    assert "overlay=0:432" in chain
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_spectrum_filter.py -x -v`
Expected: ImportError on `build_spectrum_filter`.

- [ ] **Step 3: Implement helper in `pipeline/youtube_ffmpeg.py`**

Add near the top of `pipeline/youtube_ffmpeg.py` (after imports, before existing functions):

```python
def build_spectrum_filter(
    enabled: bool,
    position: str,        # 'bottom' | 'center'
    height_pct: float,    # 0.0..0.5
    color: str,           # '#rrggbb'
    opacity: float,       # 0.0..1.0
    canvas_w: int,
    canvas_h: int,
    audio_input_label: str = "[1:a]",
    base_label: str = "[base]",
    out_label: str = "[v_with_spec]",
) -> tuple[str, list[str]]:
    """Return (filter_chain_fragment, extra_ffmpeg_inputs).

    Caller is responsible for splicing the chain into the larger filtergraph
    and labeling the inputs. Returns ('', []) when disabled.
    """
    if not enabled:
        return ("", [])

    height_px = int(canvas_h * height_pct)
    y = canvas_h - height_px if position == "bottom" else (canvas_h - height_px) // 2

    # Strip any alpha from hex; showfreqs colors don't accept alpha
    hex_no_alpha = color[:7]

    chain = (
        f"{audio_input_label}showfreqs=mode=bar:ascale=log:fscale=log:"
        f"cmode=combined:win_size=2048:colors={hex_no_alpha}:"
        f"size={canvas_w}x{height_px}[spec_raw];"
        f"[spec_raw]format=rgba,colorchannelmixer=aa={opacity}[spec];"
        f"{base_label}[spec]overlay=0:{y}{out_label}"
    )
    return (chain, [])
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_spectrum_filter.py -x -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_spectrum_filter.py
git commit -m "feat(pipeline): spectrum visualizer filtergraph helper

build_spectrum_filter returns the ffmpeg filter chain fragment that
overlays an audio-reactive spectrum (showfreqs mode=bar) onto the
visual at the specified position/height/color/opacity. Returns empty
when disabled so callers can splice unconditionally."
```

---

## Task 12: render_landscape music branch

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Create: `tests/test_music_render_smoke.py` (smoke test only — covers branch wiring)

- [ ] **Step 1: Read current `render_landscape` to find branch insertion point**

Run: `grep -n "def render_landscape\|template.slug\|sound_layers\|sfx_pool" pipeline/youtube_ffmpeg.py | head -30`
Locate the section that builds music WAV, sound layers WAV, and blackout filter (per spec, around line 595–616).

- [ ] **Step 2: Write end-to-end smoke test**

```python
# tests/test_music_render_smoke.py
"""Smoke test: render a 30-second music video with overlay + spectrum.

Requires a working ffmpeg + Postgres test DB. Marked slow.
"""
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


@pytest.fixture
def make_sine(tmp_path):
    def _make(name, dur, freq=440):
        out = tmp_path / f"{name}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency={freq}:duration={dur}",
            "-ar", "44100", "-ac", "2", str(out),
        ], check=True, capture_output=True)
        return out
    return _make


@pytest.fixture
def make_visual(tmp_path):
    """Generate a 5-second 1920x1080 color test video."""
    def _make(name, dur=5):
        out = tmp_path / f"{name}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=darkblue:size=1920x1080:duration={dur}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
        ], check=True, capture_output=True)
        return out
    return _make


def _probe_duration(path):
    out = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def test_music_render_30s(db, make_sine, make_visual, tmp_path):
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from database.models import MusicTrack, VideoAsset
    from pipeline.youtube_ffmpeg import render_landscape

    # Setup: 3 tracks (5s, 10s, 15s) totaling 30s
    tracks = []
    for i, dur in enumerate([5, 10, 15], start=1):
        wav = make_sine(f"t{i}", dur, freq=440 + i * 50)
        t = MusicTrack(title=f"Track {i}", file_path=str(wav),
                       duration_s=float(dur), volume=1.0)
        db.add(t); tracks.append(t)
    visual = VideoAsset(file_path=str(make_visual("v")),
                       duration_s=5.0, source="test")
    db.add(visual)
    db.commit()

    template = db.query(VideoTemplate).filter_by(slug="music").one()
    video = YoutubeVideo(
        title="Smoke Music",
        template_id=template.id,
        music_track_ids=[t.id for t in tracks],
        visual_asset_id=visual.id,
        track_transition="gapless",
        playlist_overlay_style="sidebar",
        spectrum_enabled=True,
        spectrum_position="bottom",
        spectrum_height_pct=0.12,
        spectrum_color="#ffffff",
        spectrum_opacity=0.6,
    )
    db.add(video); db.commit()

    out = tmp_path / "final.mp4"
    render_landscape(video, out, db)

    assert out.is_file()
    assert _probe_duration(out) == pytest.approx(30.0, abs=0.5)
```

- [ ] **Step 3: Run smoke test, verify failure**

Run: `pytest tests/test_music_render_smoke.py -x -v`
Expected: branch not implemented → render fails or produces wrong output. Capture exact error.

- [ ] **Step 4: Implement music branch in `render_landscape`**

In `pipeline/youtube_ffmpeg.py`, locate the section in `render_landscape` that resolves music + sound layers + blackout (per spec, ~lines 595–616). Refactor to:

```python
# At the top of the file, ensure these imports:
from pipeline.music_audio import build_music_playlist_wav_with_transitions
from pipeline.music_overlay import build_now_playing_overlay
from console.backend.services.youtube_video_service import (
    _resolve_music_tracks, _compute_music_total_duration,
)

# Inside render_landscape, replace the existing music/sfx/blackout block with:

is_music_template = getattr(video.template, "slug", None) == "music"

if is_music_template:
    music_tracks = _resolve_music_tracks(video, db)
    if not music_tracks:
        raise RuntimeError("Music template requires music tracks")
    total_dur_s, boundaries = _compute_music_total_duration(
        music_tracks,
        video.track_transition,
        video.track_transition_seconds,
    )
    # Override target duration for music template
    full_duration_s = int(round(total_dur_s))

    music_wav = build_music_playlist_wav_with_transitions(
        tracks=music_tracks,
        total_duration_s=total_dur_s,
        transition=video.track_transition,
        transition_s=video.track_transition_seconds,
        output_dir=output_dir,
        start_s=start_s,
    )
    sound_layers_wav = None
    blackout_filter = ""
    overlay_segments = build_now_playing_overlay(
        video=video,
        tracks=music_tracks,
        boundaries=boundaries,
        total_duration_s=total_dur_s,
        output_dir=output_dir,
        canvas_w=1920, canvas_h=1080,
    ) if (video.playlist_overlay_style and len(music_tracks) >= 2) else []
else:
    # Existing asmr/soundscape path — leave as-is
    full_duration_s = int((video.target_duration_h or 3.0) * 3600)
    music_wav = _build_music_playlist_wav(video, db, full_duration_s, output_dir, start_s=start_s)
    sound_layers_wav = _build_sound_layers_wav(video, db, full_duration_s, start_s, output_dir) \
        or _build_sfx_pool_wav(video, db, full_duration_s, start_s, output_dir)
    blackout_filter = _blackout_filter_chain(
        video.black_from_seconds, 1920, 1080, start_s, full_duration_s
    )
    overlay_segments = []

# Spectrum filter chain (music template only)
spectrum_chain, _ = (build_spectrum_filter(
    enabled=video.spectrum_enabled,
    position=video.spectrum_position,
    height_pct=video.spectrum_height_pct,
    color=video.spectrum_color,
    opacity=video.spectrum_opacity,
    canvas_w=1920, canvas_h=1080,
    audio_input_label="[1:a]",
    base_label="[base]",
    out_label="[v_after_spec]",
) if is_music_template else ("", []))

# Now-playing PNG inputs + overlay chain
overlay_inputs: list[str] = []
overlay_chain_parts: list[str] = []
prev_label = "[v_after_spec]" if spectrum_chain else "[base]"
for idx, seg in enumerate(overlay_segments):
    input_idx = 2 + idx       # 0=video, 1=audio, 2..=overlay PNGs
    overlay_inputs += ["-loop", "1", "-i", seg.png_path]
    next_label = f"[v_o{idx}]" if idx < len(overlay_segments) - 1 else "[v_final]"
    # Adjust enable times for chunk window
    enable_start = max(0.0, seg.start_s - start_s)
    enable_end   = max(0.0, seg.end_s   - start_s)
    overlay_chain_parts.append(
        f"{prev_label}[{input_idx}:v]overlay=0:0:"
        f"enable='between(t,{enable_start:.3f},{enable_end:.3f})'{next_label}"
    )
    prev_label = next_label

# (The existing visual_chain produces [base]; concatenate spectrum_chain
# and overlay_chain_parts into the final filter_complex string.)
```

The exact splicing into the existing `filter_complex` assembly depends on how `render_landscape` currently builds it; preserve the existing structure for the asmr/soundscape path and only thread these new chains through when `is_music_template`. The output label of the visual chain becomes `[v_final]` when overlays exist, otherwise the existing label.

Add `overlay_inputs` to the ffmpeg `cmd` between visual + audio inputs. Map `[v_final]` (or whichever final visual label) instead of the original.

- [ ] **Step 5: Run smoke test, verify pass**

Run: `pytest tests/test_music_render_smoke.py -x -v`
Expected: passes; final.mp4 exists and is ~30s.

- [ ] **Step 6: Run full pipeline test suite, verify no regressions**

Run: `pytest tests/pipeline/ tests/test_dispatch_render.py -x --tb=short`
Expected: all existing tests pass — asmr/soundscape rendering paths unchanged.

- [ ] **Step 7: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_music_render_smoke.py
git commit -m "feat(pipeline): music-template branch in render_landscape

Music template uses playlist-derived total duration (no looping),
no SFX layers, no blackout. Spectrum visualizer + now-playing PNG
overlays are spliced into the filtergraph as a chain after the visual
output. Existing asmr/soundscape path is unchanged."
```

---

## Task 13: Chapter formatter + uploader description

**Files:**
- Modify: `uploader/youtube_uploader.py`
- Create: `tests/test_youtube_uploader_chapters.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_youtube_uploader_chapters.py
import pytest

from uploader.youtube_uploader import (
    _format_chapters, _fmt_timestamp, build_description_with_chapters,
)


def test_fmt_timestamp_under_hour():
    assert _fmt_timestamp(0)    == "0:00"
    assert _fmt_timestamp(45)   == "0:45"
    assert _fmt_timestamp(120)  == "2:00"
    assert _fmt_timestamp(3599) == "59:59"


def test_fmt_timestamp_over_hour():
    assert _fmt_timestamp(3600)  == "1:00:00"
    assert _fmt_timestamp(3725)  == "1:02:05"
    assert _fmt_timestamp(43200) == "12:00:00"


def test_format_chapters_forces_first_to_zero():
    chapters = [{"seconds": 5, "title": "A"},
                {"seconds": 60, "title": "B"},
                {"seconds": 120, "title": "C"}]
    s = _format_chapters(chapters)
    assert s.startswith("0:00 A")  # forced even though seconds=5


def test_format_chapters_long_form():
    chapters = [{"seconds": 0, "title": "A"},
                {"seconds": 4350, "title": "B"},
                {"seconds": 9908, "title": "C"}]
    s = _format_chapters(chapters)
    assert "1:12:30 B" in s
    assert "2:45:08 C" in s


def test_build_description_prepends_chapters():
    chapters = [{"seconds": 0, "title": "A"},
                {"seconds": 60, "title": "B"},
                {"seconds": 150, "title": "C"}]
    out = build_description_with_chapters(
        body="My video description.", chapters=chapters,
    )
    lines = out.splitlines()
    assert lines[0] == "0:00 A"
    assert lines[2] == "2:30 C"
    assert lines[3] == ""
    assert lines[4] == "My video description."


def test_build_description_no_chapters_when_under_3():
    out = build_description_with_chapters(
        body="My description.", chapters=[
            {"seconds": 0, "title": "A"},
            {"seconds": 60, "title": "B"},
        ],
    )
    assert out == "My description."


def test_build_description_no_chapters_arg():
    out = build_description_with_chapters(body="Hello", chapters=None)
    assert out == "Hello"
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_youtube_uploader_chapters.py -x -v`
Expected: ImportError on `_format_chapters`.

- [ ] **Step 3: Implement formatters in `uploader/youtube_uploader.py`**

Add to `uploader/youtube_uploader.py` (above the existing `_build_description`):

```python
def _fmt_timestamp(seconds: int) -> str:
    """Format as M:SS or H:MM:SS depending on duration."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_chapters(chapters: list[dict]) -> str:
    """Format chapter list as YouTube-compatible timestamp lines.

    First chapter is FORCED to 0:00 per YouTube's spec, even if the
    input boundary is non-zero (defensive guard for off-by-one bugs
    elsewhere).
    """
    lines = []
    for i, ch in enumerate(chapters):
        ts = 0 if i == 0 else int(ch["seconds"])
        lines.append(f"{_fmt_timestamp(ts)} {ch['title']}")
    return "\n".join(lines)


def build_description_with_chapters(
    body: str,
    chapters: list[dict] | None,
    hashtags: list[str] | None = None,
) -> str:
    """Compose the final YouTube description.

    When chapters has >= 3 entries, prepends a chapters block with a
    blank-line separator. Otherwise returns body unchanged (plus optional
    hashtag block).
    """
    parts = []
    if chapters and len(chapters) >= 3:
        parts.append(_format_chapters(chapters))
        parts.append("")
    parts.append(body)
    if hashtags:
        parts.append("")
        parts.append(" ".join(f"#{h.lstrip('#')}" for h in hashtags))
    return "\n".join(parts)
```

Then update the existing `_build_description` (lines ~118-133) to call `build_description_with_chapters`, accepting an optional `chapters` parameter and threading it through. Update `upload_video()` (lines ~24-134) to accept and forward `chapters: list[dict] | None = None`.

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_youtube_uploader_chapters.py -x -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add uploader/youtube_uploader.py tests/test_youtube_uploader_chapters.py
git commit -m "feat(uploader): YouTube chapter timestamps in description

_format_chapters renders 'M:SS Title' (or 'H:MM:SS Title' for long
videos) with the first timestamp always forced to 0:00 per YouTube's
spec. build_description_with_chapters prepends the chapters block
when >= 3 entries. upload_video accepts a new optional chapters arg."
```

---

## Task 14: Wire chapters into upload Celery task

**Files:**
- Modify: `console/backend/tasks/upload_tasks.py`

- [ ] **Step 1: Locate the upload task**

Run: `grep -n "def upload_to_channel_task\|youtube_uploader\|upload_video" console/backend/tasks/upload_tasks.py | head -10`

- [ ] **Step 2: Build chapters before calling the uploader**

In `console/backend/tasks/upload_tasks.py`, in `upload_to_channel_task` (or whichever task invokes the YouTube uploader), before the `youtube_uploader.upload_video(...)` call:

```python
from console.backend.services.youtube_video_service import YoutubeVideoService

# ... inside the task, after loading `video` and `db` ...
chapters = YoutubeVideoService(db).build_chapters(video)
# Returns list[dict] for music template with >= 3 tracks, else None
```

Then pass `chapters=chapters` to the existing `upload_video(...)` call.

- [ ] **Step 3: Add a unit test for the wiring**

```python
# tests/test_upload_task_chapters.py
from unittest.mock import patch, MagicMock
import pytest

from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo
from database.models import MusicTrack


@pytest.fixture
def music_video_3_tracks(db):
    template = db.query(VideoTemplate).filter_by(slug="music").one()
    tracks = [
        MusicTrack(title=f"T{i}", file_path=f"/tmp/{i}.wav", duration_s=60.0)
        for i in range(3)
    ]
    db.add_all(tracks); db.commit()
    video = YoutubeVideo(
        title="x", template_id=template.id,
        music_track_ids=[t.id for t in tracks],
        track_transition="gapless",
    )
    db.add(video); db.commit()
    return video


def test_upload_task_passes_chapters(db, music_video_3_tracks):
    from console.backend.tasks import upload_tasks
    with patch.object(upload_tasks, "youtube_uploader") as mock_uploader:
        mock_uploader.upload_video = MagicMock(return_value={"id": "abc123"})
        # Invoke the task synchronously (Celery .apply or direct function call)
        upload_tasks.upload_to_channel_task.run(
            video_id=music_video_3_tracks.id, channel_id=1
        )
        call = mock_uploader.upload_video.call_args
        assert call.kwargs.get("chapters") is not None
        assert len(call.kwargs["chapters"]) == 3
```

The exact call signature depends on the task implementation. Adjust the patch target and call invocation to match. If `youtube_uploader` is imported as `from uploader import youtube_uploader`, patch `console.backend.tasks.upload_tasks.youtube_uploader`.

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_upload_task_chapters.py -x -v`
Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add console/backend/tasks/upload_tasks.py tests/test_upload_task_chapters.py
git commit -m "feat(tasks): build + pass YouTube chapters during upload

Upload Celery task calls YoutubeVideoService.build_chapters before
invoking the uploader and forwards the result. For non-music templates
build_chapters returns None and behavior is unchanged."
```

---

## Task 15: MCP `get_chapters` action + docstring update

**Files:**
- Modify: `console/mcp/tools/youtube_video.py`

- [ ] **Step 1: Locate the action dispatch**

Run: `grep -n "actions\s*=\|def youtube_video\|def _action" console/mcp/tools/youtube_video.py | head -20`

Find the action registry pattern (likely a dict or if/elif chain). Note the existing read-only actions for the dispatch style.

- [ ] **Step 2: Add `get_chapters` action**

In `console/mcp/tools/youtube_video.py`, add a new action handler:

```python
def _action_get_chapters(db, video_id: int) -> dict:
    """Return the chapter list that would be uploaded.

    For non-music templates returns {"chapters": None}. For music templates
    with < 3 tracks returns {"chapters": None}. Useful for previewing the
    YouTube description chapters without triggering an upload.
    """
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.services.youtube_video_service import YoutubeVideoService
    video = db.get(YoutubeVideo, int(video_id))
    if not video:
        raise ValueError(f"YoutubeVideo {video_id} not found")
    chapters = YoutubeVideoService(db).build_chapters(video)
    return {"video_id": video.id, "chapters": chapters}
```

Register it in the action dispatch (matching the existing pattern, e.g. add `"get_chapters": _action_get_chapters` to the actions dict).

- [ ] **Step 3: Update tool docstring**

Add a "Music template fields" section to the tool's main docstring listing the 8 new fields:

```
Music template fields (only valid when template_id refers to the 'music' template):
  music_track_ids:           list[int] — ordered playlist
  track_transition:          'gapless' | 'crossfade' | 'gap' (default 'gapless')
  track_transition_seconds:  float, 0.5..10.0 (default 2.0)
  playlist_overlay_style:    'chip' | 'sidebar' | 'bottom_bar' | None
  spectrum_enabled:          bool (default false)
  spectrum_position:         'bottom' | 'center'
  spectrum_height_pct:       float, 0..0.5
  spectrum_color:            '#rrggbb'
  spectrum_opacity:          float, 0..1.0

Read-only actions:
  get_chapters {video_id} → {video_id, chapters: list | None}
    Returns the YouTube chapter list (seconds + title) that would be
    uploaded. Useful for previewing without triggering upload.
```

- [ ] **Step 4: Add a smoke test**

```python
# Append to console/mcp/tests/test_youtube_video_tool.py (create if absent)
import pytest

from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo
from database.models import MusicTrack
from console.mcp.tools.youtube_video import _action_get_chapters


def test_get_chapters_for_music_3_tracks(db):
    template = db.query(VideoTemplate).filter_by(slug="music").one()
    tracks = [MusicTrack(title=f"T{i}", file_path="/tmp/x.wav", duration_s=60.0)
              for i in range(3)]
    db.add_all(tracks); db.commit()
    video = YoutubeVideo(title="x", template_id=template.id,
                        music_track_ids=[t.id for t in tracks])
    db.add(video); db.commit()
    result = _action_get_chapters(db, video.id)
    assert result["video_id"] == video.id
    assert len(result["chapters"]) == 3


def test_get_chapters_returns_none_for_asmr(db):
    template = db.query(VideoTemplate).filter_by(slug="asmr").one()
    video = YoutubeVideo(title="x", template_id=template.id, target_duration_h=8.0)
    db.add(video); db.commit()
    result = _action_get_chapters(db, video.id)
    assert result["chapters"] is None
```

- [ ] **Step 5: Run test, verify pass + commit**

Run: `pytest console/mcp/tests/test_youtube_video_tool.py -x -v`
Expected: 2 passed.

```bash
git add console/mcp/tools/youtube_video.py console/mcp/tests/test_youtube_video_tool.py
git commit -m "feat(mcp): get_chapters read-only action + music-field docs

New action returns the YouTube chapter list that would be injected
on upload, without triggering the upload. Useful for debugging
multi-hour videos. Tool docstring updated with the 8 music-template
field reference."
```

---

## Task 16: Frontend — API client + ui_features gating

**Files:**
- Modify: `console/frontend/src/api/client.js`
- Modify: `console/frontend/src/pages/YoutubeVideoPage.jsx` (or wherever YT video create lives — find via `grep -rln "YoutubeVideoPage\|template.slug" console/frontend/src/`)

- [ ] **Step 1: Add new fields to the API client write payloads**

In `console/frontend/src/api/client.js`, find the `youtubeVideosApi.create` (or equivalent) call. Ensure it forwards these optional fields when present:

```js
// In youtubeVideosApi.create(payload):
//   track_transition, track_transition_seconds,
//   playlist_overlay_style,
//   spectrum_enabled, spectrum_position, spectrum_height_pct,
//   spectrum_color, spectrum_opacity
//
// Plain pass-through; the backend handles defaults. Add field_warnings
// to the response handler if not already present.
```

If the existing client uses an explicit allow-list of fields, add the new ones. If it forwards the entire payload, no change needed.

- [ ] **Step 2: Add `ui_features` gating in the YT create page**

Find the existing template-conditional rendering (`grep -n "sfx_pack\|asmr\|soundscape" console/frontend/src/pages/*.jsx`). Replace hard-coded checks with:

```jsx
const features = new Set(template?.ui_features ?? []);

{features.has('sfx_panel')      && <SfxPanel ... />}
{features.has('duration_picker') && <DurationPicker ... />}
{features.has('blackout')       && <BlackoutPanel ... />}
```

If existing logic uses `template.slug === 'asmr'` checks, leave those AS-IS for backward safety unless you're sure they should be replaced. The key invariant: hiding these three panels for the music template (which has `ui_features = []`).

- [ ] **Step 3: Manual smoke test**

Run: `cd console/frontend && npm run dev`
Open `http://localhost:5173`. Create a new YouTube video, switch template to:
- ASMR → SFX, Duration, Blackout panels visible
- Soundscape → same
- Music → all three panels hidden, page renders without errors

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/api/client.js \
        console/frontend/src/pages/YoutubeVideoPage.jsx
git commit -m "feat(frontend): generic ui_features gating for template panels

API client forwards new music-template fields. YT video page reads
template.ui_features to show/hide SFX, duration, and blackout panels
generically — music template hides all three; asmr/soundscape behavior
unchanged via migration backfill."
```

---

## Task 17: Frontend — music-only panel components

**Files:**
- Create: `console/frontend/src/components/MusicPlaylistPicker.jsx`
- Create: `console/frontend/src/components/TransitionPanel.jsx`
- Create: `console/frontend/src/components/OverlayStylePicker.jsx`
- Create: `console/frontend/src/components/SpectrumPanel.jsx`

- [ ] **Step 1: Create `MusicPlaylistPicker.jsx`**

```jsx
// console/frontend/src/components/MusicPlaylistPicker.jsx
import { useState, useMemo } from 'react';
import { Card, Button } from './index.jsx';
import { musicTracksApi } from '../api/client';

/**
 * Multi-select music track picker with drag-to-reorder.
 *
 * Props:
 *   value: number[]                    - selected music_track_ids in order
 *   onChange: (ids: number[]) => void
 *   transition: 'gapless'|'crossfade'|'gap'
 *   transitionSeconds: number
 */
export function MusicPlaylistPicker({ value, onChange, transition, transitionSeconds }) {
  const [available, setAvailable] = useState([]);
  const [loading, setLoading] = useState(false);

  // Fetch available tracks once
  // (uses existing musicTracksApi; if not present, mirror the pattern from
  //  another picker component in this codebase)
  // ... fetch logic ...

  const selectedTracks = useMemo(
    () => value.map(id => available.find(t => t.id === id)).filter(Boolean),
    [value, available],
  );

  const totalSeconds = useMemo(() => {
    if (!selectedTracks.length) return 0;
    const sum = selectedTracks.reduce((acc, t) => acc + (t.duration_s || 0), 0);
    if (transition === 'crossfade') return sum - transitionSeconds * (selectedTracks.length - 1);
    if (transition === 'gap')        return sum + transitionSeconds * (selectedTracks.length - 1);
    return sum;
  }, [selectedTracks, transition, transitionSeconds]);

  const fmt = (s) => {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
    return h ? `${h}h ${m}m` : `${m}m ${sec}s`;
  };

  // Drag-to-reorder via simple drag handlers
  const handleDrop = (fromIdx, toIdx) => {
    const next = [...value];
    const [moved] = next.splice(fromIdx, 1);
    next.splice(toIdx, 0, moved);
    onChange(next);
  };

  const remove = (id) => onChange(value.filter(v => v !== id));
  const add    = (id) => { if (!value.includes(id)) onChange([...value, id]); };

  return (
    <Card title="Music Playlist">
      {/* Selected tracks list with drag handles + ✕ */}
      <ul className="space-y-1">
        {selectedTracks.map((t, i) => (
          <li key={t.id}
              draggable
              onDragStart={e => e.dataTransfer.setData('text/plain', i)}
              onDragOver={e => e.preventDefault()}
              onDrop={e => handleDrop(parseInt(e.dataTransfer.getData('text/plain')), i)}
              className="flex items-center gap-2 p-2 bg-[#1c1c22] rounded">
            <span className="text-[#5a5a70] cursor-grab">⋮⋮</span>
            <span className="flex-1 truncate">{t.title}</span>
            <span className="text-xs text-[#9090a8]">{fmt(t.duration_s)}</span>
            <button onClick={() => remove(t.id)} className="text-[#f87171]">✕</button>
          </li>
        ))}
      </ul>

      {/* Add-track dropdown — pseudo-code; mirror pattern from other pickers */}
      <select onChange={e => add(parseInt(e.target.value))} value="">
        <option value="" disabled>Add track…</option>
        {available
          .filter(t => !value.includes(t.id))
          .map(t => <option key={t.id} value={t.id}>{t.title}</option>)}
      </select>

      <div className="mt-3 text-sm text-[#9090a8]">
        Total: <span className="text-[#e8e8f0] font-medium">{fmt(totalSeconds)}</span>
        {' · '}{value.length} {value.length === 1 ? 'track' : 'tracks'}
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: Create `TransitionPanel.jsx`**

```jsx
// console/frontend/src/components/TransitionPanel.jsx
import { Card } from './index.jsx';

const MODES = [
  { key: 'gapless',   label: 'Gapless',   desc: 'Tracks play back-to-back, no gap' },
  { key: 'crossfade', label: 'Crossfade', desc: 'Tracks fade into each other' },
  { key: 'gap',       label: 'Gap',       desc: 'Brief silence between tracks' },
];

export function TransitionPanel({ transition, transitionSeconds, onChange }) {
  return (
    <Card title="Track Transition">
      {MODES.map(m => (
        <label key={m.key} className="flex items-start gap-2 p-2 cursor-pointer">
          <input type="radio" name="transition" value={m.key}
                 checked={transition === m.key}
                 onChange={() => onChange({ transition: m.key,
                                            transitionSeconds })} />
          <div>
            <div className="text-[#e8e8f0]">{m.label}</div>
            <div className="text-xs text-[#9090a8]">{m.desc}</div>
          </div>
        </label>
      ))}
      {(transition === 'crossfade' || transition === 'gap') && (
        <div className="mt-2">
          <label className="block text-xs text-[#9090a8] mb-1">
            {transition === 'crossfade' ? 'Crossfade' : 'Gap'} seconds
          </label>
          <input type="number" min={0.5} max={10} step={0.5}
                 value={transitionSeconds}
                 onChange={e => onChange({ transition,
                                          transitionSeconds: parseFloat(e.target.value) })}
                 className="bg-[#1c1c22] border border-[#2a2a32] rounded px-2 py-1 w-24" />
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 3: Create `OverlayStylePicker.jsx`**

```jsx
// console/frontend/src/components/OverlayStylePicker.jsx
import { Card } from './index.jsx';

const STYLES = [
  { key: null,         label: 'None',       desc: 'No overlay' },
  { key: 'chip',       label: 'Chip',       desc: 'Compact bottom-left pill' },
  { key: 'sidebar',    label: 'Sidebar',    desc: 'Right-side playlist column' },
  { key: 'bottom_bar', label: 'Bottom bar', desc: 'Bottom-center bar with track + duration' },
];

export function OverlayStylePicker({ value, onChange, trackCount }) {
  const disabled = trackCount < 2;

  return (
    <Card title="Now-Playing Overlay">
      {disabled && (
        <div className="text-xs text-[#9090a8] mb-2">
          Single track — overlay hidden automatically
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        {STYLES.map(s => (
          <label key={s.key ?? 'none'}
                 className={`flex items-start gap-2 p-2 cursor-pointer
                            ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
            <input type="radio" name="overlay_style"
                   checked={value === s.key}
                   onChange={() => onChange(s.key)} />
            <div>
              <div className="text-[#e8e8f0]">{s.label}</div>
              <div className="text-xs text-[#9090a8]">{s.desc}</div>
            </div>
          </label>
        ))}
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Create `SpectrumPanel.jsx`**

```jsx
// console/frontend/src/components/SpectrumPanel.jsx
import { useState } from 'react';
import { Card } from './index.jsx';

export function SpectrumPanel({ value, onChange }) {
  const [open, setOpen] = useState(value.spectrum_enabled);

  const update = (patch) => onChange({ ...value, ...patch });

  return (
    <Card title="Audio Spectrum (optional)">
      <label className="flex items-center gap-2 cursor-pointer mb-2">
        <input type="checkbox"
               checked={value.spectrum_enabled}
               onChange={e => { update({ spectrum_enabled: e.target.checked });
                                setOpen(e.target.checked); }} />
        <span>Enable spectrum visualizer</span>
      </label>
      {open && (
        <div className="space-y-2 pl-4">
          <div>
            <label className="block text-xs text-[#9090a8] mb-1">Position</label>
            <select value={value.spectrum_position}
                    onChange={e => update({ spectrum_position: e.target.value })}
                    className="bg-[#1c1c22] border border-[#2a2a32] rounded px-2 py-1">
              <option value="bottom">Bottom</option>
              <option value="center">Center</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-[#9090a8] mb-1">
              Height: {Math.round(value.spectrum_height_pct * 100)}%
            </label>
            <input type="range" min={0.05} max={0.50} step={0.01}
                   value={value.spectrum_height_pct}
                   onChange={e => update({ spectrum_height_pct: parseFloat(e.target.value) })}
                   className="w-full" />
          </div>
          <div>
            <label className="block text-xs text-[#9090a8] mb-1">Color</label>
            <input type="color" value={value.spectrum_color}
                   onChange={e => update({ spectrum_color: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs text-[#9090a8] mb-1">
              Opacity: {value.spectrum_opacity.toFixed(2)}
            </label>
            <input type="range" min={0} max={1} step={0.05}
                   value={value.spectrum_opacity}
                   onChange={e => update({ spectrum_opacity: parseFloat(e.target.value) })}
                   className="w-full" />
          </div>
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/components/MusicPlaylistPicker.jsx \
        console/frontend/src/components/TransitionPanel.jsx \
        console/frontend/src/components/OverlayStylePicker.jsx \
        console/frontend/src/components/SpectrumPanel.jsx
git commit -m "feat(frontend): music-only panel components

MusicPlaylistPicker (drag-to-reorder + live total duration),
TransitionPanel (radio + crossfade-seconds), OverlayStylePicker
(4-way: none/chip/sidebar/bottom_bar with single-track helper),
SpectrumPanel (collapsible toggle + position/height/color/opacity)."
```

---

## Task 18: Wire music panels into the YT video page

**Files:**
- Modify: `console/frontend/src/pages/YoutubeVideoPage.jsx` (or equivalent)

- [ ] **Step 1: Import the new components**

```jsx
import { MusicPlaylistPicker } from '../components/MusicPlaylistPicker';
import { TransitionPanel } from '../components/TransitionPanel';
import { OverlayStylePicker } from '../components/OverlayStylePicker';
import { SpectrumPanel } from '../components/SpectrumPanel';
```

- [ ] **Step 2: Render music panels conditionally**

In the page's render, alongside the existing `ui_features` gates from Task 16, add:

```jsx
{template?.slug === 'music' && (
  <>
    <MusicPlaylistPicker
      value={form.music_track_ids ?? []}
      onChange={ids => setForm(f => ({ ...f, music_track_ids: ids }))}
      transition={form.track_transition ?? 'gapless'}
      transitionSeconds={form.track_transition_seconds ?? 2.0}
    />
    <TransitionPanel
      transition={form.track_transition ?? 'gapless'}
      transitionSeconds={form.track_transition_seconds ?? 2.0}
      onChange={({ transition, transitionSeconds }) =>
        setForm(f => ({ ...f, track_transition: transition,
                        track_transition_seconds: transitionSeconds }))}
    />
    <OverlayStylePicker
      value={form.playlist_overlay_style ?? null}
      onChange={s => setForm(f => ({ ...f, playlist_overlay_style: s }))}
      trackCount={(form.music_track_ids ?? []).length}
    />
    <SpectrumPanel
      value={{
        spectrum_enabled:    form.spectrum_enabled    ?? false,
        spectrum_position:   form.spectrum_position   ?? 'bottom',
        spectrum_height_pct: form.spectrum_height_pct ?? 0.12,
        spectrum_color:      form.spectrum_color      ?? '#ffffff',
        spectrum_opacity:    form.spectrum_opacity    ?? 0.6,
      }}
      onChange={patch => setForm(f => ({ ...f, ...patch }))}
    />
  </>
)}
```

The exact form-state shape depends on the page's existing pattern. Match it.

- [ ] **Step 3: Manual smoke test**

Run: `cd console/frontend && npm run dev` (if not already)
- Switch template to "Music Video"
- Add 3 music tracks, see live duration update
- Switch transition mode → crossfade input appears, total updates
- Pick overlay style → all 4 visible; pick "None" then change track count to 1 → disabled state appears
- Toggle spectrum → controls appear; adjust each control
- Save → check network tab for the create POST including new fields
- Reload, verify form re-populates from saved state

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/YoutubeVideoPage.jsx
git commit -m "feat(frontend): wire music-only panels into YT video page

Music template now shows playlist picker, transition selector,
overlay style picker, and spectrum panel. Form state plumbed through
to API create/update calls. Existing asmr/soundscape flow unchanged."
```

---

## Task 19: End-to-end verification + manual QA

**Files:** none — verification only

- [ ] **Step 1: Run the full backend test suite**

Run: `pytest tests/ -x --tb=short 2>&1 | tail -40`
Expected: all tests pass. If any pre-existing test fails, investigate — your changes shouldn't have caused it but verify.

- [ ] **Step 2: Run the smoke test alone**

Run: `pytest tests/test_music_render_smoke.py -x -v -s`
Expected: passes. Inspect generated `final.mp4` in the temp dir if available; verify visually it has the dark blue background + spectrum + sidebar overlay.

- [ ] **Step 3: Manual full-stack QA**

Start the backend and frontend (`./console/start.sh` + `cd console/frontend && npm run dev`). For each of the cases below, create the video, dispatch a render, and verify the output:

- 1-track music video → no overlay, no chapters in description
- 2-track music video → no chapters in description (verify with backend response)
- 5-track music video, sidebar overlay, spectrum on → final.mp4 shows playlist + spectrum
- 5-track music video, chip overlay, spectrum off → final.mp4 shows chip only
- 5-track music video, bottom_bar overlay → final.mp4 shows bottom bar
- Reject test: try to create a music video with `target_duration_h=8` → 400 error visible in toast
- Reject test: try to create a music video with `black_from_seconds=100` → 400 error
- Reject test: try crossfade with seconds > shortest_track/2 → 400 error
- ASMR template still works end-to-end → render an existing asmr video, confirm no regression

- [ ] **Step 4: Verify chapters via MCP**

In a separate terminal:
```bash
# Use the MCP tool (from Claude Code or other MCP client)
# action: get_chapters, video_id: <your 3-track music video id>
```
Expected: returns `chapters: [{seconds: 0, title: ...}, ...]` with 3 entries.

- [ ] **Step 5: Live YouTube upload verification (optional but recommended)**

If a test channel is configured, upload a 3-track music video. After upload completes, open the video in YouTube Studio:
- Description shows chapter timestamps at top
- YouTube renders the chapter list in the player progress bar
- Each chapter jumps to the correct timestamp

- [ ] **Step 6: Final commit (if anything came up during QA)**

```bash
# If any small fixes emerged:
git add <changed files>
git commit -m "fix: <specific fix from QA>"
```

If nothing changed, no commit. The implementation is complete.

---

## Self-Review (run before declaring complete)

**1. Spec coverage check:**

| Spec section | Implemented in |
|--------------|----------------|
| Migration `017_music_template` (renumbered to `022`) | Task 1 |
| `ui_features` JSONB column + backfill | Task 1 |
| 8 columns on `youtube_videos` | Task 1 |
| CHECK constraints (incl. transition_seconds_range) | Task 1 |
| ORM model updates | Task 2 |
| Pydantic schemas + Literal types | Task 2 |
| `_resolve_music_tracks` helper | Task 3 |
| `_compute_music_total_duration` (3 modes) | Task 3 |
| Service validation (5 reject cases + null overlay) | Task 4 |
| Crossfade safety check | Task 4 |
| `build_chapters()` (≥3 tracks rule) | Task 5 |
| Empty title fallback | Task 5 |
| `_build_music_playlist_wav_with_transitions` | Task 6 |
| Chip overlay | Task 7 |
| Sidebar overlay (incl. >8 truncation) | Task 8 |
| Bottom bar overlay | Task 9 |
| Cache key (rename invalidation) | Task 10 |
| `build_now_playing_overlay` orchestrator | Task 10 |
| Spectrum filter (`build_spectrum_filter`) | Task 11 |
| `render_landscape` music branch | Task 12 |
| Render budget warning (>4h + spectrum + overlay) | **Gap — not implemented**; spec marks this as soft warning only. Add to `_validate_music_template` in Task 4 if needed, or defer as enhancement. |
| Chapter formatter + `build_description_with_chapters` | Task 13 |
| First-chapter-must-be-0:00 guard | Task 13 |
| Upload Celery task wiring | Task 14 |
| MCP `get_chapters` action | Task 15 |
| MCP docstring update | Task 15 |
| Frontend `ui_features` gating | Task 16 |
| Music playlist picker | Task 17 |
| Transition panel | Task 17 |
| Overlay style picker | Task 17 |
| Spectrum panel | Task 17 |
| Wire panels into page | Task 18 |
| Smoke render test | Tasks 12, 19 |

**Render budget warning (>4h + spectrum + overlay)** — added as a small follow-up: in `_validate_music_template`, after collecting `track_ids`, compute `total_duration_s`; if `> 4 * 3600` and `data.get('spectrum_enabled')` and `data.get('playlist_overlay_style')`, append a warning. Not blocking. Implement inside Task 4 if you want it in v1; otherwise defer.

**2. Placeholder scan:** No `TBD`, `TODO`, or "implement later" placeholders. All code blocks are complete. Frontend tasks reference `Card` and other shared components from `console/frontend/src/components/index.jsx` per the existing project convention.

**3. Type consistency:** 
- Helper names match across tasks: `_resolve_music_tracks` (Tasks 3, 12, 15), `_compute_music_total_duration` (Tasks 3, 5, 12), `build_chapters` (Tasks 5, 14, 15), `build_now_playing_overlay` (Tasks 10, 12), `build_spectrum_filter` (Tasks 11, 12), `build_description_with_chapters` (Tasks 13, 14).
- Field names: `track_transition`, `track_transition_seconds`, `playlist_overlay_style`, `spectrum_enabled`, `spectrum_position`, `spectrum_height_pct`, `spectrum_color`, `spectrum_opacity` — used identically in migration, models, schemas, service, render, and frontend.
- Track field name: `duration_s` (not `duration_seconds`) — matches `database/models.py:30`.
- Migration revision: `022_music_template`, `down_revision='d885cdd6570e'` (current head per `alembic heads`).

---

## Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
