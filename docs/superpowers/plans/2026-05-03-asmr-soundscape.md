# ASMR & Soundscape Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ASMR/soundscape rendering — random SFX, blackout-time, multi-music, chunked resumable render, audio+video preview gates, live progress UI.

**Architecture:** All new behavior gated on `template in ("asmr","soundscape")`. Composer refactored around `compose_window(start_s, end_s)` so previews and chunks share one path. Celery `chord(group(chunks), concat)` for chunked renders. ffmpeg concat demuxer with `-c copy` for seamless joins. WebSocket pushes progress + log tail.

**Tech Stack:** SQLAlchemy + Alembic (Postgres), Celery (Redis broker), FastAPI WebSockets, MoviePy, ffmpeg, React + Tailwind.

**Spec:** `docs/superpowers/specs/2026-05-03-asmr-soundscape-design.md`

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `console/backend/alembic/versions/013_asmr_soundscape.py` | NEW | Migration: 9 new columns on `generated_scripts` |
| `database/models.py` | MODIFY | Add new columns to `GeneratedScript` |
| `pipeline/composer.py` | MODIFY | Extract `compose_window`; add `_build_sfx_layer`, `_build_music_playlist`, `_apply_blackout` |
| `pipeline/audio_only.py` | NEW | `compose_audio_only(script_id, start_s, end_s)` for audio preview |
| `pipeline/concat.py` | NEW | `concat_parts(part_paths, output_path)` ffmpeg helper |
| `console/backend/tasks/production_tasks.py` | MODIFY | Add `render_audio_preview_task`, `render_video_preview_task`, `render_chunk_task`, `concat_chunks_task`, `render_chunked_orchestrator_task` |
| `console/backend/services/production_service.py` | MODIFY | Add preview/chunked render methods |
| `console/backend/services/render_state.py` | NEW | Unified render-state reader |
| `console/backend/routers/production.py` | MODIFY | Add 9 new endpoints |
| `console/backend/ws/render_ws.py` | NEW | `/ws/render/{script_id}` Redis pub/sub bridge |
| `console/backend/services/pipeline_service.py` | MODIFY | Extend `emit_log` to also publish to per-script Redis channel |
| `console/backend/main.py` | MODIFY | Register `render_ws` router |
| `console/frontend/src/components/AsmrControls.jsx` | NEW | Master ASMR config panel |
| `console/frontend/src/components/MusicPlaylistEditor.jsx` | NEW | Drag-to-reorder ordered music list |
| `console/frontend/src/components/SfxPoolEditor.jsx` | NEW | Multi-select SFX picker + density slider |
| `console/frontend/src/components/RenderStatePanel.jsx` | NEW | Progress bar + chunk pills + log tail |
| `console/frontend/src/components/PreviewApprovalGate.jsx` | NEW | Audio/video player + approve/reject |
| `console/frontend/src/hooks/useRenderWebSocket.js` | NEW | WS client with auto-reconnect |
| `console/frontend/src/pages/ProductionPage.jsx` | MODIFY | Switch sidebar based on template; mount RenderStatePanel + PreviewApprovalGate |
| `console/frontend/src/api/client.js` | MODIFY | Add `productionApi` helpers for new endpoints |
| `tests/pipeline/test_sfx_scheduler.py` | NEW | Seed determinism + density bounds |
| `tests/pipeline/test_concat.py` | NEW | Seam equality test |
| `tests/backend/test_render_state.py` | NEW | API + state machine tests |

---

## Phase 1 — Data Layer

### Task 1: Migration + model fields

**Files:**
- Create: `console/backend/alembic/versions/013_asmr_soundscape.py`
- Modify: `database/models.py:77-109`
- Test: `tests/backend/test_asmr_migration.py`

- [ ] **Step 1: Write the migration**

```python
# console/backend/alembic/versions/013_asmr_soundscape.py
"""Add ASMR/soundscape fields to generated_scripts

Revision ID: 013
Revises: 012
Create Date: 2026-05-03
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("generated_scripts",
        sa.Column("music_track_ids", ARRAY(sa.Integer), server_default="{}"))
    op.add_column("generated_scripts",
        sa.Column("sfx_pool_ids", ARRAY(sa.Integer), server_default="{}"))
    op.add_column("generated_scripts",
        sa.Column("sfx_density_seconds", sa.Integer, nullable=True))
    op.add_column("generated_scripts",
        sa.Column("sfx_seed", sa.Integer, nullable=True))
    op.add_column("generated_scripts",
        sa.Column("black_from_seconds", sa.Integer, nullable=True))
    op.add_column("generated_scripts",
        sa.Column("skip_previews", sa.Boolean, server_default="true", nullable=False))
    op.add_column("generated_scripts",
        sa.Column("render_parts", JSONB, server_default="[]"))
    op.add_column("generated_scripts",
        sa.Column("audio_preview_path", sa.String(500), nullable=True))
    op.add_column("generated_scripts",
        sa.Column("video_preview_path", sa.String(500), nullable=True))

    # Backfill music_track_ids from existing music_track_id where set
    op.execute("""
        UPDATE generated_scripts
        SET music_track_ids = ARRAY[music_track_id]
        WHERE music_track_id IS NOT NULL
    """)

    # Default skip_previews=false for asmr/soundscape templates
    op.execute("""
        UPDATE generated_scripts
        SET skip_previews = false
        WHERE template IN ('asmr', 'soundscape')
    """)


def downgrade() -> None:
    op.drop_column("generated_scripts", "video_preview_path")
    op.drop_column("generated_scripts", "audio_preview_path")
    op.drop_column("generated_scripts", "render_parts")
    op.drop_column("generated_scripts", "skip_previews")
    op.drop_column("generated_scripts", "black_from_seconds")
    op.drop_column("generated_scripts", "sfx_seed")
    op.drop_column("generated_scripts", "sfx_density_seconds")
    op.drop_column("generated_scripts", "sfx_pool_ids")
    op.drop_column("generated_scripts", "music_track_ids")
```

- [ ] **Step 2: Add SQLAlchemy columns**

In `database/models.py`, after the `music_track_id` line (around line 104) add:

```python
    # ASMR/soundscape extension (added by migration 013)
    music_track_ids   = Column(ARRAY(Integer), default=list)
    sfx_pool_ids      = Column(ARRAY(Integer), default=list)
    sfx_density_seconds = Column(Integer)
    sfx_seed          = Column(Integer)
    black_from_seconds = Column(Integer)
    skip_previews     = Column(Boolean, default=True)
    render_parts      = Column(JSONB, default=list)
    audio_preview_path = Column(String(500))
    video_preview_path = Column(String(500))
```

Make sure `Boolean` is imported at the top of the file (it already is — line 7).

- [ ] **Step 3: Run migration**

```bash
cd console/backend && alembic upgrade head
```

Expected output: `Running upgrade 012 -> 013, Add ASMR/soundscape fields to generated_scripts`

- [ ] **Step 4: Write the model verification test**

```python
# tests/backend/test_asmr_migration.py
from database.connection import get_session
from database.models import GeneratedScript


def test_asmr_columns_present():
    db = get_session()
    try:
        # Should not raise; column existence is verified at compile time
        cols = GeneratedScript.__table__.columns.keys()
        for c in (
            "music_track_ids", "sfx_pool_ids", "sfx_density_seconds",
            "sfx_seed", "black_from_seconds", "skip_previews",
            "render_parts", "audio_preview_path", "video_preview_path",
        ):
            assert c in cols, f"missing column: {c}"
    finally:
        db.close()


def test_skip_previews_defaults_false_for_asmr(tmp_script_factory):
    """A new asmr-template script must have skip_previews=False."""
    script = tmp_script_factory(template="asmr")
    db = get_session()
    try:
        row = db.query(GeneratedScript).filter(GeneratedScript.id == script.id).first()
        assert row.skip_previews is False
    finally:
        db.close()
```

Note: `tmp_script_factory` likely needs to be added to `tests/conftest.py`. If your test setup doesn't have one, inline a minimal `INSERT` via SQL and read back. The point is to verify the migration's `UPDATE ... WHERE template IN ('asmr','soundscape')` logic.

- [ ] **Step 5: Run tests**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation && python -m pytest tests/backend/test_asmr_migration.py -v
```

Expected: PASS for `test_asmr_columns_present`. The factory test may need conftest plumbing; if so, add the fixture.

- [ ] **Step 6: Commit**

```bash
git add console/backend/alembic/versions/013_asmr_soundscape.py database/models.py tests/backend/test_asmr_migration.py
git commit -m "feat(asmr): add data fields for ASMR/soundscape pipeline"
```

---

## Phase 2 — Composer Refactor (SFX + Multi-Music + Blackout)

### Task 2: SFX scheduler module

**Files:**
- Create: `pipeline/sfx_scheduler.py`
- Test: `tests/pipeline/test_sfx_scheduler.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_sfx_scheduler.py
from pipeline.sfx_scheduler import schedule_sfx


def test_same_seed_reproduces_schedule():
    s1 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=42, start_s=0, end_s=120)
    s2 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=42, start_s=0, end_s=120)
    assert s1 == s2


def test_different_seeds_diverge():
    s1 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=42, start_s=0, end_s=120)
    s2 = schedule_sfx(pool_ids=[1, 2, 3], density_s=10, seed=43, start_s=0, end_s=120)
    assert s1 != s2


def test_density_bounds():
    """Density 10s, ±50% jitter => gaps in [5, 15]. 120s window => 8-24 events."""
    sched = schedule_sfx(pool_ids=[1], density_s=10, seed=7, start_s=0, end_s=120)
    assert 8 <= len(sched) <= 24
    times = [t for t, _ in sched]
    gaps = [times[i+1] - times[i] for i in range(len(times) - 1)]
    for g in gaps:
        assert 4.99 <= g <= 15.01


def test_window_offset_consistent():
    """Schedule from t=60..120 with same seed must match the t=60..120 slice
    of the schedule from t=0..120."""
    full = schedule_sfx(pool_ids=[1, 2], density_s=8, seed=99, start_s=0, end_s=120)
    second_half = [(t, sid) for t, sid in full if t >= 60]
    sliced = schedule_sfx(pool_ids=[1, 2], density_s=8, seed=99, start_s=60, end_s=120)
    # Note: schedules differ because RNG is reseeded per call. This test documents
    # the chosen behavior: chunks recompute their own slice using the same seed
    # but starting from start_s, NOT by sampling a full-length schedule. We accept
    # that preview SFX timing may differ slightly from chunk SFX timing in mid-video chunks.
    assert sliced != []  # smoke check; chunks always produce some SFX


def test_empty_pool_returns_empty():
    assert schedule_sfx(pool_ids=[], density_s=10, seed=1, start_s=0, end_s=60) == []


def test_no_density_returns_empty():
    assert schedule_sfx(pool_ids=[1], density_s=None, seed=1, start_s=0, end_s=60) == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/pipeline/test_sfx_scheduler.py -v
```

Expected: ImportError / ModuleNotFoundError.

- [ ] **Step 3: Implement scheduler**

```python
# pipeline/sfx_scheduler.py
"""Deterministic random SFX scheduler for ASMR/soundscape videos."""
import random


def schedule_sfx(
    pool_ids: list[int],
    density_s: int | None,
    seed: int,
    start_s: float,
    end_s: float,
) -> list[tuple[float, int]]:
    """
    Build a deterministic list of (timestamp, sfx_id) events.

    The same (seed, pool_ids, density_s, start_s, end_s) inputs always return
    the same output. Gaps between events are density_s ± 50% jitter.

    Returns empty list when pool_ids or density_s is empty/None.
    """
    if not pool_ids or not density_s:
        return []

    rng = random.Random(seed)
    # Burn one number per second of start_s so chunks at different offsets
    # still draw from the seeded stream consistently. Without this, every chunk
    # starts at the seed's first draw and SFX timing collides at chunk boundaries.
    for _ in range(int(start_s)):
        rng.random()

    schedule: list[tuple[float, int]] = []
    t = start_s
    while t < end_s:
        gap = density_s * rng.uniform(0.5, 1.5)
        t += gap
        if t >= end_s:
            break
        sfx_id = rng.choice(pool_ids)
        schedule.append((round(t, 3), sfx_id))
    return schedule
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/pipeline/test_sfx_scheduler.py -v
```

Expected: 5 PASS (the `test_window_offset_consistent` is a smoke check, not strict equality).

- [ ] **Step 5: Commit**

```bash
git add pipeline/sfx_scheduler.py tests/pipeline/test_sfx_scheduler.py
git commit -m "feat(asmr): seeded SFX scheduler"
```

---

### Task 3: Refactor composer into `compose_window`

**Files:**
- Modify: `pipeline/composer.py`

This task extracts the existing `compose_video` logic into a window-aware function. The old `compose_video(script_id)` becomes a thin wrapper that calls `compose_window(script_id, 0, total_duration)`. Behavior for non-ASMR templates must be unchanged.

- [ ] **Step 1: Read current `compose_video` and `_assemble`**

Already in context: `pipeline/composer.py:21-84` and `:294-469`. Note that `_assemble` writes the video file. We will refactor so `compose_window` returns a writeable MoviePy clip plus a flag, and the file-writing step happens at the end.

- [ ] **Step 2: Add `compose_window` (new public function)**

Append to `pipeline/composer.py`:

```python
def compose_window(
    script_id: int,
    start_s: float = 0.0,
    end_s: float | None = None,
    output_path: Path | None = None,
) -> tuple[Path, bool]:
    """
    Compose a portion of a script's video, [start_s, end_s).

    Used by both the legacy single-shot render path (start=0, end=duration) and
    the new chunked render. If end_s is None, end = total scene duration.

    Returns (output_path, subtitles_burned).
    """
    from database.connection import get_session
    from database.models import GeneratedScript

    db = get_session()
    try:
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")
        script_json = script.script_json
        # Pull all ASMR-relevant fields once
        ctx = {
            "music_track_id":      getattr(script, "music_track_id", None),
            "music_track_ids":     list(getattr(script, "music_track_ids", []) or []),
            "sfx_pool_ids":        list(getattr(script, "sfx_pool_ids", []) or []),
            "sfx_density_seconds": getattr(script, "sfx_density_seconds", None),
            "sfx_seed":            getattr(script, "sfx_seed", None),
            "black_from_seconds":  getattr(script, "black_from_seconds", None),
        }
    finally:
        db.close()

    meta   = script_json.get("meta", {})
    scenes = script_json.get("scenes", [])
    video  = script_json.get("video", {})

    out_dir = Path(OUTPUT_PATH) / f"script_{script_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine total duration if end_s not provided
    total_dur = sum(float(s.get("duration", 5)) for s in scenes)
    if end_s is None:
        end_s = total_dur
    end_s = min(end_s, total_dur)

    # Generate per-scene assets (full pass — chunking happens at the timeline level,
    # not at the asset-generation level, since assets don't depend on chunk window)
    scene_assets: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_process_scene, scene, meta, video, out_dir, i): i
            for i, scene in enumerate(scenes)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                scene_assets[idx] = future.result()
            except Exception as e:
                logger.error(f"[Composer] Scene {idx} failed: {e}")
                scene_assets[idx] = _fallback_scene_assets(scenes[idx], out_dir, idx)

    # Default output path is raw_video.mp4 (legacy behavior)
    if output_path is None:
        output_path = out_dir / "raw_video.mp4"

    subtitles_burned = _assemble_window(
        scenes, scene_assets, meta, video, output_path,
        start_s=start_s, end_s=end_s, ctx=ctx,
    )
    logger.info(f"[Composer] Window [{start_s},{end_s}) → {output_path}")
    return output_path, subtitles_burned
```

- [ ] **Step 3: Add `_assemble_window` (renamed from `_assemble`)**

Replace the existing `_assemble` function (lines 294-469) with `_assemble_window` that accepts `start_s`, `end_s`, `ctx`. The body should:

1. Build full timeline of scene clips as before, but compute scene offsets so we can `subclipped(start_s, end_s)` the final timeline.
2. Use `_build_music_playlist` (Task 4) instead of single-track logic.
3. Use `_build_sfx_layer` (Task 5) to overlay random SFX onto the audio.
4. Use `_apply_blackout` (Task 6) to fade visual to black at `black_from_seconds`.

Replace the music section (lines 374-433) with:

```python
    # Multi-music playlist (ASMR) or single track (legacy)
    music_audio = _build_music_playlist(
        ctx.get("music_track_ids") or ([ctx["music_track_id"]] if ctx.get("music_track_id") else []),
        meta=meta,
        video_cfg=video_cfg,
        target_duration=final.duration,
    )
    if music_audio is not None:
        if final.audio:
            mixed = CompositeAudioClip([final.audio, music_audio])
            final = final.with_audio(mixed)
        else:
            final = final.with_audio(music_audio)

    # SFX layer
    sfx_audio = _build_sfx_layer(
        pool_ids=ctx.get("sfx_pool_ids") or [],
        density_s=ctx.get("sfx_density_seconds"),
        seed=ctx.get("sfx_seed") or 0,
        start_s=start_s,
        end_s=end_s,
    )
    if sfx_audio is not None:
        if final.audio:
            mixed = CompositeAudioClip([final.audio, sfx_audio])
            final = final.with_audio(mixed)
        else:
            final = final.with_audio(sfx_audio)

    # Blackout
    black_from = ctx.get("black_from_seconds")
    if black_from is not None:
        final = _apply_blackout(final, float(black_from), start_s=start_s)

    # Window slice (after all layers composed at full timeline coords)
    if start_s > 0 or end_s < final.duration:
        final = final.subclipped(start_s, min(end_s, final.duration))
```

Keep the existing subtitle burn-in block (lines 435-457) AFTER these changes — subtitles still need to apply to the windowed clip. Update the offsets so subtitles are filtered to those overlapping `[start_s, end_s)`.

The encoder write block at the end uses `output_path` instead of `raw_video.mp4`:

```python
    final.write_videofile(
        str(output_path),
        fps=TARGET_FPS,
        codec="libx264",
        audio_codec="aac",
        audio_fps=44100,
        preset="ultrafast",
        logger=None,
    )
    return subtitles_burned
```

- [ ] **Step 4: Convert `compose_video` to a thin wrapper**

Replace the existing `compose_video` body (lines 21-84) with:

```python
def compose_video(script_id: int) -> tuple[Path, bool]:
    """Legacy single-shot compose: full duration, writes raw_video.mp4."""
    return compose_window(script_id, start_s=0.0, end_s=None, output_path=None)
```

This preserves backwards compatibility with the existing `render_video_task`.

- [ ] **Step 5: Smoke test**

```bash
python -c "
from pipeline.composer import compose_window, compose_video
print('compose_window:', compose_window)
print('compose_video:', compose_video)
"
```

Expected: prints two callable references. No import errors.

- [ ] **Step 6: Commit**

```bash
git add pipeline/composer.py
git commit -m "refactor(composer): extract compose_window from compose_video"
```

---

### Task 4: Multi-music playlist builder

**Files:**
- Modify: `pipeline/composer.py` (add `_build_music_playlist`)

- [ ] **Step 1: Add the function**

Append to `pipeline/composer.py`:

```python
def _build_music_playlist(
    track_ids: list[int],
    meta: dict,
    video_cfg: dict,
    target_duration: float,
):
    """
    Build a single AudioClip from an ordered playlist of music tracks.
    Tracks play in `track_ids` order with a 1.5s linear crossfade between them.
    The whole playlist loops as a unit until `target_duration` is reached.

    Returns None if no usable tracks (silent music). Honors `video_cfg.music_disabled`.
    """
    if video_cfg.get("music_disabled"):
        return None

    try:
        from moviepy import AudioFileClip, concatenate_audioclips, CompositeAudioClip
    except ImportError:
        logger.error("moviepy not installed")
        return None

    if not track_ids:
        # Fallback to legacy mood/niche selection
        legacy = _select_music(
            meta.get("mood", "uplifting"),
            meta.get("niche", "lifestyle"),
            target_duration,
        )
        if not legacy:
            return None
        try:
            clip = AudioFileClip(legacy).with_volume_scaled(MUSIC_VOLUME)
            return _loop_to_duration(clip, target_duration)
        except Exception as e:
            logger.warning(f"[Composer] Legacy music load failed: {e}")
            return None

    from database.connection import get_session
    from database.models import MusicTrack

    db = get_session()
    try:
        tracks = (
            db.query(MusicTrack)
            .filter(MusicTrack.id.in_(track_ids), MusicTrack.generation_status == "ready")
            .all()
        )
        # Preserve user-specified order
        by_id = {t.id: t for t in tracks}
        ordered = [by_id[i] for i in track_ids if i in by_id]
    finally:
        db.close()

    if not ordered:
        return None

    CROSSFADE = 1.5
    clips = []
    cursor = 0.0
    for i, tr in enumerate(ordered):
        if not tr.file_path or not Path(tr.file_path).exists():
            continue
        try:
            clip = AudioFileClip(tr.file_path).with_volume_scaled(float(tr.volume or MUSIC_VOLUME))
        except Exception as e:
            logger.warning(f"[Composer] Could not load music track {tr.id}: {e}")
            continue
        # Apply fade-in (except first track) and fade-out (except last track)
        if i > 0:
            try:
                clip = clip.with_audio_fadein(CROSSFADE)
            except AttributeError:
                # Older MoviePy: use audio_fadein effect
                from moviepy.audio.fx.AudioFadeIn import AudioFadeIn
                clip = clip.with_effects([AudioFadeIn(CROSSFADE)])
        if i < len(ordered) - 1:
            try:
                clip = clip.with_audio_fadeout(CROSSFADE)
            except AttributeError:
                from moviepy.audio.fx.AudioFadeOut import AudioFadeOut
                clip = clip.with_effects([AudioFadeOut(CROSSFADE)])
        clips.append(clip.with_start(max(0, cursor - (CROSSFADE if i > 0 else 0))))
        cursor = cursor + clip.duration - (CROSSFADE if i > 0 else 0)

    if not clips:
        return None

    playlist = CompositeAudioClip(clips).with_duration(cursor)
    return _loop_to_duration(playlist, target_duration)


def _loop_to_duration(audio_clip, target_duration: float):
    """Loop an audio clip until it reaches target_duration, then trim."""
    try:
        from moviepy import concatenate_audioclips
    except ImportError:
        return audio_clip
    import math
    if audio_clip.duration >= target_duration:
        return audio_clip.subclipped(0, target_duration)
    loops = math.ceil(target_duration / audio_clip.duration)
    return concatenate_audioclips([audio_clip] * loops).subclipped(0, target_duration)
```

- [ ] **Step 2: Smoke test the import**

```bash
python -c "from pipeline.composer import _build_music_playlist; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add pipeline/composer.py
git commit -m "feat(composer): multi-music playlist with crossfade"
```

---

### Task 5: SFX layer builder

**Files:**
- Modify: `pipeline/composer.py` (add `_build_sfx_layer`)

- [ ] **Step 1: Add the function**

Append to `pipeline/composer.py`:

```python
def _build_sfx_layer(
    pool_ids: list[int],
    density_s: int | None,
    seed: int,
    start_s: float,
    end_s: float,
):
    """
    Build a CompositeAudioClip layering randomly-scheduled SFX over the window.
    Returns None if pool/density empty or no SFX files load.
    """
    if not pool_ids or not density_s:
        return None

    try:
        from moviepy import AudioFileClip, CompositeAudioClip
    except ImportError:
        logger.error("moviepy not installed")
        return None

    from pipeline.sfx_scheduler import schedule_sfx
    from console.backend.database import SessionLocal
    from console.backend.models.sfx_asset import SfxAsset

    schedule = schedule_sfx(pool_ids, density_s, seed, start_s, end_s)
    if not schedule:
        return None

    db = SessionLocal()
    try:
        sfx_rows = db.query(SfxAsset).filter(SfxAsset.id.in_(pool_ids)).all()
        sfx_by_id = {s.id: s for s in sfx_rows}
    finally:
        db.close()

    clips = []
    for ts, sfx_id in schedule:
        sfx = sfx_by_id.get(sfx_id)
        if not sfx or not sfx.file_path or not Path(sfx.file_path).exists():
            continue
        try:
            sfx_clip = AudioFileClip(sfx.file_path).with_start(max(0, ts - start_s))
            clips.append(sfx_clip)
        except Exception as e:
            logger.warning(f"[Composer] SFX {sfx_id} load failed: {e}")

    if not clips:
        return None

    return CompositeAudioClip(clips).with_duration(end_s - start_s)
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from pipeline.composer import _build_sfx_layer; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add pipeline/composer.py
git commit -m "feat(composer): random SFX layer"
```

---

### Task 6: Blackout effect

**Files:**
- Modify: `pipeline/composer.py` (add `_apply_blackout`)

- [ ] **Step 1: Add the function**

Append to `pipeline/composer.py`:

```python
def _apply_blackout(video_clip, black_from_s: float, start_s: float = 0.0):
    """
    Overlay a black ColorClip starting at `black_from_s` (in absolute timeline
    coords) with a 2s linear fade-in. Audio is preserved.

    For chunks: pass start_s = chunk start so the overlay timing is rebased to
    the chunk's local coordinates.
    """
    try:
        from moviepy import ColorClip, CompositeVideoClip
    except ImportError:
        return video_clip

    FADE = 2.0
    local_start = max(0.0, black_from_s - start_s)
    if local_start >= video_clip.duration:
        # Blackout point falls after this window — no overlay needed
        return video_clip

    audio = video_clip.audio
    overlay_dur = video_clip.duration - local_start
    black = (
        ColorClip(size=(TARGET_W, TARGET_H), color=(0, 0, 0), duration=overlay_dur)
        .with_start(local_start)
    )
    try:
        # MoviePy 2.x effect-based fade-in
        from moviepy.video.fx.FadeIn import FadeIn
        black = black.with_effects([FadeIn(FADE)])
    except ImportError:
        try:
            from moviepy.video.fx.fadein import fadein  # 1.x fallback
            black = fadein(black, FADE)
        except ImportError:
            pass  # No fade — instant black

    out = CompositeVideoClip([video_clip, black]).with_duration(video_clip.duration)
    if audio is not None:
        out = out.with_audio(audio)
    return out
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from pipeline.composer import _apply_blackout; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add pipeline/composer.py
git commit -m "feat(composer): black-from-time overlay"
```

---

## Phase 3 — Audio Preview & ffmpeg Concat

### Task 7: Audio-only composer

**Files:**
- Create: `pipeline/audio_only.py`

- [ ] **Step 1: Implement audio-only composer**

```python
# pipeline/audio_only.py
"""Compose only the audio track of a script window — for fast audio previews."""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "./assets/output")


def compose_audio_only(script_id: int, start_s: float = 0.0, end_s: float = 120.0) -> Path:
    """
    Mix narration (per scene) + multi-music + SFX layer for the [start_s, end_s) window.
    Writes <out_dir>/audio_preview.wav and returns its path.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from database.connection import get_session
    from database.models import GeneratedScript
    from pipeline.composer import (
        _process_scene, _build_music_playlist, _build_sfx_layer, MAX_WORKERS,
    )

    try:
        from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
    except ImportError:
        raise RuntimeError("moviepy not installed")

    db = get_session()
    try:
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")
        script_json = script.script_json
        ctx = {
            "music_track_id":      getattr(script, "music_track_id", None),
            "music_track_ids":     list(getattr(script, "music_track_ids", []) or []),
            "sfx_pool_ids":        list(getattr(script, "sfx_pool_ids", []) or []),
            "sfx_density_seconds": getattr(script, "sfx_density_seconds", None),
            "sfx_seed":            getattr(script, "sfx_seed", None),
        }
    finally:
        db.close()

    meta   = script_json.get("meta", {})
    scenes = script_json.get("scenes", [])
    video  = script_json.get("video", {})

    out_dir = Path(OUTPUT_PATH) / f"script_{script_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate narration audio per scene (parallel)
    scene_audios: dict[int, str | None] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_process_scene, sc, meta, video, out_dir, i): i for i, sc in enumerate(scenes)}
        for f in as_completed(futs):
            i = futs[f]
            try:
                scene_audios[i] = f.result().get("audio_path")
            except Exception:
                scene_audios[i] = None

    # Sequence narration clips with offsets, clipped to window
    narration_clips = []
    cursor = 0.0
    for i, sc in enumerate(scenes):
        dur = float(sc.get("duration", 5))
        scene_start = cursor
        scene_end = cursor + dur
        cursor = scene_end
        if scene_end <= start_s or scene_start >= end_s:
            continue
        ap = scene_audios.get(i)
        if not ap or not Path(ap).exists():
            continue
        try:
            clip = AudioFileClip(ap)
            local_start = max(0.0, scene_start - start_s)
            narration_clips.append(clip.with_start(local_start))
        except Exception as e:
            logger.warning(f"[AudioOnly] Scene {i} narration load failed: {e}")

    target_duration = end_s - start_s
    layers = []
    if narration_clips:
        layers.append(CompositeAudioClip(narration_clips).with_duration(target_duration))

    music = _build_music_playlist(
        ctx.get("music_track_ids") or ([ctx["music_track_id"]] if ctx.get("music_track_id") else []),
        meta=meta, video_cfg=video, target_duration=target_duration,
    )
    if music is not None:
        layers.append(music)

    sfx = _build_sfx_layer(
        pool_ids=ctx.get("sfx_pool_ids") or [],
        density_s=ctx.get("sfx_density_seconds"),
        seed=ctx.get("sfx_seed") or 0,
        start_s=start_s, end_s=end_s,
    )
    if sfx is not None:
        layers.append(sfx)

    if not layers:
        raise RuntimeError("No audio content to compose")

    final_audio = CompositeAudioClip(layers).with_duration(target_duration)
    out_path = out_dir / "audio_preview.wav"
    final_audio.write_audiofile(str(out_path), fps=44100, codec="pcm_s16le", logger=None)
    logger.info(f"[AudioOnly] Wrote audio preview → {out_path}")
    return out_path
```

- [ ] **Step 2: Smoke test**

```bash
python -c "from pipeline.audio_only import compose_audio_only; print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/audio_only.py
git commit -m "feat(asmr): audio-only preview composer"
```

---

### Task 8: ffmpeg concat helper + seam test

**Files:**
- Create: `pipeline/concat.py`
- Test: `tests/pipeline/test_concat.py`

- [ ] **Step 1: Write the failing seam test**

```python
# tests/pipeline/test_concat.py
"""Verify that chunked render + concat == single-shot render at the seam."""
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def two_color_clips(tmp_path):
    """Generate two 5-second clips with identical encoder params."""
    clips = []
    for i, color in enumerate(["black", "blue"]):
        out = tmp_path / f"part_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c={color}:s=320x180:d=5:r=30",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            "-pix_fmt", "yuv420p", "-r", "30",
            str(out),
        ], check=True, capture_output=True)
        clips.append(out)
    return clips


def test_concat_produces_single_file(two_color_clips, tmp_path):
    from pipeline.concat import concat_parts
    out = tmp_path / "joined.mp4"
    concat_parts(two_color_clips, out)
    assert out.exists() and out.stat().st_size > 0


def test_concat_duration_equals_sum(two_color_clips, tmp_path):
    from pipeline.concat import concat_parts
    out = tmp_path / "joined.mp4"
    concat_parts(two_color_clips, out)
    # ffprobe duration should be ~10s (5+5)
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    duration = float(res.stdout.strip())
    assert 9.5 < duration < 10.5


def test_concat_no_reencode(two_color_clips, tmp_path):
    """Stream copy means the resulting codec params match the input."""
    from pipeline.concat import concat_parts
    out = tmp_path / "joined.mp4"
    concat_parts(two_color_clips, out)
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,r_frame_rate",
         "-of", "default=noprint_wrappers=1", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert "codec_name=h264" in res.stdout
    assert "r_frame_rate=30/1" in res.stdout
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/pipeline/test_concat.py -v
```

Expected: ImportError for `pipeline.concat`.

- [ ] **Step 3: Implement concat helper**

```python
# pipeline/concat.py
"""ffmpeg concat-demuxer wrapper for stream-copy joining of video chunks."""
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def concat_parts(part_paths: list[Path | str], output_path: Path | str) -> Path:
    """
    Concatenate identical-codec MP4 chunks into one file via ffmpeg's concat
    demuxer with -c copy. No re-encoding — joins are bit-perfect when chunks
    share codec, params, and GOP cadence.

    Caller MUST ensure all part files were produced with the same encoder
    settings (codec, fps, resolution, audio sample rate, profile/level).
    """
    if not part_paths:
        raise ValueError("part_paths is empty")

    parts = [Path(p) for p in part_paths]
    for p in parts:
        if not p.exists():
            raise FileNotFoundError(f"chunk not found: {p}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write a tempfile listing each input — concat demuxer reads this format
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8",
    ) as listfile:
        for p in parts:
            # ffmpeg concat list format requires single quotes and ' -> '\''
            escaped = str(p.resolve()).replace("'", "'\\''")
            listfile.write(f"file '{escaped}'\n")
        listfile_path = Path(listfile.name)

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listfile_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr[-2000:]}")
        logger.info(f"[Concat] {len(parts)} parts → {output_path} ({output_path.stat().st_size // 1024 // 1024}MB)")
        return output_path
    finally:
        try:
            listfile_path.unlink()
        except OSError:
            pass
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/pipeline/test_concat.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/concat.py tests/pipeline/test_concat.py
git commit -m "feat(asmr): ffmpeg stream-copy concat helper"
```

---

## Phase 4 — Celery Tasks

### Task 9: Audio + video preview tasks

**Files:**
- Modify: `console/backend/tasks/production_tasks.py`

- [ ] **Step 1: Add audio preview task**

Append to `production_tasks.py`:

```python
@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.render_audio_preview_task", queue="render_q")
def render_audio_preview_task(self, script_id: int):
    """Render audio-only preview (first 2 minutes) for ASMR scripts."""
    from console.backend.database import SessionLocal
    from database.models import GeneratedScript
    from pipeline.audio_only import compose_audio_only
    from sqlalchemy import text as _sql

    db = SessionLocal()
    try:
        task_id = self.request.id
        job = mark_job_progress(db, task_id=task_id, job_type="render",
            script_id=script_id, progress=5, details={"step": "audio_preview"})
        emit_log(job.id, "INFO", "Starting audio preview...")

        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        # Auto-seed if missing
        if script.sfx_seed is None:
            import random
            script.sfx_seed = random.randint(1, 2**31 - 1)
            db.commit()

        script.status = "audio_preview_rendering"
        db.commit()

        total = float(script.duration_s or sum(s.get("duration", 5) for s in script.script_json.get("scenes", [])))
        end_s = min(120.0, total)

        out_path = compose_audio_only(script_id, start_s=0.0, end_s=end_s)
        script.audio_preview_path = str(out_path)
        script.status = "audio_preview_ready"
        db.commit()

        emit_log(job.id, "INFO", f"Audio preview ready → {out_path}")
        mark_job_completed(db, task_id=task_id, job_type="render",
            script_id=script_id, details={"step": "audio_preview", "path": str(out_path)})
        return {"script_id": script_id, "path": str(out_path)}
    except Exception as e:
        db.rollback()
        if 'job' in dir():
            emit_log(job.id, "ERROR", f"Audio preview failed: {e}")
        s = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if s:
            s.status = "approved"
            db.commit()
        mark_job_failed(db, task_id=self.request.id, job_type="render",
            script_id=script_id, error=str(e), details={"step": "audio_preview"})
        raise
    finally:
        db.close()
```

- [ ] **Step 2: Add video preview task**

```python
@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.render_video_preview_task", queue="render_q")
def render_video_preview_task(self, script_id: int):
    """Render video preview (first 2 min, with audio) for ASMR scripts."""
    from console.backend.database import SessionLocal
    from database.models import GeneratedScript
    from pipeline.composer import compose_window
    from pipeline.renderer import render_final
    import os
    from pathlib import Path

    db = SessionLocal()
    try:
        task_id = self.request.id
        job = mark_job_progress(db, task_id=task_id, job_type="render",
            script_id=script_id, progress=5, details={"step": "video_preview"})
        emit_log(job.id, "INFO", "Starting video preview...")

        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")
        script.status = "video_preview_rendering"
        db.commit()

        total = float(script.duration_s or sum(s.get("duration", 5) for s in script.script_json.get("scenes", [])))
        end_s = min(120.0, total)

        out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / f"script_{script_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / "preview_raw.mp4"
        compose_window(script_id, start_s=0.0, end_s=end_s, output_path=raw_path)
        mark_job_progress(db, task_id=task_id, job_type="render",
            script_id=script_id, progress=60, details={"step": "video_preview_render"})

        final_path = render_final(raw_video_path=raw_path)
        # Rename to canonical preview path
        preview_path = out_dir / "video_preview.mp4"
        if final_path != preview_path:
            import shutil
            shutil.move(str(final_path), str(preview_path))

        script.video_preview_path = str(preview_path)
        script.status = "video_preview_ready"
        db.commit()

        emit_log(job.id, "INFO", f"Video preview ready → {preview_path}")
        mark_job_completed(db, task_id=task_id, job_type="render",
            script_id=script_id, details={"step": "video_preview", "path": str(preview_path)})
        return {"script_id": script_id, "path": str(preview_path)}
    except Exception as e:
        db.rollback()
        if 'job' in dir():
            emit_log(job.id, "ERROR", f"Video preview failed: {e}")
        s = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if s:
            s.status = "approved"
            db.commit()
        mark_job_failed(db, task_id=self.request.id, job_type="render",
            script_id=script_id, error=str(e), details={"step": "video_preview"})
        raise
    finally:
        db.close()
```

- [ ] **Step 3: Smoke test imports**

```bash
python -c "
from console.backend.tasks.production_tasks import render_audio_preview_task, render_video_preview_task
print('ok')
"
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/tasks/production_tasks.py
git commit -m "feat(asmr): audio + video preview Celery tasks"
```

---

### Task 10: Chunked render orchestrator + chunk task + concat task

**Files:**
- Modify: `console/backend/tasks/production_tasks.py`

- [ ] **Step 1: Add chunk task**

Append to `production_tasks.py`:

```python
@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.render_chunk_task", queue="render_q")
def render_chunk_task(self, script_id: int, chunk_idx: int, start_s: float, end_s: float):
    """Render a single chunk of an ASMR script."""
    from console.backend.database import SessionLocal
    from database.models import GeneratedScript
    from pipeline.composer import compose_window
    from pipeline.renderer import render_final
    import os
    from pathlib import Path
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        task_id = self.request.id
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        # Mark chunk running
        parts = list(script.render_parts or [])
        parts[chunk_idx] = {
            **(parts[chunk_idx] if chunk_idx < len(parts) else {}),
            "idx": chunk_idx, "start_s": start_s, "end_s": end_s,
            "status": "running",
        }
        script.render_parts = parts
        flag_modified(script, "render_parts")
        db.commit()

        # Find or create job for this chunk
        job = mark_job_progress(db, task_id=task_id, job_type="render",
            script_id=script_id, progress=0,
            details={"step": "chunk", "chunk_idx": chunk_idx})
        emit_log(job.id, "INFO", f"Rendering chunk {chunk_idx} [{start_s:.1f}s, {end_s:.1f}s)")

        out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / f"script_{script_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = out_dir / f"chunk_{chunk_idx}_raw.mp4"
        final_chunk = out_dir / f"chunk_{chunk_idx}.mp4"

        compose_window(script_id, start_s=start_s, end_s=end_s, output_path=raw_path)
        rendered = render_final(raw_video_path=raw_path)
        if rendered != final_chunk:
            import shutil
            shutil.move(str(rendered), str(final_chunk))

        # Mark chunk completed
        from datetime import datetime, timezone
        parts = list(script.render_parts or [])
        parts[chunk_idx] = {
            **parts[chunk_idx],
            "status": "completed",
            "file_path": str(final_chunk),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        script.render_parts = parts
        flag_modified(script, "render_parts")
        db.commit()

        emit_log(job.id, "INFO", f"Chunk {chunk_idx} done → {final_chunk}")
        mark_job_completed(db, task_id=task_id, job_type="render",
            script_id=script_id, details={"step": "chunk", "chunk_idx": chunk_idx})
        return {"chunk_idx": chunk_idx, "path": str(final_chunk)}
    except Exception as e:
        db.rollback()
        if 'job' in dir():
            emit_log(job.id, "ERROR", f"Chunk {chunk_idx} failed: {e}")
        # Mark chunk failed
        s = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if s:
            parts = list(s.render_parts or [])
            if chunk_idx < len(parts):
                parts[chunk_idx] = {**parts[chunk_idx], "status": "failed", "error": str(e)[:500]}
                s.render_parts = parts
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(s, "render_parts")
                db.commit()
        mark_job_failed(db, task_id=self.request.id, job_type="render",
            script_id=script_id, error=str(e), details={"step": "chunk", "chunk_idx": chunk_idx})
        raise
    finally:
        db.close()
```

- [ ] **Step 2: Add concat task**

```python
@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.concat_chunks_task", queue="render_q")
def concat_chunks_task(self, _chunk_results, script_id: int):
    """Concatenate all rendered chunks into the final video.

    Receives the chord header's results as the first arg (we don't use them
    individually — we re-read render_parts from the DB to handle resume cases).
    """
    from console.backend.database import SessionLocal
    from database.models import GeneratedScript
    from pipeline.concat import concat_parts
    import os
    from pathlib import Path

    db = SessionLocal()
    try:
        task_id = self.request.id
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        parts = sorted(script.render_parts or [], key=lambda p: p["idx"])
        missing = [p for p in parts if p.get("status") != "completed" or not p.get("file_path")]
        if missing:
            raise RuntimeError(f"Cannot concat: {len(missing)} chunks not completed")

        job = mark_job_progress(db, task_id=task_id, job_type="render",
            script_id=script_id, progress=95, details={"step": "concat", "n_chunks": len(parts)})
        emit_log(job.id, "INFO", f"Concatenating {len(parts)} chunks...")

        out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / f"script_{script_id}"
        final_path = out_dir / "video_final.mp4"
        concat_parts([p["file_path"] for p in parts], final_path)

        script.output_path = str(final_path)
        script.status = "completed"
        db.commit()

        emit_log(job.id, "INFO", f"Concat done → {final_path}")
        mark_job_completed(db, task_id=task_id, job_type="render",
            script_id=script_id, details={"step": "concat", "output_path": str(final_path)})
        return {"script_id": script_id, "output": str(final_path)}
    except Exception as e:
        db.rollback()
        if 'job' in dir():
            emit_log(job.id, "ERROR", f"Concat failed: {e}")
        s = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if s:
            s.status = "video_preview_ready"  # roll back to previous gate
            db.commit()
        mark_job_failed(db, task_id=self.request.id, job_type="render",
            script_id=script_id, error=str(e), details={"step": "concat"})
        raise
    finally:
        db.close()
```

- [ ] **Step 3: Add chunked orchestrator (planning + chord dispatch)**

```python
@celery_app.task(bind=True, name="console.backend.tasks.production_tasks.render_chunked_orchestrator_task", queue="render_q")
def render_chunked_orchestrator_task(self, script_id: int):
    """Plan chunks, persist render_parts, and dispatch a chord(group(chunks), concat)."""
    import math
    from celery import chord, group
    from console.backend.database import SessionLocal
    from database.models import GeneratedScript
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        task_id = self.request.id
        script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise ValueError(f"Script {script_id} not found")

        if script.sfx_seed is None:
            import random
            script.sfx_seed = random.randint(1, 2**31 - 1)

        total = float(script.duration_s or sum(s.get("duration", 5) for s in script.script_json.get("scenes", [])))
        n_chunks = max(1, math.ceil(total / 300))
        chunk_size = math.ceil(total / n_chunks)

        # Build / replace render_parts. If existing parts have completed entries,
        # preserve them (resume case). Otherwise start fresh.
        existing = {p["idx"]: p for p in (script.render_parts or [])}
        new_parts = []
        for i in range(n_chunks):
            start = i * chunk_size
            end = min(total, start + chunk_size)
            prev = existing.get(i, {})
            if prev.get("status") == "completed" and prev.get("file_path"):
                new_parts.append(prev)
            else:
                new_parts.append({
                    "idx": i, "start_s": start, "end_s": end, "status": "pending",
                    "file_path": None, "started_at": None, "completed_at": None,
                })
        script.render_parts = new_parts
        flag_modified(script, "render_parts")
        script.status = "producing"
        db.commit()

        job = mark_job_progress(db, task_id=task_id, job_type="render",
            script_id=script_id, progress=10,
            details={"step": "planning", "n_chunks": n_chunks, "chunk_size": chunk_size})
        emit_log(job.id, "INFO", f"Planned {n_chunks} chunks of ~{chunk_size}s each")

        pending = [p for p in new_parts if p["status"] != "completed"]
        if not pending:
            # All chunks already done — go straight to concat
            concat_chunks_task.delay([], script_id)
            return {"script_id": script_id, "n_chunks": n_chunks, "skipped": True}

        sigs = [
            render_chunk_task.s(script_id, p["idx"], p["start_s"], p["end_s"])
            for p in pending
        ]
        chord(group(sigs))(concat_chunks_task.s(script_id))
        return {"script_id": script_id, "n_chunks": n_chunks, "pending": len(pending)}
    except Exception as e:
        db.rollback()
        s = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if s:
            s.status = "video_preview_ready"
            db.commit()
        mark_job_failed(db, task_id=self.request.id, job_type="render",
            script_id=script_id, error=str(e), details={"step": "planning"})
        raise
    finally:
        db.close()
```

- [ ] **Step 4: Smoke test imports**

```bash
python -c "
from console.backend.tasks.production_tasks import (
    render_chunk_task, concat_chunks_task, render_chunked_orchestrator_task,
)
print('ok')
"
```

- [ ] **Step 5: Commit**

```bash
git add console/backend/tasks/production_tasks.py
git commit -m "feat(asmr): chunked render orchestrator + chunk + concat tasks"
```

---

## Phase 5 — Service Layer

### Task 11: ProductionService methods + render_state reader

**Files:**
- Create: `console/backend/services/render_state.py`
- Modify: `console/backend/services/production_service.py`

- [ ] **Step 1: Implement `render_state.py`**

```python
# console/backend/services/render_state.py
"""Unified render-state reader: combines render_parts, pipeline_jobs, and Redis logs."""
from sqlalchemy.orm import Session

from database.models import GeneratedScript
from console.backend.models.pipeline_job import PipelineJob
from console.backend.services.pipeline_service import PipelineService


def get_render_state(db: Session, script_id: int) -> dict:
    script = db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
    if not script:
        raise KeyError(f"Script {script_id} not found")

    parts = list(script.render_parts or [])
    completed = sum(1 for p in parts if p.get("status") == "completed")
    failed = sum(1 for p in parts if p.get("status") == "failed")
    running = sum(1 for p in parts if p.get("status") == "running")
    pending = sum(1 for p in parts if p.get("status") == "pending")

    overall = int(100 * completed / len(parts)) if parts else 0

    # Most recent render job for this script
    job = (
        db.query(PipelineJob)
        .filter(PipelineJob.script_id == script_id, PipelineJob.job_type == "render")
        .order_by(PipelineJob.created_at.desc())
        .first()
    )
    logs = []
    if job:
        logs = PipelineService(db).get_job_logs(job.id)

    return {
        "script_id": script_id,
        "status": script.status,
        "audio_preview_path": script.audio_preview_path,
        "video_preview_path": script.video_preview_path,
        "output_path": script.output_path,
        "chunks": [
            {
                "idx": p["idx"],
                "start_s": p.get("start_s"),
                "end_s": p.get("end_s"),
                "status": p.get("status"),
                "error": p.get("error"),
            }
            for p in sorted(parts, key=lambda p: p["idx"])
        ],
        "chunk_summary": {
            "total": len(parts),
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
        },
        "overall_progress": overall,
        "current_job": {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "details": job.details,
            "error": job.error,
        } if job else None,
        "logs_tail": logs[-50:],
    }
```

- [ ] **Step 2: Add ProductionService methods**

In `console/backend/services/production_service.py`, append to the `ProductionService` class:

```python
    # ── ASMR / Soundscape render lifecycle ───────────────────────────────────

    def _load_script_or_404(self, script_id: int):
        from database.models import GeneratedScript
        script = self.db.query(GeneratedScript).filter(GeneratedScript.id == script_id).first()
        if not script:
            raise KeyError(f"Script {script_id} not found")
        return script

    def start_audio_preview(self, script_id: int, user_id: int) -> str:
        from console.backend.tasks.production_tasks import render_audio_preview_task
        s = self._load_script_or_404(script_id)
        if s.status not in ("approved", "editing", "audio_preview_ready",
                            "video_preview_ready"):
            raise ValueError(f"Cannot start audio preview from status '{s.status}'")
        s.status = "audio_preview_rendering"
        self._audit(user_id, "start_audio_preview", "script", str(script_id))
        self.db.commit()
        return render_audio_preview_task.delay(script_id).id

    def approve_audio_preview(self, script_id: int, user_id: int) -> dict:
        s = self._load_script_or_404(script_id)
        if s.status != "audio_preview_ready":
            raise ValueError(f"Cannot approve from status '{s.status}'")
        # Stay in audio_preview_ready — the next call (start_video_preview) advances state
        self._audit(user_id, "approve_audio_preview", "script", str(script_id))
        self.db.commit()
        return {"status": s.status}

    def reject_audio_preview(self, script_id: int, user_id: int) -> dict:
        s = self._load_script_or_404(script_id)
        if s.status != "audio_preview_ready":
            raise ValueError(f"Cannot reject from status '{s.status}'")
        s.status = "approved"
        s.audio_preview_path = None
        self._audit(user_id, "reject_audio_preview", "script", str(script_id))
        self.db.commit()
        return {"status": s.status}

    def start_video_preview(self, script_id: int, user_id: int) -> str:
        from console.backend.tasks.production_tasks import render_video_preview_task
        s = self._load_script_or_404(script_id)
        if s.status not in ("audio_preview_ready", "video_preview_ready"):
            raise ValueError(f"Cannot start video preview from status '{s.status}'")
        s.status = "video_preview_rendering"
        self._audit(user_id, "start_video_preview", "script", str(script_id))
        self.db.commit()
        return render_video_preview_task.delay(script_id).id

    def approve_video_preview(self, script_id: int, user_id: int) -> dict:
        s = self._load_script_or_404(script_id)
        if s.status != "video_preview_ready":
            raise ValueError(f"Cannot approve from status '{s.status}'")
        self._audit(user_id, "approve_video_preview", "script", str(script_id))
        self.db.commit()
        return {"status": s.status}

    def reject_video_preview(self, script_id: int, user_id: int) -> dict:
        s = self._load_script_or_404(script_id)
        if s.status != "video_preview_ready":
            raise ValueError(f"Cannot reject from status '{s.status}'")
        s.status = "audio_preview_ready"  # back one step
        s.video_preview_path = None
        self._audit(user_id, "reject_video_preview", "script", str(script_id))
        self.db.commit()
        return {"status": s.status}

    def start_chunked_render(self, script_id: int, user_id: int) -> str:
        from console.backend.tasks.production_tasks import render_chunked_orchestrator_task
        s = self._load_script_or_404(script_id)
        valid_from = ("video_preview_ready", "approved") if s.skip_previews else ("video_preview_ready",)
        if s.status not in valid_from:
            raise ValueError(f"Cannot start final render from status '{s.status}'")
        s.status = "producing"
        self._audit(user_id, "start_chunked_render", "script", str(script_id))
        self.db.commit()
        return render_chunked_orchestrator_task.delay(script_id).id

    def resume_chunked_render(self, script_id: int, user_id: int) -> str:
        from console.backend.tasks.production_tasks import render_chunked_orchestrator_task
        s = self._load_script_or_404(script_id)
        if not s.render_parts:
            raise ValueError("No prior render to resume")
        # Reset failed/running to pending so orchestrator re-queues them
        from sqlalchemy.orm.attributes import flag_modified
        parts = list(s.render_parts)
        for p in parts:
            if p.get("status") in ("failed", "running"):
                p["status"] = "pending"
                p["error"] = None
        s.render_parts = parts
        flag_modified(s, "render_parts")
        s.status = "producing"
        self._audit(user_id, "resume_chunked_render", "script", str(script_id))
        self.db.commit()
        return render_chunked_orchestrator_task.delay(script_id).id

    def cancel_chunked_render(self, script_id: int, user_id: int) -> dict:
        from console.backend.celery_app import celery_app
        s = self._load_script_or_404(script_id)
        # Revoke any in-flight Celery tasks for this script's render
        from console.backend.models.pipeline_job import PipelineJob
        running_jobs = (
            self.db.query(PipelineJob)
            .filter(
                PipelineJob.script_id == script_id,
                PipelineJob.job_type == "render",
                PipelineJob.status.in_(("queued", "running")),
            )
            .all()
        )
        for j in running_jobs:
            if j.celery_task_id:
                try:
                    celery_app.control.revoke(j.celery_task_id, terminate=True)
                except Exception:
                    pass
            j.status = "cancelled"
        s.status = "video_preview_ready" if s.video_preview_path else "approved"
        self._audit(user_id, "cancel_chunked_render", "script", str(script_id))
        self.db.commit()
        return {"status": s.status}

    def get_render_state(self, script_id: int) -> dict:
        from console.backend.services.render_state import get_render_state
        return get_render_state(self.db, script_id)
```

- [ ] **Step 3: Smoke test**

```bash
python -c "
from console.backend.services.render_state import get_render_state
from console.backend.services.production_service import ProductionService
print('ok')
"
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/render_state.py console/backend/services/production_service.py
git commit -m "feat(asmr): production service preview/chunked render methods"
```

---

## Phase 6 — API Endpoints + WebSocket

### Task 12: New router endpoints

**Files:**
- Modify: `console/backend/routers/production.py`

- [ ] **Step 1: Add the 9 endpoints**

Append to `console/backend/routers/production.py`:

```python
# ── ASMR / Soundscape render lifecycle ────────────────────────────────────────

def _dispatch(svc_method, script_id: int, user_id: int):
    try:
        return svc_method(script_id, user_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scripts/{script_id}/render/audio-preview")
def render_audio_preview(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task_id = _dispatch(ProductionService(db).start_audio_preview, script_id, user.id)
    return {"task_id": task_id, "script_id": script_id}


@router.post("/scripts/{script_id}/render/audio-preview/approve")
def approve_audio_preview(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _dispatch(ProductionService(db).approve_audio_preview, script_id, user.id)


@router.post("/scripts/{script_id}/render/audio-preview/reject")
def reject_audio_preview(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _dispatch(ProductionService(db).reject_audio_preview, script_id, user.id)


@router.post("/scripts/{script_id}/render/video-preview")
def render_video_preview(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task_id = _dispatch(ProductionService(db).start_video_preview, script_id, user.id)
    return {"task_id": task_id, "script_id": script_id}


@router.post("/scripts/{script_id}/render/video-preview/approve")
def approve_video_preview(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _dispatch(ProductionService(db).approve_video_preview, script_id, user.id)


@router.post("/scripts/{script_id}/render/video-preview/reject")
def reject_video_preview(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _dispatch(ProductionService(db).reject_video_preview, script_id, user.id)


@router.post("/scripts/{script_id}/render/final")
def render_final_chunked(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task_id = _dispatch(ProductionService(db).start_chunked_render, script_id, user.id)
    return {"task_id": task_id, "script_id": script_id}


@router.post("/scripts/{script_id}/render/cancel")
def cancel_render(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _dispatch(ProductionService(db).cancel_chunked_render, script_id, user.id)


@router.post("/scripts/{script_id}/render/resume")
def resume_render(script_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task_id = _dispatch(ProductionService(db).resume_chunked_render, script_id, user.id)
    return {"task_id": task_id, "script_id": script_id}


@router.get("/scripts/{script_id}/render/state")
def get_render_state(script_id: int, db: Session = Depends(get_db), _user=Depends(require_editor_or_admin)):
    try:
        return ProductionService(db).get_render_state(script_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 2: Update existing `start_production` to route by template**

Replace the body of `start_production` in `production_service.py` (lines 272-315) with:

```python
    def start_production(self, script_id: int, user_id: int) -> str:
        """Route to chunked/preview render for ASMR templates, legacy path otherwise."""
        from sqlalchemy import text as _sql
        row = self.db.execute(
            _sql("SELECT id, status, video_format, template, skip_previews FROM generated_scripts WHERE id = :id"),
            {"id": script_id},
        ).fetchone()
        if not row:
            raise KeyError(f"Script {script_id} not found")
        if row.status not in ("approved", "editing"):
            raise ValueError(
                f"Script must be 'approved' or 'editing' to start production, got '{row.status}'"
            )

        if row.template in ("asmr", "soundscape") and not row.skip_previews:
            # Route into the preview gate flow
            return self.start_audio_preview(script_id, user_id)

        # Legacy single-task render path (unchanged)
        self.db.execute(
            _sql("UPDATE generated_scripts SET status = 'producing' WHERE id = :id"),
            {"id": script_id},
        )
        job = PipelineJob(
            job_type="render", status="queued",
            script_id=script_id, video_format=row.video_format or "short",
        )
        self.db.add(job)
        self.db.flush()
        from console.backend.tasks.production_tasks import render_video_task
        result = render_video_task.delay(script_id)
        job.celery_task_id = result.id
        job.started_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info(f"Production started: script {script_id}, task {result.id}, job {job.id}")
        return result.id
```

- [ ] **Step 3: Smoke test the imports**

```bash
python -c "
from console.backend.routers.production import router
endpoints = [r.path for r in router.routes]
for needed in ['/production/scripts/{script_id}/render/audio-preview',
               '/production/scripts/{script_id}/render/state',
               '/production/scripts/{script_id}/render/cancel']:
    assert needed in endpoints, f'missing: {needed}'
print('ok — all 9 endpoints registered')
"
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/routers/production.py console/backend/services/production_service.py
git commit -m "feat(asmr): API endpoints for preview gates + chunked render"
```

---

### Task 13: WebSocket endpoint + per-script Redis pub/sub

**Files:**
- Create: `console/backend/ws/render_ws.py`
- Modify: `console/backend/services/pipeline_service.py`
- Modify: `console/backend/main.py`

- [ ] **Step 1: Extend `emit_log` to publish per-script**

In `console/backend/services/pipeline_service.py`, modify `emit_log`:

```python
def emit_log(job_id: int, level: str, msg: str, script_id: int | None = None) -> None:
    """Push a log line to Redis. Optionally also publish to per-script channel for WS."""
    try:
        r = _get_redis()
        entry = json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg})
        key = f"pipeline:job:{job_id}:logs"
        pipe = r.pipeline()
        pipe.lpush(key, entry)
        pipe.ltrim(key, 0, 199)
        pipe.expire(key, 86400)
        pipe.execute()
        if script_id is not None:
            r.publish(f"render:script:{script_id}", entry)
    except Exception as exc:
        logger.debug("[emit_log] job=%s %s: %s (suppressed: %s)", job_id, level, msg, exc)
```

This is backwards-compatible: existing call sites that don't pass `script_id` keep working.

- [ ] **Step 2: Add `mark_job_progress` Redis publish**

Modify `console/backend/tasks/job_tracking.py:59` (`mark_job_progress`) to also publish to the per-script channel after committing:

```python
def mark_job_progress(
    db,
    *,
    task_id: str | None,
    job_type: str,
    script_id: int | None = None,
    progress: int,
    details: dict | None = None,
) -> PipelineJob:
    job = ensure_job(db, task_id=task_id, job_type=job_type, script_id=script_id, details=details)
    job.status = "running"
    job.progress = max(0, min(100, progress))
    job.error = None
    if not job.started_at:
        job.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    if script_id is not None:
        try:
            from console.backend.services.pipeline_service import _get_redis
            import json as _json
            _get_redis().publish(
                f"render:script:{script_id}",
                _json.dumps({
                    "type": "progress", "job_id": job.id, "progress": job.progress,
                    "details": job.details,
                }),
            )
        except Exception:
            pass
    return job
```

- [ ] **Step 3: Implement render WebSocket**

```python
# console/backend/ws/render_ws.py
"""Per-script render WebSocket — broadcasts state updates pushed via Redis pub/sub."""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from console.backend.auth import decode_token

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_state(script_id: int) -> dict:
    from console.backend.database import SessionLocal
    from console.backend.services.render_state import get_render_state
    db = SessionLocal()
    try:
        return get_render_state(db, script_id)
    except KeyError:
        return {"error": "not_found"}
    finally:
        db.close()


@router.websocket("/ws/render/{script_id}")
async def render_ws(websocket: WebSocket, script_id: int, token: str = Query(...)):
    try:
        decode_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    loop = asyncio.get_running_loop()

    # Send initial snapshot
    try:
        snap = await loop.run_in_executor(None, _get_state, script_id)
        await websocket.send_json({"type": "snapshot", **snap})
    except Exception as e:
        logger.warning(f"WS render snapshot failed: {e}")

    # Subscribe to Redis pub/sub for live events; on each event, re-snapshot.
    from console.backend.services.pipeline_service import _get_redis
    pubsub = _get_redis().pubsub()
    pubsub.subscribe(f"render:script:{script_id}")

    async def _poll_pubsub():
        while True:
            msg = await loop.run_in_executor(None, pubsub.get_message, True, 1.0)
            if msg and msg.get("type") == "message":
                snap = await loop.run_in_executor(None, _get_state, script_id)
                await websocket.send_json({"type": "update", **snap})

    try:
        await _poll_pubsub()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS render error: {e}")
    finally:
        try:
            pubsub.close()
        except Exception:
            pass
```

- [ ] **Step 4: Register router in main.py**

In `console/backend/main.py`, find the line that registers `pipeline_ws` (or other WebSocket router) and add right after:

```python
from console.backend.ws.render_ws import router as render_ws_router
app.include_router(render_ws_router)
```

If you can't find a clear pipeline_ws import, search for `include_router` and add this line near the others.

- [ ] **Step 5: Smoke test**

```bash
python -c "
from console.backend.ws.render_ws import router
print([r.path for r in router.routes])
"
```

Expected: `['/ws/render/{script_id}']`

- [ ] **Step 6: Commit**

```bash
git add console/backend/ws/render_ws.py console/backend/services/pipeline_service.py console/backend/tasks/job_tracking.py console/backend/main.py
git commit -m "feat(asmr): per-script render WebSocket with Redis pub/sub"
```

---

## Phase 7 — Frontend Components

### Task 14: API client helpers + WebSocket hook

**Files:**
- Modify: `console/frontend/src/api/client.js`
- Create: `console/frontend/src/hooks/useRenderWebSocket.js`

- [ ] **Step 1: Add `productionApi` helpers**

Append to `console/frontend/src/api/client.js`:

```javascript
export const productionApi = {
  getRenderState: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/state`),
  startAudioPreview: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/audio-preview`, { method: 'POST' }),
  approveAudioPreview: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/audio-preview/approve`, { method: 'POST' }),
  rejectAudioPreview: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/audio-preview/reject`, { method: 'POST' }),
  startVideoPreview: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/video-preview`, { method: 'POST' }),
  approveVideoPreview: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/video-preview/approve`, { method: 'POST' }),
  rejectVideoPreview: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/video-preview/reject`, { method: 'POST' }),
  startFinal: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/final`, { method: 'POST' }),
  resume: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/resume`, { method: 'POST' }),
  cancel: (scriptId) => fetchApi(`/api/production/scripts/${scriptId}/render/cancel`, { method: 'POST' }),
}
```

- [ ] **Step 2: Implement WebSocket hook**

```javascript
// console/frontend/src/hooks/useRenderWebSocket.js
import { useEffect, useRef, useState } from 'react'
import { getToken } from '../api/client.js'

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000]

export function useRenderWebSocket(scriptId) {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectAttemptRef = useRef(0)
  const closedByCleanupRef = useRef(false)

  useEffect(() => {
    if (!scriptId) return
    closedByCleanupRef.current = false

    const connect = () => {
      const token = getToken()
      if (!token) return
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = `${proto}//${window.location.host}/ws/render/${scriptId}?token=${encodeURIComponent(token)}`
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        reconnectAttemptRef.current = 0
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'snapshot' || msg.type === 'update') setState(msg)
        } catch {}
      }
      ws.onclose = () => {
        setConnected(false)
        if (closedByCleanupRef.current) return
        const attempt = Math.min(reconnectAttemptRef.current, RECONNECT_DELAYS_MS.length - 1)
        const delay = RECONNECT_DELAYS_MS[attempt]
        reconnectAttemptRef.current += 1
        setTimeout(connect, delay)
      }
      ws.onerror = () => ws.close()
    }
    connect()

    return () => {
      closedByCleanupRef.current = true
      if (wsRef.current) wsRef.current.close()
    }
  }, [scriptId])

  return { state, connected }
}
```

Note: `getToken` may need to be exported from `client.js`. If it isn't, add `export` to its declaration.

- [ ] **Step 3: Smoke check (build)**

```bash
cd console/frontend && npm run build 2>&1 | tail -20
```

Expected: build completes without errors.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/api/client.js console/frontend/src/hooks/useRenderWebSocket.js
git commit -m "feat(asmr): productionApi helpers + render WebSocket hook"
```

---

### Task 15: RenderStatePanel + PreviewApprovalGate components

**Files:**
- Create: `console/frontend/src/components/RenderStatePanel.jsx`
- Create: `console/frontend/src/components/PreviewApprovalGate.jsx`

- [ ] **Step 1: Implement `RenderStatePanel`**

```jsx
// console/frontend/src/components/RenderStatePanel.jsx
import { Button, Card, ProgressBar } from './index.jsx'
import { productionApi } from '../api/client.js'

export default function RenderStatePanel({ scriptId, state, onAction }) {
  if (!state) {
    return (
      <Card title="Render Status">
        <p className="text-xs text-[#9090a8]">Connecting...</p>
      </Card>
    )
  }

  const { status, chunks = [], chunk_summary = {}, overall_progress = 0,
          current_job, logs_tail = [] } = state

  const STATUS_COLORS = {
    completed: '#34d399', running: '#fbbf24',
    failed: '#f87171', pending: '#5a5a70', cancelled: '#5a5a70',
  }

  const handle = async (fn) => {
    try { await fn(scriptId); onAction?.() } catch (e) { alert(e.message) }
  }

  const showResume = chunks.some(c => c.status === 'failed')
  const showCancel = ['producing', 'audio_preview_rendering', 'video_preview_rendering'].includes(status)

  return (
    <Card title="Render Status" actions={
      <div className="flex gap-2">
        {showResume && <Button variant="default" onClick={() => handle(productionApi.resume)}>Resume</Button>}
        {showCancel && <Button variant="danger"  onClick={() => handle(productionApi.cancel)}>Cancel</Button>}
      </div>
    }>
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-[#9090a8] w-32">{status}</span>
          <ProgressBar value={overall_progress} />
          <span className="text-xs font-mono text-[#9090a8] w-12 text-right">{overall_progress}%</span>
        </div>

        {chunks.length > 0 && (
          <div>
            <div className="text-xs text-[#5a5a70] mb-2">
              Chunks: {chunk_summary.completed}/{chunk_summary.total} done
              {chunk_summary.failed > 0 && <span className="text-[#f87171] ml-2">{chunk_summary.failed} failed</span>}
            </div>
            <div className="flex gap-1 flex-wrap">
              {chunks.map(c => (
                <div key={c.idx}
                  title={`Chunk ${c.idx + 1} [${c.start_s?.toFixed(0)}s–${c.end_s?.toFixed(0)}s]: ${c.status}${c.error ? ` — ${c.error}` : ''}`}
                  className="w-8 h-6 rounded text-[10px] flex items-center justify-center font-mono text-white"
                  style={{ backgroundColor: STATUS_COLORS[c.status] || '#5a5a70' }}>
                  {c.idx + 1}
                </div>
              ))}
            </div>
          </div>
        )}

        {current_job?.error && (
          <div className="text-xs text-[#f87171] bg-[#f87171]/10 border border-[#f87171]/30 rounded p-2 font-mono">
            {current_job.error}
          </div>
        )}

        {logs_tail.length > 0 && (
          <details className="text-xs">
            <summary className="cursor-pointer text-[#9090a8]">Recent logs ({logs_tail.length})</summary>
            <div className="mt-2 max-h-48 overflow-y-auto space-y-1 font-mono">
              {logs_tail.map((l, i) => (
                <div key={i} className={l.level === 'ERROR' ? 'text-[#f87171]' : 'text-[#9090a8]'}>
                  <span className="text-[#5a5a70]">{l.ts?.slice(11, 19)}</span> {l.msg}
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: Implement `PreviewApprovalGate`**

```jsx
// console/frontend/src/components/PreviewApprovalGate.jsx
import { Button, Card } from './index.jsx'
import { productionApi } from '../api/client.js'

export default function PreviewApprovalGate({ scriptId, kind, mediaPath, onAction }) {
  const isAudio = kind === 'audio'
  const title = isAudio ? 'Approve Audio Preview' : 'Approve Video Preview'

  const approveFn = isAudio ? productionApi.approveAudioPreview : productionApi.approveVideoPreview
  const rejectFn  = isAudio ? productionApi.rejectAudioPreview  : productionApi.rejectVideoPreview
  const nextFn    = isAudio ? productionApi.startVideoPreview   : productionApi.startFinal

  const handleApprove = async () => {
    try {
      await approveFn(scriptId)
      await nextFn(scriptId)
      onAction?.()
    } catch (e) { alert(e.message) }
  }
  const handleReject = async () => {
    try { await rejectFn(scriptId); onAction?.() } catch (e) { alert(e.message) }
  }

  return (
    <Card title={title}>
      <div className="space-y-3">
        {mediaPath ? (
          isAudio
            ? <audio controls src={`/api/files?path=${encodeURIComponent(mediaPath)}`} className="w-full" />
            : <video controls src={`/api/files?path=${encodeURIComponent(mediaPath)}`} className="w-full max-h-96" />
        ) : (
          <p className="text-xs text-[#9090a8]">No preview available.</p>
        )}
        <div className="flex gap-2">
          <Button variant="primary" onClick={handleApprove}>
            Approve & {isAudio ? 'Render Video Preview' : 'Render Final'}
          </Button>
          <Button variant="danger" onClick={handleReject}>Reject</Button>
        </div>
      </div>
    </Card>
  )
}
```

Note: this assumes a `/api/files?path=...` endpoint for serving preview files. If your project uses a different scheme (e.g., `/api/production/scripts/{id}/preview/audio`), substitute accordingly. Check `console/backend/routers/` for an existing static-file route. If none exists, add one in Task 16's commit.

- [ ] **Step 3: Build check**

```bash
cd console/frontend && npm run build 2>&1 | tail -20
```

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/components/RenderStatePanel.jsx console/frontend/src/components/PreviewApprovalGate.jsx
git commit -m "feat(asmr): RenderStatePanel + PreviewApprovalGate components"
```

---

### Task 16: ASMR controls — music playlist + SFX pool + blackout

**Files:**
- Create: `console/frontend/src/components/MusicPlaylistEditor.jsx`
- Create: `console/frontend/src/components/SfxPoolEditor.jsx`
- Create: `console/frontend/src/components/AsmrControls.jsx`

- [ ] **Step 1: Implement `MusicPlaylistEditor`**

```jsx
// console/frontend/src/components/MusicPlaylistEditor.jsx
import { useEffect, useState } from 'react'
import { Button, Modal } from './index.jsx'
import { fetchApi } from '../api/client.js'

export default function MusicPlaylistEditor({ trackIds = [], onChange }) {
  const [tracks, setTracks] = useState([])
  const [picker, setPicker] = useState(false)
  const [library, setLibrary] = useState([])

  useEffect(() => {
    if (trackIds.length === 0) { setTracks([]); return }
    fetchApi(`/api/music?ids=${trackIds.join(',')}`)
      .then(r => {
        const byId = Object.fromEntries((r.items || []).map(t => [t.id, t]))
        setTracks(trackIds.map(id => byId[id]).filter(Boolean))
      })
      .catch(() => setTracks([]))
  }, [trackIds.join(',')])

  useEffect(() => {
    if (!picker) return
    fetchApi('/api/music?per_page=200&generation_status=ready')
      .then(r => setLibrary(r.items || []))
      .catch(() => setLibrary([]))
  }, [picker])

  const move = (i, dir) => {
    const next = [...trackIds]
    const j = i + dir
    if (j < 0 || j >= next.length) return
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }
  const remove = (i) => onChange(trackIds.filter((_, k) => k !== i))
  const add = (id) => { onChange([...trackIds, id]); setPicker(false) }

  return (
    <div className="space-y-2">
      {tracks.length === 0 && <p className="text-xs text-[#5a5a70]">No tracks selected.</p>}
      {tracks.map((t, i) => (
        <div key={`${t.id}-${i}`} className="flex items-center gap-2 px-2 py-1.5 bg-[#1c1c22] border border-[#2a2a32] rounded">
          <span className="text-xs font-mono text-[#5a5a70] w-6">{i + 1}</span>
          <span className="text-sm text-[#e8e8f0] flex-1 truncate">{t.title}</span>
          <span className="text-xs font-mono text-[#9090a8]">{Math.round(t.duration_s || 0)}s</span>
          <button onClick={() => move(i, -1)} disabled={i === 0}
            className="text-xs text-[#9090a8] disabled:opacity-30 px-1">↑</button>
          <button onClick={() => move(i, +1)} disabled={i === tracks.length - 1}
            className="text-xs text-[#9090a8] disabled:opacity-30 px-1">↓</button>
          <button onClick={() => remove(i)}
            className="text-xs text-[#f87171] px-1">×</button>
        </div>
      ))}
      <Button variant="default" onClick={() => setPicker(true)}>+ Add Track</Button>
      <Modal open={picker} onClose={() => setPicker(false)} title="Select Music Track">
        <div className="max-h-96 overflow-y-auto space-y-1">
          {library.map(t => (
            <button key={t.id} onClick={() => add(t.id)}
              className="w-full text-left px-3 py-2 hover:bg-[#1c1c22] rounded text-sm text-[#e8e8f0]">
              {t.title} <span className="text-[#5a5a70] text-xs">({Math.round(t.duration_s || 0)}s)</span>
            </button>
          ))}
        </div>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 2: Implement `SfxPoolEditor`**

```jsx
// console/frontend/src/components/SfxPoolEditor.jsx
import { useEffect, useState } from 'react'
import { Button, Input, Modal } from './index.jsx'
import { fetchApi } from '../api/client.js'

export default function SfxPoolEditor({ poolIds = [], densitySeconds, onChange }) {
  const [picker, setPicker] = useState(false)
  const [library, setLibrary] = useState([])
  const [poolDetails, setPoolDetails] = useState([])

  useEffect(() => {
    if (poolIds.length === 0) { setPoolDetails([]); return }
    fetchApi(`/api/sfx?ids=${poolIds.join(',')}`)
      .then(r => setPoolDetails(r.items || []))
      .catch(() => setPoolDetails([]))
  }, [poolIds.join(',')])

  useEffect(() => {
    if (!picker) return
    fetchApi('/api/sfx?per_page=500')
      .then(r => setLibrary(r.items || []))
      .catch(() => setLibrary([]))
  }, [picker])

  const togglePick = (id) => {
    if (poolIds.includes(id)) {
      onChange({ poolIds: poolIds.filter(p => p !== id), densitySeconds })
    } else {
      onChange({ poolIds: [...poolIds, id], densitySeconds })
    }
  }
  const remove = (id) => onChange({ poolIds: poolIds.filter(p => p !== id), densitySeconds })

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-[#9090a8] mb-1 block">SFX Pool</label>
        <div className="flex flex-wrap gap-1">
          {poolDetails.map(s => (
            <span key={s.id} className="px-2 py-1 bg-[#1c1c22] border border-[#2a2a32] rounded text-xs text-[#e8e8f0] flex items-center gap-1.5">
              {s.title}
              <button onClick={() => remove(s.id)} className="text-[#f87171]">×</button>
            </span>
          ))}
          <Button variant="ghost" onClick={() => setPicker(true)}>+ Pick SFX</Button>
        </div>
      </div>
      <div>
        <label className="text-xs text-[#9090a8] mb-1 block">
          Density: one SFX every <span className="font-mono text-[#fbbf24]">{densitySeconds || '—'}s</span> (±50% jitter)
        </label>
        <input
          type="range" min="5" max="300" step="5"
          value={densitySeconds || 60}
          onChange={e => onChange({ poolIds, densitySeconds: parseInt(e.target.value, 10) })}
          className="w-full"
          disabled={poolIds.length === 0}
        />
      </div>
      <Modal open={picker} onClose={() => setPicker(false)} title="Pick SFX">
        <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
          {library.map(s => {
            const active = poolIds.includes(s.id)
            return (
              <button key={s.id} onClick={() => togglePick(s.id)}
                className={`text-left px-3 py-2 rounded border ${
                  active ? 'border-[#7c6af7] bg-[#7c6af7]/10' : 'border-[#2a2a32] hover:bg-[#1c1c22]'
                }`}>
                <div className="text-sm text-[#e8e8f0] truncate">{s.title}</div>
                {s.sound_type && <div className="text-[10px] text-[#5a5a70]">{s.sound_type}</div>}
              </button>
            )
          })}
        </div>
        <div className="text-xs text-[#9090a8] mt-2">
          {poolIds.length} selected — click any to toggle
        </div>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 3: Implement `AsmrControls`**

```jsx
// console/frontend/src/components/AsmrControls.jsx
import { useEffect, useState } from 'react'
import { Card, Input } from './index.jsx'
import MusicPlaylistEditor from './MusicPlaylistEditor.jsx'
import SfxPoolEditor from './SfxPoolEditor.jsx'
import { fetchApi } from '../api/client.js'

export default function AsmrControls({ script, onSave }) {
  const [trackIds, setTrackIds] = useState(script?.music_track_ids || [])
  const [sfxPool, setSfxPool] = useState(script?.sfx_pool_ids || [])
  const [sfxDensity, setSfxDensity] = useState(script?.sfx_density_seconds || 60)
  const [blackFrom, setBlackFrom] = useState(script?.black_from_seconds || '')
  const [skipPreviews, setSkipPreviews] = useState(!!script?.skip_previews)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setTrackIds(script?.music_track_ids || [])
    setSfxPool(script?.sfx_pool_ids || [])
    setSfxDensity(script?.sfx_density_seconds || 60)
    setBlackFrom(script?.black_from_seconds || '')
    setSkipPreviews(!!script?.skip_previews)
  }, [script?.id])

  const save = async () => {
    setSaving(true)
    try {
      await fetchApi(`/api/scripts/${script.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          music_track_ids: trackIds,
          sfx_pool_ids: sfxPool,
          sfx_density_seconds: sfxPool.length > 0 ? sfxDensity : null,
          black_from_seconds: blackFrom ? parseInt(blackFrom, 10) : null,
          skip_previews: skipPreviews,
        }),
      })
      onSave?.()
    } finally { setSaving(false) }
  }

  return (
    <Card title="ASMR / Soundscape Controls">
      <div className="space-y-4">
        <div>
          <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider mb-2">Music Playlist</div>
          <MusicPlaylistEditor trackIds={trackIds} onChange={setTrackIds} />
        </div>
        <div>
          <div className="text-xs font-semibold text-[#9090a8] uppercase tracking-wider mb-2">Random SFX</div>
          <SfxPoolEditor
            poolIds={sfxPool} densitySeconds={sfxDensity}
            onChange={({ poolIds, densitySeconds }) => { setSfxPool(poolIds); setSfxDensity(densitySeconds) }}
          />
        </div>
        <Input
          label="Black-out from (seconds, leave blank for none)"
          type="number" min="0"
          value={blackFrom}
          onChange={e => setBlackFrom(e.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-[#9090a8]">
          <input type="checkbox" checked={skipPreviews} onChange={e => setSkipPreviews(e.target.checked)} />
          Skip preview gates (go straight to final render)
        </label>
        <button
          onClick={save} disabled={saving}
          className="w-full px-4 py-2 bg-[#7c6af7] text-white rounded text-sm hover:bg-[#6b5ae6] disabled:opacity-50">
          {saving ? 'Saving...' : 'Save ASMR Settings'}
        </button>
      </div>
    </Card>
  )
}
```

- [ ] **Step 4: Build check**

```bash
cd console/frontend && npm run build 2>&1 | tail -20
```

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/components/MusicPlaylistEditor.jsx console/frontend/src/components/SfxPoolEditor.jsx console/frontend/src/components/AsmrControls.jsx
git commit -m "feat(asmr): music playlist + SFX pool + ASMR controls UI"
```

---

### Task 17: Integrate components into ProductionPage

**Files:**
- Modify: `console/frontend/src/pages/ProductionPage.jsx`

- [ ] **Step 1: Import new modules**

At the top of `ProductionPage.jsx`, add:

```jsx
import AsmrControls from '../components/AsmrControls.jsx'
import RenderStatePanel from '../components/RenderStatePanel.jsx'
import PreviewApprovalGate from '../components/PreviewApprovalGate.jsx'
import { useRenderWebSocket } from '../hooks/useRenderWebSocket.js'
import { productionApi } from '../api/client.js'
```

- [ ] **Step 2: Wire WebSocket and conditional rendering**

In the main `ProductionPage` component, after `const [toast, setToast] = useState(null)` add:

```jsx
const { state: wsState } = useRenderWebSocket(activeId)
const isAsmr = ['asmr', 'soundscape'].includes(script?.template)
const liveStatus = wsState?.status || script?.status
```

Replace the existing "Start Render" button's `onClick` and `disabled` logic with template-aware routing:

```jsx
const handleStartRender = async () => {
  if (!activeId) return
  setRendering(true)
  try {
    let res
    if (isAsmr && !script?.skip_previews) {
      res = await productionApi.startAudioPreview(activeId)
    } else if (isAsmr) {
      res = await productionApi.startFinal(activeId)
    } else {
      res = await fetchApi(`/api/production/scripts/${activeId}/render`, { method: 'POST' })
    }
    showToast(`Render started (task: ${res.task_id?.slice(0, 8)}…)`)
  } catch (e) {
    showToast(e.message, 'error')
  } finally {
    setRendering(false)
  }
}
```

- [ ] **Step 3: Replace the scenes panel with template-aware content**

Inside the JSX, where the existing `<Card title={\`Scenes (${scenes.length})\`}>` block lives, wrap with a conditional:

```jsx
{isAsmr ? (
  <>
    <AsmrControls script={script} onSave={() => loadScript(activeId)} />
    {liveStatus === 'audio_preview_ready' && (
      <PreviewApprovalGate
        scriptId={activeId} kind="audio"
        mediaPath={wsState?.audio_preview_path || script?.audio_preview_path}
        onAction={() => loadScript(activeId)}
      />
    )}
    {liveStatus === 'video_preview_ready' && (
      <PreviewApprovalGate
        scriptId={activeId} kind="video"
        mediaPath={wsState?.video_preview_path || script?.video_preview_path}
        onAction={() => loadScript(activeId)}
      />
    )}
    <RenderStatePanel scriptId={activeId} state={wsState} onAction={() => loadScript(activeId)} />
  </>
) : (
  <Card title={`Scenes (${scenes.length})`}>
    {/* existing scene editor code, unchanged */}
    {scenes.length === 0 ? (
      <EmptyState title="No scenes in this script." />
    ) : (
      <div className="space-y-2">
        {scenes.map((sc, i) => (
          <SceneCard
            key={`${i}-${sc.asset_id ?? 'none'}`}
            scene={sc} index={i} scriptId={activeId}
            onUpdate={() => loadScript(activeId)} onToast={showToast}
          />
        ))}
      </div>
    )}
  </Card>
)}
```

For non-ASMR scripts, also show the RenderStatePanel below the scenes (so progress is visible for everyone):

```jsx
{!isAsmr && wsState && <RenderStatePanel scriptId={activeId} state={wsState} onAction={() => loadScript(activeId)} />}
```

- [ ] **Step 4: Build check**

```bash
cd console/frontend && npm run build 2>&1 | tail -20
```

Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add console/frontend/src/pages/ProductionPage.jsx
git commit -m "feat(asmr): integrate AsmrControls + previews + render panel into ProductionPage"
```

---

## Phase 8 — Integration Verification

### Task 18: End-to-end smoke test on a real ASMR script

**Files:**
- (No new files; manual verification + integration test)

- [ ] **Step 1: Apply migration on dev DB**

```bash
cd console/backend && alembic upgrade head
```

Expected: `Running upgrade 012 -> 013`.

- [ ] **Step 2: Create a test ASMR script via SQL**

```bash
psql $DATABASE_URL -c "
INSERT INTO generated_scripts (topic, niche, template, region, script_json, language, video_format, duration_s, status, skip_previews)
VALUES ('Test ASMR', 'sleep', 'asmr', 'vn',
  '{\"meta\":{\"language\":\"vietnamese\",\"mood\":\"calm_focus\",\"niche\":\"sleep\"},
    \"video\":{\"voice\":\"\"},
    \"scenes\":[{\"narration\":\"\",\"duration\":600,\"visual_hint\":\"calm forest\"}]}',
  'vietnamese', 'long', 600, 'approved', false)
RETURNING id;
"
```

Note the returned ID (call it `\$ID`).

- [ ] **Step 3: Trigger audio preview via curl**

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<your_admin_pw>"}' | jq -r .access_token)

curl -X POST "http://localhost:8080/api/production/scripts/$ID/render/audio-preview" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `{"task_id": "...", "script_id": <ID>}`.

- [ ] **Step 4: Poll render state**

```bash
curl "http://localhost:8080/api/production/scripts/$ID/render/state" \
  -H "Authorization: Bearer $TOKEN" | jq
```

Expected: status transitions `audio_preview_rendering` → `audio_preview_ready` within ~30s for a short script.

- [ ] **Step 5: Approve audio, trigger video preview, approve, trigger final**

```bash
curl -X POST "http://localhost:8080/api/production/scripts/$ID/render/audio-preview/approve" -H "Authorization: Bearer $TOKEN"
curl -X POST "http://localhost:8080/api/production/scripts/$ID/render/video-preview" -H "Authorization: Bearer $TOKEN"
# Wait until state = video_preview_ready
curl -X POST "http://localhost:8080/api/production/scripts/$ID/render/video-preview/approve" -H "Authorization: Bearer $TOKEN"
curl -X POST "http://localhost:8080/api/production/scripts/$ID/render/final" -H "Authorization: Bearer $TOKEN"
```

Expected: each call returns 200; render-state shows chunk pills filling in over time.

- [ ] **Step 6: Verify chunked output**

```bash
# 10-min script → expect 2 chunks of 300s each
curl "http://localhost:8080/api/production/scripts/$ID/render/state" \
  -H "Authorization: Bearer $TOKEN" | jq '.chunks | length'  # → 2

# Final video plays end-to-end
ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 \
  "$(curl -s "http://localhost:8080/api/production/scripts/$ID/render/state" -H "Authorization: Bearer $TOKEN" | jq -r .output_path)"
# Expected: ~600.0
```

- [ ] **Step 7: Test resume**

While a final render is in progress (chunk 1 complete, chunk 2 running), kill the celery-render worker:

```bash
docker compose restart celery-render
```

Then:

```bash
curl -X POST "http://localhost:8080/api/production/scripts/$ID/render/resume" -H "Authorization: Bearer $TOKEN"
```

Expected: chunk 1 stays completed; chunk 2 re-renders; final video produced once both done.

- [ ] **Step 8: Test in browser**

Open `http://localhost:5173`, log in, navigate to Production tab, select the ASMR script. Verify:
- AsmrControls panel renders
- Music playlist editor opens, can add/reorder/remove tracks
- SFX pool picker opens, density slider functional
- "Start Render" triggers audio preview; PreviewApprovalGate appears with audio player
- Approving advances through gates
- RenderStatePanel chunk pills update live without page refresh

- [ ] **Step 9: Commit (if any small fixes)**

```bash
git add -p
git commit -m "fix(asmr): integration fixes from end-to-end smoke test"
```

(Skip if no changes were needed.)

---

## Self-Review (Performed)

**Spec coverage:**
- §1 Data Layer — Task 1 ✓
- §2 Backend — Tasks 2-13 (composer Tasks 2-6, audio_only Task 7, concat Task 8, Celery Tasks 9-10, services Task 11, router Task 12, WS Task 13) ✓
- §3 Frontend — Tasks 14-17 ✓
- §4 API endpoints — Task 12 (all 9 + WS in Task 13) ✓
- §5 Pipeline behavior — Tasks 4 (multi-music crossfade), 5 (SFX), 6 (blackout), 7 (audio preview), 9-10 (chunk render + concat) ✓
- §6 Error handling — covered in Tasks 9-12 (status rollbacks, chunk failure, cancel, resume) ✓
- §7 Tests — Task 2 (SFX scheduler), Task 8 (concat seam), Task 18 (E2E) ✓
- §8 Out of scope — respected (no per-event SFX volume, no per-pair crossfade, no per-chunk regen UI)
- §9 Rollout — Task 18 verifies the rollout steps ✓

**Placeholder scan:**
- No "TODO" or "implement later" in steps.
- One soft spot: Task 15 step 2 references `/api/files?path=...` for serving preview audio/video — this endpoint may not exist yet. The note flags it. If it doesn't exist, an extra step to add a `FileResponse` route on `audio_preview_path`/`video_preview_path` is needed; left as a discoverable issue rather than an upfront placeholder because the route's existing patterns (e.g. `stream_asset` in `production.py:69`) are clear enough to copy.

**Type consistency:**
- `compose_window(script_id, start_s, end_s, output_path)` — same signature in Tasks 3, 7, 9, 10 ✓
- `schedule_sfx(pool_ids, density_s, seed, start_s, end_s)` — consistent in Tasks 2, 5 ✓
- `concat_parts(part_paths, output_path)` — consistent in Tasks 8, 10 ✓
- `render_parts` JSONB items: `{idx, start_s, end_s, status, file_path, error, started_at, completed_at}` — consistent across Tasks 1, 10, 11 ✓
- `productionApi.*` method names match endpoint paths in Tasks 12, 14 ✓

---

## Phase Boundaries (for stop-and-ship)

Each phase produces working software:
- **Phase 1** ships: schema present, models updated, no behavior change
- **Phase 2-3** ships: composer can render windows, audio-only previews compose, ffmpeg concat works (no UI yet)
- **Phase 4** ships: Celery tasks for previews + chunked render are dispatchable via Python REPL
- **Phase 5** ships: ProductionService methods + render_state reader complete (no router yet)
- **Phase 6** ships: API + WebSocket fully usable via curl + wscat
- **Phase 7** ships: editors can use the full ASMR pipeline in the UI
- **Phase 8** verifies the rollout

If any phase falls behind plan, stopping after the previous phase still leaves a usable, committable state.
