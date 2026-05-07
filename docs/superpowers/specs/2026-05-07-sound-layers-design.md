# Sound Layers Redesign

**Date:** 2026-05-07  
**Status:** Approved  
**Replaces:** `sfx_overrides`, `sfx_pool`, `sfx_density_seconds` (old rendering paths)

---

## Problem

The current SFX system has two disconnected parts:
- `sfx_overrides` — three fixed looping files (foreground / midground / background), no randomisation
- `sfx_pool` + `sfx_density_seconds` — one random pool at a single density interval

This is insufficient for soundscape/ASMR videos which need multiple independent layers with distinct appearance frequencies, a true looping ambient bed, and all of it reproducible across chunked renders.

---

## Solution Overview

Replace both systems with a single `sound_layers` JSONB column that describes four named layers. The renderer builds one mixed WAV from all active layers per chunk, chunk-safely.

---

## 1. Data Schema

### New column on `youtube_videos`

```sql
ALTER TABLE youtube_videos ADD COLUMN sound_layers JSONB;
```

Nullable. Old videos with `sound_layers IS NULL` produce no SFX (music playlist is unaffected).

### `sound_layers` shape

```json
{
  "background": {
    "asset_id": 5,
    "volume": 0.4
  },
  "midground": {
    "pool": [1, 2, 3, 8],
    "volume": 0.5,
    "interval_min_s": 10,
    "interval_max_s": 25
  },
  "foreground": {
    "pool": [10, 11],
    "volume": 0.7,
    "interval_min_s": 45,
    "interval_max_s": 60
  },
  "random_sfx": {
    "pool": [20, 21, 22],
    "volume": 0.6,
    "interval_min_s": 60,
    "interval_max_s": 100
  }
}
```

All four keys are optional — omitting a key disables that layer.

### Layer semantics

| Layer | Appearance pattern | Volume scope |
|---|---|---|
| `background` | Loops for full video duration | Per-layer |
| `midground` | Random event every `interval_min_s`–`interval_max_s` s | Per-layer (all pool files share it) |
| `foreground` | Same, slower cadence | Per-layer |
| `random_sfx` | Same, slowest cadence | Per-layer |

### Existing columns

- `sfx_seed` (Integer, nullable) — kept, drives all three scheduled layers. When `NULL`, defaults to `0` (same fallback as the current `_build_sfx_pool_wav`).
- `sfx_pool`, `sfx_density_seconds`, `sfx_overrides` — remain in DB, renderer no longer reads them

---

## 2. Scheduling Logic (`pipeline/sfx_scheduler.py`)

### New function

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
    Seed-burn: advance RNG by int(start_s) steps before drawing, so any
    [start_s, end_s) window produces the same positions as a full render.
    Returns empty list when pool_ids is empty or interval_min_s <= 0.
    """
```

The existing `schedule_sfx()` function is kept unchanged (backward compat, no longer called by the new render path).

### Layer seeds

Each layer gets an independent RNG stream derived from the master `sfx_seed`:

| Layer | Seed offset |
|---|---|
| `midground` | `sfx_seed + 0` |
| `foreground` | `sfx_seed + 100003` |
| `random_sfx` | `sfx_seed + 200003` |

The prime offsets prevent the three streams from ever producing the same sequence at the same `start_s`.

---

## 3. Rendering (`pipeline/youtube_ffmpeg.py`)

### New function: `_build_sound_layers_wav()`

```python
def _build_sound_layers_wav(
    video,
    db,
    target_duration_s: int,
    start_s: float,
    output_dir: Path,
) -> str | None:
```

Returns path to a single mixed WAV covering `[start_s, start_s + target_duration_s)`, or `None` if `sound_layers` is absent or all layers are empty.

**Background layer:**
1. Load `SfxAsset` by `asset_id`. Skip if `is_loopable` is False or file missing.
2. Feed to ffmpeg with `-stream_loop -1`.
3. Seek to `start_s % asset_duration_s` so the loop phase is consistent across chunks (same modulo-seek pattern as the existing SFX layers in `render_landscape`).

**Midground / Foreground / Random SFX layers:**
1. Call `schedule_sfx_layer(pool_ids, interval_min_s, interval_max_s, layer_seed, start_s, start_s + target_duration_s)`.
2. For each `(ts, sfx_id)` event, load the file, apply `adelay=(ts - start_s) * 1000` ms.
3. All events across all three layers are collected into one flat list of ffmpeg inputs.

**Mixing:**
All streams (background + all scheduled events) are mixed with:
```
amix=inputs=N:duration=longest:normalize=0
```
followed by `apad=whole_dur=target_duration_s` to ensure the output is exactly `target_duration_s` long.

Output: single `sound_layers.wav` (PCM s16le, 44100 Hz, stereo).

### Changes to `render_landscape()`

Remove:
```python
sfx_wav   = _build_sfx_pool_wav(video, db, target_dur, start_s, output_dir)
sfx_layers = resolve_sfx_layers(video, db)
```

Add:
```python
sound_layers_wav = _build_sound_layers_wav(video, db, target_dur, start_s, output_dir)
```

Update `audio_inputs` assembly:
```python
if music_wav:
    audio_inputs.append((music_wav, 1.0))
if sound_layers_wav:
    audio_inputs.append((sound_layers_wav, 1.0))
```

`resolve_sfx_layers()` and `_build_sfx_pool_wav()` are kept in the file but no longer called from `render_landscape()`.

### Changes to `render_audio_preview()` (`pipeline/youtube_audio_only.py`)

Same swap: replace `_build_sfx_pool_wav` + `resolve_sfx_layers` calls with `_build_sound_layers_wav`.

---

## 4. Migration

One new Alembic migration (next version after current head):

```python
op.add_column("youtube_videos", sa.Column("sound_layers", postgresql.JSONB(), nullable=True))
```

No columns dropped. No data migration required (old videos simply have `sound_layers = NULL`).

---

## 5. Chunk Safety Summary

The three scheduled layers use `schedule_sfx_layer()` which inherits the seed-burn pattern from the existing `schedule_sfx()`. For any chunk `[start_s, end_s)`:

- RNG is advanced by `int(start_s)` steps before drawing the first event
- This means a chunk starting at `start_s=3600` draws exactly the same events as positions 3600+ in a full render
- The background layer uses modulo seek so its loop phase is identical whether rendered as one file or as 10 chunks

All three scheduled layers use distinct seeds so their event timings are statistically independent of each other.

---

## 6. Out of Scope

- Frontend UI updates for `sound_layers` configuration (separate task)
- Migrating existing `sfx_overrides` data to the new format (old videos get no SFX, which is acceptable)
- Per-file volume within a pool (intentionally excluded — layer-level volume is sufficient)
