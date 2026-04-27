# LLM Tab Improvements — Design Spec

**Date:** 2026-04-27  
**Status:** Approved

---

## Overview

Five improvements to the LLM tab and script editor:

1. Add a Kokoro TTS card to the LLM page with voice selection
2. Show real Suno API credits (not DB count)
3. Improve ElevenLabs card with model descriptions and voice dropdowns
4. Add TTS service + voice picker to the script editor (language-gated)
5. Fix background music to support explicit "no music" option
6. Propagate language through the Celery script generation task

---

## 1. Data Layer — `config/tts_voices.json`

Single file committed to the repo. Owned by the backend. Frontend never reads it directly — only via `GET /api/llm/voices`.

### Structure

```json
{
  "kokoro": {
    "american_english": {
      "female": [{ "id": "af_heart", "name": "Heart" }, ...],
      "male":   [{ "id": "am_adam",  "name": "Adam"  }, ...]
    },
    "british_english": {
      "female": [{ "id": "bf_emma",   "name": "Emma"   }, ...],
      "male":   [{ "id": "bm_george", "name": "George" }, ...]
    }
  },
  "elevenlabs": {
    "en": {
      "male":   [{ "id": "UgBBYS2sOqTuMpoF3BR0", "name": "..." }, ...],
      "female": [{ "id": "56AoDkrOh6qfVPDXZ7Pt", "name": "..." }, ...]
    },
    "vi": {
      "male":   [{ "id": "3VnrjnYrskPMDsapTr8X", "name": "..." }, ...],
      "female": [{ "id": "A5w1fw5x0uXded1LDvZp", "name": "..." }, ...]
    }
  }
}
```

### Kokoro voices (hardcoded)

Sourced from HuggingFace `hexgrad/Kokoro-82M` VOICES.md. Only American English (prefix `af_`, `am_`) and British English (prefix `bf_`, `bm_`) are included.

Voice IDs:
- American English female (`af_`): heart, bella, nicole, aoede, sky
- American English male (`am_`): adam, michael, echo, eric, liam
- British English female (`bf_`): emma, isabella, lily
- British English male (`bm_`): george, lewis, daniel

### ElevenLabs voices (one-time build)

**`scripts/build_elevenlabs_voices.py`** calls `GET https://api.elevenlabs.io/v1/voices/{voice_id}` for each ID below, pulls `name`, writes the `elevenlabs` section into `config/tts_voices.json`. Run once, commit the result.

Voice IDs to fetch:

| Language | Gender | IDs |
|---|---|---|
| EN | male | UgBBYS2sOqTuMpoF3BR0, NOpBlnGInO9m6vDvFkFC, EkK5I93UQWFDigLMpZcX, uju3wxzG5OhpWcoi3SMy, NFG5qt843uXKj4pFvR7C |
| EN | female | 56AoDkrOh6qfVPDXZ7Pt, tnSpp4vdxKPjI9w0GnoV, Z3R5wn05IrDiVCyEkUrK, kPzsL2i3teMYv0FxEYQ6, aMSt68OGf4xUZAnLpTU8, RILOU7YmBhvwJGDGjNmP, flHkNRp1BlvT73UL6gyz, KoVIHoyLDrQyd4pGalbs, yj30vwTGJxSHezdAGsv9 |
| VI | female | A5w1fw5x0uXded1LDvZp, d5HVupAWCwe4e6GvMCAL, DvG3I1kDzdBY3u4EzYh6, foH7s9fX31wFFH2yqrFa, jdlxsPOZOHdGEfcItXVu, BlZK9tHPU6XXjwOSIiYA, a3AkyqGG4v8Pg7SWQ0Y3, HQZkBNMmZF5aISnrU842, qByVAGjXwGlkcRDJoiHg |
| VI | male | 3VnrjnYrskPMDsapTr8X, aN7cv9yXNrfIR87bDmyD, ueSxRO0nLF1bj93J2hVt, UsgbMVmY3U59ijwK5mdh, XBDAUT8ybuJTTCoOLSUj, 9EE00wK5qV6tPtpQIxvy |

The build script requires the ElevenLabs API key from `config/api_keys.json`. On any fetch failure, it logs the error and writes a placeholder `{ "id": "...", "name": "Unknown" }` so the file is always valid.

---

## 2. Backend Changes

### 2a. `config/api_config.py`

Add `kokoro` to `_DEFAULT`:

```python
_DEFAULT = {
    ...
    "kokoro": { "default_voice_en": "af_heart" },
    "elevenlabs": { "api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": "eleven_flash_v2_5" },
    ...
}
```

Note: default ElevenLabs model changes from `eleven_multilingual_v2` to `eleven_flash_v2_5`.

### 2b. `console/backend/services/llm_service.py`

**`get_status()`** — add Kokoro entry (always available; local model has no key requirement):

```python
"kokoro": { "available": True }
```

**`get_quota()`** — replace the Suno DB-count fallback with a real API call:

```
GET https://api.sunoapi.org/api/v1/credits
Authorization: Bearer <suno_api_key>
```

Expected response: `{ "credits": <number> }`. Store as `result["suno"] = { "credits": N }`. Fall back to `{ "error": "..." }` on failure or missing key.

**New method `get_voices()`** — reads `config/tts_voices.json` and returns the parsed dict. Caches with the same 30s TTL pattern used by `api_config`.

### 2c. `console/backend/routers/llm.py`

Add one route:

```
GET /api/llm/voices   →  LLMService().get_voices()   (require_editor_or_admin)
```

### 2d. `console/backend/schemas/script.py`

Add `language` to `ScriptUpdate`:

```python
class ScriptUpdate(BaseModel):
    script_json: dict
    editor_notes: str | None = None
    language: str | None = None
```

### 2e. `console/backend/services/script_service.py`

`update_script()` — when `language` is provided in the update payload, write it to `row.language`:

```python
if language is not None:
    row.language = language
```

### 2f. `console/backend/tasks/script_tasks.py`

Add `language: str = "vietnamese"` parameter to `generate_script_task`. Pass it through to `ScriptService.generate_script()`.

### 2g. `console/backend/services/pipeline_service.py`

In `_dispatch()`, when `job_type == "generate"`, look up the script row to get its language before dispatching:

```python
elif job_type == "generate":
    from console.backend.tasks.script_tasks import generate_script_task
    row = self.db.query(Script).filter(Script.id == script_id).first()
    lang = getattr(row, "language", "vietnamese") if row else "vietnamese"
    result = generate_script_task.delay(
        topic=row.topic, niche=row.niche, template=row.template,
        language=lang, context_video_ids=None
    )
```

---

## 3. LLM Page — Frontend (`LLMPage.jsx`)

### 3a. Kokoro card (new, inserted between ElevenLabs and Suno)

- Status dot: green (reads `status.kokoro.available`)
- Single "Default voice" dropdown, grouped by accent and gender:
  - `<optgroup label="American English — Female">` → `af_*` voices
  - `<optgroup label="American English — Male">` → `am_*` voices
  - `<optgroup label="British English — Female">` → `bf_*` voices
  - `<optgroup label="British English — Male">` → `bm_*` voices
- Voices loaded from `GET /api/llm/voices` (shared fetch with script editor)
- Save writes `kokoro.default_voice_en` to `api_keys.json` via `PUT /api/llm/config`
- Card key: `'kokoro'` (added to the `saving` state union)

### 3b. ElevenLabs card (updated)

**Model dropdown** — replace static list with 3 options plus helper text:

| Value | Display | Helper text |
|---|---|---|
| `eleven_flash_v2_5` | Eleven 2.5 Flash | Fast, low-latency. Best for most uses. (default) |
| `eleven_v3` | Eleven 3 | Highest quality, most expressive. |
| `eleven_multilingual_v2` | Multilingual v2 | Legacy. Broad language support. |

Helper text rendered as a `<p>` below the select, switching based on current selection.

**Voice dropdowns** — replace the two raw text inputs with `<select>` dropdowns:

- "Default EN Voice" — options from `tts_voices.elevenlabs.en`, grouped `<optgroup label="Male">` / `<optgroup label="Female">`
- "Default VI Voice" — options from `tts_voices.elevenlabs.vi`, grouped same way
- Voices loaded from `GET /api/llm/voices`
- Values still saved as `elevenlabs.voice_id_en` and `elevenlabs.voice_id_vi` in `api_keys.json`

Quota bar, scope-restricted message, and error display are unchanged.

### 3c. Suno card (updated)

Replace `{q.suno.tracks_generated} tracks generated` with:

- When credits available: `Credits remaining: {q.suno.credits}` in monospace
- When error: `<p className="text-xs text-[#f87171] font-mono">{q.suno.error}</p>`

---

## 4. Script Editor — Frontend (`ScriptsPage.jsx`)

Changes are confined to `ScriptEditorModal` and its Video/Metadata sections.

### 4a. Language field (Metadata section)

Add a `Select` to the Metadata grid:

```jsx
<Select
  label="Language"
  value={data?.language || 'vietnamese'}
  onChange={e => setLanguage(e.target.value)}
  options={[
    { value: 'vietnamese', label: 'Vietnamese' },
    { value: 'english',    label: 'English' },
  ]}
/>
```

`language` is managed as separate local state (not inside `draft`/`script_json`), since it lives on the DB row, not inside `script_json`. It is included in the `PUT /api/scripts/{id}` payload alongside `script_json` and `editor_notes`.

### 4b. TTS service + voice picker (Video section)

Replace the current `Voice` `<Select>` (hardcoded `VOICES` array) with two fields:

**TTS Service select:**

```jsx
<Select
  label="TTS Service"
  value={video.tts_service || (language === 'vietnamese' ? 'elevenlabs' : 'kokoro')}
  onChange={e => setScriptField('video', 'tts_service', e.target.value)}
  options={ttsServiceOptions}  // filtered by language
/>
```

- `language === 'vietnamese'` → only `[{ value: 'elevenlabs', label: 'ElevenLabs' }]` (locked)
- `language === 'english'` → `[{ value: 'kokoro', label: 'Kokoro' }, { value: 'elevenlabs', label: 'ElevenLabs' }]`

**Voice select** (dynamic, depends on tts_service + language):

| `language` | `tts_service` | Voice options |
|---|---|---|
| english | kokoro | All Kokoro voices, grouped by American/British + gender |
| english | elevenlabs | `tts_voices.elevenlabs.en`, grouped Male/Female |
| vietnamese | elevenlabs | `tts_voices.elevenlabs.vi`, grouped Male/Female |

Value stored in `video.voice` (existing field, now stores Kokoro short name or ElevenLabs UUID).

Voices loaded once at modal open via `GET /api/llm/voices`, stored in component state.

When `language` changes:
- Reset `video.tts_service` to default for that language
- Reset `video.voice` to `''`

### 4c. Background music (Video section)

Change the music dropdown from a two-state (`null` = auto, track ID = assigned) to three explicit states:

| Option label | Value | `video.music_disabled` | `video.music_track_id` |
|---|---|---|---|
| Auto (by mood) | `"auto"` | `false` | `null` |
| No music | `"none"` | `true` | `null` |
| [track name] | `"<id>"` | `false` | `<id>` |

The select `value` is computed:
- `video.music_disabled` → `"none"`
- `video.music_track_id` set → `String(video.music_track_id)`
- otherwise → `"auto"`

On change:
```js
if (val === 'none')  { setScriptField('video', 'music_disabled', true);  setScriptField('video', 'music_track_id', null) }
if (val === 'auto')  { setScriptField('video', 'music_disabled', false); setScriptField('video', 'music_track_id', null) }
if (val is track ID) { setScriptField('video', 'music_disabled', false); setScriptField('video', 'music_track_id', parseInt(val)) }
```

---

## 5. Pipeline — `pipeline/composer.py`

Before the `_select_music()` fallback (line 230), read the `music_disabled` flag:

```python
music_disabled = (script.script_json or {}).get('video', {}).get('music_disabled', False)
music_track_path = None
if not music_disabled:
    music_track_path = _assigned_track or _select_music(
        meta.get("mood", "uplifting"), meta.get("niche", "lifestyle"), final.duration
    )
```

When `music_disabled` is true, `music_track_path` stays `None` and the music mixing block is skipped entirely.

---

## 6. Files Changed

| File | Type | Change |
|---|---|---|
| `scripts/build_elevenlabs_voices.py` | New | One-time build script for ElevenLabs voice data |
| `config/tts_voices.json` | New | Combined Kokoro + ElevenLabs voice data |
| `config/api_config.py` | Modified | Add `kokoro` section to `_DEFAULT`; update ElevenLabs default model |
| `console/backend/services/llm_service.py` | Modified | Kokoro status, Suno real credits, `get_voices()` method |
| `console/backend/routers/llm.py` | Modified | Add `GET /api/llm/voices` |
| `console/backend/schemas/script.py` | Modified | Add `language` to `ScriptUpdate` |
| `console/backend/services/script_service.py` | Modified | `update_script()` saves `row.language` |
| `console/backend/tasks/script_tasks.py` | Modified | Add `language` param to `generate_script_task` |
| `console/backend/services/pipeline_service.py` | Modified | Pass language when dispatching "generate" job |
| `console/frontend/src/pages/LLMPage.jsx` | Modified | Kokoro card, ElevenLabs voice dropdowns + model descriptions, Suno real credits |
| `console/frontend/src/pages/ScriptsPage.jsx` | Modified | Language field, TTS service + voice picker, music Auto/None/track dropdown |
| `pipeline/composer.py` | Modified | Skip `_select_music()` when `video.music_disabled` is true |

---

## Constraints & Notes

- No DB migration required. `language` is already a column on `GeneratedScript`. TTS fields (`tts_service`, `voice`, `music_disabled`) live in `script_json` (JSONB) — no schema change needed.
- The build script (`build_elevenlabs_voices.py`) must be run once before deploying. It reads the ElevenLabs API key from `config/api_keys.json`.
- Vietnamese scripts can only use ElevenLabs + Vietnamese voices. The TTS service dropdown is locked to ElevenLabs when `language === 'vietnamese'`. Kokoro has no Vietnamese support.
- The Suno credits endpoint (`/api/v1/credits`) is from the sunoapi.org third-party API, consistent with the existing `SUNO_BASE` in `suno_provider.py`.
- `GET /api/llm/voices` is available to editors and admins (same permission as `/api/llm/status`).
