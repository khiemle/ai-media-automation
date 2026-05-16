---
name: music-video
description: Three-in-one toolkit for original instrumental music YouTube videos — Lofi Acoustic, Classical, Jazz, and EDM (all no-vocal / instrumental). (1) Music — a two-persona composer's interview (Producer + genre Artist) that outputs paste-ready Suno Custom Mode fields with an ElevenLabs Music fallback prompt. (2) Visual — Midjourney still + Runway Gen-4 loop tuned for music-video backgrounds. (3) SEO Data — YouTube title, description, tags, thumbnail text, pinned comment, end-screen, cards, chapter markers tuned for music discovery. Use whenever the user wants music, visuals, or YouTube SEO for an original instrumental music video — lofi beats, lofi acoustic, classical piano, chamber, orchestral, jazz trio, swing, bossa, EDM, future bass, melodic house, chillstep — even if they don't name Suno / ElevenLabs / Midjourney / Runway / SEO. Trigger on phrases like "make a lofi track", "suno prompt for jazz", "classical piano music for studying", "EDM instrumental", "visual for my music video", "youtube SEO for lofi mix", "data for the next video in my plan". This skill is for ORIGINAL composed instrumental music with melody, harmony, and structure — not pure ambient drone (use visual-video for sleep/ambient/ASMR drone content).
---

# Music Video — Production Toolkit

This skill bundles three production workflows for **original instrumental music** YouTube videos. It is the sibling of `visual-video` — that skill is for ambient / sleep / ASMR drone content; **this skill is for music with melody, harmony, and structure**: Lofi Acoustic, Classical, Jazz, and EDM, all instrumental (no vocals).

1. **Music** — a two-persona composer's interview (**Producer + genre Artist**) that outputs paste-ready Suno Custom Mode fields, plus an ElevenLabs Music fallback prompt
2. **Visual** — Midjourney still + Runway Gen-4 loop, tuned for music-video backgrounds (richer motion allowed than sleep content)
3. **SEO Data** — YouTube title, description, tags, thumbnail text, pinned comment, end-screen, cards, chapter markers, tuned for **music discovery** (genre + mood + use-case keywords)

Every workflow produces both a human-readable `.md` file (for the user to read and copy-paste from) and a machine-readable `.json` file. The `.json` files are the source of truth for downstream automation — a video pipeline, an audio engine, scheduled tasks, the channel launch plans in `.docs/channels/`, or anything else the user imports them into. **Both files are always required — never save one without the other.**

The three workflows are designed to chain (Music → Visual → SEO), but each can also run standalone. The SEO workflow in particular is much sharper when it can read the paired music + visual JSON files for context.

---

## When to use which workflow

| User wants… | Run workflow |
|---|---|
| A composed instrumental track — Suno fields + ElevenLabs fallback, with Producer + Artist decisions | **Music** |
| Midjourney image + Runway loop for the music-video background | **Visual** |
| YouTube title, description, tags, thumbnail text, pinned comment, chapter markers | **SEO Data** |
| Complete package for one video | **Chained** — Music → Visual → SEO |

If the user's request is ambiguous, ask which workflow they want before starting. **Never silently default to all three** — a short clarifying question is cheap.

### Routing cues

- "make a track / suno / instrumental / lofi beat / classical piece / jazz tune / EDM track / compose" → **Music**
- "make a visual / midjourney / runway / background / loop / scene for the music video" → **Visual**
- "youtube SEO / title / tags / description / thumbnail text / pinned comment / chapters" → **SEO Data**
- "give me everything for [theme]" / "complete package" / "data for the next video in the plan" → **Chained run**

For the chained run: complete each workflow fully (including saving its files) before starting the next. The Visual workflow can pull genre / mood / energy context from the Music session; the SEO workflow pulls from both. When chaining, fill the cross-file references (`paired_music_file`, `paired_visual_file`) automatically.

---

## The four genres this skill serves

This skill is built for four channels, one genre each. Every workflow adapts to the genre.

| Genre | Channel character | Music has | Typical deliverable |
|---|---|---|---|
| **Lofi Acoustic** | Warm, nostalgic, study/relax | Jazzy chords, mellow melody, vinyl texture, gentle groove | 30–60 min mixes + single-track loops |
| **Classical** | Concert-hall, timeless, focus/study | Solo piano / chamber / orchestral, real form (nocturne, adagio, prelude), dynamics, rubato | 1–3 h compilations + single pieces |
| **Jazz** | Sophisticated, evening, café/dinner | Trio/quartet, swing or bossa or ballad, head–solo–head, walking bass, comping | 1–3 h mixes + single tunes |
| **EDM** | Energetic or chill-electronic, drive/gym/focus | Build–drop structure, supersaw/bass, sidechain, hook, energy arc | 3–4 min singles + 30–60 min mix sets |

**This skill never produces vocal music.** Every track is instrumental — Suno's Instrumental toggle stays ON, lyrics field stays empty. The four channels are all no-vocal by design.

> **What this skill is NOT for:** pure ambient drone, sleep texture, ASMR, rain/fireplace soundscapes with no melody. That is `visual-video`'s job. If the user asks for "8-hour rain sounds with no melody", route them to `visual-video` instead.

---

## Universal language rule (applies to all three workflows)

**Explanations → Vietnamese. Prompts → English. No exceptions.**

| Content type | Language |
|---|---|
| Interview questions, choices, descriptions, creative briefs, Producer/Artist persona notes, reasoning, file labels | **Vietnamese** |
| Suno fields (Style of Music / Title / Exclude Styles) · ElevenLabs Music prompt · Midjourney prompt · Runway Gen-4 prompt · YouTube title / description body / tags / thumbnail text / pinned comment | **English** |
| Saved file content | Follow the same split: Vietnamese for narrative/explanation, English for all paste-ready prompt blocks and all SEO content destined for YouTube |

This rule exists because (1) the user reads Vietnamese more comfortably, and (2) Suno, ElevenLabs, Midjourney, Runway, and the YouTube algorithm all perform significantly better with English input. The SEO content in particular *must* be in English because the YouTube algorithm indexes English keywords for global reach.

**When in doubt:** if a piece of text is meant to be *pasted into a tool* (or read by an algorithm), write it in English. If it is meant to be *read by the user*, write it in Vietnamese.

---

## Workflow files

Each workflow is documented in detail in its own reference file. Read the relevant file when the user picks that workflow — do **not** load all three upfront.

- `references/music_prompt.md` — full Music workflow: the two-persona interview (Producer + genre Artist), per-genre presets, Suno field composition, ElevenLabs fallback, and canonical JSON schema. Read when the user wants a composed track.
- `references/visual_prompt.md` — full Visual workflow: Midjourney + Runway Gen-4 for music-video backgrounds, static-camera rules, motion guidance by genre, and canonical JSON schema. Read when the user wants visuals.
- `references/seo_data.md` — full SEO Data workflow: music-discovery keyword strategy, the seven SEO blocks, and canonical JSON schema. Read when the user wants YouTube metadata.

For a chained run, read all three in order (music first, visual second, SEO last).

---

## Output folder convention

All outputs land in the **current project's local path**, under a top-level `working/` folder, inside a single subfolder named after the music video. The music-video name is the kebab-case track/theme slug (e.g., `rainy-night-lofi-piano`) — the same slug used inside JSON `meta` fields. **One folder per video, four subfolders inside.**

```
./working/{music-video-name}/
├── json/      ← machine-readable outputs (music / visual / seo .json)
├── md/        ← human-readable outputs (music / visual / seo .md)
├── audio/     ← placeholder — Suno / ElevenLabs renders go here in a future pipeline step
└── videos/    ← placeholder — Runway clips and final cuts go here in a future pipeline step
```

**Always create all four subfolders** when the music-video folder is first created — even if `audio/` and `videos/` start empty. This keeps the layout predictable for downstream automation. If `./working/` itself does not exist yet, create it first.

### Filename patterns inside `json/` and `md/`

```
json/
├── {YYYY-MM-DD}_{channel}_{theme-slug}_music.json
├── {YYYY-MM-DD}_{channel}_{theme-slug}_visual.json
└── {YYYY-MM-DD}_{channel}_{theme-slug}_seo.json

md/
├── {YYYY-MM-DD}_{channel}_{theme-slug}_music.md
├── {YYYY-MM-DD}_{channel}_{theme-slug}_visual.md
└── {YYYY-MM-DD}_{channel}_{theme-slug}_seo.md
```

`channel` is `lofi` / `classical` / `jazz` / `edm`. `theme-slug` is the kebab-case music-video name. The `_music` / `_visual` / `_seo` suffix tells the three workflows apart at a glance.

If you don't yet know the project root, treat it as the user's current working folder. If the workflow is invoked outside any obvious project, ask the user once where to put the `working/` folder.

After saving, present the prompts inline in chat as well — the user wants to copy-paste right away — then mention the saved file paths at the end so they have a record.

---

## Cross-file references

When workflows are chained, fill these references automatically so downstream automation can reconstruct the full package:

- `visual.meta.paired_music_file` → path to the music JSON if it exists
- `seo.meta.paired_music_file` → path to the music JSON if it exists
- `seo.meta.paired_visual_file` → path to the visual JSON if it exists

When a workflow runs standalone, ask the user whether a paired file already exists on disk. If yes, ask for the path and load it (the SEO workflow especially benefits from this — it can pull genre, mood, BPM, and chapter cues from the paired files instead of re-asking the user).

---

## JSON schema preservation

The JSON schemas in the three reference files are hard contracts used by downstream import (the video pipeline, the channel launch plans, scheduled automation). **Do not modify these schemas.** If the user asks for a field that is not in the schema, add it as a Vietnamese note in the `.md` file — never invent new top-level JSON keys.

---

## Conversation style (applies to all three workflows)

- Keep questions short and concrete. The user is a creator who wants to ship videos, not a music-theory student — but the Music workflow's two personas DO carry real craft, so let them speak with authority.
- Offer 2–4 specific options for any step where decision fatigue is likely. ("What feel?" → "Late-night introspective, sunny and warm, or melancholic?")
- When a user gives a vague answer ("something chill"), pull a concrete proposal from the relevant genre preset and confirm it.
- Use `AskUserQuestion` for multiple-choice picks where 3–5 options can be enumerated. Use plain prose for free-text answers (artist references, channel names, mood descriptions).
- For batch work ("give me 5 tracks for the mix"), run the interview once for the *genre + mood identity*, then iterate the per-track configuration while keeping the identity fixed.
- Always follow the language rule. If the user writes in Vietnamese, respond in Vietnamese. Never write a Suno / ElevenLabs / Midjourney / Runway / SEO prompt in Vietnamese.
- If the user pastes an existing prompt and asks for fixes, skip the interview. Identify the problems, propose a corrected version inline with a short bulleted "what changed and why" note.

---

## Final step — STOP and ask about the next stage

This skill's job ends when all requested workflow files are written to disk. **Do not start uploading, rendering, or publishing on your own.**

After saving the files for the workflow(s) the user picked:

1. **Confirm what was produced.** List the absolute paths of every `.json` and `.md` file you wrote, grouped by `json/` and `md/` subfolder. If the user only ran one or two of the three workflows, list only what got written.

2. **Stop and ask the user via `AskUserQuestion`** whether they want to chain into the next stage. Use this framing (translate labels to Vietnamese if the user has been speaking Vietnamese):

   - **Question:** "Files are saved at `working/{slug}/`. What next?"
   - **Header:** "Next step"
   - **Options:**
     - "Continue to the next workflow" — if only Music or Music+Visual ran, offer to chain into the remaining workflow(s).
     - "Generate another track/variation" — run the Music workflow again for a sibling track in the same series (carry over genre + mood identity).
     - "Stop here — I'll review the files first" — stops so the user can inspect / tweak the JSON.

3. **Never** silently continue past file save into rendering or upload. The pipeline is destructive (consumes Suno / ElevenLabs / Runway quota and uploads to YouTube); the user must explicitly opt in.
