# Music Video YouTube Template — Design

**Date:** 2026-05-10
**Status:** Draft (pending user review)
**Author:** Brainstorming session with khiemlq@gmail.com

## Goal

Add a third YouTube video template — `music` — alongside the existing `asmr` and `soundscape` templates. The music template publishes a curated playlist of music tracks over a static (or playlist) visual, with three additions that don't exist in the current templates:

1. YouTube **chapter timestamps** in the upload description, one chapter per music track
2. An on-screen **now-playing playlist overlay** that switches as tracks change
3. An optional **audio spectrum visualizer** (ffmpeg-rendered)

The template removes three features that don't apply to music: SFX layer config, target-duration selection (derived from the playlist), and the blackout/fade-to-black control.

## Non-goals

- Animated overlays (pulsing dot, per-track progress bar)
- Custom spectrum modes beyond ffmpeg `showfreqs mode=bar`
- Per-track volume normalization (LUFS)
- Music-template Shorts variant — deferred
- Auto-generation of music tracks (handled by existing `music` MCP tool)

## High-level approach

The repo already supports almost everything needed: multi-track music (`YoutubeVideo.music_track_ids`), visual playlists (`visual_asset_ids`), the ffmpeg render pipeline. This spec is mostly assembly + three new pieces of work:

- **Data model** — one new template row, eight new columns on `youtube_videos`, one new `ui_features` flag column on `video_templates` for generic UI gating
- **Render pipeline** — track-transition modes (gapless / crossfade / gap), now-playing PNG overlay, optional ffmpeg `showfreqs` spectrum
- **Uploader** — chapter block injected at top of YouTube description when ≥3 tracks
- **Frontend** — template-driven UI, hides asmr/soundscape-only panels for music, shows playlist + transition + overlay + spectrum panels
- **MCP** — exposes new fields automatically; one new read-only `get_chapters` action for debugging

## Data model

### Alembic migration `017_music_template.py`

**`video_templates` changes:**

```sql
ALTER TABLE video_templates
  ADD COLUMN ui_features JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE video_templates
   SET ui_features = '["sfx_panel", "duration_picker", "blackout"]'::jsonb
 WHERE slug IN ('asmr', 'soundscape');

INSERT INTO video_templates (slug, label, output_format, target_duration_h,
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
);
```

Prompt template fields are left null at migration time and edited via the admin UI.

**`youtube_videos` changes:**

```sql
ALTER TABLE youtube_videos
  ADD COLUMN track_transition          VARCHAR(20)  NOT NULL DEFAULT 'gapless',
  ADD COLUMN track_transition_seconds  REAL         NOT NULL DEFAULT 2.0,
  ADD COLUMN playlist_overlay_style    VARCHAR(20),
  ADD COLUMN spectrum_enabled          BOOLEAN      NOT NULL DEFAULT FALSE,
  ADD COLUMN spectrum_position         VARCHAR(10)  NOT NULL DEFAULT 'bottom',
  ADD COLUMN spectrum_height_pct       REAL         NOT NULL DEFAULT 0.12,
  ADD COLUMN spectrum_color            VARCHAR(9)   NOT NULL DEFAULT '#ffffff',
  ADD COLUMN spectrum_opacity          REAL         NOT NULL DEFAULT 0.6;

ALTER TABLE youtube_videos
  ADD CONSTRAINT track_transition_valid
    CHECK (track_transition IN ('gapless', 'crossfade', 'gap')),
  ADD CONSTRAINT playlist_overlay_style_valid
    CHECK (playlist_overlay_style IS NULL
           OR playlist_overlay_style IN ('chip', 'sidebar', 'bottom_bar')),
  ADD CONSTRAINT spectrum_position_valid
    CHECK (spectrum_position IN ('bottom', 'center')),
  ADD CONSTRAINT spectrum_height_pct_range
    CHECK (spectrum_height_pct > 0.0 AND spectrum_height_pct <= 0.5),
  ADD CONSTRAINT spectrum_opacity_range
    CHECK (spectrum_opacity >= 0.0 AND spectrum_opacity <= 1.0),
  ADD CONSTRAINT track_transition_seconds_range
    CHECK (track_transition_seconds >= 0.5 AND track_transition_seconds <= 10.0);
```

### Pydantic schemas

`console/backend/schemas/youtube_video.py`:

```python
TrackTransition  = Literal["gapless", "crossfade", "gap"]
OverlayStyle     = Literal["chip", "sidebar", "bottom_bar"]
SpectrumPosition = Literal["bottom", "center"]

class YoutubeVideoCreate(BaseModel):
    # ... existing fields ...
    track_transition: TrackTransition = "gapless"
    track_transition_seconds: float = 2.0
    playlist_overlay_style: OverlayStyle | None = None
    spectrum_enabled: bool = False
    spectrum_position: SpectrumPosition = "bottom"
    spectrum_height_pct: float = 0.12
    spectrum_color: str = "#ffffff"
    spectrum_opacity: float = 0.6
```

Response schema gains `total_duration_s: float | None` — computed by the service when the template is `music`.

### Service-layer validation

When the template is `music`, the service rejects requests that set:

- `target_duration_h` — 400, "music template derives duration from tracks"
- `black_from_seconds` — 400, "music template does not support blackout"
- `sound_layers`, `sfx_overrides`, `sfx_pool` — 400, "music template does not support SFX layers"

Other validation:

- `music_track_ids` length must be ≥ 1 (400 if empty)
- If `playlist_overlay_style` is set with only 1 track → silently null it, return `field_warnings: ["overlay hidden for single-track playlists"]`
- `crossfade` with `track_transition_seconds > shortest_track_duration / 2` → 400, "crossfade exceeds half the shortest track duration"

For `asmr` / `soundscape`, no new validation — the new columns are unused.

### Backwards compatibility

- Existing videos: all new columns get defaults, no data migration needed.
- `ui_features` is backfilled for asmr/soundscape so the existing UI keeps working unchanged.

## Render pipeline

### Branch in `pipeline/youtube_ffmpeg.py:render_landscape`

A new helper `_resolve_music_tracks(video, db)` returns the ordered list of `MusicTrack` rows for `video.music_track_ids`, preserving order and erroring if any ID is missing.

```python
if video.template.slug == 'music':
    music_tracks = _resolve_music_tracks(video, db)
    total_dur_s, boundaries = _compute_music_total_duration(
        music_tracks, video.track_transition, video.track_transition_seconds
    )
    music_wav = _build_music_playlist_wav_with_transitions(
        music_tracks, total_dur_s, video.track_transition,
        video.track_transition_seconds, output_dir, start_s
    )
    sound_layers_wav = None
    blackout_filter  = ""
    overlay_segments = (
        _build_now_playing_overlay(video, music_tracks, boundaries,
                                   total_dur_s, output_dir)
        if video.playlist_overlay_style and len(music_tracks) >= 2
        else []
    )
else:
    # existing asmr/soundscape path, unchanged
    ...
```

`render_parts` chunked rendering still works — `start_s` / `end_s` clip the overlay `enable=between(t,...)` windows.

### Duration math

```python
def _compute_music_total_duration(tracks, transition, transition_s) -> tuple[float, list[float]]:
    """Returns (total_seconds, track_boundary_seconds_list)."""
    if not tracks:
        return 0.0, []
    boundaries = [0.0]
    if transition == 'gapless' or len(tracks) == 1:
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + t.duration_s)
        total = boundaries[-1] + tracks[-1].duration_s
    elif transition == 'crossfade':
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + t.duration_s - transition_s)
        total = boundaries[-1] + tracks[-1].duration_s
    elif transition == 'gap':
        for t in tracks[:-1]:
            boundaries.append(boundaries[-1] + t.duration_s + transition_s)
        total = boundaries[-1] + tracks[-1].duration_s
    return total, boundaries
```

If a `MusicTrack.duration_s` is null at render time, the service runs `ffprobe` once and persists the value. A second null on the same track is a hard render error.

### Audio assembly

`_build_music_playlist_wav_with_transitions` mixes the playlist into a single WAV at the target sample rate (44.1kHz):

- `gapless` — ffmpeg `concat` filter
- `crossfade` — ffmpeg `acrossfade` filter chained pairwise (`d=transition_seconds`)
- `gap` — ffmpeg `aevalsrc=0` silence insertions between tracks

Returns `(wav_path, boundaries)`. Boundaries are reused for both chapter generation and overlay segment timing.

### Now-playing PNG overlay

New module `pipeline/music_overlay.py`:

```python
@dataclass
class OverlaySegment:
    png_path: Path
    start_s: float
    end_s: float

def build_now_playing_overlay(
    video: YoutubeVideo,
    tracks: list[MusicTrack],
    boundaries: list[float],
    total_duration_s: float,
    output_dir: Path,
    canvas_w: int = 1920,
    canvas_h: int = 1080,
) -> list[OverlaySegment]: ...
```

One PNG per track, rendered with Pillow:

- Transparent RGBA at full canvas resolution (1920×1080)
- Composed widget anchored per style with proper padding
- Cached on disk in `output_dir` by filename `overlay_{style}_{track_index}_{playlist_sha1}.png`, where `playlist_sha1` hashes the ordered list of `(track_id, track_title)` tuples — so the cache invalidates automatically if a track is renamed or the playlist changes
- Font: IBM Plex Sans (already in project), system fallback

**Style: `chip`**

- Bottom-left, 4% margin
- Pill, `rgba(10,14,28,0.55)` background, 1px white-10% border, 999px radius
- Static dot (no animation), violet `#7c6af7`
- Text: `{i+1} / {n} · {title}` truncated at 40 chars

**Style: `sidebar`**

- Right side, vertically centered, 3% margin
- 28% canvas width
- `rgba(8,10,20,0.45)` background, 1px white-8% border, 8px radius
- Header: `Playlist · {n} tracks`
- Per row: marker (`✓` played, `▶` current, number for upcoming) + title (truncated at 30 chars)
- For >8 tracks: show 4 around the current one with `…` markers above/below

**Style: `bottom_bar`**

- Bottom-center, 6% margin
- 60% canvas width
- `rgba(8,10,20,0.55)` background, 1px white-8% border, 6px radius
- Single line: `Track {i+1} / {n} · {title} · {track_duration}`
- **No animated progress bar in v1.** A future iteration can use ffmpeg `drawbox` with time expressions.

### Spectrum visualizer

When `video.spectrum_enabled`, the filtergraph adds:

```
[1:a]showfreqs=mode=bar:ascale=log:fscale=log:cmode=combined:
              win_size=2048:colors={hex_no_alpha}:
              size={W}x{spectrum_height_px}[spec_raw];
[spec_raw]format=rgba,colorchannelmixer=aa={opacity}[spec];
[base][spec]overlay=0:{y_position}[v_with_spec];
```

Where:
- `spectrum_height_px = int(canvas_h * spectrum_height_pct)`
- `y_position = canvas_h - spectrum_height_px` (bottom) or `(canvas_h - spectrum_height_px) // 2` (center)

### Filtergraph composition

Single ffmpeg pipeline, single render pass:

```
[0:v]<visual_chain>[base];
# Spectrum overlay (conditional)
[base][spec]overlay=0:y_pos[v_with_spec];
# Now-playing PNG overlays (conditional, one per track)
[v_with_spec][2:v]overlay=…:enable='between(t,0,180.5)'[v1];
[v1][3:v]overlay=…:enable='between(t,180.5,420.0)'[v2];
[v2][4:v]overlay=…:enable='between(t,420.0,720.0)'[final_v];
```

Each PNG is `-loop 1 -i overlay_N.png`. Only one is "active" at a time (no per-frame cost beyond the active overlay).

### Render budget warning

The service surfaces a soft warning (not a block) on response:

```python
if total_duration_s > 4 * 3600 and video.spectrum_enabled and video.playlist_overlay_style:
    warnings.append("Long video with spectrum + overlay; consider chunked render")
```

The existing `render_parts` chunking already handles long renders.

## Chapters and uploader

### Chapter generation

New helper in `console/backend/services/youtube_video_service.py`:

```python
def build_chapters(video: YoutubeVideo, db) -> list[dict] | None:
    if video.template.slug != 'music':
        return None
    tracks = _resolve_music_tracks(video, db)
    if len(tracks) < 3:                                # YouTube minimum
        return None
    _, boundaries = _compute_music_total_duration(
        tracks, video.track_transition, video.track_transition_seconds
    )
    return [
        {"seconds": int(round(boundaries[i])),
         "title": tracks[i].title or f"Track {i+1}"}
        for i in range(len(tracks))
    ]
```

Empty/missing track titles fall back to `"Track {i+1}"` with a warning logged. Long-term, the music tool should validate titles on save, but this is a defensive fallback.

### Description format

In `uploader/youtube_uploader.py`, `_build_description()` accepts an optional `chapters` list:

```python
def _build_description(self, body: str, chapters: list[dict] | None = None,
                       hashtags: list[str] | None = None) -> str:
    parts = []
    if chapters and len(chapters) >= 3:
        parts.append(_format_chapters(chapters))
        parts.append("")
    parts.append(body)
    if hashtags:
        parts.append("")
        parts.append(" ".join(f"#{h}" for h in hashtags))
    return "\n".join(parts)

def _format_chapters(chapters: list[dict]) -> str:
    lines = []
    for i, ch in enumerate(chapters):
        ts = 0 if i == 0 else ch["seconds"]            # YouTube requires 0:00 first
        lines.append(f"{_fmt_timestamp(ts)} {ch['title']}")
    return "\n".join(lines)

def _fmt_timestamp(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
```

Output examples:

```
0:00 Moonlit Stream
4:32 Hollow Echoes
9:18 Forest Veil

<existing description body>
```

For long-form (≥1h):

```
0:00 Moonlit Stream
1:12:30 Hollow Echoes
2:45:08 Forest Veil
```

### Upload Celery task wiring

`console/backend/tasks/upload_tasks.py:upload_to_channel_task`:

- Calls `youtube_video_service.build_chapters(video, db)` before constructing the YouTube API request
- Passes result to `youtube_uploader.upload_video(..., chapters=chapters)`
- For non-music templates, `build_chapters` returns `None` → no change in behavior

### Edge cases

| Case | Behavior |
|------|----------|
| Music template, 1 track | No chapters injected |
| Music template, 2 tracks | No chapters injected (YouTube wouldn't render them) |
| Music template, 3+ tracks, empty title on one track | Substitute `"Track {i+1}"`, log warning |
| Track title with leading timestamp e.g. `"0:30 - Intro"` | Pass through; YouTube parses by line position |
| Total duration > 11h59m | Format degrades to `12:34:56 Title` — no special handling needed |
| Crossfade math | Boundaries account for overlap; chapter for track 2 starts when track 1's audio has crossfaded under track 2's |

## MCP tool surface

`console/mcp/tools/youtube_video.py`:

1. The CRUD tool already accepts arbitrary kwargs forwarded to FastAPI — the 8 new fields work automatically. Update the docstring with a "Music template fields" section.
2. New action `get_chapters {video_id}` — read-only, returns the chapter list that *would* be uploaded. Wraps `build_chapters()`. Useful for debugging multi-hour videos without triggering an upload.

`console/mcp/tools/music.py`: no changes required.

## Frontend

### Template-driven rendering

The existing YouTube create page reads `template.ui_features` to gate panels:

```jsx
const features = new Set(template.ui_features ?? []);
{features.has('sfx_panel')      && <SfxPanel ... />}
{features.has('duration_picker') && <DurationPicker ... />}
{features.has('blackout')       && <BlackoutPanel ... />}

{template.slug === 'music' && (
  <>
    <MusicPlaylistPicker ... />
    <TransitionPanel ... />
    <OverlayStylePicker ... />
    <SpectrumPanel ... />
  </>
)}
```

Hard-coding `template.slug === 'music'` is acceptable here since the panels are music-specific (not just a hidden/shown variant). Generalize when a fourth template arrives.

### Music-only panels

**1. Music playlist picker**

- Multi-select from `music_tracks`, drag-to-reorder
- Per-row: title, niche tag, duration, ✕ remove
- Live footer: `Total: 1h 24m · 5 tracks` (recomputes on transition mode change)

**2. Transition mode**

- Three radio buttons: Gapless / Crossfade / Gap
- Numeric input for `track_transition_seconds` (range 0.5–10, default 2.0), shown only for crossfade or gap

**3. Now-playing overlay**

- Four radio buttons: None / Chip / Sidebar / Bottom bar
- Each option has a 120×68 thumbnail preview generated server-side and cached
- Disabled with helper text "Single track — overlay hidden automatically" when `music_track_ids.length < 2`

**4. Spectrum visualizer (collapsible)**

- Toggle: Enabled / Disabled (default off)
- When enabled: Position (bottom/center), Height % slider (5–50), Color picker, Opacity slider

### Visual asset selection

Reuses the existing visual asset picker (single asset or `visual_asset_ids` playlist already supported by the render pipeline).

## Error handling

### Service layer

| Failure | Response |
|---------|----------|
| Music template, empty `music_track_ids` | 400, "music template requires at least 1 music track" |
| `target_duration_h` set on music template | 400, "music template derives duration from tracks; remove target_duration_h" |
| `black_from_seconds` set on music template | 400, "music template does not support blackout" |
| `sound_layers` / `sfx_overrides` / `sfx_pool` set on music template | 400, "music template does not support SFX layers" |
| `playlist_overlay_style` set with 1 track | Silently null it, return `field_warnings` |
| `crossfade` with `transition_seconds > shortest_track / 2` | 400, "crossfade exceeds half the shortest track duration" |
| `MusicTrack.duration_s` null at render time | Service runs ffprobe + persists; second null = render error |
| Spectrum + overlay + >4h video | Soft warning in API response, no block |

### Render task

| Failure | Response |
|---------|----------|
| ffmpeg `showfreqs` filter unavailable | Hard fail at preflight with clear message |
| PNG generation fails (Pillow / font error) | Render fails, logs failing track index, no partial outputs |
| Visual shorter than music duration | Existing loop logic handles it |

## Testing

### Unit tests

`tests/test_music_overlay.py`:
- PNG renderer for each style produces transparent RGBA at canvas size
- Sidebar with >8 tracks shows ellipsis truncation
- Title truncation at 30 / 40 chars per style

`tests/test_chapter_builder.py`:
- 1, 2, 3, 5, 50 tracks → returns `None` for <3, list for ≥3
- Crossfade boundaries differ from gapless boundaries by expected delta
- Empty title falls back to `"Track N"` and logs warning
- First chapter forced to 0:00 even if `boundaries[0] > 0`

`tests/test_youtube_video_service.py`:
- Each rejected-field validation returns 400 with expected message
- Single-track + overlay style → silently nulled
- Total duration computation across the three transition modes

`tests/test_youtube_uploader.py` (mocked YouTube API):
- Description with chapters has chapter block at top
- Description without chapters unchanged
- Format renders `H:MM:SS` for ≥1h, `M:SS` for <1h

### Integration test

`tests/test_music_render_smoke.py`:

End-to-end render of a 30-second music video with 3 short tracks (5s, 10s, 15s), spectrum on, sidebar overlay. Asserts:

- Final MP4 exists
- ffprobe shows 30s ±0.1s duration, video + audio streams present
- PNG segment count matches track count
- Chapters block correctly built with 3 entries

### Manual QA checklist (added to PR)

- 1-track music video → no overlay, no chapters
- 2-track music video → chapters absent in description (verify with YT API dry-run)
- 5-track music video, each overlay style → visual review
- Spectrum on/off render diff
- Verify chapters appear in YouTube Studio after live upload

## Out of scope (explicit)

- Animated overlays (pulsing dot, per-track progress bar)
- Custom spectrum modes beyond `showfreqs mode=bar`
- Per-track volume normalization (LUFS)
- Visual clip transitions (existing `concat_loop` / `per_clip` modes used as-is)
- Auto-generation of music tracks (already handled by `music` MCP tool)
- Music template Shorts variant (different chapter/overlay constraints; deferred)

## Open questions resolved during brainstorming

| Question | Decision |
|----------|----------|
| Track transition mode | Per-video selectable: gapless / crossfade / gap |
| Now-playing overlay style | Per-video selectable: chip / sidebar / bottom_bar / none |
| Spectrum visualizer | Include now as opt-in toggle with raw styling fields |
| Chapter description placement | Top of description, skip if <3 tracks |
| `get_chapters` MCP action | Include — useful for debugging without upload |
| Empty title fallback | `"Track {i+1}"` with warning log |
| First-chapter-must-be-0:00 enforcement | Force in formatter (defensive guard) |
| Animated progress bar in `bottom_bar` style | Drop for v1 — deferred |
| PNG canvas size | Full 1920×1080 RGBA per overlay segment |
| `ui_features` flags | `["sfx_panel", "duration_picker", "blackout"]` for asmr/soundscape; `[]` for music |
