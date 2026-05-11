# Spectrum Bars Style Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second spectrum visualizer style — `bars` — that pre-renders 50 white rounded-corner bars with 2px gaps as an alpha-channel video, then overlays it onto the music render.

**Architecture:** New `spectrum_style: Literal['classic', 'bars']` field on `youtube_videos` (default `'classic'`, keeps existing music videos unchanged). The bars style is implemented as a new `pipeline/spectrum_bars.py` module that uses `scipy.signal.stft` to compute 50 log-binned frequency band amplitudes per frame, draws each frame via NumPy slice-assignment from a pre-built bar template, and pipes raw RGBA frames at 15fps to ffmpeg `libvpx-vp9` for an alpha-preserving WebM. The render path in `pipeline/youtube_ffmpeg.py:_render_landscape_music` calls the new renderer when `spectrum_style=='bars'` and overlays the resulting video as an additional ffmpeg input — same pattern as the now-playing PNG overlays.

**Tech Stack:** Python 3.11 · scipy 1.17 (already installed) · NumPy · ffmpeg (libvpx-vp9 with yuva420p) · SQLAlchemy 2.0 · Alembic · Pydantic v2 · React 18

**Spec:** `docs/superpowers/specs/2026-05-12-spectrum-bars-style-design.md`

---

## File Structure Overview

| File | Purpose | Action |
|------|---------|--------|
| `console/backend/alembic/versions/023_spectrum_style.py` | Add `spectrum_style` column to youtube_videos | Create |
| `console/backend/models/youtube_video.py` | Add `spectrum_style` ORM column | Modify |
| `console/backend/routers/youtube_videos.py` | Add `SpectrumStyle` Literal + field to Create/Update schemas | Modify |
| `console/backend/services/youtube_video_service.py` | `editable_fields`, `_video_to_dict`, `_MUSIC_NOT_NULL_FIELDS` plumbing for `spectrum_style` | Modify |
| `pipeline/spectrum_bars.py` | NEW — bar template + STFT/binning/smoothing + `render_spectrum_bars_video` | Create |
| `pipeline/youtube_ffmpeg.py` | `_render_landscape_music` branches on `spectrum_style`; bars path adds extra ffmpeg input + overlay chain | Modify |
| `console/frontend/src/components/SpectrumPanel.jsx` | Add Style select | Modify |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | `spectrumStyle` useState; pass to SpectrumPanel; include in isMusic payload | Modify |
| `tests/test_spectrum_bars.py` | Unit tests (template, math, smoke render, caching) | Create |
| `tests/test_youtube_video_service_music_fields.py` | Add round-trip test for `spectrum_style` | Modify |
| `tests/test_music_render_smoke.py` | Add `spectrum_style='bars'` smoke test | Modify |

---

## Task 1: Alembic migration

**Files:**
- Create: `console/backend/alembic/versions/023_spectrum_style.py`

- [ ] **Step 1: Confirm current alembic head**

Run: `cd console/backend && alembic heads`
Expected: `022_music_template (head)`. The new migration's `down_revision = "022_music_template"`.

- [ ] **Step 2: Create the migration**

```python
# console/backend/alembic/versions/023_spectrum_style.py
"""spectrum_style

Revision ID: 023_spectrum_style
Revises: 022_music_template
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa


revision = "023_spectrum_style"
down_revision = "022_music_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "spectrum_style",
            sa.String(20),
            nullable=False,
            server_default="classic",
        ),
    )
    op.create_check_constraint(
        "spectrum_style_valid",
        "youtube_videos",
        "spectrum_style IN ('classic', 'bars')",
    )


def downgrade() -> None:
    op.drop_constraint("spectrum_style_valid", "youtube_videos", type_="check")
    op.drop_column("youtube_videos", "spectrum_style")
```

- [ ] **Step 3: Apply against test DB**

Run:
```bash
cd console/backend
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test alembic upgrade head
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test alembic downgrade -1
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test alembic upgrade head
```
Expected: all three commands succeed without errors.

- [ ] **Step 4: Verify column + constraint**

Run:
```bash
PGPASSWORD=123456 psql -U admin -h localhost -d ai_media_test -c \
  "\d youtube_videos" | grep -E "spectrum_style"
PGPASSWORD=123456 psql -U admin -h localhost -d ai_media_test -c \
  "SELECT conname FROM pg_constraint WHERE conname = 'spectrum_style_valid';"
```
Expected: `spectrum_style` column with default `'classic'::character varying`; constraint `spectrum_style_valid` present.

- [ ] **Step 5: Apply migration to dev DB so backend doesn't break on next restart**

Run:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic upgrade head
```
Expected: dev DB now has the new column.

- [ ] **Step 6: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/backend/alembic/versions/023_spectrum_style.py
git commit -m "feat(db): add spectrum_style column to youtube_videos

Migration 023 adds a spectrum_style VARCHAR(20) column on
youtube_videos with default 'classic' and CHECK constraint
restricting values to 'classic' or 'bars'. Existing rows get the
default automatically — no data migration needed."
```

---

## Task 2: SQLAlchemy + Pydantic + service plumbing

**Files:**
- Modify: `console/backend/models/youtube_video.py`
- Modify: `console/backend/routers/youtube_videos.py`
- Modify: `console/backend/services/youtube_video_service.py`
- Modify: `tests/test_youtube_video_service_music_fields.py`

- [ ] **Step 1: Add ORM column to `YoutubeVideo`**

Open `console/backend/models/youtube_video.py`. Find the existing `spectrum_*` block (added in migration 022) and add a sibling column:

```python
spectrum_style: Mapped[str] = mapped_column(
    sa.String(20), nullable=False, default="classic", server_default="classic"
)
```

If the file uses `String` directly (not `sa.String`), match the existing style.

- [ ] **Step 2: Add Pydantic Literal + Create/Update fields**

Open `console/backend/routers/youtube_videos.py`. Near the other `Literal` type aliases (`TrackTransition`, `OverlayStyle`, `SpectrumPosition`) add:

```python
SpectrumStyle = Literal["classic", "bars"]
```

In `YoutubeVideoCreate`, add (placed alongside the existing spectrum fields):

```python
spectrum_style: SpectrumStyle = "classic"
```

In `YoutubeVideoUpdate`, add:

```python
spectrum_style: SpectrumStyle | None = None
```

- [ ] **Step 3: Add service-layer plumbing**

Open `console/backend/services/youtube_video_service.py`.

Add `"spectrum_style"` to `_MUSIC_NOT_NULL_FIELDS` (the tuple of fields that reject `None` in update payloads).

Add `"spectrum_style"` to the `editable_fields` list inside `update_video`.

In the `YoutubeVideo(...)` constructor call inside `create_video` (where the existing music fields are passed), add:

```python
spectrum_style=data.get("spectrum_style", "classic"),
```

In `_video_to_dict`, add:

```python
"spectrum_style": v.spectrum_style or "classic",
```

next to the other `spectrum_*` keys.

- [ ] **Step 4: Write failing round-trip test**

Append to `tests/test_youtube_video_service_music_fields.py`:

```python
def test_spectrum_style_round_trip_create(db):
    from console.backend.models.video_template import VideoTemplate
    from console.backend.services.youtube_video_service import YoutubeVideoService
    music = db.query(VideoTemplate).filter_by(slug="music").one()
    from database.models import MusicTrack
    t = MusicTrack(title="A", file_path="/tmp/a.wav", duration_s=60.0)
    db.add(t); db.commit()
    svc = YoutubeVideoService(db)
    result = svc.create_video({
        "title": "x", "template_id": music.id,
        "music_track_ids": [t.id],
        "spectrum_enabled": True,
        "spectrum_style": "bars",
    }, user_id=None)
    assert result["spectrum_style"] == "bars"


def test_spectrum_style_defaults_to_classic(db):
    from console.backend.models.video_template import VideoTemplate
    from console.backend.services.youtube_video_service import YoutubeVideoService
    asmr = db.query(VideoTemplate).filter_by(slug="asmr").one()
    svc = YoutubeVideoService(db)
    result = svc.create_video({
        "title": "x", "template_id": asmr.id,
        "target_duration_h": 8.0,
    }, user_id=None)
    assert result["spectrum_style"] == "classic"


def test_spectrum_style_update_rejects_null(db):
    import pytest
    from console.backend.models.video_template import VideoTemplate
    from console.backend.services.youtube_video_service import YoutubeVideoService
    asmr = db.query(VideoTemplate).filter_by(slug="asmr").one()
    svc = YoutubeVideoService(db)
    created = svc.create_video({"title": "x", "template_id": asmr.id}, user_id=None)
    with pytest.raises(ValueError, match="cannot be null"):
        svc.update_video(created["id"], {"spectrum_style": None}, user_id=None)


def test_spectrum_style_pydantic_rejects_invalid():
    import pytest
    from pydantic import ValidationError
    from console.backend.routers.youtube_videos import YoutubeVideoCreate
    with pytest.raises(ValidationError):
        YoutubeVideoCreate(title="x", template_id=1, spectrum_style="rainbow")
```

- [ ] **Step 5: Run tests, expect pass**

Run:
```bash
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test \
  python3 -m pytest tests/test_youtube_video_service_music_fields.py -v 2>&1 | tail -25
```
Expected: all tests pass (including the new 4).

- [ ] **Step 6: Commit**

```bash
git add console/backend/models/youtube_video.py \
        console/backend/routers/youtube_videos.py \
        console/backend/services/youtube_video_service.py \
        tests/test_youtube_video_service_music_fields.py
git commit -m "feat(svc): spectrum_style enum plumbed through models, schemas, service

Adds spectrum_style Literal['classic','bars'] to YoutubeVideoCreate
and YoutubeVideoUpdate, the ORM column, _video_to_dict serialization,
editable_fields whitelist, _MUSIC_NOT_NULL_FIELDS guard, and the
create_video constructor passthrough."
```

---

## Task 3: Bar template builder

**Files:**
- Create: `pipeline/spectrum_bars.py`
- Create: `tests/test_spectrum_bars.py`

- [ ] **Step 1: Write failing test for bar template**

Create `tests/test_spectrum_bars.py`:

```python
import numpy as np
import pytest

from pipeline.spectrum_bars import _build_bar_template


def test_bar_template_shape_and_dtype():
    tpl = _build_bar_template(bar_w=20, bar_h=100, radius=2, color_rgb=(255, 255, 255))
    assert tpl.shape == (100, 20, 4)
    assert tpl.dtype == np.uint8


def test_bar_template_interior_fully_opaque():
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    # Pixel well inside the bar (away from any corner)
    assert tpl[50, 10, 3] == 255   # center
    assert tpl[99, 10, 3] == 255   # bottom-middle
    # Color matches
    assert tuple(tpl[50, 10, :3]) == (255, 255, 255)


def test_bar_template_top_corners_anti_aliased():
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    # Top-left corner pixel (0,0): outside the radius=2 quarter-circle, alpha should be 0 or near 0
    assert tpl[0, 0, 3] < 255
    # Top-right corner pixel (0, bar_w-1)
    assert tpl[0, 19, 3] < 255


def test_bar_template_bottom_corners_NOT_rounded():
    """Bars grow upward; bottom corners should be sharp (full alpha)."""
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[99, 0, 3] == 255
    assert tpl[99, 19, 3] == 255


def test_bar_template_zero_radius_is_pure_rectangle():
    tpl = _build_bar_template(20, 100, 0, (255, 255, 255))
    assert np.all(tpl[..., 3] == 255)


def test_bar_template_respects_color():
    tpl = _build_bar_template(20, 100, 2, (124, 106, 247))  # the project accent purple
    assert tuple(tpl[50, 10, :3]) == (124, 106, 247)
```

- [ ] **Step 2: Run test, expect ImportError**

Run:
```bash
python3 -m pytest tests/test_spectrum_bars.py -x -v 2>&1 | tail -10
```
Expected: ImportError on `pipeline.spectrum_bars` (the module doesn't exist yet).

- [ ] **Step 3: Create module skeleton + bar template builder**

Create `pipeline/spectrum_bars.py`:

```python
"""Pre-render the 'bars' spectrum visualizer as an alpha-channel video.

The bars style cannot be expressed in a native ffmpeg filtergraph because
fixed-count rounded-corner bars require per-pixel logic that depends on
time-varying audio amplitudes. Instead, this module computes 50 log-binned
frequency band amplitudes per frame using scipy STFT, composes each frame
via NumPy slice-assignment from a pre-built rounded-corner bar template,
and pipes raw RGBA frames to ffmpeg libvpx-vp9 for an alpha-preserving
WebM. The result is overlaid onto the main render as a separate input.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert '#rrggbb' or 'rrggbb' to (r, g, b) tuple."""
    s = hex_color.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _build_bar_template(
    bar_w: int,
    bar_h: int,
    radius: int,
    color_rgb: tuple[int, int, int],
) -> np.ndarray:
    """Build one rounded-top-corner bar as an (bar_h, bar_w, 4) uint8 RGBA array.

    Bottom corners are sharp (bars grow upward from the baseline).
    Top corners use a quarter-circle alpha mask with sub-pixel anti-aliasing.
    """
    arr = np.zeros((bar_h, bar_w, 4), dtype=np.uint8)
    arr[..., 0] = color_rgb[0]
    arr[..., 1] = color_rgb[1]
    arr[..., 2] = color_rgb[2]
    arr[..., 3] = 255

    if radius <= 0:
        return arr

    for y in range(radius):
        for x in range(radius):
            # Distance from this pixel's center to the corner-circle center
            dx = (radius - x) - 0.5
            dy = (radius - y) - 0.5
            dist = (dx * dx + dy * dy) ** 0.5
            # AA: pixels at distance < radius are full, > radius+1 are zero,
            # in between get a linear ramp
            coverage = max(0.0, min(1.0, radius - dist + 0.5))
            alpha = int(round(255 * coverage))
            arr[y, x, 3] = alpha                  # top-left
            arr[y, bar_w - 1 - x, 3] = alpha      # top-right
    return arr
```

- [ ] **Step 4: Run tests, expect pass**

Run:
```bash
python3 -m pytest tests/test_spectrum_bars.py -v 2>&1 | tail -15
```
Expected: 6/6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/spectrum_bars.py tests/test_spectrum_bars.py
git commit -m "feat(pipeline): bar template builder for spectrum bars style

Pre-builds a single rounded-top-corner bar as an RGBA NumPy array.
The whole frame composition just slice-copies portions of this
template into the frame buffer, avoiding per-frame Pillow draw
overhead. Bottom corners are sharp (bars grow upward); top corners
use sub-pixel anti-aliasing."
```

---

## Task 4: STFT analysis + log binning + smoothing

**Files:**
- Modify: `pipeline/spectrum_bars.py`
- Modify: `tests/test_spectrum_bars.py`

- [ ] **Step 1: Append failing tests for `compute_bar_heights`**

Append to `tests/test_spectrum_bars.py`:

```python
import subprocess
from pipeline.spectrum_bars import compute_bar_heights


@pytest.fixture
def sine_wav(tmp_path):
    """Create a stereo 44.1kHz sine WAV for testing."""
    def _make(name: str, dur: float, freq: int) -> str:
        out = tmp_path / f"{name}.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency={freq}:duration={dur}",
            "-ar", "44100", "-ac", "2", str(out),
        ], check=True, capture_output=True)
        return str(out)
    return _make


def test_compute_bar_heights_shape(sine_wav):
    """5s WAV @ 15fps → (75, 50) bar_heights."""
    path = sine_wav("a", dur=5.0, freq=1000)
    heights = compute_bar_heights(
        wav_path=path, total_duration_s=5.0,
        bar_count=50, spectrum_fps=15,
    )
    assert heights.shape == (75, 50)
    assert heights.dtype == np.float32


def test_compute_bar_heights_range_normalized(sine_wav):
    """All values in [0, 1]."""
    path = sine_wav("a", dur=2.0, freq=440)
    heights = compute_bar_heights(
        wav_path=path, total_duration_s=2.0,
        bar_count=50, spectrum_fps=15,
    )
    assert heights.min() >= 0.0
    assert heights.max() <= 1.0


def test_compute_bar_heights_mid_freq_dominates_for_1khz(sine_wav):
    """1kHz sine should produce a peak in a mid-range bar."""
    path = sine_wav("a", dur=2.0, freq=1000)
    heights = compute_bar_heights(
        wav_path=path, total_duration_s=2.0,
        bar_count=50, spectrum_fps=15,
    )
    # Sum across time → which bar has the most energy?
    energy_per_bar = heights.sum(axis=0)
    peak_bar = int(np.argmax(energy_per_bar))
    # With log spacing 60Hz..16kHz over 50 bars, 1kHz is at:
    # log(1000/60) / log(16000/60) * 50 ≈ 0.5 * 50 = ~25
    # Allow some tolerance for STFT smearing
    assert 18 <= peak_bar <= 32, f"Peak bar {peak_bar} not near expected ~25 for 1kHz"


def test_compute_bar_heights_smoothing_prevents_sudden_drops():
    """Synthetic test: feed two amplitude vectors and verify smoothing clamp."""
    from pipeline.spectrum_bars import _apply_smoothing
    raw = np.array([
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ], dtype=np.float32)
    smoothed = _apply_smoothing(raw.copy(), decay=0.85)
    # Frame 1 was 1.0, frame 2 raw is 0.0 → smoothed should be at least 0.85
    assert np.all(smoothed[1] >= 0.85)
    # Frame 3 should be at least 0.85 * 0.85 ≈ 0.7225
    assert np.all(smoothed[2] >= 0.85 * 0.85)


def test_compute_bar_heights_handles_mono(tmp_path):
    """Mono WAV should not blow up — should be averaged trivially."""
    out = tmp_path / "mono.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=500:duration=2",
        "-ar", "44100", "-ac", "1", str(out),
    ], check=True, capture_output=True)
    heights = compute_bar_heights(
        wav_path=str(out), total_duration_s=2.0,
        bar_count=50, spectrum_fps=15,
    )
    assert heights.shape == (30, 50)
```

- [ ] **Step 2: Run tests, expect ImportError**

Run:
```bash
python3 -m pytest tests/test_spectrum_bars.py -v -k "compute_bar_heights or smoothing" 2>&1 | tail -10
```
Expected: ImportError on `compute_bar_heights` / `_apply_smoothing`.

- [ ] **Step 3: Implement STFT + binning + smoothing**

Append to `pipeline/spectrum_bars.py`:

```python
def _apply_smoothing(bar_heights: np.ndarray, decay: float = 0.85) -> np.ndarray:
    """In-place exponential decay smoothing: each frame is max(raw, prev * decay)."""
    for k in range(1, bar_heights.shape[0]):
        np.maximum(bar_heights[k], bar_heights[k - 1] * decay, out=bar_heights[k])
    return bar_heights


def compute_bar_heights(
    wav_path: str,
    total_duration_s: float,
    bar_count: int = 50,
    spectrum_fps: int = 15,
    f_low: float = 60.0,
    f_high: float = 16000.0,
    smoothing_decay: float = 0.85,
) -> np.ndarray:
    """Compute (n_target_frames, bar_count) bar heights in [0, 1] from a WAV file."""
    import scipy.io.wavfile
    import scipy.signal

    sample_rate, audio = scipy.io.wavfile.read(wav_path)

    # Normalize to float32 [-1, 1] and mix to mono
    if np.issubdtype(audio.dtype, np.integer):
        audio = audio.astype(np.float32) / float(np.iinfo(audio.dtype).max)
    else:
        audio = audio.astype(np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # STFT
    nperseg = 2048
    noverlap = 1024
    f, t, Zxx = scipy.signal.stft(
        audio, fs=sample_rate, nperseg=nperseg, noverlap=noverlap, boundary=None
    )
    magnitudes = np.abs(Zxx).astype(np.float32)  # (n_freq_bins, n_time_frames)

    # Log-spaced frequency bin edges
    freq_edges = np.geomspace(f_low, f_high, num=bar_count + 1)
    bin_indices = np.searchsorted(f, freq_edges)

    # Sum magnitudes within each bar's bin range
    bar_amps = np.zeros((bar_count, magnitudes.shape[1]), dtype=np.float32)
    for i in range(bar_count):
        lo = int(bin_indices[i])
        hi = max(int(bin_indices[i + 1]), lo + 1)
        bar_amps[i] = magnitudes[lo:hi].sum(axis=0)

    # Dynamic range compression + normalization
    bars = np.log1p(bar_amps * 0.05).T  # (n_time_frames, bar_count)
    peak = float(bars.max())
    if peak > 1e-6:
        bars /= peak
    np.clip(bars, 0.0, 1.0, out=bars)

    # Resample to spectrum_fps
    n_target_frames = int(round(total_duration_s * spectrum_fps))
    if n_target_frames <= 0:
        return np.zeros((0, bar_count), dtype=np.float32)
    src_times = t
    dst_times = np.linspace(0.0, total_duration_s, num=n_target_frames)
    bar_heights = np.empty((n_target_frames, bar_count), dtype=np.float32)
    for i in range(bar_count):
        bar_heights[:, i] = np.interp(dst_times, src_times, bars[:, i])

    # Exponential smoothing (anti-jitter)
    _apply_smoothing(bar_heights, decay=smoothing_decay)
    return bar_heights
```

- [ ] **Step 4: Run tests, expect pass**

Run:
```bash
python3 -m pytest tests/test_spectrum_bars.py -v 2>&1 | tail -25
```
Expected: all spectrum_bars tests pass (11 total now).

- [ ] **Step 5: Commit**

```bash
git add pipeline/spectrum_bars.py tests/test_spectrum_bars.py
git commit -m "feat(pipeline): STFT + log-binning + smoothing for bars spectrum

compute_bar_heights runs scipy.signal.stft on the music WAV once, bins
its magnitudes into 50 log-spaced frequency bands (60Hz..16kHz),
compresses dynamic range via log1p, resamples to spectrum_fps with
np.interp, and applies exponential decay smoothing so bars don't
jitter every frame. Returns a (n_frames, 50) float32 array in [0, 1]."
```

---

## Task 5: Frame composition + ffmpeg pipe + caching

**Files:**
- Modify: `pipeline/spectrum_bars.py`
- Modify: `tests/test_spectrum_bars.py`

- [ ] **Step 1: Append failing smoke + caching tests**

Append to `tests/test_spectrum_bars.py`:

```python
from pipeline.spectrum_bars import render_spectrum_bars_video


def _ffprobe_duration(path) -> float:
    out = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def test_render_spectrum_video_smoke(tmp_path, sine_wav):
    """End-to-end: 3s sine → spectrum.webm at expected duration."""
    a = sine_wav("a", dur=3.0, freq=1000)
    out_path = tmp_path / "spec.webm"
    out = render_spectrum_bars_video(
        music_wav=a,
        out_path=out_path,
        total_duration_s=3.0,
        canvas_w=1920,
        canvas_h=1080,
        height_pct=0.12,
        color_hex="#ffffff",
    )
    assert Path(out).is_file()
    dur = _ffprobe_duration(out)
    assert 2.9 <= dur <= 3.2


def test_render_spectrum_video_caches(tmp_path, sine_wav):
    """Re-running with same inputs reuses the cached output."""
    a = sine_wav("a", dur=2.0, freq=440)
    out_path = tmp_path / "spec.webm"
    render_spectrum_bars_video(
        music_wav=a, out_path=out_path, total_duration_s=2.0,
        canvas_w=1920, canvas_h=1080, height_pct=0.12, color_hex="#ffffff",
    )
    mtime1 = out_path.stat().st_mtime
    # Force the os to register a measurable mtime delta if a re-render did happen
    import time
    time.sleep(1.1)
    render_spectrum_bars_video(
        music_wav=a, out_path=out_path, total_duration_s=2.0,
        canvas_w=1920, canvas_h=1080, height_pct=0.12, color_hex="#ffffff",
    )
    assert out_path.stat().st_mtime == mtime1  # cache hit, no re-render


def test_render_spectrum_video_invalidates_on_audio_change(tmp_path, sine_wav):
    """If the music WAV is newer than the cached output, re-render."""
    a = sine_wav("a", dur=2.0, freq=440)
    out_path = tmp_path / "spec.webm"
    render_spectrum_bars_video(
        music_wav=a, out_path=out_path, total_duration_s=2.0,
        canvas_w=1920, canvas_h=1080, height_pct=0.12, color_hex="#ffffff",
    )
    mtime1 = out_path.stat().st_mtime
    # Replace the WAV with a fresh one (newer mtime)
    import time, os
    time.sleep(1.1)
    a2 = sine_wav("a", dur=2.0, freq=1500)
    os.utime(a2)  # ensure mtime is now > mtime1
    render_spectrum_bars_video(
        music_wav=a2, out_path=out_path, total_duration_s=2.0,
        canvas_w=1920, canvas_h=1080, height_pct=0.12, color_hex="#ffffff",
    )
    assert out_path.stat().st_mtime > mtime1


def test_render_spectrum_video_raises_when_audio_missing(tmp_path):
    import pytest
    with pytest.raises((FileNotFoundError, RuntimeError)):
        render_spectrum_bars_video(
            music_wav="/nonexistent/audio.wav",
            out_path=tmp_path / "spec.webm",
            total_duration_s=1.0,
            canvas_w=1920, canvas_h=1080, height_pct=0.12, color_hex="#ffffff",
        )
```

- [ ] **Step 2: Run tests, expect ImportError**

Run:
```bash
python3 -m pytest tests/test_spectrum_bars.py::test_render_spectrum_video_smoke -x -v 2>&1 | tail -10
```
Expected: ImportError on `render_spectrum_bars_video`.

- [ ] **Step 3: Implement the renderer**

Append to `pipeline/spectrum_bars.py`:

```python
def render_spectrum_bars_video(
    music_wav: str,
    out_path: Path,
    total_duration_s: float,
    canvas_w: int,
    canvas_h: int,
    height_pct: float,
    color_hex: str,
    bar_count: int = 50,
    bar_gap_px: int = 2,
    corner_radius_px: int = 2,
    spectrum_fps: int = 15,
) -> Path:
    """Pre-render the spectrum as a libvpx-vp9 yuva420p WebM with alpha.

    Returns the path to the rendered file. Caches: if out_path already exists
    AND its mtime is newer than the music WAV's mtime, returns immediately
    without re-rendering.
    """
    out_path = Path(out_path)
    music_path = Path(music_wav)
    if not music_path.is_file():
        raise FileNotFoundError(f"Music WAV not found: {music_wav}")

    # Cache check
    if (
        out_path.is_file()
        and out_path.stat().st_mtime >= music_path.stat().st_mtime
    ):
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Geometry
    strip_h = max(1, int(canvas_h * height_pct))
    slot_w = max(1, canvas_w // bar_count)
    bar_w = max(1, slot_w - bar_gap_px)

    # Pre-build the bar template
    color_rgb = _hex_to_rgb(color_hex)
    template = _build_bar_template(
        bar_w=bar_w, bar_h=strip_h,
        radius=corner_radius_px, color_rgb=color_rgb,
    )

    # Compute heights
    bar_heights = compute_bar_heights(
        wav_path=music_wav,
        total_duration_s=total_duration_s,
        bar_count=bar_count,
        spectrum_fps=spectrum_fps,
    )
    if bar_heights.shape[0] == 0:
        raise RuntimeError("compute_bar_heights returned zero frames")

    # Launch ffmpeg as a subprocess accepting rawvideo on stdin
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pixel_format", "rgba",
        "-video_size", f"{canvas_w}x{strip_h}",
        "-framerate", str(spectrum_fps),
        "-i", "pipe:0",
        "-c:v", "libvpx-vp9",
        "-pix_fmt", "yuva420p",
        "-t", str(total_duration_s),
        "-an",
        "-deadline", "realtime",
        "-cpu-used", "8",
        "-b:v", "0",
        "-crf", "32",
        str(out_path),
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    frame_buf = np.zeros((strip_h, canvas_w, 4), dtype=np.uint8)
    try:
        for k in range(bar_heights.shape[0]):
            frame_buf.fill(0)
            for i in range(bar_count):
                h_px = int(round(float(bar_heights[k, i]) * strip_h))
                if h_px <= 0:
                    continue
                x_start = i * slot_w
                x_end = x_start + bar_w
                if x_end > canvas_w:
                    x_end = canvas_w
                bar_slice_w = x_end - x_start
                # Copy bottom `h_px` rows of the template, into the bottom of the strip
                tpl_slice = template[strip_h - h_px:, :bar_slice_w]
                frame_buf[strip_h - h_px:, x_start:x_end] = tpl_slice
            proc.stdin.write(frame_buf.tobytes())
    finally:
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait()

    if proc.returncode != 0:
        err = proc.stderr.read().decode("utf-8", "ignore")[-500:]
        raise RuntimeError(f"spectrum bars ffmpeg failed (rc={proc.returncode}): {err}")
    return out_path
```

- [ ] **Step 4: Run all spectrum_bars tests**

Run:
```bash
python3 -m pytest tests/test_spectrum_bars.py -v 2>&1 | tail -25
```
Expected: 15 tests pass (6 template + 5 heights + 4 renderer).

- [ ] **Step 5: Commit**

```bash
git add pipeline/spectrum_bars.py tests/test_spectrum_bars.py
git commit -m "feat(pipeline): render_spectrum_bars_video — frame compose + ffmpeg pipe

Composes each spectrum frame via NumPy slice-assignment from the
pre-built bar template, pipes raw RGBA frames at 15fps to ffmpeg
libvpx-vp9 with yuva420p (preserves alpha). Caches by out_path mtime
vs music WAV mtime — skips re-render when audio hasn't changed."
```

---

## Task 6: Integrate bars renderer into the music render path

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py`
- Modify: `tests/test_music_render_smoke.py`

- [ ] **Step 1: Read current `_render_landscape_music` to find the spectrum-chain section**

Run:
```bash
grep -n "spectrum_chain\|build_spectrum_filter\|spectrum_enabled\|_render_landscape_music" pipeline/youtube_ffmpeg.py | head -20
```
Locate the block where `build_spectrum_filter` is called and the spectrum filter chain is built.

- [ ] **Step 2: Write failing smoke test**

Append to `tests/test_music_render_smoke.py`:

```python
def test_music_render_with_bars_spectrum(db, make_sine, make_visual, tmp_path):
    """Render a music video with spectrum_style='bars' — spectrum.webm exists,
    final MP4 has the right duration, the overlay is visible (non-empty pixels)."""
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from database.models import MusicTrack, VideoAsset
    from pipeline.youtube_ffmpeg import render_landscape

    tracks = []
    for i, dur in enumerate([3, 4, 3], start=1):
        wav = make_sine(f"t{i}", dur, freq=440 + i * 200)
        t = MusicTrack(title=f"Track {i}", file_path=str(wav),
                       duration_s=float(dur), volume=1.0)
        db.add(t); tracks.append(t)
    db.commit()
    visual = VideoAsset(file_path=str(make_visual("v")),
                       duration_s=5.0, source="test")
    db.add(visual); db.commit()

    template = db.query(VideoTemplate).filter_by(slug="music").one()
    video = YoutubeVideo(
        title="Smoke Music Bars",
        template_id=template.id,
        music_track_ids=[t.id for t in tracks],
        visual_asset_id=visual.id,
        track_transition="gapless",
        playlist_overlay_style=None,
        spectrum_enabled=True,
        spectrum_style="bars",
        spectrum_position="bottom",
        spectrum_height_pct=0.15,
        spectrum_color="#ffffff",
        spectrum_opacity=0.7,
    )
    db.add(video); db.commit()
    db.refresh(video)

    out = tmp_path / "final.mp4"
    render_landscape(video, out, db)

    assert out.is_file()
    # Total duration should be 3 + 4 + 3 = 10s
    import subprocess
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(out),
    ], capture_output=True, text=True, check=True)
    duration = float(probe.stdout.strip())
    assert 9.5 <= duration <= 10.5

    # The pre-rendered spectrum video should exist next to the output
    spectrum_files = list(tmp_path.glob("spectrum*.webm"))
    assert len(spectrum_files) >= 1, "Expected pre-rendered spectrum.webm to exist"
```

- [ ] **Step 3: Run the smoke test, expect failure**

Run:
```bash
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test \
  python3 -m pytest tests/test_music_render_smoke.py::test_music_render_with_bars_spectrum -x -v 2>&1 | tail -25
```
Expected: failure — `_render_landscape_music` doesn't branch on `spectrum_style` yet, so the bars path isn't taken. Either ffmpeg won't find the bars spectrum, OR the test will assert spectrum.webm wasn't created.

- [ ] **Step 4: Update `_render_landscape_music` to branch on spectrum_style**

Open `pipeline/youtube_ffmpeg.py`. At the top, ensure the import is present:

```python
from pipeline.spectrum_bars import render_spectrum_bars_video
```

Inside `_render_landscape_music`, find the section that builds the spectrum chain (currently always uses `build_spectrum_filter`). Replace it with a branch:

```python
# Spectrum: classic uses inline showfreqs filter; bars pre-renders a separate video
spectrum_video_path = None
spectrum_chain = ""
if video.spectrum_enabled and video.spectrum_style == "bars":
    spectrum_video_path = render_spectrum_bars_video(
        music_wav=music_wav,
        out_path=output_dir / "spectrum.webm",
        total_duration_s=total_dur_s,
        canvas_w=w,
        canvas_h=h,
        height_pct=video.spectrum_height_pct,
        color_hex=video.spectrum_color,
    )
elif video.spectrum_enabled:  # classic (default)
    spectrum_chain, _ = build_spectrum_filter(
        enabled=True,
        position=video.spectrum_position,
        height_pct=video.spectrum_height_pct,
        color=video.spectrum_color,
        opacity=video.spectrum_opacity,
        canvas_w=w, canvas_h=h,
        audio_input_label="[1:a]",
        base_label="[base]",
        out_label="[v_after_spec]",
    )
```

Where the ffmpeg command is being assembled, after the existing audio inputs, add the spectrum video as an extra `-i` input when `spectrum_video_path` is set:

```python
# After audio inputs are appended:
extra_input_idx_base = 2  # 0=visual, 1=music; bars spectrum is index 2 if present
if spectrum_video_path is not None:
    cmd += ["-i", str(spectrum_video_path)]
# Now-playing PNG overlays start at index 2 (or 3 if spectrum bars present)
overlay_input_start = extra_input_idx_base + (1 if spectrum_video_path else 0)
```

In the filter chain section, when `spectrum_video_path` is set, splice in a bars-style overlay (instead of `spectrum_chain`):

```python
# Build filter chain step by step
parts: list[str] = []
parts.append(f"[0:v]{base_vf}[base]")

if spectrum_chain:
    # Classic spectrum
    parts.append(spectrum_chain)
    prev_label = "[v_after_spec]"
elif spectrum_video_path is not None:
    # Bars spectrum: overlay the pre-rendered video onto [base]
    spec_input_idx = 2  # 0=video, 1=music, 2=spectrum bars
    strip_h = int(h * video.spectrum_height_pct)
    y_pos = (h - strip_h) if video.spectrum_position == "bottom" else (h - strip_h) // 2
    parts.append(
        f"[{spec_input_idx}:v]format=rgba,colorchannelmixer=aa={video.spectrum_opacity}[spec_bars];"
        f"[base][spec_bars]overlay=0:{y_pos}[v_after_spec]"
    )
    prev_label = "[v_after_spec]"
else:
    prev_label = "[base]"
```

The exact splicing must respect the existing input-index numbering. Look at the existing music branch carefully — if it already increments overlay PNG input indices, the bars spectrum input must slot in BEFORE the now-playing PNG inputs, AND the overlay loop must add 1 to its index counter when `spectrum_video_path` is set.

In short: ANY existing `2 + idx` arithmetic for overlay PNGs becomes `(2 if no bars spec else 3) + idx`. Add a helper variable `overlay_input_start` and reference it consistently.

- [ ] **Step 5: Run all smoke tests**

Run:
```bash
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test \
  python3 -m pytest tests/test_music_render_smoke.py -v 2>&1 | tail -15
```
Expected: 3/3 pass (existing 2 plus the new bars smoke).

- [ ] **Step 6: Verify no regression on classic spectrum**

Run:
```bash
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test \
  python3 -m pytest tests/test_spectrum_filter.py tests/test_music_render_smoke.py -v 2>&1 | tail -20
```
Expected: all tests pass — classic path still works.

- [ ] **Step 7: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_music_render_smoke.py
git commit -m "feat(pipeline): _render_landscape_music branches on spectrum_style

When spectrum_style=='bars', pre-renders spectrum.webm via
pipeline.spectrum_bars and adds it as an extra ffmpeg input + overlay
chain. Classic style (default) keeps using the inline showfreqs
filter. Input indexing for now-playing PNG overlays is adjusted to
skip past the bars spectrum input when present."
```

---

## Task 7: Frontend SpectrumPanel — Style select

**Files:**
- Modify: `console/frontend/src/components/SpectrumPanel.jsx`

- [ ] **Step 1: Read the current SpectrumPanel structure**

Run:
```bash
cat console/frontend/src/components/SpectrumPanel.jsx
```
Note where the Position select sits (around line 33–35). Insert the Style select directly above it.

- [ ] **Step 2: Add Style select inside the collapsible content**

In `console/frontend/src/components/SpectrumPanel.jsx`, find the block that renders inside `{open && (...)}`. Add the Style select before Position. The block typically looks like:

```jsx
{open && (
  <div className="space-y-2 pl-4">
    <div>
      <label className="block text-xs text-[#9090a8] mb-1">Position</label>
      <select ...>
        ...
      </select>
    </div>
    ...
```

Change to:

```jsx
{open && (
  <div className="space-y-2 pl-4">
    <div>
      <label className="block text-xs text-[#9090a8] mb-1">Style</label>
      <select
        value={value.spectrum_style ?? 'classic'}
        onChange={e => update({ spectrum_style: e.target.value })}
        className="bg-[#1c1c22] border border-[#2a2a32] rounded px-2 py-1"
      >
        <option value="classic">Classic (showfreqs)</option>
        <option value="bars">Bars (50, rounded)</option>
      </select>
    </div>
    <div>
      <label className="block text-xs text-[#9090a8] mb-1">Position</label>
      <select ...>
        ...
```

Keep all other fields (Position, Height, Color, Opacity) unchanged.

- [ ] **Step 3: Build and verify**

Run:
```bash
cd console/frontend && npm run build 2>&1 | tail -10
```
Expected: clean build, no errors.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/frontend/src/components/SpectrumPanel.jsx
git commit -m "feat(frontend): SpectrumPanel Style select (classic/bars)

Adds a Style dropdown to the SpectrumPanel between the Enable
checkbox and the Position select. Two options: 'Classic (showfreqs)'
and 'Bars (50, rounded)'. Value plumbed via the existing
value/onChange interface — no other panel changes required."
```

---

## Task 8: Frontend page state — wire spectrumStyle into create/update payload

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

- [ ] **Step 1: Locate existing spectrum state hooks**

Run:
```bash
grep -n "spectrumEnabled\|spectrumPosition\|spectrumHeightPct\|spectrumColor\|spectrumOpacity\|setSpectrum" console/frontend/src/pages/YouTubeVideosPage.jsx | head -20
```
Locate where the existing `useState` hooks for spectrum fields are declared, where they're passed into SpectrumPanel's `value`, and where they're included in the submit payload.

- [ ] **Step 2: Add `spectrumStyle` useState alongside the existing ones**

Find the block declaring `const [spectrumEnabled, setSpectrumEnabled] = useState(...)` and add:

```jsx
const [spectrumStyle, setSpectrumStyle] = useState(
  isEdit && existingVideo.spectrum_style ? existingVideo.spectrum_style : 'classic'
)
```

- [ ] **Step 3: Pass `spectrum_style` into the SpectrumPanel value object**

Find the SpectrumPanel JSX (in the `④c MUSIC OPTIONS` section). The `value` prop currently looks like:

```jsx
<SpectrumPanel
  value={{
    spectrum_enabled:    spectrumEnabled,
    spectrum_position:   spectrumPosition,
    spectrum_height_pct: spectrumHeightPct,
    spectrum_color:      spectrumColor,
    spectrum_opacity:    spectrumOpacity,
  }}
  onChange={patch => {
    if ('spectrum_enabled' in patch) setSpectrumEnabled(patch.spectrum_enabled)
    ...
  }}
/>
```

Add `spectrum_style` to both `value` and `onChange`:

```jsx
<SpectrumPanel
  value={{
    spectrum_enabled:    spectrumEnabled,
    spectrum_style:      spectrumStyle,
    spectrum_position:   spectrumPosition,
    spectrum_height_pct: spectrumHeightPct,
    spectrum_color:      spectrumColor,
    spectrum_opacity:    spectrumOpacity,
  }}
  onChange={patch => {
    if ('spectrum_enabled'    in patch) setSpectrumEnabled(patch.spectrum_enabled)
    if ('spectrum_style'      in patch) setSpectrumStyle(patch.spectrum_style)
    if ('spectrum_position'   in patch) setSpectrumPosition(patch.spectrum_position)
    if ('spectrum_height_pct' in patch) setSpectrumHeightPct(patch.spectrum_height_pct)
    if ('spectrum_color'      in patch) setSpectrumColor(patch.spectrum_color)
    if ('spectrum_opacity'    in patch) setSpectrumOpacity(patch.spectrum_opacity)
  }}
/>
```

- [ ] **Step 4: Include `spectrum_style` in the isMusic payload spread**

Find the `handleSubmit` function. Inside the body assembly, the music-only spread looks like:

```jsx
...(isMusic ? {
  music_track_ids: musicTrackIds,
  track_transition: trackTransition,
  track_transition_seconds: trackTransitionSeconds,
  playlist_overlay_style: playlistOverlayStyle,
  spectrum_enabled: spectrumEnabled,
  spectrum_position: spectrumPosition,
  spectrum_height_pct: spectrumHeightPct,
  spectrum_color: spectrumColor,
  spectrum_opacity: spectrumOpacity,
} : {}),
```

Add `spectrum_style`:

```jsx
...(isMusic ? {
  music_track_ids: musicTrackIds,
  track_transition: trackTransition,
  track_transition_seconds: trackTransitionSeconds,
  playlist_overlay_style: playlistOverlayStyle,
  spectrum_enabled: spectrumEnabled,
  spectrum_style: spectrumStyle,
  spectrum_position: spectrumPosition,
  spectrum_height_pct: spectrumHeightPct,
  spectrum_color: spectrumColor,
  spectrum_opacity: spectrumOpacity,
} : {}),
```

- [ ] **Step 5: Build and verify**

Run:
```bash
cd console/frontend && npm run build 2>&1 | tail -10
```
Expected: clean build.

- [ ] **Step 6: Manual smoke check (no commit yet)**

Start Vite dev server if not running. In the YouTube Videos tab, click `+ New Video ▾` → `Music Video`. Open the Spectrum panel and verify the Style select shows Classic / Bars and changing it updates state. Save the video and check that the Network tab POST/PUT to `/api/youtube-videos` includes `spectrum_style` in the body.

- [ ] **Step 7: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(frontend): wire spectrumStyle into YT video page state + payload

New spectrumStyle useState defaulting to 'classic' (or existing
video's value on edit), passed in/out of SpectrumPanel, and included
in the isMusic create/update payload spread."
```

---

## Task 9: End-to-end verification

**Files:** none — verification only

- [ ] **Step 1: Full backend test suite (excluding music render smoke)**

Run:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test \
  python3 -m pytest tests/ --ignore=tests/test_music_render_smoke.py -q --tb=no 2>&1 | tail -8
```
Expected: passes consistent with prior baseline (pre-existing failures only).

- [ ] **Step 2: Spectrum bars test suite**

Run:
```bash
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test \
  python3 -m pytest tests/test_spectrum_bars.py -v 2>&1 | tail -20
```
Expected: 15/15 pass.

- [ ] **Step 3: Smoke render — both spectrum styles**

Run:
```bash
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test \
  python3 -m pytest tests/test_music_render_smoke.py -v -s 2>&1 | tail -20
```
Expected: 3/3 pass (existing classic + no-overlay + new bars).

- [ ] **Step 4: Migration round-trip**

Run:
```bash
cd console/backend
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test alembic downgrade -1
DATABASE_URL=postgresql://admin:123456@localhost:5432/ai_media_test alembic upgrade head
PGPASSWORD=123456 psql -U admin -h localhost -d ai_media_test -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name = 'youtube_videos' AND column_name = 'spectrum_style';"
```
Expected: clean downgrade + upgrade; column re-appears after upgrade.

- [ ] **Step 5: Frontend build**

Run:
```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/frontend && npm run build 2>&1 | tail -8
```
Expected: clean build.

- [ ] **Step 6: Manual visual QA (the only step the tests can't do)**

- Start backend (`./console/start.sh` from project root)
- Start frontend (`cd console/frontend && npm run dev`)
- Create a new Music Video with 3 short tracks, `spectrum_enabled=true`, `spectrum_style='bars'`
- Queue the render. Inspect the rendered MP4:
  - 50 distinct white bars with visible 2px gaps
  - Rounded corners on bar tops (subtle but visible)
  - Bars react to music (bass → low-index bars, treble → high-index bars)
  - No per-frame jitter (smoothing visible)
- Render the same video with `spectrum_style='classic'` and verify it still produces the old `showfreqs`-style spectrum (regression check)

- [ ] **Step 7: Final commit if any small fixes emerged from QA**

If everything passed without changes, no commit. Otherwise:

```bash
git add <files>
git commit -m "fix: <specific issue from QA>"
```

The work is complete.

---

## Self-Review

**1. Spec coverage check:**

| Spec section | Task |
|---|---|
| Migration `023_spectrum_style` | Task 1 |
| ORM `spectrum_style` column | Task 2 |
| Pydantic `SpectrumStyle` Literal + Create/Update fields | Task 2 |
| `_MUSIC_NOT_NULL_FIELDS` + `editable_fields` + `_video_to_dict` + create_video passthrough | Task 2 |
| `_build_bar_template` with anti-aliased top corners | Task 3 |
| `compute_bar_heights` (STFT + log binning + resample + smoothing) | Task 4 |
| `_apply_smoothing` | Task 4 |
| `render_spectrum_bars_video` (full renderer + cache check) | Task 5 |
| `_render_landscape_music` branch on `spectrum_style` | Task 6 |
| Render budget soft warning (>4h + bars) | **Gap — not in any task** |
| SpectrumPanel Style select | Task 7 |
| YouTubeVideosPage state + payload | Task 8 |
| Manual QA: visual check, regression check on classic | Task 9 step 6 |

**The render budget soft warning extension** (Section "Validation + error handling" in the spec):
The spec extends the existing soft warning in `_validate_music_template` to add a bars-specific message. This is a small addition to `console/backend/services/youtube_video_service.py`. It's not in any task above. **Adding to Task 2 Step 3:** after the existing service-layer plumbing, add a one-line message change in the existing `total_dur_s > 4 * 3600` block. Implementer: when modifying Task 2 Step 3, also update the warnings block in `_validate_music_template` (if it exists) to differentiate the bars message. If the warnings block doesn't exist yet (it was a soft TODO in the music-template work), skip — not blocking.

**2. Placeholder scan:** All code blocks are complete. No "TBD", "TODO", or vague guidance.

**3. Type consistency:**
- `spectrum_style: Literal['classic','bars']` — same in migration CHECK, ORM column, Pydantic schema, frontend dropdown, payload spread.
- Function names match across tasks: `_build_bar_template`, `compute_bar_heights`, `_apply_smoothing`, `render_spectrum_bars_video`, `_hex_to_rgb`.
- Render pipeline integration: `_render_landscape_music` branches on `video.spectrum_style`. The bars input index starts at 2 (0=visual, 1=music). Now-playing overlay inputs (from existing music-template work) start at `overlay_input_start = 2 + (1 if spectrum_video_path else 0) = 2 or 3`. Consistent.

---

## Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
