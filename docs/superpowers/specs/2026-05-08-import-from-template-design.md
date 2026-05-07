# Import from Template — Design Spec

**Date:** 2026-05-08
**Status:** Approved

---

## Overview

Add an "Import Template" button inside the YouTube create modal (`CreationPanel`) that opens a 4-step wizard sub-modal. The wizard reads one or both JSON template files (Suno music JSON and/or soundscape SFX JSON), generates a music track via ElevenLabs and/or N SFX assets via ElevenLabs text-to-sound-effects, then pre-fills the YouTube create modal with `music_track_id` and `sound_layers` when done.

The import is entirely frontend-orchestrated using existing backend endpoints. No new backend code is required.

---

## Template JSON Formats

### Music JSON (Suno prompt format)

Example: `suno-prompt_20260506-0158_study-focus_d-dorian_koto.json`

Relevant fields:
```json
{
  "meta":       { "title": "Study Focus · D Dorian · Koto & Wind" },
  "deliverable": { "loop_safe": true },
  "composer": {
    "function_tag": "study music",
    "key_mode": "D Dorian mode",
    "bpm": 70,
    "primary_instrument": "koto",
    "harmonic_bed": "warm analog pad",
    "textural_layer": "wind through trees",
    "dynamic_rule": "no crescendo, no climax",
    "reverb": "warm hall reverb",
    "timbre": "lush and atmospheric"
  },
  "suno": { "style_of_music": "study music, koto..." }
}
```

Validation: must have `composer` or `suno.style_of_music`.

### SFX JSON (soundscape visual prompt format)

Example: `2026-05-07_soundscapes_amazon-rainforest-cabin-morning-rain.json`

Relevant fields:
```json
{
  "meta": { "title": "Amazon Rainforest — Cabin Morning Rain" },
  "sfx": {
    "background": { "english_prompt": "...", "loop_type": "crossfade" },
    "midground":  [ { "name_en": "...", "english_prompt": "...", "interval_seconds": "10-18", ... } ],
    "foreground": [],
    "random_sfx": {
      "trigger_interval_seconds": "60-100",
      "items": [ { "name_en": "...", "english_prompt": "...", "automation_only": false } ]
    }
  }
}
```

Validation: must have `sfx` key.

---

## Architecture

Entirely frontend-driven. Reuses existing endpoints:

| Endpoint | Used for |
|---|---|
| `POST /api/music/elevenlabs/plan` | Generate composition plan from text prompt |
| `POST /api/music/elevenlabs/compose` | Start async music generation from plan |
| `GET /api/music/tasks/{task_id}` | Poll music generation status |
| `POST /api/sfx/generate` | Generate one SFX asset (sync per item) |

---

## Data Mapping

### Music JSON → ElevenLabs composition prompt

Built from `composer` fields:

```
"{function_tag}, {key_mode}, {bpm} BPM, {primary_instrument}, {harmonic_bed},
{textural_layer}, {dynamic_rule}, {reverb}, {timbre}, instrumental, no vocals"
```

Fallback: use `suno.style_of_music` if `composer` is absent.

`music_length_ms` is always **600,000** (600 seconds fixed).

### SFX JSON → items to generate

Items collected in order: `background` (1) → `midground[]` → `foreground[]` → `random_sfx.items[]`.

`automation_only: true` items are silently skipped — they are volume/reverb automation instructions, not audio files.

Per-item mapping to `POST /api/sfx/generate`:
```js
{
  text:             item.english_prompt,
  loop:             layer === 'background',  // only background loops
  title:            item.name_en || item.name_vi || item.english_prompt.slice(0, 60),
  // duration_seconds omitted — let ElevenLabs decide
}
```

### SFX assets → sound_layers

After all SFX assets are generated, `sound_layers` is assembled:

```js
{
  background: { asset_id: bgAsset.id, volume: 0.4 },

  midground: {
    pool:             midAssets.map(a => a.id),
    volume:           0.5,
    interval_min_s:   min of all midground item interval mins,
    interval_max_s:   max of all midground item interval maxes,
  },

  foreground: {
    pool:             fgAssets.map(a => a.id),
    volume:           0.7,
    interval_min_s:   min of all foreground item interval mins,
    interval_max_s:   max of all foreground item interval maxes,
  },

  random_sfx: {
    pool:             rsfxAssets.map(a => a.id),   // automation_only excluded
    volume:           0.6,
    interval_min_s:   parsed from trigger_interval_seconds (e.g. "60-100" → 60),
    interval_max_s:   parsed from trigger_interval_seconds (e.g. "60-100" → 100),
  },
}
```

Layers with no items are omitted. Interval strings (e.g. `"10-18"`) are parsed by splitting on `-`.
Volumes use spec defaults (0.4/0.5/0.7/0.6) — the JSON uses dB-relative values that don't map cleanly to the 0–1 scale.

---

## UI: ImportFromTemplateModal

New component in `YouTubeVideosPage.jsx`. Opened by a ghost button "↓ Import Template" added to `CreationPanel`.

### Trigger Button Placement

In `CreationPanel`, in the modal header actions row (alongside the existing close button):
```jsx
<Button variant="ghost" size="sm" onClick={() => setShowImportTemplate(true)}>
  ↓ Import Template
</Button>
```

Always visible regardless of form state.

### Step 1 — Input

Two panels (Music JSON / SFX JSON), each optional:

- **File picker** (`accept=".json"`) + **"or paste"** toggle revealing a textarea
- On file select or paste: parse JSON immediately
  - Success: green badge showing title from `meta.title`
  - For SFX: also shows item count: `🔊 12 sounds (1 bg, 3 mid, 0 fg, 8 random, 2 skipped)`
  - Failure: inline red error (invalid JSON / missing required keys)
- "Next →" button enabled when at least one JSON is valid

### Step 2 — Music Plan Preview *(skipped if no music JSON)*

1. Shows read-only "Extracted Prompt" textarea pre-filled from `composer` fields
2. "Generate Composition Plan →" button → calls `POST /music/elevenlabs/plan`, shows spinner
3. On success: editable monospace JSON textarea (~20 lines) pre-filled with the plan
4. User can edit plan JSON before proceeding
5. "Next: Generate →" enabled once plan is loaded and JSON is valid (client-side parse check)
6. On plan API error: inline error + "Retry" button; wizard does not advance

### Step 3 — Generation Progress

Runs automatically on entry. Sequential order: music first (if present), then SFX items.

Vertical list, one row per item:
```
🎵  Study Focus · D Dorian · Koto & Wind    [generating… ████░░]
🔊  Background Rain on Canopy               [✓ done]
🔊  Rain Drop on Wooden Floor               [✓ done]
🔊  Tropical Leaves Rustling                [generating…]
🔊  Light Rain on Deck                      [pending]
🔊  Distant Wind Gust                       [⚠ skipped: automation_only]
…
```

- Music row shows a pulsing progress bar while polling `GET /music/tasks/{task_id}`
  - Poll interval: 3 seconds
  - Timeout: 5 minutes total; on timeout → mark failed, continue to SFX
- SFX rows run one at a time: each becomes "generating" then "done" or "failed" before the next starts
- Failed items show red badge + truncated error message; generation continues for remaining items
- No user interaction in this step

### Step 4 — Done

Summary panel:
```
✓  Music track saved: Study Focus · D Dorian · Koto & Wind  (600s)
✓  11 / 12 SFX saved  (1 failed: ElevenLabs quota)
⚠  2 SFX skipped (automation_only)
```

Buttons:
- **"Apply to Video →"** — visible when at least one item succeeded
  - Calls `onImported({ music_track_id, sound_layers })` and closes sub-modal
  - `music_track_id` is `null` if music generation failed or no music JSON was provided
  - `sound_layers` is `{}` if no SFX JSON was provided or all SFX failed
  - Parent `CreationPanel` receives the result and sets:
    - `musicTrackIds` adds the new track id (playlist append)
    - `form.music_track_id` set to new track id (single-track selector)
    - `soundLayers` state updated with assembled `sound_layers`
- **"Close"** — always visible; closes without applying

**All failed state:** If both music and all SFX failed, hide "Apply to Video →", show only "Close".

---

## Error Handling Summary

| Stage | Failure | Behaviour |
|---|---|---|
| JSON parse (Step 1) | Invalid JSON / missing keys | Inline red error, Next disabled |
| Plan API (Step 2) | HTTP error | Inline error + Retry button, wizard stays on step 2 |
| Music compose (Step 3) | Task failed or timeout | Music row marked failed, continue to SFX |
| SFX generate (Step 3) | HTTP error | Item marked failed, continue to next item |
| All items failed | — | Step 4 shows error state, Apply button hidden |

---

## Files Changed

| File | Change |
|---|---|
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | Add `ImportFromTemplateModal` component + `showImportTemplate` state + "↓ Import Template" button in `CreationPanel` + `onImported` handler to pre-fill form state |

No backend changes. No new files outside `YouTubeVideosPage.jsx`.

---

## Out of Scope

- Automatic discovery of paired JSON files via `paired_visual_file` / `paired_suno_file` fields
- Per-SFX volume derived from `mix_level_db_relative_to_music` (spec defaults used instead)
- Editing individual SFX prompts before generation
- Re-running failed items after Step 3 completes
- SFX `sound_type` classification (saved with `sound_type: null`)
