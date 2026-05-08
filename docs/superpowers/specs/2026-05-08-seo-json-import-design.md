# SEO JSON Import — Design Spec
Date: 2026-05-08

## Problem

The "Import Template — Select Files" modal in `YouTubeVideosPage.jsx` currently extracts SEO data (title, description, tags) as a side-effect of loading the SFX JSON file. SEO data is now produced as a dedicated `*_seo.json` file (e.g. `output/seo/2026-05-06_soundscapes_bamboo-engawa-rain_seo.json`) with a richer, purpose-built structure. The SFX JSON should only be responsible for sound design; SEO should come from the SEO JSON.

## Goal

Add a third file-picker section ("SEO JSON") to Step 1 of the Import Template modal. When an SEO JSON file is loaded, its data populates the form's SEO fields instead of the SFX-derived extraction. Existing SFX-based SEO extraction is kept as a fallback for backwards compatibility.

## Scope

Frontend only — `console/frontend/src/pages/YouTubeVideosPage.jsx`. No backend changes. No DB schema changes. No API changes.

## SEO JSON Format (source of truth)

File naming convention: `{date}_{channel}_{slug}_seo.json`  
Location: `output/seo/`

Relevant fields:
```json
{
  "meta":        { "video_length_hours": 8 },
  "titles":      { "recommended": "…", "alternatives": ["…"] },
  "description": { "full": "…" },
  "tags":        { "all": ["…", "…"] }
}
```

Fields ignored for now: `pinned_comment`, `thumbnail`, `chapter_markers`, `cards`, `end_screen`.

## Data Flow

```
seoJson loaded   →  extractSeoFromSeoJson(seoJson)   [priority]
sfxJson loaded   →  extractSeoFromSfxJson(sfxJson)   [fallback, unchanged]
neither          →  null
```

Both `handleApplyDataOnly` and `handleApply` use this priority.  
`onImported` callback signature is unchanged: `{ music_track_id, sound_layers, seo, prompts }`.

## Field Mapping

| SEO JSON field              | Form field        |
|-----------------------------|-------------------|
| `titles.recommended`        | `seo_title`       |
| `description.full`          | `seo_description` |
| `tags.all` (joined `, `)    | `seo_tags`        |
| `meta.video_length_hours`   | `target_duration_h` (optional) |

## New Functions

### `parseSeoJson(text: string) → object`
Parses and validates raw JSON text. Throws if `titles.recommended` and `description.full` are both absent.

### `extractSeoFromSeoJson(seoJson: object) → SeoFields`
Maps SEO JSON fields to the form's SEO shape `{ seo_title, seo_description, seo_tags, target_duration_h }`.

## UI Changes — Step 1 of Import Template Modal

A third section is appended after SFX JSON, following the identical File/Paste toggle pattern:

- Label: `SEO JSON` (same style as `MUSIC JSON` / `SFX JSON`)
- File input: accepts `.json`
- Paste textarea: placeholder `Paste SEO JSON here…`
- On success: green badge showing `titles.recommended` (truncated to ~60 chars) + tag count
- On error: red error message
- The existing SFX JSON inline SEO preview (Theme / Duration / Title / Tags) is unchanged; it only appears when `sfxJson` is loaded and no `seoJson` is present, so it degrades naturally

## State Changes in `ImportFromTemplateModal`

New state variables (Step 1):
- `seoJson` / `setSeoJson`
- `seoJsonError` / `setSeoJsonError`
- `seoMode` / `setSeoMode` — `'file'` | `'paste'`
- `seoPaste` / `setSeoPaste`

`canNext1` updated:
```js
const canNext1 = musicJson !== null || sfxJson !== null || seoJson !== null
```

## Out of Scope

- Auto-discovery of SEO file by slug
- Storing `pinned_comment`, `thumbnail`, `chapter_markers` on the video record
- Backend / DB changes
