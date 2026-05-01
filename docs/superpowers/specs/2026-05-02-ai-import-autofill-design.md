# AI Import Autofill — Design Spec

**Date:** 2026-05-02
**Feature:** AI-assisted autofill for Music, SFX, and Video/Image Asset import modals

---

## Overview

Add an AI button to the three existing import modals (Music, SFX, Video/Image Asset). When clicked, it sends the selected file's metadata plus any values the user has already typed to a backend Gemini endpoint. Gemini returns structured suggestions for all modal fields, which overwrite the current form state. This reduces manual metadata entry for imported files.

---

## Architecture

```
[Import Modal]
  → user selects file + optionally fills fields
  → clicks "AI ✨" button (disabled until file selected)
  → POST /api/llm/autofill { modal_type, metadata, form_values }
      → AutofillPromptBuilder.build(modal_type, metadata, form_values) → prompt string
      → GeminiRouter.generate(prompt) → raw JSON string
      → AutofillResponseParser.parse(modal_type, raw) → typed dict
  → frontend receives typed dict → overwrites all form fields
```

**Backend location:** `routers/llm.py` (existing) + `services/llm_service.py` (existing)
**Frontend location:** Each import modal component + `api/client.js`

The endpoint reuses the existing `GeminiRouter` (with rate limiting) from `rag/llm_router.py`. No new infrastructure required.

---

## Backend

### Endpoint

```
POST /api/llm/autofill
```

**Request body:**
```json
{
  "modal_type": "music" | "sfx" | "asset",
  "metadata": {
    "filename": "string",
    "file_size_bytes": "number",
    "mime_type": "string",
    "duration_s": "number | null"
  },
  "form_values": {
    "...": "any current user input, all fields optional"
  }
}
```

**Response — `music`:**
```json
{
  "title": "string",
  "niches": ["string"],
  "moods": ["uplifting" | "calm_focus" | "energetic" | "dramatic" | "neutral"],
  "genres": ["pop" | "rock" | "electronic" | "jazz" | "classical" | "hip-hop" | "ambient" | "cinematic"],
  "volume": "number (0–1)",
  "quality_score": "number (0–100)",
  "is_vocal": "boolean"
}
```

**Response — `sfx`:**
```json
{
  "title": "string",
  "sound_type": "string (from known sound type list)"
}
```

**Response — `asset`:**
```json
{
  "description": "string",
  "keywords": ["string"],
  "source": "manual" | "midjourney" | "runway" | "pexels" | "veo" | "stock"
}
```

### Prompt Templates (`AutofillPromptBuilder`)

Each modal type has a dedicated prompt template in `services/llm_service.py`. Templates instruct Gemini to:
- Return only valid JSON, no prose
- Pick `moods`, `genres`, `niches`, `keywords` from the explicitly listed allowed values only
- Not guess `volume` or `quality_score` from filename alone (use defaults: `0.15` and `80`)
- Use `form_values` as intent signals when present

### Response Parsing (`AutofillResponseParser`)

- Strips markdown code fences if Gemini wraps output in ```json blocks
- Validates against a per-modal Pydantic schema
- Missing fields are returned as `null` (not defaulted on the backend — frontend decides)

---

## Frontend

### AI Button

- Placed in the modal footer, to the left of Cancel/Import
- Disabled when no file is selected
- Shows a spinner and is disabled while the request is in flight
- Label: sparkle/AI icon (consistent with existing "✨ Expand with Gemini" pattern)

```
[ ✨ AI ]  [ Cancel ]  [ Import ]
```

### Metadata Extraction

Collected from the `File` object at button-click time:
- `file.name`, `file.size`, `file.type` — always available
- `duration_s` — extracted via Web Audio API (already implemented in MusicPage; SFX reuses same pattern; assets omit)

### Field Mapping (`handleAutofill`)

Each modal has a `handleAutofill(data)` function that calls its existing React state setters. Only fields present (non-null) in the response are overwritten.

**Music:**
```js
if (data.title != null) setTitle(data.title)
if (data.niches != null) setSelectedNiches(data.niches)
if (data.moods != null) setSelectedMoods(data.moods)
if (data.genres != null) setSelectedGenres(data.genres)
if (data.volume != null) setVolume(data.volume)
if (data.quality_score != null) setQualityScore(data.quality_score)
if (data.is_vocal != null) setIsVocal(data.is_vocal)
```

**SFX:**
```js
if (data.title != null) setTitle(data.title)
if (data.sound_type != null) setSoundType(data.sound_type)
```

**Asset:**
```js
if (data.description != null) setDescription(data.description)
if (data.keywords != null) setKeywords(data.keywords.join(', '))
if (data.source != null) setSource(data.source)
```

### API Client

New function in `api/client.js`:
```js
autofillApi.suggest(modal_type, metadata, form_values)
// → POST /api/llm/autofill
```

---

## Error Handling

| Scenario | Backend response | Frontend behavior |
|---|---|---|
| Gemini returns malformed JSON | `422` with message | Toast: "AI suggestion failed — fill in manually". Form unchanged. |
| Rate limited | `429` | Toast: "AI quota reached — try again later". Form unchanged. |
| Network error | — | Standard fetch error toast. Form unchanged. |
| Gemini omits a field | `200`, field is `null` | That field is not overwritten; user's current value preserved. |
| Filename has no useful signal | `200`, generic defaults | Gemini returns best-effort values; user can edit. |

---

## Files Changed

### Backend
- `console/backend/routers/llm.py` — add `POST /api/llm/autofill` endpoint
- `console/backend/services/llm_service.py` — add `AutofillPromptBuilder` and `AutofillResponseParser` classes

### Frontend
- `console/frontend/src/pages/MusicPage.jsx` — AI button + `handleAutofill` in `ImportModal`
- `console/frontend/src/pages/SFXPage.jsx` — AI button + `handleAutofill` in `ImportModal`
- `console/frontend/src/pages/VideoAssetsPage.jsx` — AI button + `handleAutofill` in `ImportAssetModal`
- `console/frontend/src/api/client.js` — add `autofillApi.suggest()`

---

## Out of Scope

- Image/video content analysis (multimodal Gemini) — metadata only
- Auto-trigger on file select — manual trigger only
- Per-field confirmation UI — full overwrite
- SFX duration extraction — omitted (low signal value for sound type inference)
