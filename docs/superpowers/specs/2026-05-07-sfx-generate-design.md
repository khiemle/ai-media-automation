# SFX Generate via ElevenLabs — Design Spec

**Date:** 2026-05-07  
**Status:** Approved

---

## Overview

Add a **Generate SFX** capability to the existing SFX Library page. Users describe a sound in natural language, set an optional duration and loop flag, and ElevenLabs `text_to_sound_effects.convert()` generates the audio. The result is saved directly into the SFX library (same as an imported file).

---

## Decisions

| Question | Decision |
|---|---|
| Modal inputs | prompt (required), title (optional, prefilled), loop (bool), duration (optional float) |
| sound_type for generated SFX | null — shows under "All types" only |
| Generation execution | Synchronous — modal shows loading spinner, waits for response |
| Architecture | Thin endpoint inline in `sfx.py` router, reuses existing `SfxService.import_sfx()` |

---

## Data Model

**Migration:** Add `is_loopable` column to `sfx_assets` table.

```sql
ALTER TABLE sfx_assets ADD COLUMN is_loopable BOOLEAN NOT NULL DEFAULT FALSE;
```

`_sfx_to_dict()` in `sfx_service.py` gains `"is_loopable": s.is_loopable`.

---

## Backend

### New endpoint: `POST /api/sfx/generate`

**File:** `console/backend/routers/sfx.py`

**Request body (Pydantic):**
```python
class GenerateBody(BaseModel):
    text: str                          # prompt, required
    loop: bool = False
    duration_seconds: float | None = None   # 0.5–22.0, optional
    title: str = ""                    # auto-fills from text[:60] if empty
```

**Logic:**
1. Read ElevenLabs API key from `config/api_keys.json` → `["elevenlabs"]["api_key"]`
2. Raise HTTP 503 if key is missing or blank
3. Call `ElevenLabs(api_key=key).text_to_sound_effects.convert(text=body.text, loop=body.loop, duration_seconds=body.duration_seconds)`
4. Collect the generator into bytes
5. Derive title: `body.title or body.text[:60]`
6. Call `SfxService(db).import_sfx(title, sound_type=None, source="elevenlabs", file_bytes=bytes, filename="sfx.mp3", is_loopable=body.loop)`
7. Return the new SFX dict (201)

**Error responses:**
- `503` — API key not configured
- `502` — ElevenLabs API error (surface message)

### `SfxService.import_sfx()` change

Add `is_loopable: bool = False` parameter, write it to the `SfxAsset` row.

---

## Frontend

### `sfxApi.generate()` — `console/frontend/src/api/client.js`

```js
generate: (body) => fetchApi('/api/sfx/generate', {
  method: 'POST',
  body: JSON.stringify(body),
})
```

### `GenerateSFXModal` — `console/frontend/src/pages/SFXPage.jsx`

New component in the same file as `ImportModal`. Inputs:

| Field | Type | Notes |
|---|---|---|
| Prompt | textarea | required; typing updates title if title is still auto-derived |
| Title | text input | optional; prefilled from `prompt[:60]`; user can override |
| Duration | number | 0.5–22, step 0.5, optional — empty = ElevenLabs decides |
| Loop | checkbox | maps to `loop` API param |

**Submit flow:**
1. Validate prompt is non-empty
2. Show loading spinner on Generate button
3. Call `sfxApi.generate({ text, title, loop, duration_seconds })`
4. On success: close modal, call `onGenerated()` to refresh grid
5. On error: show error toast, keep modal open

### `SFXPage` changes

- Add `showGenerate` state
- Add **"Generate SFX"** button (primary, accent purple) next to existing "Import SFX" button
- Render `<GenerateSFXModal>` when `showGenerate` is true

---

## Files Changed

| File | Change |
|---|---|
| `console/backend/models/sfx_asset.py` | Add `is_loopable` column |
| `console/backend/alembic/versions/XXX_add_sfx_is_loopable.py` | Migration |
| `console/backend/services/sfx_service.py` | Add `is_loopable` to `import_sfx()` and `_sfx_to_dict()` |
| `console/backend/routers/sfx.py` | Add `GenerateBody` + `POST /sfx/generate` endpoint |
| `console/frontend/src/api/client.js` | Add `sfxApi.generate()` |
| `console/frontend/src/pages/SFXPage.jsx` | Add `GenerateSFXModal` + "Generate SFX" button |

---

## Out of Scope

- `sound_type` tagging for generated SFX (leave null)
- Celery async generation
- Looping playback in the browser player (is_loopable is stored metadata only)
- ElevenLabs `prompt_influence` parameter exposure
