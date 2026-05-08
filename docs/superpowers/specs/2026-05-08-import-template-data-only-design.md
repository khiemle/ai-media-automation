# Import Template — Data-Only Apply & Prompt Extraction Design

**Date:** 2026-05-08
**Status:** Approved

---

## Overview

Two related enhancements to the Import Template wizard (`ImportFromTemplateModal`) and `CreationPanel` in `YouTubeVideosPage.jsx`:

1. **"Apply data only" shortcut** — Step 1 gains a second action button that extracts SEO + prompt data from the loaded JSONs and applies them immediately, bypassing Steps 2–4 entirely. No audio generation.

2. **Prompt field extraction + UI rename** — Three prompt fields are extracted from the template JSONs and patched into `CreationPanel` on import: Music Prompt, Visual Prompt, Midjourney Prompt. Two existing read-only prompt display fields are renamed.

Scope: single file — `console/frontend/src/pages/YouTubeVideosPage.jsx`.

---

## Feature 1 — "Apply data only" Mode

### Step 1 Footer Change

Step 1 currently has one footer button: "Next →" (enabled when ≥ 1 JSON is valid).

After this change, Step 1 has two footer buttons:

```
[Apply data only →]   [Next →]
```

- **"Apply data only →"** — new ghost button, left of "Next →". Enabled under the same condition as "Next →" (≥ 1 valid JSON loaded).
- **"Next →"** — unchanged primary button. Proceeds to Step 2 (music plan) or Step 3 (generation). Extracts SEO + all prompts, calls `onImported(...)`, then closes the wizard immediately. Steps 2, 3, and 4 are never entered.

### "Apply data only" Logic

When clicked:

```js
const handleApplyDataOnly = () => {
  const seo         = sfxJson ? extractSeoFromSfxJson(sfxJson) : null
  const prompts     = extractPromptsFromJsons(musicJson, sfxJson)
  onImported({ music_track_id: null, sound_layers: {}, seo, prompts })
  onClose()
}
```

No music track and no sound layers are set — only SEO and prompt fields are applied.

---

## Feature 2 — Prompt Extraction

### New Helper: `extractPromptsFromJsons(musicJson, sfxJson)`

A pure function added alongside the other helpers (after `DURATION_PRESETS`):

```js
const extractPromptsFromJsons = (musicJson, sfxJson) => {
  const result = {}
  if (musicJson) result.music   = buildMusicPrompt(musicJson)
  if (sfxJson?.runway?.prompt)             result.visual     = sfxJson.runway.prompt
  if (sfxJson?.midjourney?.full_prompt)    result.midjourney = sfxJson.midjourney.full_prompt
  return result
}
```

Returns an object with only the keys that have values. Missing fields are omitted (not set to null).

### `onImported` Payload Extended

`handleApply` (Step 4 apply) and `handleApplyDataOnly` (Step 1 shortcut) both pass `prompts` in the payload:

```js
onImported({ music_track_id, sound_layers, seo, prompts })
```

`prompts` shape: `{ music?: string, visual?: string, midjourney?: string }`

### `handleTemplateImported` in `CreationPanel`

Extended to apply prompt fields using non-destructive patch semantics — a field is only updated if the import provides a non-null, non-undefined value:

```js
if (prompts?.music)      setAutofillSuno(prompts.music)
if (prompts?.visual)     setAutofillRunway(prompts.visual)
if (prompts?.midjourney) setMidjourneyPrompt(prompts.midjourney)
```

### Override / Multi-Import Rule

Every import is a **non-destructive patch**: only fields present in the incoming import are updated; all other fields retain their existing values.

Examples:
- Import 1 (SFX JSON only): sets SEO, `visual_prompt`, `midjourney_prompt`; does not touch `music_prompt` or `music_track_id`.
- Import 2 (music JSON only): sets `music_prompt`, `music_track_id`; leaves SEO, `visual_prompt`, `midjourney_prompt` from import 1 unchanged.

This applies equally to SEO fields (already the case), sound_layers (already the case), and the new prompt fields.

---

## Feature 3 — CreationPanel Field Changes

### Renamed Labels

| Old label | New label |
|---|---|
| `"Suno Prompt (reference)"` / `"Suno Prompt (AI generated)"` | `"Music Prompt"` |
| `"Runway Prompt (reference)"` / `"Runway Prompt (AI generated)"` | `"Visual Prompt"` |

The qualifier suffix `(reference)` / `(AI generated)` is dropped. Label is always just `"Music Prompt"` or `"Visual Prompt"`.

State variables `autofillSuno` and `autofillRunway` are unchanged — only the display label changes.

### New "Midjourney Prompt" Field

New state variable:
```js
const [midjourneyPrompt, setMidjourneyPrompt] = useState(null)
```

New read-only display block added **below** the "Midjourney Image (optional)" file upload, using the same style as the existing Suno/Runway prompt blocks:
- Label: `"Midjourney Prompt"`
- Value: `midjourneyPrompt`
- Copy button (clipboard)
- Only rendered when `midjourneyPrompt` is non-null

---

## Data Flow Summary

```
Step 1: Load JSON files
  ↓ "Apply data only →"
  extractSeoFromSfxJson(sfxJson)        → seo fields
  extractPromptsFromJsons(musicJson, sfxJson)
    - buildMusicPrompt(musicJson)        → prompts.music
    - sfxJson.runway.prompt              → prompts.visual
    - sfxJson.midjourney.full_prompt     → prompts.midjourney
  onImported({ music_track_id: null, sound_layers: {}, seo, prompts })
  ↓
handleTemplateImported in CreationPanel
  - patch form: theme, seo_title, seo_description, seo_tags, target_duration_h
  - setAutofillSuno(prompts.music)       → "Music Prompt" field
  - setAutofillRunway(prompts.visual)    → "Visual Prompt" field
  - setMidjourneyPrompt(prompts.midjourney) → "Midjourney Prompt" field
```

The same prompt extraction runs on Step 4 "Apply to Video →" as well — `handleApply` now also calls `extractPromptsFromJsons` and includes `prompts` in the payload.

---

## Files Changed

| File | Change |
|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Add `extractPromptsFromJsons` helper; add `handleApplyDataOnly` to `ImportFromTemplateModal`; update `handleApply` to pass `prompts`; update Step 1 footer with second button; add `midjourneyPrompt` state + display block in `CreationPanel`; rename "Suno Prompt" and "Runway Prompt" labels; update `handleTemplateImported` to patch prompt fields |

No backend changes. No new files.
