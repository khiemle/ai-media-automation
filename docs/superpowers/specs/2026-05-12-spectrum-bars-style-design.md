# Spectrum Bars Style — Design

**Date:** 2026-05-12
**Status:** Draft (pending user review)
**Author:** Brainstorming session with khiemlq@gmail.com

## Goal

Add a second spectrum visualizer style — `bars` — alongside the existing `classic` (ffmpeg `showfreqs`) style for the music YouTube template. The bars style produces a music-player-aesthetic equalizer: 50 white rounded-corner bars with 2px gaps, growing upward from a baseline.

The current `showfreqs`-based spectrum is functional but visually unrefined (no spacing, no rounded corners, no control over bar count). The new style is opt-in via a `spectrum_style` enum so existing music videos render unchanged.

## Non-goals

- Replacing the classic style (kept available as `spectrum_style='classic'`)
- Mirror-mode bars (bars growing both directions from a center line) — deferred
- Multi-color or gradient bars — deferred (single solid color, defaults white)
- Per-frame interactivity / real-time preview
- Mobile / vertical-format Shorts spectrum (long-form landscape only)

## High-level approach

ffmpeg has no native filter that draws fixed-count rounded-corner bars. The bars style **pre-renders the spectrum as an alpha-channel video** via Python (scipy FFT + NumPy frame drawing + raw frame pipe to ffmpeg), then overlays that video onto the main render — mirroring the existing now-playing PNG overlay pattern.

Three optimizations keep the pre-render cost low:

1. **NumPy slice-assignment** for frame composition (5–10× faster than Pillow)
2. **Rawvideo pipe** to ffmpeg (no PNG encode/decode round-trip)
3. **15fps spectrum** (ffmpeg upsamples to 30fps via frame duplication — bar motion at 15fps is visually indistinguishable from 30fps for music)

Result: an 8h music video pre-renders the spectrum in ~5–10 minutes — comparable overhead to the classic style.

## Data model

### Alembic migration `023_spectrum_style.py`

```sql
ALTER TABLE youtube_videos
  ADD COLUMN spectrum_style VARCHAR(20) NOT NULL DEFAULT 'classic';

ALTER TABLE youtube_videos
  ADD CONSTRAINT spectrum_style_valid
    CHECK (spectrum_style IN ('classic', 'bars'));
```

Default `'classic'` means existing music videos render identically to before — no data migration needed.

### SQLAlchemy model

`console/backend/models/youtube_video.py`:

```python
spectrum_style: Mapped[str] = mapped_column(
    String(20), nullable=False, default="classic", server_default="classic"
)
```

### Pydantic schemas

`console/backend/routers/youtube_videos.py`:

```python
SpectrumStyle = Literal["classic", "bars"]

# YoutubeVideoCreate:
spectrum_style: SpectrumStyle = "classic"

# YoutubeVideoUpdate:
spectrum_style: SpectrumStyle | None = None
```

### Service-layer changes

- `editable_fields` in `update_video` gains `"spectrum_style"`
- `_video_to_dict` serializes `spectrum_style`
- `_MUSIC_NOT_NULL_FIELDS` (the null-guard tuple) gains `"spectrum_style"`

### Frontend

`console/frontend/src/components/SpectrumPanel.jsx`:

A new Style select inside the collapsible panel, placed between Enable checkbox and Position select:

```
Style: [Classic (showfreqs) ▾]
       [Bars (50 rounded, white) ]
```

`console/frontend/src/pages/YouTubeVideosPage.jsx`: new `spectrumStyle` useState (default `'classic'`), passed via `SpectrumPanel` value/onChange, included in the `isMusic` payload spread.

## Pre-render module

### New file: `pipeline/spectrum_bars.py`

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
    """Pre-render the spectrum as an alpha-channel video.
    Returns the path to the rendered spectrum video, ready to be used as
    a separate input to the main render filtergraph.
    """
```

### Algorithm

**1. STFT analysis (one-pass over entire audio)**

```python
sample_rate, audio = scipy.io.wavfile.read(music_wav)
if audio.ndim > 1:
    audio = audio.mean(axis=1)  # mix down to mono for analysis
audio = audio.astype(np.float32) / np.iinfo(audio.dtype).max  # normalize

f, t, Zxx = scipy.signal.stft(audio, fs=sample_rate, nperseg=2048, noverlap=1024)
magnitudes = np.abs(Zxx)  # (n_freq_bins, n_time_frames)
```

**2. Log-spaced bin reduction (50 bins, 60Hz – 16kHz)**

```python
freq_edges = np.geomspace(60.0, 16000.0, num=bar_count + 1)
bin_indices = np.searchsorted(f, freq_edges)
bar_amplitudes = np.zeros((bar_count, magnitudes.shape[1]), dtype=np.float32)
for i in range(bar_count):
    lo, hi = bin_indices[i], max(bin_indices[i+1], bin_indices[i] + 1)
    bar_amplitudes[i] = magnitudes[lo:hi].sum(axis=0)
```

**3. Dynamic range compression + normalization**

```python
bars = np.log1p(bar_amplitudes * 0.05).T  # (n_time_frames, bar_count)
bars /= max(bars.max(), 1e-6)
np.clip(bars, 0.0, 1.0, out=bars)
```

**4. Resample to spectrum_fps**

Time grid of STFT is sample_rate/hop spaced. Resample to a target grid of `spectrum_fps` per second:

```python
n_target_frames = int(round(total_duration_s * spectrum_fps))
src_times = t  # from scipy.signal.stft
dst_times = np.linspace(0.0, total_duration_s, num=n_target_frames)
bar_heights = np.empty((n_target_frames, bar_count), dtype=np.float32)
for i in range(bar_count):
    bar_heights[:, i] = np.interp(dst_times, src_times, bars[:, i])
```

**5. Exponential smoothing (anti-jitter)**

```python
for k in range(1, n_target_frames):
    bar_heights[k] = np.maximum(bar_heights[k], bar_heights[k-1] * 0.85)
```

**6. Pre-build the bar template (one rounded-corner bar)**

```python
def _build_bar_template(bar_w: int, bar_h: int, radius: int, color_rgb: tuple) -> np.ndarray:
    """Returns (bar_h, bar_w, 4) uint8 with rounded TOP corners (anti-aliased)."""
    arr = np.zeros((bar_h, bar_w, 4), dtype=np.uint8)
    arr[..., :3] = color_rgb
    arr[..., 3] = 255
    for y in range(radius):
        for x in range(radius):
            dx, dy = radius - x - 0.5, radius - y - 0.5
            dist = (dx*dx + dy*dy) ** 0.5
            alpha = max(0.0, min(1.0, radius - dist + 0.5))
            a = int(255 * alpha)
            arr[y, x, 3] = a
            arr[y, bar_w - 1 - x, 3] = a
    return arr
```

**7. Per-frame composition + ffmpeg pipe**

```python
strip_h = int(canvas_h * height_pct)
slot_w = canvas_w // bar_count
bar_w = max(1, slot_w - bar_gap_px)
template = _build_bar_template(bar_w, strip_h, corner_radius_px, color_rgb)

cmd = ["ffmpeg", "-y",
       "-f", "rawvideo", "-pixel_format", "rgba",
       "-video_size", f"{canvas_w}x{strip_h}",
       "-framerate", str(spectrum_fps),
       "-i", "pipe:0",
       "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
       "-t", str(total_duration_s),
       str(out_path)]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

frame_buf = np.zeros((strip_h, canvas_w, 4), dtype=np.uint8)
for k in range(n_target_frames):
    frame_buf.fill(0)
    for i in range(bar_count):
        h_px = int(round(bar_heights[k, i] * strip_h))
        if h_px <= 0:
            continue
        x_start = i * slot_w
        x_end = x_start + bar_w
        frame_buf[strip_h - h_px:, x_start:x_end] = template[strip_h - h_px:]
    proc.stdin.write(frame_buf.tobytes())

proc.stdin.close()
proc.wait()
if proc.returncode != 0:
    err = proc.stderr.read().decode("utf-8", "ignore")[-500:]
    raise RuntimeError(f"spectrum bars ffmpeg failed: {err}")
return out_path
```

**8. Caching**

Skip pre-render entirely if `out_path` exists and its mtime is newer than the music WAV's mtime. Save 5+ minutes on re-renders that don't change audio.

```python
if out_path.is_file() and out_path.stat().st_mtime >= Path(music_wav).stat().st_mtime:
    return out_path
```

### Performance estimate (8h video)

| Step | Time |
|---|---|
| scipy.signal.stft over 8h audio at 44.1kHz | ~30 s |
| Bin reduction + smoothing | ~5 s |
| Frame composition (15fps × 8h = 432K frames, ~0.5ms each) | ~3.5 min |
| ffmpeg encode (libvpx-vp9 yuva420p, mostly transparent frames) | ~3–5 min |
| **Total** | **~7–9 min** |

## Render integration

`pipeline/youtube_ffmpeg.py:_render_landscape_music`:

```python
if video.spectrum_enabled:
    if video.spectrum_style == "bars":
        spectrum_video = render_spectrum_bars_video(
            music_wav=music_wav,
            out_path=output_dir / "spectrum.webm",
            total_duration_s=total_dur_s,
            canvas_w=w,
            canvas_h=h,
            height_pct=video.spectrum_height_pct,
            color_hex=video.spectrum_color,
        )
        # Add as extra input, build overlay chain
        spectrum_extra_inputs = ["-i", str(spectrum_video)]
        spectrum_input_idx = next_input_idx  # depends on order
        y_pos = (h - int(h * video.spectrum_height_pct)) if video.spectrum_position == "bottom" \
            else (h - int(h * video.spectrum_height_pct)) // 2
        spectrum_chain = (
            f"[{spectrum_input_idx}:v]format=rgba,colorchannelmixer=aa={video.spectrum_opacity}[spec];"
            f"[base][spec]overlay=0:{y_pos}[v_after_spec]"
        )
    else:  # 'classic'
        spectrum_chain, _ = build_spectrum_filter(...)  # existing path
```

The pre-rendered `spectrum.webm` is added as an additional `-i` to the main render command. The filter chain overlays it onto `[base]` at the configured Y position with the configured opacity.

`build_spectrum_filter` (existing helper) is unchanged. It's only called when `spectrum_style == 'classic'`.

## Validation + error handling

### Service layer (`_validate_music_template`):

- `spectrum_style` validated by Pydantic Literal — no additional service check needed.
- Render-budget soft warning extends:
  ```python
  if total_dur_s > 4 * 3600 and video.spectrum_enabled:
      if video.spectrum_style == "bars":
          warnings.append("Bars spectrum adds ~5-10 min pre-render for long videos")
      else:
          warnings.append("Long video with spectrum enabled; consider chunked render")
  ```

### Render task:

| Failure | Response |
|---|---|
| scipy not installed | Hard fail at module import with clear "pip install scipy" message |
| Music WAV missing/unreadable | Re-raise underlying scipy error with context |
| ffmpeg pipe fails (returncode != 0) | RuntimeError with last 500 chars of stderr |
| Output spectrum.webm corrupt | Existing ffprobe-based validation in render path catches it |

## Testing

### Unit tests — `tests/test_spectrum_bars.py`

```python
def test_bar_template_has_rounded_corners():
    """Top corners are anti-aliased; interior is fully opaque."""
    tpl = _build_bar_template(20, 100, 2, (255, 255, 255))
    assert tpl[0, 0, 3] < 255            # top-left corner alpha < 255
    assert tpl[0, 19, 3] < 255           # top-right corner alpha < 255
    assert tpl[50, 10, 3] == 255         # interior fully opaque
    assert tpl[99, 10, 3] == 255         # bottom interior fully opaque

def test_50_bars_fit_canvas_with_2px_gaps():
    canvas_w, bar_count, gap = 1920, 50, 2
    slot_w = canvas_w // bar_count
    bar_w = slot_w - gap
    assert bar_w > 0
    assert (bar_count * slot_w) <= canvas_w

def test_stft_to_50_log_bins(tmp_path):
    """Synthetic 1kHz sine produces energy concentrated in mid-range bars."""
    # Generate 5s of 1kHz sine WAV
    # Run STFT + log-binning
    # Assert one of the mid-range bars dominates

def test_smoothing_clamps_decay_rate():
    """After smoothing, no consecutive frame drops by more than 15%."""
    raw = np.array([1.0, 0.0, 0.0, 0.0])
    smoothed = raw.copy()
    for k in range(1, 4):
        smoothed[k] = max(smoothed[k], smoothed[k-1] * 0.85)
    assert smoothed[1] == 0.85
    assert smoothed[2] >= 0.85 * 0.85

def test_render_spectrum_video_smoke(tmp_path, sine_wav):
    """End-to-end: 5s sine → spectrum.webm at expected duration."""
    a = sine_wav("a", dur=5.0, freq=1000)
    out = render_spectrum_bars_video(
        music_wav=str(a), out_path=tmp_path / "spec.webm",
        total_duration_s=5.0, canvas_w=1920, canvas_h=1080,
        height_pct=0.12, color_hex="#ffffff",
    )
    assert out.is_file()
    dur = _ffprobe_duration(out)
    assert 4.9 <= dur <= 5.2

def test_cache_skip_when_output_newer_than_input(tmp_path, sine_wav):
    """Second call with same inputs reuses the cached output."""
    a = sine_wav("a", dur=2.0, freq=440)
    out_path = tmp_path / "spec.webm"
    out1 = render_spectrum_bars_video(str(a), out_path, 2.0, 1920, 1080, 0.12, "#ffffff")
    mtime1 = out_path.stat().st_mtime
    out2 = render_spectrum_bars_video(str(a), out_path, 2.0, 1920, 1080, 0.12, "#ffffff")
    assert out_path.stat().st_mtime == mtime1  # not re-rendered
```

### Existing tests — adjustments

`tests/test_spectrum_filter.py`:
- No changes needed; `build_spectrum_filter` keeps its current behavior (always returns the classic filtergraph when `enabled=True`).
- Caller in `_render_landscape_music` now only calls it when `spectrum_style == 'classic'`.

`tests/test_music_render_smoke.py`:
- Add a third smoke test with `spectrum_style='bars'`, asserts spectrum.webm is generated and final MP4 has the right duration.

### Manual QA

- Render a 30s music video with `spectrum_style='bars'`; visually confirm:
  - 50 distinct white bars with visible gaps
  - Rounded corners on bar tops
  - Bars react to music (bass → low-index bars; treble → high-index bars)
  - No jitter (smoothing visible)
- Render the same video with `spectrum_style='classic'`; verify still matches old look (regression check)
- 1h+ video with bars: pre-render completes within budget

## Out of scope (deferred)

- Mirror-mode bars (symmetric from center line)
- Color gradients / per-bar colors
- Glow / blur effects
- Real-time preview in the console
- Logarithmic vs linear amplitude curve selection (locked to log via `np.log1p`)
- Mobile / vertical-format Shorts variant
- Multi-pass rendering optimization (parallelize bar rendering across CPU cores)

## Open questions resolved during brainstorming

| Question | Decision |
|---|---|
| Replace classic or add as option | Add as `spectrum_style` enum, default `'classic'` |
| Pre-render vs ffmpeg-native | Pre-render — ffmpeg has no native filter for rounded-corner fixed-count bars |
| Optimization aggressiveness | NumPy slicing + raw frame pipe + 15fps spectrum |
| FFT library | scipy.signal.stft (already a transitive dep) — no new dependency |
| Bar count, gap, color, corner radius | 50 bars, 2px gap, white default (configurable via `spectrum_color`), 2px radius |
| Bar growth direction | Single direction, upward from baseline (no mirror) |
| Frequency scale | Log (60Hz – 16kHz via `np.geomspace`) |
| Smoothing | Exponential decay with factor 0.85 (raw value or 85% of previous, whichever is higher) |
| Caching | Skip pre-render when output mtime >= input mtime |
| Where the bars classic toggle lives | New `spectrum_style` field on `youtube_videos`, new SpectrumPanel select |
