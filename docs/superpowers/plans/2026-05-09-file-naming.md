# File Naming Convention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all ID-based filenames (`sfx_10.mp3`, `1.mp3`, `asset_42.mp4`) with readable date-prefixed slugs derived from the asset title.

**Architecture:** A single `make_filename` / `make_unique_path` utility in `console/backend/utils/file_naming.py` uses `unidecode` to strip Vietnamese and other diacritics, then slugifies the title. Every save site calls this utility instead of constructing `f"{id}.ext"`. Existing files on disk are untouched — only newly saved files use the new names.

**Tech Stack:** Python `unidecode` (new dep), standard `re`, `pathlib.Path`, `datetime.date`.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `console/backend/utils/__init__.py` | package marker |
| Create | `console/backend/utils/file_naming.py` | `_slugify`, `make_filename`, `make_unique_path` |
| Create | `tests/console/backend/utils/test_file_naming.py` | unit tests for the utility |
| Modify | `console/requirements.txt` | add `unidecode` |
| Modify | `requirements.pipeline.txt` | add `unidecode` |
| Modify | `console/backend/services/sfx_service.py:75` | `sfx_{id}.ext` → `make_unique_path(title, ext, sfx_dir)` |
| Modify | `console/backend/services/music_service.py:253` | `{id}.ext` → `make_unique_path(title, ext, MUSIC_DIR)` |
| Modify | `console/backend/tasks/music_tasks.py:61,108,190` | same for Suno/Lyria/ElevenLabs generated tracks |
| Modify | `console/backend/services/production_service.py:209` | `asset_{id}.ext` → `make_unique_path(label, ext, save_dir)` |
| Modify | `console/backend/routers/production.py:338` | Runway `output_filename` |
| Modify | `console/backend/tasks/runway_task.py:86` | Runway recovery re-queue filename |
| Modify | `console/backend/routers/youtube_videos.py:429,488` | thumbnail source + generated paths |
| Modify | `pipeline/composer.py:50,70,93,130` | output dir + raw/audio/overlay filenames |
| Modify | `console/backend/tasks/production_tasks.py:112,114` | out_dir + audio_path for TTS regen task |
| Modify | `pipeline/renderer.py:203` | `video_final.mp4` → `final.mp4` |
| Modify | `console/backend/tasks/youtube_render_task.py:117,180,238` | YouTube long render output paths |
| Modify | `console/backend/tasks/youtube_short_render_task.py:59` | YouTube short render output path |

---

## Task 1: Add `unidecode` dependency

**Files:**
- Modify: `console/requirements.txt`
- Modify: `requirements.pipeline.txt`

- [ ] **Step 1: Add unidecode to both requirements files**

In `console/requirements.txt`, add on its own line:
```
unidecode>=1.3
```

In `requirements.pipeline.txt`, add on its own line:
```
unidecode>=1.3
```

- [ ] **Step 2: Install in your active environment**

```bash
pip install unidecode
```
Expected: `Successfully installed unidecode-1.3.x`

- [ ] **Step 3: Commit**

```bash
git add console/requirements.txt requirements.pipeline.txt
git commit -m "chore: add unidecode dependency for file naming slugs"
```

---

## Task 2: Create `make_filename` / `make_unique_path` utility

**Files:**
- Create: `console/backend/utils/__init__.py`
- Create: `console/backend/utils/file_naming.py`
- Create: `tests/console/backend/utils/test_file_naming.py`

- [ ] **Step 1: Write failing tests**

Create `tests/console/backend/utils/test_file_naming.py`:

```python
import pytest
from datetime import date
from pathlib import Path
from console.backend.utils.file_naming import make_filename, make_unique_path


FIXED_DATE = date(2026, 5, 9)


def test_make_filename_ascii():
    result = make_filename("Distant Izakaya Laughter — Very Muffled", ".mp3", FIXED_DATE)
    assert result == "20260509_distant-izakaya-laughter-very-muffled.mp3"


def test_make_filename_vietnamese():
    result = make_filename("Tiếng mưa rơi trên mái hiên gần", ".mp3", FIXED_DATE)
    assert result == "20260509_tieng-mua-roi-tren-mai-hien-gan.mp3"


def test_make_filename_ampersand():
    result = make_filename("City Rain & Distant Trains", ".mp3", FIXED_DATE)
    assert result == "20260509_city-rain-and-distant-trains.mp3"


def test_make_filename_long_dash():
    result = make_filename("Rainy Tokyo Night Ambience — City Rain", ".mp3", FIXED_DATE)
    assert result == "20260509_rainy-tokyo-night-ambience-city-rain.mp3"


def test_make_filename_no_ext():
    result = make_filename("Rainy Tokyo Night", "", FIXED_DATE)
    assert result == "20260509_rainy-tokyo-night"


def test_make_filename_defaults_to_today():
    result = make_filename("test", ".wav")
    today = date.today().strftime("%Y%m%d")
    assert result.startswith(today)


def test_make_filename_empty_title():
    result = make_filename("", ".mp3", FIXED_DATE)
    assert result == "20260509_untitled.mp3"


def test_make_unique_path_no_collision(tmp_path):
    p = make_unique_path("Rain Loop", ".mp3", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rain-loop.mp3"


def test_make_unique_path_collision(tmp_path):
    (tmp_path / "20260509_rain-loop.mp3").touch()
    p = make_unique_path("Rain Loop", ".mp3", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rain-loop_2.mp3"


def test_make_unique_path_multiple_collisions(tmp_path):
    (tmp_path / "20260509_rain-loop.mp3").touch()
    (tmp_path / "20260509_rain-loop_2.mp3").touch()
    p = make_unique_path("Rain Loop", ".mp3", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rain-loop_3.mp3"


def test_make_unique_path_directory(tmp_path):
    p = make_unique_path("Rainy Tokyo Night", "", tmp_path, FIXED_DATE)
    assert p == tmp_path / "20260509_rainy-tokyo-night"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/console/backend/utils/test_file_naming.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError` or `ImportError` — `file_naming` doesn't exist yet.

- [ ] **Step 3: Create the package marker**

Create `console/backend/utils/__init__.py` as an empty file.

- [ ] **Step 4: Implement `file_naming.py`**

Create `console/backend/utils/file_naming.py`:

```python
import re
from datetime import date
from pathlib import Path

from unidecode import unidecode


def _slugify(text: str) -> str:
    text = unidecode(text)
    text = text.lower()
    text = re.sub(r'[—–]', '-', text)
    text = re.sub(r'&', 'and', text)
    text = re.sub(r'[^a-z0-9-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def make_filename(title: str, ext: str, for_date: date | None = None) -> str:
    """Return a readable filename: YYYYMMDD_{slug}{ext}.

    Args:
        title: Human-readable name (Vietnamese or ASCII).
        ext:   File extension including leading dot, e.g. ".mp3". Pass "" for directories.
        for_date: Date prefix; defaults to today.
    """
    d = for_date or date.today()
    slug = _slugify(title)
    if not slug:
        slug = "untitled"
    return f"{d.strftime('%Y%m%d')}_{slug}{ext}"


def make_unique_path(title: str, ext: str, directory: Path, for_date: date | None = None) -> Path:
    """Return a unique Path in directory using the title slug.

    Appends _2, _3, ... before the extension if the base name already exists.
    """
    base = make_filename(title, ext, for_date)
    stem = Path(base).stem  # date_slug without ext
    candidate = directory / base
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
python -m pytest tests/console/backend/utils/test_file_naming.py -v
```
Expected: all 12 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add console/backend/utils/__init__.py console/backend/utils/file_naming.py tests/console/backend/utils/test_file_naming.py
git commit -m "feat: add make_filename/make_unique_path utility for readable file names"
```

---

## Task 3: Update SFX import naming

**Files:**
- Modify: `console/backend/services/sfx_service.py`

The current line 75:
```python
dest = sfx_dir / f"sfx_{row.id}{ext}"
```
The `title` parameter is already in scope — it's the first argument to `import_sfx`.

- [ ] **Step 1: Update `sfx_service.py`**

In `console/backend/services/sfx_service.py`, change the top imports to add:
```python
from console.backend.utils.file_naming import make_unique_path
```

Then replace line 75:
```python
# before
dest = sfx_dir / f"sfx_{row.id}{ext}"
# after
dest = make_unique_path(title, ext, sfx_dir)
```

- [ ] **Step 2: Smoke-test via the API**

```bash
# Start the dev server if not running, then:
curl -X POST http://localhost:8080/api/sfx/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "title=Heavy Rain on Glass" \
  -F "sound_type=background" \
  -F "file=@/tmp/test.wav"
```
Expected response: `file_path` contains `..._heavy-rain-on-glass.wav` (not `sfx_N.wav`).

- [ ] **Step 3: Commit**

```bash
git add console/backend/services/sfx_service.py
git commit -m "feat: use readable slug filename for SFX imports"
```

---

## Task 4: Update music service import naming

**Files:**
- Modify: `console/backend/services/music_service.py`

Current line 253:
```python
dest = MUSIC_DIR / f"{track.id}{extension}"
```
`title` is the first parameter of `import_track`.

- [ ] **Step 1: Update `music_service.py`**

Add import at top of file:
```python
from console.backend.utils.file_naming import make_unique_path
```

Replace line 253:
```python
# before
dest = MUSIC_DIR / f"{track.id}{extension}"
# after
dest = make_unique_path(title, extension, MUSIC_DIR)
```

- [ ] **Step 2: Commit**

```bash
git add console/backend/services/music_service.py
git commit -m "feat: use readable slug filename for imported music tracks"
```

---

## Task 5: Update generated music (Suno / Lyria / ElevenLabs) naming

**Files:**
- Modify: `console/backend/tasks/music_tasks.py`

Three places construct a `dest` path using `{track_id}`. In all cases `track["title"]` is already in scope (fetched via `svc.get_track(track_id)` earlier in each function).

- [ ] **Step 1: Update `music_tasks.py` — add import**

Add at top of file:
```python
from console.backend.utils.file_naming import make_unique_path
```

- [ ] **Step 2: Update Suno task (line ~61)**

```python
# before
dest = MUSIC_DIR / f"{track_id}.mp3"
# after
dest = make_unique_path(track["title"], ".mp3", MUSIC_DIR)
```

- [ ] **Step 3: Update Lyria task (line ~108)**

```python
# before
dest = MUSIC_DIR / f"{track_id}.mp3"
# after
dest = make_unique_path(track["title"], ".mp3", MUSIC_DIR)
```

- [ ] **Step 4: Update ElevenLabs compose task (line ~190)**

The ElevenLabs section uses `ext` (determined from response content-type). Find the `dest = MUSIC_DIR / f"{track_id}{ext}"` line in the ElevenLabs task function and replace with:
```python
dest = make_unique_path(track["title"], ext, MUSIC_DIR)
```

- [ ] **Step 5: Commit**

```bash
git add console/backend/tasks/music_tasks.py
git commit -m "feat: use readable slug filename for generated music tracks (Suno/Lyria/ElevenLabs)"
```

---

## Task 6: Update visual asset import naming (images and videos)

**Files:**
- Modify: `console/backend/services/production_service.py`

Current line ~209:
```python
dest = save_dir / f'asset_{row.id}{ext}'
```

The `import_asset` method signature (line ~180) has a `filename` param but no `title`. The router calls it with the uploaded filename only. We need to check what data is available.

- [ ] **Step 1: Read the current `import_asset` signature**

Open `console/backend/services/production_service.py` around lines 175-215 and note:
- Parameters available: `user_id`, `file_bytes`, `filename`, `asset_type`, `source`, `tags`, `description`, `assets_dir`
- The `description` field (free-text from the UI) is the best candidate for the slug; `filename` is a browser file name like `IMG_1234.jpg` which is not useful.

- [ ] **Step 2: Add `title` parameter to `import_asset`**

In `production_service.py`, update the `import_asset` method signature to add `title: str | None = None`:

```python
def import_asset(
    self,
    user_id: int,
    file_bytes: bytes,
    filename: str,
    asset_type: str,
    source: str,
    tags: list[str] | None = None,
    description: str | None = None,
    assets_dir: str | None = None,
    title: str | None = None,          # ← new param
) -> dict:
```

Then update the filename construction (line ~209):
```python
from console.backend.utils.file_naming import make_unique_path

label = title or description or Path(filename).stem
dest = make_unique_path(label, ext, save_dir)
```

- [ ] **Step 3: Pass `title` from the router**

Open `console/backend/routers/production.py`. Find the endpoint that calls `import_asset` (search for `svc.import_asset(`). Add a `title` field to the request form parameters and pass it through:

In the endpoint function signature, add:
```python
title: str | None = Form(default=None),
```

In the `import_asset` call, add:
```python
title=title,
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/production_service.py console/backend/routers/production.py
git commit -m "feat: use readable slug filename for imported visual assets (images/videos)"
```

---

## Task 7: Update Runway generated video naming

**Files:**
- Modify: `console/backend/routers/production.py` (line ~338)
- Modify: `console/backend/tasks/runway_task.py` (line ~86)

- [ ] **Step 1: Update `routers/production.py` — initial Runway dispatch**

Find line ~338:
```python
output_filename = f"runway_{child.id}.mp4"
```

Replace with (use the Runway prompt's first ~80 chars as the slug):
```python
from console.backend.utils.file_naming import make_filename
_prompt_label = (body.prompt or "runway-clip")[:80]
output_filename = make_filename(_prompt_label, ".mp4")
```

- [ ] **Step 2: Update `runway_task.py` — recovery re-queue**

Find line ~86 in `recover_pending_runway()`:
```python
output_filename = f"runway_{row.id}.mp4"
```

Replace with:
```python
from console.backend.utils.file_naming import make_filename
_label = (row.generation_prompt or f"runway-{row.id}")[:80]
output_filename = make_filename(_label, ".mp4")
```

- [ ] **Step 3: Commit**

```bash
git add console/backend/routers/production.py console/backend/tasks/runway_task.py
git commit -m "feat: use readable slug filename for Runway generated videos"
```

---

## Task 8: Update thumbnail naming

**Files:**
- Modify: `console/backend/routers/youtube_videos.py`

Two places:
- Line ~429: thumbnail source upload (`yt_{video_id}_{ts}.ext`)
- Line ~488: thumbnail generate output (`yt_{id}.png`)

- [ ] **Step 1: Update thumbnail source path (line ~429)**

Find the block:
```python
save_path = save_dir / f"yt_{video_id}_{int(time.time())}{ext}"
```

Replace with:
```python
from console.backend.utils.file_naming import make_unique_path
save_path = make_unique_path("thumbnail-source", ext, save_dir)
```

- [ ] **Step 2: Update generated thumbnail path (line ~488)**

Find:
```python
output_path = thumb_dir / f"yt_{video_id}.png"
```
(or similar — search for `generate_thumbnail` call and the `output_path` it uses)

Replace with:
```python
from console.backend.utils.file_naming import make_unique_path
output_path = make_unique_path("thumbnail", ".png", thumb_dir)
```

Note: `thumb_dir` is `Path("assets/thumbnails/generated").resolve()`. Confirm the exact variable name in the file before substituting.

- [ ] **Step 3: Commit**

```bash
git add console/backend/routers/youtube_videos.py
git commit -m "feat: use readable slug filename for video thumbnails"
```

---

## Task 9: Update legacy pipeline output directory and per-scene filenames

**Files:**
- Modify: `pipeline/composer.py` (lines 50, 70, 93, 130)
- Modify: `console/backend/tasks/production_tasks.py` (lines 112, 114)

`GeneratedScript.topic` holds the human-readable topic (e.g., `"rainy_tokyo_night_ambience"`). Both files query `GeneratedScript` before constructing paths.

- [ ] **Step 1: Update `pipeline/composer.py` — output directory**

Add import at top of file:
```python
from console.backend.utils.file_naming import make_unique_path
```

In `compose_video(script_id)`, the script is already fetched into `script` variable. After line 43 (`db.close()`), the `meta`, `scenes`, `video` are extracted from `script_json`. Add a title extraction:

```python
script_title = (script.topic or f"script-{script_id}").strip()
```

Then replace line 50:
```python
# before
out_dir = Path(OUTPUT_PATH) / f"script_{script_id}"
# after
out_dir = make_unique_path(script_title, "", Path(OUTPUT_PATH))
out_dir.mkdir(parents=True, exist_ok=True)
```

Note: `make_unique_path` with `ext=""` returns a path that is the directory itself (no trailing slash), e.g. `Path(".../20260509_rainy-tokyo-night")`. The `.mkdir()` call is already on the next line.

- [ ] **Step 2: Update per-scene filenames in `_process_scene`**

Replace line 93 (audio path):
```python
# before
audio_path = out_dir / f"audio_{idx}.wav"
# after
audio_path = out_dir / f"scene-{idx}_narration.wav"
```

Replace line 130 (overlay path):
```python
# before
overlay_path = out_dir / f"overlay_{idx}.png"
# after
overlay_path = out_dir / f"scene-{idx}_overlay.png"
```

- [ ] **Step 3: Update raw video filename**

Replace line 70:
```python
# before
raw_video_path = out_dir / "raw_video.mp4"
# after
raw_video_path = out_dir / "raw.mp4"
```

- [ ] **Step 4: Update `production_tasks.py` — TTS regen task output dir**

In `regenerate_tts_task`, around line 112:

```python
# before
out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / str(script_id)
out_dir.mkdir(parents=True, exist_ok=True)
audio_path = out_dir / f"audio_{scene_index}.wav"
# after
from console.backend.utils.file_naming import make_unique_path
script_title = (script.topic or f"script-{script_id}").strip()
_base_output = Path(os.environ.get("OUTPUT_PATH", "./assets/output"))
out_dir = _base_output / make_unique_path(script_title, "", _base_output).name
out_dir.mkdir(parents=True, exist_ok=True)
audio_path = out_dir / f"scene-{scene_index}_narration.wav"
```

Wait — there's a subtlety here: the TTS regen task needs to write to the **same directory** as the original render (which was created by `compose_video`). Using `make_unique_path` again would create a new directory if the slug name doesn't already exist. Instead, look up the existing `output_path` on the `GeneratedScript` and derive the directory from it:

```python
# The script.output_path is set by compose_video to the raw.mp4 path.
# Derive out_dir from it to stay in the same directory.
if script.output_path:
    out_dir = Path(script.output_path).parent
else:
    from console.backend.utils.file_naming import make_filename
    script_title = (script.topic or f"script-{script_id}").strip()
    out_dir = Path(os.environ.get("OUTPUT_PATH", "./assets/output")) / make_filename(script_title, "")
out_dir.mkdir(parents=True, exist_ok=True)
audio_path = out_dir / f"scene-{scene_index}_narration.wav"
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/composer.py console/backend/tasks/production_tasks.py
git commit -m "feat: use readable slug dir and scene-N filenames for legacy pipeline output"
```

---

## Task 10: Update renderer output filename

**Files:**
- Modify: `pipeline/renderer.py` (line 203)

- [ ] **Step 1: Update `render_final` output path**

In `pipeline/renderer.py`, line 203:
```python
# before
final_path = raw_path_obj.parent / "video_final.mp4"
# after
final_path = raw_path_obj.parent / "final.mp4"
```

- [ ] **Step 2: Verify the `ass_candidate` reference is still correct**

Line 217:
```python
ass_candidate = raw_path_obj.parent / "subtitles.ass"
```
This is unchanged — `subtitles.ass` stays the same filename. No change needed.

- [ ] **Step 3: Commit**

```bash
git add pipeline/renderer.py
git commit -m "feat: rename video_final.mp4 → final.mp4 in renderer output"
```

---

## Task 11: Update YouTube long-form render output paths

**Files:**
- Modify: `console/backend/tasks/youtube_render_task.py` (lines ~117, ~180, ~238)

In all three render functions in this file, `video` is a `YoutubeVideo` object, so `video.title` is available.

- [ ] **Step 1: Add import**

Add at top of `youtube_render_task.py`:
```python
from console.backend.utils.file_naming import make_filename, make_unique_path
```

- [ ] **Step 2: Update final render output (line ~117)**

Find:
```python
output_path = OUTPUT_DIR / f"youtube_{youtube_video_id}_v{int(time.time())}.mp4"
```

Replace with:
```python
output_path = make_unique_path(video.title, ".mp4", OUTPUT_DIR)
```

- [ ] **Step 3: Update audio preview output dir (line ~180)**

Find:
```python
out_dir = OUTPUT_DIR / f"youtube_{youtube_video_id}"
```
(there are two occurrences — one for audio preview ~180 and one for video preview ~238)

Replace both occurrences with:
```python
out_dir = OUTPUT_DIR / make_filename(video.title, "")
out_dir.mkdir(parents=True, exist_ok=True)
```

Note: previews share a directory per video. Using `make_filename` (not `make_unique_path`) ensures both audio preview and video preview tasks use the same directory. The `mkdir` call already exists on the next line — verify you don't duplicate it.

- [ ] **Step 4: Commit**

```bash
git add console/backend/tasks/youtube_render_task.py
git commit -m "feat: use readable slug filenames for YouTube long-form render output"
```

---

## Task 12: Update YouTube short render output path

**Files:**
- Modify: `console/backend/tasks/youtube_short_render_task.py` (line ~59)

- [ ] **Step 1: Add import**

Add at top of `youtube_short_render_task.py`:
```python
from console.backend.utils.file_naming import make_unique_path
```

- [ ] **Step 2: Update output path (line ~59)**

Find:
```python
output_path = OUTPUT_DIR / f"short_{youtube_video_id}_v{int(time.time())}.mp4"
```

Replace with:
```python
output_path = make_unique_path(video.title, ".mp4", OUTPUT_DIR)
```

`video` is already fetched earlier in the task function.

- [ ] **Step 3: Commit**

```bash
git add console/backend/tasks/youtube_short_render_task.py
git commit -m "feat: use readable slug filename for YouTube short render output"
```

---

## Self-Review Checklist

- [x] `make_filename` / `make_unique_path` signatures match all call sites
- [x] Task 9 Step 4 handles the tricky "TTS regen must use same dir as original render" via `script.output_path`
- [x] Runway recovery task uses `row.generation_prompt` (confirmed exists on `VideoAsset` model)
- [x] `caption_gen.py` derives srt path via `.with_suffix(".srt")` — automatically gets `scene-0_narration.srt` from `scene-0_narration.wav` with no changes needed
- [x] `subtitles.ass` in renderer is unchanged (spec says leave it)
- [x] `make_filename(title, "")` returns `YYYYMMDD_slug` (no trailing dot) — correct for directory names
- [x] Backward compat: no existing files renamed; DB stores absolute path so old and new coexist
