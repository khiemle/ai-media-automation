# Music Background Feature — Design Spec

**Date:** 2026-04-26  
**Status:** Approved  

---

## Overview

Add a Music library to the Management Console that lets editors manage background music tracks, generate new ones via Suno or Google Lyria, and assign tracks to scripts. The pipeline composer uses the assigned track (with per-track volume) when rendering videos, looping short tracks to match video duration.

---

## 1. Data Layer

### New table: `music_tracks` (migration `006_music_tracks.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | integer PK | |
| `title` | varchar(200) | editable display name |
| `file_path` | varchar(500) | `assets/music/{id}.{ext}` |
| `duration_s` | float | probed after file is saved |
| `niches` | ARRAY(varchar) | e.g. `["fitness", "tech"]` |
| `moods` | ARRAY(varchar) | e.g. `["energetic", "uplifting"]` |
| `genres` | ARRAY(varchar) | e.g. `["pop", "electronic"]` — fed into Suno `style` or Lyria prompt |
| `is_vocal` | boolean | false = instrumental; default false |
| `is_favorite` | boolean | default false |
| `volume` | float | 0.0–1.0; default 0.15 (matches existing `MUSIC_VOLUME`) |
| `usage_count` | integer | incremented by composer each time the track is used |
| `quality_score` | integer | 0–100; user-settable; default 80 for imports |
| `provider` | varchar | `suno` \| `lyria-clip` \| `lyria-pro` \| `import` |
| `provider_task_id` | varchar | Suno `taskId`; null for Lyria and imports |
| `generation_status` | varchar | `pending` / `ready` / `failed` |
| `generation_prompt` | text | full prompt sent to provider; null for imports |
| `created_at` | timestamp | server default now() |

### Existing table extension: `generated_scripts`

Add one nullable FK column:

```sql
music_track_id  INTEGER  REFERENCES music_tracks(id) ON DELETE SET NULL
```

Stored in `script_json.video.music_track_id` and mirrored as a top-level column for fast querying.

### File storage

`./assets/music/{id}.{ext}` — directory created on first use. Extension preserved from source (`.mp3`, `.wav`, `.m4a`, `.ogg`). MoviePy's `AudioFileClip` handles all formats.

---

## 2. Backend Architecture

### New files

| File | Responsibility |
|---|---|
| `console/backend/models/music_track.py` | SQLAlchemy `MusicTrack` model |
| `console/backend/services/music_service.py` | CRUD, Gemini prompt expansion, provider dispatch, usage increment |
| `console/backend/routers/music.py` | REST endpoints; registered in `main.py` |
| `console/backend/tasks/music_tasks.py` | Celery tasks: Suno polling, Lyria generation |
| `pipeline/music_providers/__init__.py` | |
| `pipeline/music_providers/suno_provider.py` | Suno HTTP client |
| `pipeline/music_providers/lyria_provider.py` | Lyria via `google-genai` SDK |
| `console/backend/alembic/versions/006_music_tracks.py` | DB migration |

### API endpoints

```
GET    /api/music                     list tracks (filter: niche, mood, genre, is_vocal, status, search)
POST   /api/music/generate            generate via Suno or Lyria → {task_id, track_id}
POST   /api/music/upload              import audio file (multipart) → track detail
GET    /api/music/{id}                single track detail
PUT    /api/music/{id}                update metadata (title, niches, moods, genres, favorite, volume, score)
DELETE /api/music/{id}                delete DB record + file
GET    /api/music/{id}/stream         stream audio file for browser playback
GET    /api/music/tasks/{task_id}     poll Suno/Lyria Celery task status
```

### Generation flow

```
POST /api/music/generate
  Request body includes optional boolean: expand_only

  If expand_only=true (Gemini expansion step only):
    1. MusicService.expand_prompt_with_gemini(idea, niches, moods, genres, is_vocal)
    2. Return {expanded_prompt, negative_tags} — no DB row created, no task enqueued

  If expand_only=false (default — full generation):
    1. MusicService.expand_prompt_with_gemini(idea, niches, moods, genres, is_vocal)
         → calls Gemini (gemini-2.5-flash, existing GEMINI_API_KEY)
         → returns: rich prompt string + negative_tags string
    2. Insert music_tracks row (generation_status=pending)
    3a. provider=suno
          → enqueue generate_suno_music_task(track_id)
          → returns {task_id (Celery), track_id} immediately
    3b. provider=lyria-clip or lyria-pro
          → enqueue generate_lyria_music_task(track_id)
          → returns {task_id (Celery), track_id} immediately
```

### Suno Celery task (`music_tasks.py`)

```
generate_suno_music_task(track_id):
  1. POST https://api.sunoapi.org/api/v1/generate
       customMode=true, instrumental=!is_vocal, style=genres.join(", ")
       title=track.title, prompt=generation_prompt
       model=V4_5 (default)
       callBackUrl="https://placeholder.invalid/noop"  ← required by API; we use polling, not callbacks
  2. Store suno_task_id (taskId from response) on the music_tracks row
  3. Poll GET https://api.sunoapi.org/api/v1/tasks/{suno_task_id} every 15s, up to 20 attempts (~5 min)
  4. On complete: download first of the 2 returned MP3s
                  save to assets/music/{id}.mp3
                  probe duration with ffprobe
                  update generation_status=ready, duration_s, file_path
  5. On timeout:  update generation_status=failed
```

### Lyria Celery task (`music_tasks.py`)

```
generate_lyria_music_task(track_id):
  1. Call LyriaProvider.generate(prompt, model, is_vocal)
       model: lyria-3-clip-preview (30s) or lyria-3-pro-preview (full)
       appends "instrumental, no vocals" or "with vocals" to prompt
       uses GEMINI_API_KEY (same key, same google-genai SDK)
  2. Decode base64 MP3 from response.parts
  3. Save to assets/music/{id}.mp3
  4. Probe duration with ffprobe
  5. Update generation_status=ready, duration_s, file_path
```

### Import flow

```
POST /api/music/upload (multipart: file + metadata JSON)
  1. Save file to assets/music/{id}.{ext}
  2. Probe duration with ffprobe
  3. Insert music_tracks row (generation_status=ready, provider=import)
  4. Return track detail
```

### Gemini prompt expansion

`MusicService.expand_prompt_with_gemini()` sends a structured prompt to Gemini asking it to produce:
- A rich descriptive music prompt (≤ 500 chars for Suno non-custom, ≤ 3000 for custom mode)
- A `negative_tags` string (styles to avoid)

The expanded prompt is shown in the Generate modal as editable text before submission.

### Integration touch points (existing files)

**`script_service.py` — draft creation auto-select:**
```python
# After inserting draft, query for a matching track
track = db.query(MusicTrack).filter(
    MusicTrack.generation_status == "ready",
    MusicTrack.niches.contains([script.niche])
).order_by(
    MusicTrack.is_favorite.desc(),
    MusicTrack.quality_score.desc()
).first()
script.music_track_id = track.id if track else None
```

**`pipeline/composer.py` — `compose_video()` changes:**
- Replace `_select_music(mood, niche, duration)` file-scan with a DB lookup by `music_track_id`
- Use `track.file_path` and `track.volume` instead of hardcoded `MUSIC_PATH` / `MUSIC_VOLUME`
- Existing loop logic (lines 221–228) is unchanged — still triggers when `music.duration < final.duration`
- Call `MusicService.increment_usage(track_id)` after successful mix
- Lyria Clip (30s) tracks will always loop for typical 60–90s videos

---

## 3. Frontend Architecture

### New files

| File | Responsibility |
|---|---|
| `console/frontend/src/pages/MusicPage.jsx` | Music library, generate modal, import modal, inline player |
| `console/frontend/src/api/client.js` | add `musicApi` (list, generate, upload, update, delete, pollTask, stream URL helper) |

### Sidebar

Music tab inserted between Niches and Composer. Roles: `admin` + `editor`.

### MusicPage layout

**Stats row:** Total Tracks · Suno · Lyria · Imported · Favorites

**Toolbar:** search input · niche filter · mood filter · genre filter · vocal toggle · status filter (all / ready / pending / failed) · "+ Generate" button · "↑ Import" button

**Library table columns:**
- Title
- Provider badge (`SUNO` / `LYRIA-CLIP` / `LYRIA-PRO` / `IMPORT`)
- Status badge (`ready` / `pending` / `failed`)
- Duration
- Niches tags
- Moods tags
- Genres tags
- Vocal / Instrumental badge
- Quality score
- ★ Favorite toggle
- Usage count
- Actions: ▶ Play · ✎ Edit · ✕ Delete

Pending Suno rows show a pulsing "Generating…" badge; the table polls `/api/music/tasks/{task_id}` every 10s until `ready` or `failed`.

**Inline audio player:** clicking ▶ opens a compact persistent player bar at the bottom of the page (`<audio>` streaming from `/api/music/{id}/stream`). One track at a time.

**Edit modal:** title, niches, moods, genres, vocal toggle, volume slider, quality score, favorite toggle.

### Generate Music modal

```
[ General idea / description ]  textarea (short natural language input)

[ Niche    ]  multi-select  (loaded from /api/niches)
[ Mood     ]  multi-select  (uplifting / calm_focus / energetic / dramatic / neutral)
[ Genre    ]  multi-select  (pop / rock / electronic / jazz / classical / hip-hop / ambient / cinematic)
[ Provider ]  select        Suno | Lyria Clip (30s) | Lyria Pro
[ Vocal    ]  toggle        Off = instrumental (default) / On = with vocals

[ Expand with Gemini ]  → POST /api/music/generate with expand_only=true
                          replaces textarea with expanded prompt (still editable)

[ Generate ]  → POST /api/music/generate
                closes modal, new pending row appears in table
```

### Import Music modal

```
[ Choose file ]  file picker  (.mp3 / .wav / .m4a / .ogg)
                 shows filename + detected duration on selection (client-side AudioContext)

[ Title        ]  text input   (pre-filled with filename, editable)
[ Niche        ]  multi-select
[ Mood         ]  multi-select
[ Genre        ]  multi-select
[ Vocal        ]  toggle  (default Off = instrumental)
[ Volume       ]  slider  0.0 – 1.0  (default 0.15)
[ Quality Score]  0–100   (default 80)

[ Import ]  → POST /api/music/upload (multipart)
              on success: track appears immediately with status=ready
```

### ScriptsPage — ScriptEditorModal changes

In the existing "Video" section, replace the `music_mood` text input with:

```
[ Background Music ]  searchable select
                       options loaded from /api/music?status=ready&niche={script.niche}
                       shows: title · duration · genre tags
                       "None" option always available
[ Mood             ]  select  (kept — still used as fallback metadata by composer)
```

Selecting a track writes `video.music_track_id` into `script_json`. Clearing sets it to null.

Auto-select on draft creation is handled entirely in the backend — no frontend change required.

---

## 4. Environment Variables

| Variable | Used by | Notes |
|---|---|---|
| `SUNO_API_KEY` | `suno_provider.py` | Bearer token for sunoapi.org |
| `GEMINI_API_KEY` | `lyria_provider.py`, `music_service.py` | already set; reused for Lyria + Gemini expansion |
| `MUSIC_PATH` | `composer.py` | already set; fallback for scripts without `music_track_id` |

Add `SUNO_API_KEY` to `console/.env.example`.

---

## 5. Key Constraints

- Suno returns 2 tracks per request — only the first is saved.
- Lyria Clip always produces 30s audio — looping is automatic in the composer.
- Lyria Pro produces full songs (a few minutes) — looping may not trigger.
- Vocal control: Suno uses `instrumental` boolean; Lyria appends text to prompt.
- Genres feed into Suno `style` field; for Lyria they are appended to the prompt.
- The existing `_select_music()` file-scan in `composer.py` is kept as a final fallback for scripts where `music_track_id` is null and a local file exists.
- All async operations (Suno polling, Lyria generation) run in Celery `render_q` queue (existing).
