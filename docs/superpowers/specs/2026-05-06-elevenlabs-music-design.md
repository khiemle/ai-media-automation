# ElevenLabs Music Generation — Design Spec

**Date:** 2026-05-06
**Status:** Approved

---

## Overview

Add ElevenLabs as a third music generation provider (alongside Suno and Lyria) in the Music tab of the Management Console. Editors can supply a free-text prompt or a raw composition plan JSON, optionally preview and edit the structured plan, then generate a music track that is saved to the shared library.

Per-video automation: when a script enters production and no suitable library track exists, `ProductionService` can optionally auto-generate an ElevenLabs track using script metadata (niche, mood, duration). This is disabled by default via config flag.

**No changes to:** YouTube page, Production page, composer, renderer, or any existing provider.

---

## ElevenLabs API

Two relevant SDK calls:

```python
# Phase 1 — generate composition plan from text prompt
plan = elevenlabs.music.composition_plan.create(
    prompt="...",
    music_length_ms=60000
)

# Phase 2 — generate audio from composition plan
audio = elevenlabs.music.compose(
    composition_plan=plan,
    respect_sections_durations=True,
    output_format="mp3_44100_192"   # optional query param
)
```

**Input detection:** if the user's input parses as JSON and contains `sections` or `positive_global_styles` keys → treat as composition plan (skip Phase 1). Otherwise → treat as text prompt and run Phase 1 first.

**Supported output formats** (via `output_format` query param): `mp3_44100_192` (default), `pcm_44100`, `opus_48000_192`, others. File extension is derived from the format prefix. API key is read from `config/api_keys.json` under `cfg["elevenlabs"]["api_key"]` — the same path used by the existing ElevenLabs TTS code.

---

## Data Model

One column added to `music_tracks`:

```python
composition_plan = Column(JSONB, nullable=True)
```

Stores the final composition plan used to generate the track — enables re-editing and regeneration later. The `provider` column accepts `"elevenlabs"` as a new valid value (no schema constraint change needed). `generation_prompt` stores the original user input (text prompt or raw JSON).

**Alembic migration required.**

---

## Backend

### New file: `pipeline/music_providers/elevenlabs_provider.py`

```python
class ElevenLabsProvider:
    def create_plan(self, input: str, music_length_ms: int) -> dict:
        """Return composition plan dict. Detects prompt vs JSON input."""

    def compose(self, plan: dict, output_format: str, respect_sections_durations: bool) -> bytes:
        """Return raw audio bytes."""
```

Input detection logic in `create_plan`:
1. Try `json.loads(input)`
2. If parsed dict has `sections` or `positive_global_styles` → return as-is (skip API call)
3. Otherwise → call `elevenlabs.music.composition_plan.create(prompt=input, music_length_ms=music_length_ms)`

### New endpoints in `console/backend/routers/music.py`

**`POST /music/elevenlabs/plan`** — synchronous

```
Request:  { input: str, music_length_ms: int = 60000 }
Response: { composition_plan: dict }
```

Calls `ElevenLabsProvider.create_plan()`. Returns the plan for the editor to inspect/modify. No DB write, no audio generated.

**`POST /music/elevenlabs/compose`** — async

```
Request:  {
    composition_plan: dict,
    title: str,
    niches: list[str],
    moods: list[str],
    genres: list[str] = [],
    output_format: str = "mp3_44100_192",
    respect_sections_durations: bool = True
}
Response: { task_id: str, track_id: int }
```

Creates a `MusicTrack` row with `status="pending"`, `provider="elevenlabs"`, dispatches `generate_elevenlabs_music_task(track_id, composition_plan, output_format, respect_sections_durations)`.

### New Celery task: `generate_elevenlabs_music_task` (queue: `music_q`)

1. Call `ElevenLabsProvider.compose(plan, output_format, respect_sections_durations)`
2. Derive file extension from format prefix (e.g. `mp3_44100_192` → `.mp3`, `pcm_44100` → `.wav`)
3. Save audio bytes to `{MUSIC_PATH}/{track_id}.{ext}`
4. ffprobe to extract `duration_s`
5. Update `MusicTrack`: `file_path`, `duration_s`, `composition_plan` (JSON), `generation_status="ready"`
6. On any exception: `generation_status="failed"`, log error

Polling uses the existing `GET /music/tasks/{task_id}` endpoint — no changes needed.

---

## Frontend (Music Tab only)

### New ElevenLabs section in Music tab

Fields:
- **Textarea** — "Prompt or Composition Plan JSON". Auto-detects input type via `JSON.parse` and shows a small badge: `text prompt` or `JSON plan`
- **Duration (ms)** — number input, default `60000`, disabled when input is detected as JSON plan
- **Output Format** — dropdown: `mp3_44100_192` (default), `pcm_44100`, `opus_48000_192`
- **Niches** — tag input (same pattern as Suno/Lyria form)
- **Moods** — tag input
- **Title** — text input

Two action buttons:
- **"Preview Plan"** — calls `POST /music/elevenlabs/plan`, opens Plan Editor modal
- **"Generate Direct"** — skips plan editor, calls `POST /music/elevenlabs/compose` immediately

### Plan Editor modal

- Full-width monospace JSON textarea (~30 lines), pre-filled with the composition plan from `/plan`
- If user input was already a JSON plan, modal opens pre-filled with their own JSON
- Buttons: **"Generate Audio"** (submits edited JSON to `/compose`) and **"Cancel"**
- No JSON validation UI beyond a parse error message on submit if the JSON is malformed

After generation is dispatched, uses the same polling + toast pattern as Suno/Lyria.

---

## Per-Video Automation

### Config additions (`config/pipeline_config.yaml`)

```yaml
production:
  auto_music_elevenlabs: false
  auto_music_elevenlabs_format: mp3_44100_192
  auto_music_elevenlabs_length_ms: 0   # 0 = derive from video duration in seconds * 1000
```

### `ProductionService` logic (on script entering production)

1. Run existing `_select_music(mood, niche, duration)` — if a library track is found, use it (no change)
2. If no track found AND `auto_music_elevenlabs: true`:
   - Build prompt: `"{mood} background music for a {niche} video, {duration}s, instrumental"`
   - `length_ms = auto_music_elevenlabs_length_ms or int(duration * 1000)`
   - Call `ElevenLabsProvider.create_plan(prompt, length_ms)` then `compose(plan, format)` synchronously (already inside a Celery task)
   - Save track to library with script's niche/mood tags
   - Assign `music_track_id` on the script before composing video

**High-priority override:** `generate_fresh_music: bool` on the script's production config bypasses the library check and always generates a new ElevenLabs track.

---

## Files Changed

| File | Change |
|------|--------|
| `pipeline/music_providers/elevenlabs_provider.py` | New |
| `database/models.py` | Add `composition_plan` JSONB column to `MusicTrack` |
| `console/backend/alembic/versions/` | New migration for `composition_plan` column |
| `console/backend/routers/music.py` | Add `/elevenlabs/plan` and `/elevenlabs/compose` endpoints |
| `console/backend/tasks/music_tasks.py` | Add `generate_elevenlabs_music_task` |
| `console/backend/services/production_service.py` | Add auto-ElevenLabs fallback |
| `config/pipeline_config.yaml` | Add `auto_music_elevenlabs` config block |
| `console/frontend/src/pages/MusicPage.jsx` | Add ElevenLabs section + Plan Editor modal |

---

## Out of Scope

- YouTube page — no changes; music is still selected from library
- Production page — no changes
- Composer, renderer — no changes
- Structured form editor for composition plan (JSON textarea only for now)
