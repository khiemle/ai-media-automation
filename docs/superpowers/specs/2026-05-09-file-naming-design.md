# File Naming Convention — Design Spec

**Date:** 2026-05-09  
**Scope:** Library assets (SFX, music, images, videos) + pipeline output files  
**Backward compatibility:** Existing files keep their current names; new rule applies to newly imported/generated files only.

---

## Problem

All file types currently use database ID as filename:
- `sfx_10.mp3`, `1.mp3`, `asset_42.mp4`, `yt_28_1777979768.png`

These are unreadable and unusable outside the system (e.g., when reviewing files in Finder or passing them to another tool).

---

## Core Naming Algorithm

A single shared utility: `console/backend/utils/file_naming.py`

**Function:** `make_filename(title: str, ext: str, date: date | None = None) -> str`

**Steps:**
1. Apply `unidecode(title)` — removes Vietnamese and all Unicode diacritics (e.g., "Tiếng mưa" → "Tieng mua")
2. Lowercase
3. Replace `—`, `–`, `&` with `-`
4. Strip all non-alphanumeric except `-`
5. Collapse multiple `-` → single `-`, trim leading/trailing `-`
6. Prepend `{YYYYMMDD}_` if date is provided (default: today)
7. Append `{ext}` (must include leading dot)

**Collision handling:** If the resulting path already exists on disk, append `_2`, `_3`, etc. before the extension.

**Examples:**
```
"Tiếng mưa rơi trên mái hiên gần"   → 20260509_tieng-mua-roi-tren-mai-hien-gan.mp3
"Distant Izakaya Laughter — Very Muffled" → 20260509_distant-izakaya-laughter-very-muffled.mp3
"Rainy Tokyo Night Ambience — City Rain & Distant Trains" → 20260509_rainy-tokyo-night-ambience-city-rain-distant-trains.mp3
"Narrow Tokyo back alley at night..." (first 8 words) → 20260509_narrow-tokyo-back-alley-at-night-in-steady.png
```

**Dependency:** `unidecode` (add to `requirements.txt` if not present).

---

## Library Asset Naming Rules

All library assets use: `{YYYYMMDD}_{slug(title)}{ext}`

The **title** is the display name shown in the UI / modal — the same value already stored in the DB `title` column.

| Asset type | Service file | Current pattern | New pattern | Title source |
|---|---|---|---|---|
| SFX (import) | `sfx_service.py` | `sfx_{id}.mp3` | `20260509_tieng-mua-roi-tren-mai-hien-gan.mp3` | `title` form field |
| SFX (ElevenLabs generated) | `routers/sfx.py` | `sfx_{id}.mp3` | same rule | `title` form field |
| Music (import) | `music_service.py` | `{id}.mp3` | `20260509_rainy-tokyo-night-ambience.mp3` | `title` param |
| Music (Suno/Lyria generated) | `music_service.py` | `{id}.mp3` | same rule | `title` param |
| Image (import or Midjourney) | `production_service.py` | `asset_{id}.png` | `20260509_narrow-tokyo-back-alley-night.png` | `title` field; fallback: first 8 words of description/prompt |
| Video (import or Runway) | `production_service.py` | `asset_{id}.mp4` | `20260509_locked-off-tripod-rain-loop.mp4` | `title` field; fallback: first 8 words of prompt |
| Thumbnail source (Midjourney upload) | `routers/youtube_videos.py` | `yt_{id}_{ts}.png` | `20260509_thumbnail-source.png` (+ collision suffix if needed) | fixed label "thumbnail-source" |
| Thumbnail generated | `routers/youtube_videos.py` | `yt_{id}.png` | `20260509_thumbnail.png` | fixed label "thumbnail" |

### Code changes — library assets

Three service files, one-liner change each:

**`sfx_service.py` line ~75:**
```python
# before
dest = sfx_dir / f"sfx_{row.id}{ext}"
# after
from console.backend.utils.file_naming import make_filename
dest = sfx_dir / make_filename(title, ext)
```

**`music_service.py` line ~253:**
```python
# before
dest = MUSIC_DIR / f"{track.id}{extension}"
# after
from console.backend.utils.file_naming import make_filename
dest = MUSIC_DIR / make_filename(title, extension)
```

**`production_service.py` line ~209:**
```python
# before
dest = save_dir / f'asset_{row.id}{ext}'
# after
from console.backend.utils.file_naming import make_filename
label = title or Path(filename).stem  # title param passed from router
dest = save_dir / make_filename(label, ext)
```

**`routers/youtube_videos.py` lines ~429, ~488:**
```python
# thumbnail source (line ~429)
# before: save_path = save_dir / f"yt_{video_id}_{int(time.time())}{ext}"
# after:
from console.backend.utils.file_naming import make_filename
save_path = save_dir / make_filename("thumbnail-source", ext)

# thumbnail generated (line ~488)
output_path = thumb_dir / make_filename("thumbnail", ".png")
```

---

## Pipeline Output Files

### Output directory

The per-script output directory currently named `script_{id}` is renamed to use the `YoutubeVideo.title` field:

| Current | New |
|---|---|
| `assets/output/script_{id}/` | `assets/output/{YYYYMMDD}_{slug(youtube_video_title)}/` |

Example: `assets/output/20260509_rainy-tokyo-night-ambience-city-rain-distant-trains/`

If two videos share the same title slug, collision suffix `_2` is appended.

### Files inside the output directory

The directory name provides all context; files use short positional names:

| Current | New |
|---|---|
| `audio_0.wav` | `scene-0_narration.wav` |
| `audio_1.wav` | `scene-1_narration.wav` |
| `audio_{N}.wav` | `scene-{N}_narration.wav` |
| `overlay_0.png` | `scene-0_overlay.png` |
| `overlay_{N}.png` | `scene-{N}_overlay.png` |
| `raw_video.mp4` | `raw.mp4` |
| `video_final.mp4` | `final.mp4` |
| `raw_video.srt` | `subtitles.srt` |
| `audio_0.srt` | `scene-0_subtitles.srt` |
| `subtitles.ass` | `subtitles.ass` (unchanged) |

### Code changes — pipeline output

Two places construct the output directory (both need updating):

**`pipeline/composer.py` line 50** — main pipeline path:
```python
# before
out_dir = Path(OUTPUT_PATH) / f"script_{script_id}"
# after — needs script title passed in or looked up from DB
out_dir = Path(OUTPUT_PATH) / make_filename(script_title, "")
```

**`console/backend/tasks/production_tasks.py` line 112** — console task path:
```python
# before
out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / str(script_id)
# after
out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / make_filename(script_title, "")
```

In both cases `script_title` comes from `GeneratedScript` → `YoutubeVideo.title` (or falls back to `f"script-{script_id}"` if no video title is linked yet).

Per-file fragments to update in `pipeline/composer.py`:
```python
# line 93
audio_path = out_dir / f"scene-{idx}_narration.wav"   # was: audio_{idx}.wav
# line 130
overlay_path = out_dir / f"scene-{idx}_overlay.png"   # was: overlay_{idx}.png
# line 70
raw_video_path = out_dir / "raw.mp4"                   # was: raw_video.mp4
```

`pipeline/renderer.py` — update the output filename from `video_final.mp4` → `final.mp4`.  
`pipeline/caption_gen.py` — update srt filenames: `raw_video.srt` → `subtitles.srt`, `audio_{N}.srt` → `scene-{N}_subtitles.srt`.

---

## Backward Compatibility

- All existing files on disk keep their current names unchanged.
- The DB `file_path` column stores the absolute path, so old `sfx_10.mp3` and new `20260509_tieng-mua-roi-tren-mai-hien-gan.mp3` coexist without conflict.
- No migration script required.

---

## Dependencies

- `unidecode` — add to `requirements.txt` (and `console/requirements.txt` if separate).
- No other new dependencies.

---

## Files to Create / Modify

| Action | File |
|---|---|
| **Create** | `console/backend/utils/__init__.py` (if not exists) |
| **Create** | `console/backend/utils/file_naming.py` |
| **Modify** | `console/backend/services/sfx_service.py` |
| **Modify** | `console/backend/services/music_service.py` |
| **Modify** | `console/backend/services/production_service.py` |
| **Modify** | `console/backend/routers/youtube_videos.py` |
| **Modify** | `pipeline/composer.py` (output dir + audio/overlay/raw paths) |
| **Modify** | `pipeline/renderer.py` (`video_final.mp4` → `final.mp4`) |
| **Modify** | `pipeline/caption_gen.py` (srt filenames) |
| **Modify** | `console/backend/tasks/production_tasks.py` (output dir construction) |
| **Modify** | `requirements.txt` / `console/requirements.txt` — add `unidecode` |
