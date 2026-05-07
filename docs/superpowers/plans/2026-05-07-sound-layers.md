# Sound Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old `sfx_overrides`/`sfx_pool` SFX system with a 4-layer `sound_layers` JSONB config (background loop + midground/foreground/random_sfx scheduled pools) that is deterministic and chunk-safe.

**Architecture:** A new `schedule_sfx_layer()` scheduler drives three independent timed SFX pools. A new `_build_sound_layers_wav()` renders all four layers to one mixed WAV per chunk. `render_landscape()` and `render_audio_preview()` swap to this new WAV, dropping the old `_build_sfx_pool_wav` and `resolve_sfx_layers` calls.

**Tech Stack:** Python 3.11, ffmpeg, SQLAlchemy/Alembic (PostgreSQL JSONB), pytest, unittest.mock

---

## File Map

| Action | File |
|---|---|
| Modify | `pipeline/sfx_scheduler.py` — add `schedule_sfx_layer()` |
| Modify | `tests/pipeline/test_sfx_scheduler.py` — add tests for new function |
| Create | `console/backend/alembic/versions/021_sound_layers.py` — migration |
| Modify | `console/backend/models/youtube_video.py` — add `sound_layers` column |
| Modify | `pipeline/youtube_ffmpeg.py` — add `_build_sound_layers_wav()`, update `render_landscape()` |
| Modify | `pipeline/youtube_audio_only.py` — update `render_audio_preview()` |
| Modify | `tests/test_youtube_ffmpeg.py` — update `_make_video()`, add new tests |

---

## Task 1: `schedule_sfx_layer()` in `pipeline/sfx_scheduler.py`

**Files:**
- Modify: `pipeline/sfx_scheduler.py`
- Modify: `tests/pipeline/test_sfx_scheduler.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/pipeline/test_sfx_scheduler.py`:

```python
from pipeline.sfx_scheduler import schedule_sfx, schedule_sfx_layer


def test_sfx_layer_empty_pool_returns_empty():
    assert schedule_sfx_layer([], 10, 25, seed=42, start_s=0, end_s=120) == []


def test_sfx_layer_zero_interval_returns_empty():
    assert schedule_sfx_layer([1], 0, 0, seed=42, start_s=0, end_s=120) == []


def test_sfx_layer_deterministic():
    r1 = schedule_sfx_layer([1, 2, 3], 10, 25, seed=42, start_s=0, end_s=120)
    r2 = schedule_sfx_layer([1, 2, 3], 10, 25, seed=42, start_s=0, end_s=120)
    assert r1 == r2
    assert r1 != []


def test_sfx_layer_different_seeds_diverge():
    r1 = schedule_sfx_layer([1, 2], 10, 25, seed=42, start_s=0, end_s=120)
    r2 = schedule_sfx_layer([1, 2], 10, 25, seed=99, start_s=0, end_s=120)
    assert r1 != r2


def test_sfx_layer_events_within_window():
    result = schedule_sfx_layer([1, 2, 3], 10, 25, seed=7, start_s=0, end_s=120)
    for ts, sfx_id in result:
        assert 0 <= ts < 120
        assert sfx_id in [1, 2, 3]


def test_sfx_layer_gaps_within_interval_bounds():
    result = schedule_sfx_layer([1], 10, 25, seed=7, start_s=0, end_s=600)
    timestamps = [ts for ts, _ in result]
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i - 1]
        assert 9.99 <= gap <= 25.01


def test_sfx_layer_chunk_is_deterministic():
    """Same (seed, start_s, end_s) always produces the same schedule."""
    r1 = schedule_sfx_layer([1, 2], 10, 25, seed=42, start_s=3600, end_s=7200)
    r2 = schedule_sfx_layer([1, 2], 10, 25, seed=42, start_s=3600, end_s=7200)
    assert r1 == r2
    assert r1 != []


def test_sfx_layer_burn_makes_chunks_differ():
    """Chunks at different offsets must produce different first-event timestamps
    (the RNG burn advances state so chunks don't all start with the same pattern)."""
    r1 = schedule_sfx_layer([1], 10, 25, seed=42, start_s=0,    end_s=120)
    r2 = schedule_sfx_layer([1], 10, 25, seed=42, start_s=3600, end_s=3720)
    # First timestamps differ because start_s burn advances the RNG differently
    ts1 = r1[0][0] if r1 else None
    ts2 = r2[0][0] - 3600 if r2 else None  # normalise to window-local time
    assert ts1 != ts2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/pipeline/test_sfx_scheduler.py -k "sfx_layer" -v 2>&1 | tail -20
```

Expected: all new tests fail with `ImportError: cannot import name 'schedule_sfx_layer'`

- [ ] **Step 3: Implement `schedule_sfx_layer()`**

Append to `pipeline/sfx_scheduler.py`:

```python
def schedule_sfx_layer(
    pool_ids: list[int],
    interval_min_s: float,
    interval_max_s: float,
    seed: int,
    start_s: float,
    end_s: float,
) -> list[tuple[float, int]]:
    """
    Build a deterministic list of (timestamp, sfx_id) events for one layer.

    Gap between events = rng.uniform(interval_min_s, interval_max_s).
    Seed-burn: advance RNG by int(start_s) steps before drawing so any
    [start_s, end_s) chunk produces non-repeating events relative to
    other chunks of the same video.
    Returns empty list when pool_ids is empty or interval_min_s <= 0.
    """
    if not pool_ids or interval_min_s <= 0:
        return []

    rng = random.Random(seed)
    for _ in range(int(start_s)):
        rng.random()

    schedule: list[tuple[float, int]] = []
    t = start_s
    while t < end_s:
        gap = rng.uniform(interval_min_s, interval_max_s)
        t += gap
        if t >= end_s:
            break
        sfx_id = rng.choice(pool_ids)
        schedule.append((round(t, 3), sfx_id))
    return schedule
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/pipeline/test_sfx_scheduler.py -v 2>&1 | tail -20
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/sfx_scheduler.py tests/pipeline/test_sfx_scheduler.py
git commit -m "feat: add schedule_sfx_layer() with per-layer interval range and seed-burn"
```

---

## Task 2: Alembic Migration + Model Update

**Files:**
- Create: `console/backend/alembic/versions/021_sound_layers.py`
- Modify: `console/backend/models/youtube_video.py`

- [ ] **Step 1: Create migration 021**

Create `console/backend/alembic/versions/021_sound_layers.py`:

```python
"""add sound_layers to youtube_videos

Revision ID: 021
Revises: 020
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "youtube_videos",
        sa.Column("sound_layers", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("youtube_videos", "sound_layers")
```

- [ ] **Step 2: Add `sound_layers` to the SQLAlchemy model**

In `console/backend/models/youtube_video.py`, add after the `render_parts` line (around line 54):

```python
    sound_layers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

The import for `JSONB` is already present at the top of the file.

- [ ] **Step 3: Run the migration**

```bash
cd console/backend
alembic upgrade head
```

Expected output ends with: `Running upgrade 020 -> 021`

- [ ] **Step 4: Verify column exists**

```bash
cd console/backend
python -c "
from database.connection import get_session
from sqlalchemy import text
db = get_session()
result = db.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='youtube_videos' AND column_name='sound_layers'\")).fetchone()
print('Column exists:', result is not None)
db.close()
"
```

Expected: `Column exists: True`

- [ ] **Step 5: Commit**

```bash
cd ../..
git add console/backend/alembic/versions/021_sound_layers.py console/backend/models/youtube_video.py
git commit -m "feat: add sound_layers JSONB column to youtube_videos (migration 021)"
```

---

## Task 3: `_build_sound_layers_wav()` in `pipeline/youtube_ffmpeg.py`

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Modify: `tests/test_youtube_ffmpeg.py`

- [ ] **Step 1: Update `_make_video()` in the test file**

In `tests/test_youtube_ffmpeg.py`, update `_make_video()` to set `sound_layers=None` by default so existing tests don't accidentally trigger the new code path via a truthy MagicMock attribute. Find the existing `_make_video` function (lines 6–24) and replace it with:

```python
def _make_video(sfx_overrides=None, visual_asset_id=None, music_track_id=None,
                target_duration_h=3.0, output_quality="1080p",
                music_track_ids=None, sfx_pool=None,
                sfx_density_seconds=None, sfx_seed=None,
                black_from_seconds=None, sound_layers=None):
    v = MagicMock()
    v.visual_asset_id = visual_asset_id
    v.music_track_id = music_track_id
    v.sfx_overrides = sfx_overrides
    v.target_duration_h = target_duration_h
    v.output_quality = output_quality
    v.music_track_ids = music_track_ids if music_track_ids is not None else []
    v.sfx_pool = sfx_pool if sfx_pool is not None else []
    v.sfx_density_seconds = sfx_density_seconds
    v.sfx_seed = sfx_seed
    v.black_from_seconds = black_from_seconds
    v.sound_layers = sound_layers
    v.visual_asset_ids = []
    v.visual_clip_durations_s = []
    v.visual_loop_mode = "concat_loop"
    return v
```

- [ ] **Step 2: Write failing tests for `_build_sound_layers_wav`**

Append to `tests/test_youtube_ffmpeg.py`:

```python
# ── _build_sound_layers_wav ───────────────────────────────────────────────────

def _make_sfx(id_, file_path, is_loopable=False):
    s = MagicMock()
    s.id = id_
    s.file_path = file_path
    s.is_loopable = is_loopable
    return s


def _make_db_with_sfx(sfx_list):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = sfx_list
    return db


def test_build_sound_layers_wav_returns_none_when_no_config(tmp_path):
    from pipeline.youtube_ffmpeg import _build_sound_layers_wav
    video = _make_video(sound_layers=None)
    assert _build_sound_layers_wav(video, MagicMock(), 300, 0.0, tmp_path) is None


def test_build_sound_layers_wav_returns_none_when_empty_config(tmp_path):
    from pipeline.youtube_ffmpeg import _build_sound_layers_wav
    video = _make_video(sound_layers={})
    assert _build_sound_layers_wav(video, MagicMock(), 300, 0.0, tmp_path) is None


def test_build_sound_layers_wav_background_uses_stream_loop(tmp_path):
    bg_file = tmp_path / "bg.wav"
    bg_file.write_bytes(b"")
    sfx = _make_sfx(5, str(bg_file), is_loopable=True)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff, \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=30.0):
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)

    assert result is not None
    cmd = " ".join(mock_ff.call_args[0][0])
    assert "-stream_loop" in cmd
    assert str(bg_file) in cmd


def test_build_sound_layers_wav_skips_non_loopable_background(tmp_path):
    bg_file = tmp_path / "bg.wav"
    bg_file.write_bytes(b"")
    sfx = _make_sfx(5, str(bg_file), is_loopable=False)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    from pipeline.youtube_ffmpeg import _build_sound_layers_wav
    result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)
    assert result is None  # only layer was skipped → nothing to mix


def test_build_sound_layers_wav_midground_events_use_adelay(tmp_path):
    sfx_file = tmp_path / "mid.wav"
    sfx_file.write_bytes(b"")
    sfx = _make_sfx(1, str(sfx_file))

    video = _make_video(sfx_seed=42, sound_layers={
        "midground": {"pool": [1], "volume": 0.5, "interval_min_s": 10, "interval_max_s": 25}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff:
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)

    assert result is not None
    cmd = " ".join(mock_ff.call_args[0][0])
    assert "adelay=" in cmd


def test_build_sound_layers_wav_chunk_seeks_background(tmp_path):
    bg_file = tmp_path / "bg.wav"
    bg_file.write_bytes(b"")
    sfx = _make_sfx(5, str(bg_file), is_loopable=True)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff, \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=60.0):
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        # start_s=90, probe=60 → seek = 90 % 60 = 30 → -ss applied
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 90.0, tmp_path)

    assert result is not None
    cmd = " ".join(mock_ff.call_args[0][0])
    assert "-ss" in cmd


def test_build_sound_layers_wav_all_three_scheduled_layers(tmp_path):
    sfx_file = tmp_path / "sfx.wav"
    sfx_file.write_bytes(b"")
    sfx = _make_sfx(1, str(sfx_file))

    video = _make_video(sfx_seed=0, sound_layers={
        "midground":  {"pool": [1], "volume": 0.5, "interval_min_s": 10, "interval_max_s": 25},
        "foreground": {"pool": [1], "volume": 0.7, "interval_min_s": 45, "interval_max_s": 60},
        "random_sfx": {"pool": [1], "volume": 0.6, "interval_min_s": 60, "interval_max_s": 100},
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg") as mock_ff:
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 600, 0.0, tmp_path)

    assert result is not None
    # Three layers active → multiple adelay entries in filter_complex
    cmd = " ".join(mock_ff.call_args[0][0])
    assert cmd.count("adelay=") >= 3


def test_build_sound_layers_wav_output_filename(tmp_path):
    sfx_file = tmp_path / "bg.wav"
    sfx_file.write_bytes(b"")
    sfx = _make_sfx(5, str(sfx_file), is_loopable=True)

    video = _make_video(sfx_seed=42, sound_layers={
        "background": {"asset_id": 5, "volume": 0.4}
    })

    with patch("pipeline.youtube_ffmpeg._run_ffmpeg"), \
         patch("pipeline.youtube_ffmpeg._probe_duration", return_value=30.0):
        from pipeline.youtube_ffmpeg import _build_sound_layers_wav
        result = _build_sound_layers_wav(video, _make_db_with_sfx([sfx]), 300, 0.0, tmp_path)

    assert result is not None
    assert result.endswith("sound_layers.wav")
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -k "sound_layers" -v 2>&1 | tail -20
```

Expected: all new tests fail with `ImportError: cannot import name '_build_sound_layers_wav'`

- [ ] **Step 4: Implement `_build_sound_layers_wav()`**

In `pipeline/youtube_ffmpeg.py`, add this function after `_build_sfx_pool_wav()` (around line 390):

```python
LAYER_SEED_OFFSETS = {
    "midground":  0,
    "foreground": 100003,
    "random_sfx": 200003,
}


def _build_sound_layers_wav(
    video,
    db,
    target_duration_s: int,
    start_s: float,
    output_dir: Path,
) -> str | None:
    """Render background loop + 3 scheduled SFX layers to a single temp WAV.

    Replaces both _build_sfx_pool_wav and resolve_sfx_layers for the new
    sound_layers config. Returns None if sound_layers is absent or all layers
    resolve to nothing.
    """
    from console.backend.models.sfx_asset import SfxAsset
    from pipeline.sfx_scheduler import schedule_sfx_layer

    sound_layers = getattr(video, "sound_layers", None) or {}
    if not sound_layers:
        return None

    sfx_seed = getattr(video, "sfx_seed", None) or 0
    end_s = start_s + target_duration_s

    # Collect all referenced asset IDs to load in one query
    all_asset_ids: set[int] = set()
    bg_config = sound_layers.get("background") or {}
    if bg_config.get("asset_id") is not None:
        all_asset_ids.add(int(bg_config["asset_id"]))
    for layer_name in LAYER_SEED_OFFSETS:
        for aid in (sound_layers.get(layer_name) or {}).get("pool", []):
            all_asset_ids.add(int(aid))

    if not all_asset_ids:
        return None

    sfx_by_id = {
        s.id: s
        for s in db.query(SfxAsset).filter(SfxAsset.id.in_(list(all_asset_ids))).all()
    }

    # ── Background layer ─────────────────────────────────────────────────────
    # (path, volume, seek_s)  — seek_s is the ffmpeg -ss value for loop phase
    bg_inputs: list[tuple[str, float, float]] = []
    if bg_config:
        asset_id = bg_config.get("asset_id")
        volume = float(bg_config.get("volume", 1.0))
        if asset_id is not None:
            sfx = sfx_by_id.get(int(asset_id))
            if sfx and sfx.file_path and Path(sfx.file_path).is_file() and sfx.is_loopable:
                asset_dur = _probe_duration(sfx.file_path)
                seek = (start_s % asset_dur) if asset_dur > 0.5 and start_s > 0 else 0.0
                bg_inputs.append((sfx.file_path, volume, seek))
            else:
                logger.warning(
                    "[SoundLayers] background asset %s not found, missing, or not loopable", asset_id
                )

    # ── Scheduled layers ─────────────────────────────────────────────────────
    # (path, volume, local_ts_ms)
    scheduled: list[tuple[str, float, int]] = []
    for layer_name, seed_offset in LAYER_SEED_OFFSETS.items():
        layer = sound_layers.get(layer_name) or {}
        if not layer:
            continue
        pool_ids = [int(x) for x in layer.get("pool", [])]
        if not pool_ids:
            continue
        volume = float(layer.get("volume", 1.0))
        interval_min = float(layer.get("interval_min_s", 10))
        interval_max = float(layer.get("interval_max_s", 25))
        layer_seed = sfx_seed + seed_offset

        events = schedule_sfx_layer(pool_ids, interval_min, interval_max, layer_seed, start_s, end_s)
        for ts, sfx_id in events:
            sfx = sfx_by_id.get(sfx_id)
            if sfx and sfx.file_path and Path(sfx.file_path).is_file():
                local_ts_ms = int((ts - start_s) * 1000)
                scheduled.append((sfx.file_path, volume, local_ts_ms))

    if not bg_inputs and not scheduled:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "sound_layers.wav"

    cmd = ["ffmpeg", "-y"]

    # Inputs: background (looped) then scheduled events
    for path, _vol, seek in bg_inputs:
        if seek > 0.5:
            cmd += ["-ss", str(seek)]
        cmd += ["-stream_loop", "-1", "-i", path]

    for path, _vol, _ts_ms in scheduled:
        cmd += ["-i", path]

    # Filter complex
    parts: list[str] = []
    labels: list[str] = []
    fi = 0

    for i, (_, vol, _) in enumerate(bg_inputs):
        parts.append(f"[{fi}:a]volume={vol}[bg{i}]")
        labels.append(f"[bg{i}]")
        fi += 1

    for i, (_, vol, ts_ms) in enumerate(scheduled):
        parts.append(f"[{fi}:a]volume={vol},adelay={ts_ms}|{ts_ms}[ev{i}]")
        labels.append(f"[ev{i}]")
        fi += 1

    n = len(labels)
    if n == 1:
        parts.append(f"{labels[0]}apad=whole_dur={target_duration_s}[out]")
    else:
        mix_in = "".join(labels)
        parts.append(f"{mix_in}amix=inputs={n}:duration=longest:normalize=0[mixed]")
        parts.append(f"[mixed]apad=whole_dur={target_duration_s}[out]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[out]",
        "-t", str(target_duration_s),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(out_path),
    ]
    _run_ffmpeg(cmd, max(120, target_duration_s + 60))
    return str(out_path)
```

- [ ] **Step 5: Run new tests**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -k "sound_layers" -v 2>&1 | tail -20
```

Expected: all new tests PASS

- [ ] **Step 6: Run the full test suite to check for regressions**

```bash
python -m pytest tests/test_youtube_ffmpeg.py -v 2>&1 | tail -30
```

Expected: all previously passing tests still PASS

- [ ] **Step 7: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "feat: add _build_sound_layers_wav() for 4-layer sound config"
```

---

## Task 4: Wire `render_landscape()` and `render_audio_preview()`

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py` — `render_landscape()`
- Modify: `pipeline/youtube_audio_only.py` — `render_audio_preview()`
- Modify: `tests/test_youtube_ffmpeg.py` — update render_landscape tests

- [ ] **Step 1: Write a failing test that confirms `render_landscape` uses `_build_sound_layers_wav`**

Append to `tests/test_youtube_ffmpeg.py`:

```python
def test_render_landscape_uses_build_sound_layers_wav(tmp_path):
    """render_landscape must call _build_sound_layers_wav, not _build_sfx_pool_wav."""
    output = tmp_path / "out.mp4"
    video = _make_video(sound_layers={"background": {"asset_id": 1, "volume": 0.4}})

    with patch("shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("subprocess.run") as mock_run, \
         patch("pipeline.youtube_ffmpeg._build_music_playlist_wav", return_value=None), \
         patch("pipeline.youtube_ffmpeg._build_sound_layers_wav", return_value=None) as mock_sl, \
         patch("pipeline.youtube_ffmpeg._build_sfx_pool_wav") as mock_old:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        from pipeline.youtube_ffmpeg import render_landscape
        render_landscape(video, output, MagicMock())

    mock_sl.assert_called_once()
    mock_old.assert_not_called()
```

- [ ] **Step 2: Run the failing test**

```bash
python -m pytest tests/test_youtube_ffmpeg.py::test_render_landscape_uses_build_sound_layers_wav -v 2>&1 | tail -10
```

Expected: FAIL — `mock_old.assert_not_called()` fails because `_build_sfx_pool_wav` is still called

- [ ] **Step 3: Update `render_landscape()` in `pipeline/youtube_ffmpeg.py`**

Find the block starting at ~line 463:

```python
    # Pre-render music playlist + SFX pool to temp WAVs (separate ffmpeg passes)
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir, start_s=start_s)
    sfx_wav = _build_sfx_pool_wav(video, db, target_dur, start_s, output_dir)

    # Existing 3-layer SFX overrides remain additive
    sfx_layers = resolve_sfx_layers(video, db)

    audio_inputs: list[tuple[str, float]] = []
    if music_wav:
        audio_inputs.append((music_wav, 1.0))  # already volume-scaled internally
    if sfx_wav:
        audio_inputs.append((sfx_wav, 1.0))
    audio_inputs.extend(sfx_layers)
```

Replace with:

```python
    # Pre-render music playlist + sound layers to temp WAVs (separate ffmpeg passes)
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir, start_s=start_s)
    sound_layers_wav = _build_sound_layers_wav(video, db, target_dur, start_s, output_dir)

    audio_inputs: list[tuple[str, float]] = []
    if music_wav:
        audio_inputs.append((music_wav, 1.0))
    if sound_layers_wav:
        audio_inputs.append((sound_layers_wav, 1.0))
```

Then find the loop that checks `if path in (music_wav, sfx_wav):` (~line 511):

```python
        if path in (music_wav, sfx_wav):
            cmd += ["-i", path]
```

Replace with:

```python
        if path in (music_wav, sound_layers_wav):
            cmd += ["-i", path]
```

- [ ] **Step 4: Update `render_audio_preview()` in `pipeline/youtube_audio_only.py`**

Find the block (~line 38):

```python
    # Pre-render music + SFX (these are exact-duration WAVs)
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir)
    sfx_wav   = _build_sfx_pool_wav(video, db, target_dur, start_s, output_dir)

    # Existing 3-layer SFX (looped at runtime)
    sfx_layers = resolve_sfx_layers(video, db)

    audio_inputs: list[tuple[str, float, bool]] = []  # (path, volume, needs_loop)
    if music_wav:
        audio_inputs.append((music_wav, 1.0, False))
    if sfx_wav:
        audio_inputs.append((sfx_wav, 1.0, False))
    for path, vol in sfx_layers:
        audio_inputs.append((path, vol, True))
```

Replace with:

```python
    # Pre-render music + sound layers (exact-duration WAVs)
    music_wav = _build_music_playlist_wav(video, db, target_dur, output_dir, start_s=start_s)
    sound_layers_wav = _build_sound_layers_wav(video, db, target_dur, start_s, output_dir)

    audio_inputs: list[tuple[str, float, bool]] = []  # (path, volume, needs_loop)
    if music_wav:
        audio_inputs.append((music_wav, 1.0, False))
    if sound_layers_wav:
        audio_inputs.append((sound_layers_wav, 1.0, False))
```

Also update the import at the top of `pipeline/youtube_audio_only.py`. Find:

```python
    from pipeline.youtube_ffmpeg import (
        _build_music_playlist_wav,
        _build_sfx_pool_wav,
        resolve_sfx_layers,
        _run_ffmpeg,
    )
```

Replace with:

```python
    from pipeline.youtube_ffmpeg import (
        _build_music_playlist_wav,
        _build_sound_layers_wav,
        _run_ffmpeg,
    )
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/test_youtube_ffmpeg.py tests/pipeline/test_sfx_scheduler.py -v 2>&1 | tail -30
```

Expected: all tests PASS including the new `test_render_landscape_uses_build_sound_layers_wav`

- [ ] **Step 6: Commit**

```bash
git add pipeline/youtube_ffmpeg.py pipeline/youtube_audio_only.py tests/test_youtube_ffmpeg.py
git commit -m "feat: wire render_landscape and render_audio_preview to sound_layers"
```

---

## Done

After all four tasks, run the full test suite one final time:

```bash
python -m pytest tests/ -v 2>&1 | tail -40
```

All tests should PASS. The new `sound_layers` JSONB column is live, the three scheduled layers and background loop are chunk-safe, and both render paths (full video + audio preview) use the new system.
