# YouTube Video Pipeline — Design Spec
**Date:** 2026-04-30  
**Status:** Approved  
**Scope:** Template-driven YouTube long-form video pipeline integrated into AI Media Console

---

## 1. Overview

Extends the console to support two parallel production tracks:
- **Short Videos** — existing TikTok/Shorts pipeline (unchanged)
- **YouTube Long-form** — new ASMR and Soundscape videos (1–10h), produced from Suno music + SFX layers + MidJourney/Runway visuals

A **template-driven architecture** (Approach C) unifies both tracks. All production jobs reference a `video_template`, which carries render config, SFX defaults, and prompt templates. Adding future YouTube templates requires a new DB row and a new creation form — no code changes to the pipeline.

---

## 2. Navigation Restructure

Sidebar gets four labeled sections (non-collapsible dividers, like VS Code):

```
LIBRARY
  Niches
  Music
  SFX               ← new
  Assets            ← extended (MidJourney + Runway)

SHORT VIDEOS
  Composer
  Scraper
  Scripts
  Production

YOUTUBE VIDEOS
  YouTube Videos    ← new page

  Uploads           ← shared, no section label
  Pipeline

ADMIN
  LLM               ← extended (Runway API)
  Performance
  System
```

`App.jsx` — `ALL_TABS` gets a `section` field: `'library'` | `'short'` | `'youtube'` | `'shared'` | `'admin'`. Sidebar renders section headers between groups. Role filtering unchanged.

---

## 3. Music Management — Suno Manual Flow

### 3.1 Provider rename
Current `suno` (API-generated via SunoAPI) → renamed to `sunoapi` in DB, badge, and filter dropdown. New `suno` = manual import from suno.com.

Badge colors: `SUNOAPI` purple · `SUNO` violet (distinct shade) · `LYRIA-CLIP` blue · `LYRIA-PRO` green · `IMPORT` grey

### 3.2 GenerateModal — provider moved to top

When provider is `SunoAPI`, `Lyria Clip`, `Lyria Pro` → current layout unchanged.

When provider is `Suno (Manual)` → modal transforms:

```
Provider      [Suno (Manual) ▼]       ← moved to top
Music Type    [ASMR ▼]                ← new: determines prompt + warnings

┌── SUNO PROMPT ────────────────────────────────┐
│ [Instrumental] heavy rainfall on glass...     │
│                                        [Copy] │
└───────────────────────────────────────────────┘

⚠ ASMR SOUND RULES
• No melody — melody disrupts sleep
• No sudden volume peaks
• Keep texture consistent throughout
• High-frequency roll-off above 12kHz

▸ HOW TO EXTEND ON SUNO  (collapsible)
  Step 1 — Generate initial clip (~2 min)
  Step 2 — Click ··· → Extend
  Step 3 — Extend again from the NEW clip (not the original)
  Step 4 — Repeat 2–4× more
  Step 5 — On the last clip: ··· → Get Whole Song → Download MP3

  ASMR: 2–3 extends (~6 min total) is enough — texture loops invisibly
  Soundscape: 4–5 extends (~10 min) — melody needs longer variation

Upload finished file
[  Drop MP3/WAV here or click to browse  ]

Title / Niches / Moods / Genres (same as Import modal)
```

Footer shows **Upload** instead of **Generate + Expand with Gemini** when Suno manual is selected.

### 3.3 Music type config (data-driven)

Music type config is **derived from `video_templates`** — no separate table needed. ASMR music type → `video_templates` row with slug `asmr` (`suno_prompt_template`, `sound_rules`, `suno_extends_recommended`). Soundscape music type → slug `soundscape`. The Music Type dropdown in the Suno manual modal maps directly to template slugs.

| type (template slug) | extends_recommended | key sound rules |
|---|---|---|
| ASMR | 2–3 | no melody, no peaks, roll-off >12kHz |
| Soundscape | 4–5 | subtle melody ok, wide stereo, dynamic range moderate |

Adding a new music type = adding a new YouTube template row. No modal code changes.

---

## 4. SFX Asset Management

### 4.1 New `sfx_assets` table

| field | type | notes |
|---|---|---|
| `id` | uuid | |
| `title` | text | e.g. "Heavy Rain Stereo" |
| `file_path` | text | |
| `source` | enum | `freesound` \| `import` |
| `sound_type` | varchar | free-text, indexed (see suggestion list below) |
| `duration_s` | float | |
| `usage_count` | int | |

`sound_type` is free-text (not enum) — filter on SFX page loads distinct values dynamically. UI shows a grouped combo input with curated suggestions:

```
RAIN      rain_heavy · rain_light · rain_window · rain_forest · rain_tent
WATER     ocean_waves · stream_river · waterfall · fountain · lake
WEATHER   thunder · wind_gentle · wind_strong · blizzard · hail
FIRE      fireplace · campfire · crackling_embers
NATURE    birds · crickets · forest_ambience · leaves_rustling · frogs
URBAN     cafe_chatter · coffee_machine · pub_tavern · city_traffic
          train · keyboard_typing · pages_turning · restaurant
NOISE     pink_noise · white_noise · brown_noise
SPECIAL   space_hum · magical_ambient · underwater · crowd_distant
```

### 4.2 SFX page (Library section)

Same pattern as Music page: list table with play/edit/delete, filter by `sound_type`, `+ Import` button. No generation — all SFX are manual imports.

### 4.3 Template SFX pack

Stored in `video_templates.sfx_pack` JSON:

```json
{
  "foreground": { "asset_id": "uuid", "volume": 0.60 },
  "midground":  { "asset_id": "uuid", "volume": 0.30 },
  "background": { "asset_id": "uuid", "volume": 0.10 }
}
```

### 4.4 Render — ffmpeg audio mix

```bash
ffmpeg \
  -i music.mp3 \
  -stream_loop -1 -i foreground.wav \
  -stream_loop -1 -i midground.wav \
  -stream_loop -1 -i background.wav \
  -filter_complex \
    "[1]volume=0.60[fg];[2]volume=0.30[mid];[3]volume=0.10[bg];
     [0][fg][mid][bg]amix=inputs=4:duration=first" \
  -t {target_duration_seconds} \
  output_audio.wav
```

Music is the duration reference. All SFX loop to match. The mixed audio is then composed with the visual loop.

---

## 5. Assets — MidJourney + Runway Integration

### 5.1 Schema additions to `video_assets`

| new field | type | notes |
|---|---|---|
| `asset_type` | enum | `still_image` \| `video_clip` |
| `parent_asset_id` | uuid FK → self | Runway loop → MidJourney source |
| `generation_prompt` | text | MidJourney or Runway prompt |
| `runway_status` | enum | `none` \| `pending` \| `ready` \| `failed` |

New source badge values: `MIDJOURNEY` (orange) · `RUNWAY` (teal)

### 5.2 Import flows

**`+ Import Still` (MidJourney)** — uploads `.jpg/.png`, stores as `still_image`, records MidJourney prompt. Card shows image thumbnail + **"Animate with Runway →"** button.

**`+ Import Video`** — unchanged for manual loops.

### 5.3 "Animate with Runway" modal

```
Source image    [thumbnail preview]
Runway prompt   [pre-filled from template if triggered from YouTube
                 video creation form, otherwise blank]
Motion intensity  [━━●──────]  2/10
Duration          [5s ▼]
                        [Cancel]  [Generate Loop →]
```

Celery task → Runway API → polls → saves new `video_clip` asset with `parent_asset_id` set → `runway_status = ready`. MidJourney source card shows linked badge to generated loop.

### 5.4 Visual source options (in YouTube video creation form)

| option | flow |
|---|---|
| MidJourney → Runway (hybrid) | Upload MJ still → Runway animates → loop saved to Assets |
| Runway only | Text prompt → Runway generates video loop directly |
| Manual import | Editor brings finished loop from any external tool |

### 5.5 LLM tab — Runway section

Alongside Gemini and Ollama: Runway API key, model selector (`gen3-alpha` / `gen4-turbo`), test connection. Credit usage shown if available from Runway API, otherwise omitted.

Celery task for Runway animation polls every 30s, times out after 10 minutes, marks `runway_status = failed` on timeout.

### 5.6 Assets page filters

Filter bar gains: `asset_type` toggle (All / Stills / Video Clips) + source additions (MidJourney, Runway). Still images show as image cards; video clips show as video previews.

---

## 6. Video Templates + YouTube Videos Page

### 6.1 `video_templates` table

| field | type | notes |
|---|---|---|
| `id` | uuid | |
| `slug` | varchar | `asmr` \| `soundscape` \| `asmr_viral` \| `soundscape_viral` |
| `label` | text | Display name |
| `output_format` | enum | `landscape_long` \| `portrait_short` |
| `target_duration_h` | float | Default duration (editor can override) |
| `suno_extends_recommended` | int | null for viral shorts |
| `sfx_pack` | JSON | null for viral shorts |
| `suno_prompt_template` | text | |
| `midjourney_prompt_template` | text | |
| `runway_prompt_template` | text | |
| `sound_rules` | JSON array | Warning strings for Suno guide |
| `seo_title_formula` | text | |
| `seo_description_template` | text | |

Seeded with 4 rows. Future templates = new rows, no code changes.

### 6.2 `youtube_videos` table

| field | type |
|---|---|
| `id` | uuid |
| `title` | text |
| `template_id` | FK → video_templates |
| `theme` | text |
| `music_track_id` | FK → music_tracks |
| `visual_asset_id` | FK → video_assets (Runway loop) |
| `sfx_overrides` | JSON (null = use template defaults) |
| `seo_title` | text |
| `seo_description` | text |
| `seo_tags` | text[] |
| `target_duration_h` | float |
| `status` | enum: `draft` → `rendering` → `ready` → `uploaded` |
| `output_path` | text |
| `created_at`, `updated_at` | timestamp | |

### 6.3 YouTube Videos page

```
YouTube Videos                    [+ New ASMR]  [+ New Soundscape]

[All ▼]  [Status: All ▼]  [Search...]

┌──────────────────────────────────────────────────────┐
│ ASMR  Heavy Rain Window — 8h           ● ready       │
│       🎵 asmr_rain_20260430  🖼 rain_window_loop      │
│              [+ Make Short]  [Preview]  [Upload]  [···]│
├──────────────────────────────────────────────────────┤
│ SOUNDSCAPE  Rainy Tokyo Night — 3h     ● rendering   │
│       🎵 tokyo_night_01  🖼 tokyo_street_loop  ██░    │
│                                          [···]       │
└──────────────────────────────────────────────────────┘
```

### 6.4 Creation form (slide-over panel, 5 sections)

```
① THEME & SEO
  Theme         [                    ]
  Duration      [8h ▼]  custom option available
                💡 ASMR recommended: 8–10h
  SEO Title     [pre-filled from formula, editable]
  SEO Tags      [generated from template tag list + theme keyword, editable]

② MUSIC
  [Pick from library]  or  [Open Suno Guide →]
  Suno Prompt (reference / copy):  [pre-filled]  [Copy]

③ VISUAL
  Source  ○ MidJourney → Runway  ○ Runway only  ○ Manual import
  [Pick existing loop]  or  [Create new →]
  MidJourney Prompt:  [pre-filled, copyable]
  Runway Prompt:      [pre-filled, adjustable]

④ SFX LAYERS  (template defaults, override per layer)
  Foreground 60%  [rain_heavy     ] [━━━━━━━●──] [swap]
  Midground  30%  [thunder_distant] [━━━●──────] [swap]
  Background 10%  [pink_noise     ] [●─────────] [swap]

⑤ RENDER
  Output quality  [1080p ▼]
                    [Cancel]  [Queue Render →]
```

Duration `custom` option shows a number input (hours, accepts decimals).

---

## 7. Viral Shorts — asmr_viral / soundscape_viral

Independently produced 9:16 vertical shorts. Created from the YouTube Videos page via **"+ Make Short"** on any `ready` YouTube video card.

### 7.1 Creation form (lightweight modal)

```
NEW ASMR VIRAL SHORT
──────────────────────────────────────
Parent video   Heavy Rain Window — 8h  (read-only)
Template       asmr_viral              (auto-selected)

Music          ○ Same as parent  ○ Pick different
Visual         ○ Same loop (9:16 crop)  ○ Pick different
Duration       [58s]  (fixed)
CTA overlay    [Full 8-hour version on channel ↑]  (editable)
CTA position   ○ Last 10s  ○ Throughout

                          [Cancel]  [Queue Render →]
```

The resulting job is a standard `production_job` with `template = asmr_viral` and `parent_youtube_video_id` FK. Appears in the Production page (Short Videos section), filterable by template.

---

## 8. Pipeline + Uploads Integration

### 8.1 Pipeline page

One addition: **format filter** alongside existing Type and Status filters.

```
[All ▼]  [Type ▼]  [Status ▼]  [Format: All ▼]
                                All · Short · YouTube Long
```

YouTube render jobs display a `YOUTUBE` template badge and a different step sequence:

```
Short:    Scrape → Generate → TTS → Render → Done
YouTube:  Mix Audio → Loop Visual → Compose → Render → Done
```

No other changes — same WebSocket, same job rows, same log panel.

### 8.2 Uploads page

Videos sub-tab gets a **format toggle**:

```
[All]  [Short]  [YouTube Long]
```

YouTube long-form entries show:
- Duration badge: `8h` / `3h` instead of seconds
- Platform restricted to YouTube only (TikTok/Instagram hidden)

YouTube Videos page "Upload →" button jumps to Uploads pre-filtered to that video. Uploads remains the single place to manage upload execution.

---

## 9. Data Flow Summary

```
LIBRARY
  Music (Suno manual → upload MP3)  ─────────────────┐
  SFX (Freesound import)            ──────────────┐  │
  Assets (MJ still → Runway loop)   ───────────┐  │  │
                                               │  │  │
YOUTUBE VIDEOS page                            │  │  │
  Creation form                                │  │  │
    ├── picks music track           ───────────┼──┘  │
    ├── picks visual loop           ───────────┘     │
    ├── SFX layers (template default + override) ────┘
    └── queues youtube_render job
          ↓
PIPELINE (youtube_render job)
  Mix Audio (music + 3 SFX layers, ffmpeg amix)
  Loop Visual (ffmpeg -stream_loop to target_duration)
  Compose (audio + visual → final MP4)
  Render (ffmpeg quality pass)
          ↓
UPLOADS (YouTube Data API v3)

YouTube Videos page → "+ Make Short" →
PRODUCTION (asmr_viral job, 9:16, 58s)
  Compose (music clip + cropped visual + CTA overlay)
          ↓
UPLOADS (TikTok / YouTube Shorts)
```

---

## 10. Backend Tasks Summary

| service/router | new file | notes |
|---|---|---|
| `sfx_service.py` | `services/sfx_service.py` | CRUD, file upload, usage tracking |
| `sfx` router | `routers/sfx.py` | REST endpoints |
| `youtube_video_service.py` | `services/youtube_video_service.py` | CRUD, status workflow |
| `youtube_videos` router | `routers/youtube_videos.py` | REST + trigger render |
| `youtube_render_task` | `tasks/youtube_render_task.py` | Celery: mix audio, loop visual, compose |
| `runway_service.py` | `services/runway_service.py` | Runway API client, poll task |
| migration | `alembic/versions/` | sfx_assets, video_templates, youtube_videos, video_assets extensions (asset_type, parent_asset_id, generation_prompt, runway_status), production_jobs extension (parent_youtube_video_id FK, template slug), music_tracks rename suno→sunoapi |

---

## 11. Frontend Tasks Summary

| page/component | file | notes |
|---|---|---|
| App.jsx nav restructure | `App.jsx` | section headers, new tabs |
| SFX page | `pages/SFXPage.jsx` | import, list, filter, play |
| Assets page extension | `pages/VideoAssetsPage.jsx` | MJ/Runway sources, Animate modal, filters |
| MusicPage Suno manual modal | `pages/MusicPage.jsx` | provider reorder, Suno guide flow |
| YouTube Videos page | `pages/YouTubeVideosPage.jsx` | list + slide-over creation form |
| Make Short modal | inside YouTubeVideosPage | lightweight viral short form |
| Pipeline format filter | `pages/PipelinePage.jsx` | format dropdown, YOUTUBE badge |
| Uploads format toggle | `pages/UploadsPage.jsx` | All/Short/YouTube Long toggle |
| LLM Runway section | `pages/LLMPage.jsx` | API key, model, test, credit usage |
