---
name: rain-visual-video
description: Three-in-one production toolkit for RAIN-themed sleep / focus YouTube videos (Rainfall Retreat channel). (1) Visual — Midjourney still + Runway Gen-4 loop + layered SFX, with rain-physics rules so rain never leaks indoors. (2) Suno Music — Suno Custom Mode prompt builder for rain-bed ambient music. (3) SEO Data — YouTube title, description, tags, thumbnail, pinned comment, chapters. Every video is rain and serves either deep sleep (8–10h) or focus/study (2–3h). Use whenever the user wants visuals, music, or SEO for a rain video — rain on a window, cabin roof, rainforest downpour, jungle waterfall, rain on leaves, monsoon storm, rain + distant thunder. Trigger on phrases like "visual for my rain video", "midjourney for a rain sleep video", "runway rain loop", "suno prompt for rain ambience", "rain sounds for studying music", "8-hour rain sounds video", "youtube SEO for rain video". Prefer over generic prompt-writing or the broader visual-video skill when the deliverable is specifically a RAIN video.
---

# Rain Visual Video — Production Toolkit

This skill bundles three production workflows for **rain-themed** relaxation / sleep / focus YouTube videos. It is the rain-specialised sibling of the general `visual-video` skill, built specifically for the **Rainfall Retreat** channel.

1. **Visual Prompt** — Midjourney + Runway Gen-4 + layered SFX sound design, with rain-physics rules baked in
2. **Suno Music** — Suno Custom Mode prompt builder for rain-bed instrumental ambience
3. **SEO Data** — YouTube title, description, tags, thumbnail text, pinned comment, end-screen, cards, chapters

Every workflow produces both a human-readable `.md` file (for the user to read and copy-paste from) and a machine-readable `.json` file. The `.json` files are the source of truth for downstream automation — a video pipeline, an audio engine, scheduled tasks, or anything else the user imports them into. **Both files are always required — never save one without the other.**

The three workflows are designed to chain (Visual → Suno → SEO), but each can also run standalone. The SEO workflow in particular is much sharper when it can read the paired visual + suno JSON files for context.

---

## What makes this skill different from `visual-video`

Use this skill — not `visual-video` — whenever the deliverable is **specifically a rain video**. The differences are not cosmetic:

- **Rain is always the hero.** The visual scene always features rain, and the SFX/music design always treats the rain bed as the primary layer, never a background texture.
- **Every video has a declared intent: `sleep` or `focus`.** This is the single most important branching decision in all three workflows. Rather than asking "ASMR or Soundscapes?", this skill asks "deep sleep or focus/study?" — and that answer drives video length, motion intensity, melody rules, thunder rules, title formula, and chapter spacing.
- **Rain-physics is a first-class rule.** The Visual workflow's Environment Physics Rule is elevated and rain-specific: rain must obey roofs, eaves, windows, and canopies. Rain falling inside a cabin is the single most common failure for this content — the workflow defends against it explicitly.
- **One channel, two intents.** All output is for the `rainfall` channel. There is no `asmr` / `soundscapes` split here — instead the `use_case` field carries `sleep` or one of the focus variants.

If the user's video is *not* rain (ocean, fireplace alone, forest birds, café), use the general `visual-video` skill instead.

---

## When to use which workflow

| User wants… | Run workflow |
|---|---|
| Midjourney image, Runway loop, rain SFX layers, scene/sound design | **Visual Prompt** |
| Style of Music + Title + Exclude Styles for Suno Custom Mode | **Suno Music** |
| YouTube title, description, tags, thumbnail text, pinned comment, chapter markers | **SEO Data** |
| Complete package for one rain video | **Chained** — Visual → Suno → SEO |

If the user's request is ambiguous, ask which workflow they want before starting. **Never silently default to all three** — running the wrong workflow wastes their time. A short clarifying question is cheap.

### Routing cues

- "make a visual / midjourney / runway / scene / SFX / sound design / rain loop" → **Visual Prompt**
- "make music / suno / rain ambience track / rain bed / sleep rain music / study rain music" → **Suno Music**
- "youtube SEO / title / tags / description / thumbnail text / pinned comment / chapters / end screen" → **SEO Data**
- "give me everything for [rain theme]" / "complete package" / "all three" → **Chained run**

For the chained run: complete each workflow fully (including saving its files) before starting the next. The Suno workflow can pull theme / intent context from the Visual session; the SEO workflow pulls from both. When chaining, fill the cross-file references (`paired_visual_file`, `paired_suno_file`) automatically.

---

## The intent question — ask this first, every time

Before any workflow starts, you must know the video's **intent**. This is non-negotiable and there is no default.

Ask: **"Video này cho ngủ sâu (sleep, 8–10h) hay cho tập trung làm việc/học (focus, 2–3h)?"**

| Intent | Video length | Motion | Melody | Thunder | Title formula | Chapters |
|---|---|---|---|---|---|---|
| **sleep** | 8–10h | 1–2/10 | none — pure texture | distant rolling only, never a crack | `Rain Sounds for Deep Sleep — [Environment] \| {N} Hours` | hourly |
| **focus** | 2–3h | 3–4/10 | barely-audible ambient pad allowed, no melodic phrase | none or extremely faint and distant | `[Environment] Rain — [Study/Focus/Deep Work] Ambience \| {N} Hour` | 30-minute |

Carry the chosen intent through all three workflows. In JSON, it lands in `meta.use_case` as `sleep`, `study`, `focus`, or `deep_work` (`study` / `focus` / `deep_work` are all "focus" intents — pick the one closest to what the user said).

---

## Universal language rule (applies to all three workflows)

**Explanations → Vietnamese. Prompts → English. No exceptions.**

| Content type | Language |
|---|---|
| Interview questions, choices, descriptions, creative briefs, composer notes, SFX layer descriptions, reasoning, file labels | **Vietnamese** |
| Midjourney prompt text · Runway Gen-4 prompt text · SFX search prompts (🔍 blocks) · Suno fields (Style of Music / Title / Exclude Styles) · YouTube title · YouTube description body · tags · thumbnail text · pinned comment | **English** |
| SFX sound names in the random list | **English** (with Vietnamese description below) |
| Saved file content | Follow the same split: Vietnamese for narrative/explanation, English for all paste-ready prompt blocks and all SEO content destined for YouTube |

This rule exists because (1) the user reads Vietnamese more comfortably, and (2) Midjourney, Runway, Suno, and the YouTube algorithm all perform significantly better with English input. The SEO content in particular *must* be in English because the YouTube algorithm indexes English keywords for global reach. Mixing languages in any prompt or SEO field degrades output quality.

**When in doubt:** if a piece of text is meant to be *pasted into a tool* (or read by an algorithm), write it in English. If it is meant to be *read by the user*, write it in Vietnamese.

---

## Workflow files

Each workflow is documented in detail in its own reference file. Read the relevant file when the user picks that workflow — do **not** load all three upfront.

- `references/visual_prompt.md` — full Visual Prompt workflow (7-step interview + rain-physics rules + SFX design + Midjourney/Runway prompt composition + canonical JSON schema). Read when the user wants visuals, scene design, or sound design.
- `references/suno_music.md` — full Suno Music workflow (5-phase composer's interview for rain-bed ambience + canonical JSON schema). Read when the user wants instrumental music.
- `references/seo_data.md` — full SEO Data workflow (interview + assembly rules + canonical JSON schema). Read when the user wants YouTube metadata.

For a chained run, read all three in order (visual first, suno second, SEO last).

---

## Output folder convention

All outputs land in the **current project's local path**, under a top-level `working/` folder, inside a single subfolder named after the rain video. The video name is the kebab-case theme slug (e.g., `jungle-cabin-roof-rain`) — the same slug used inside JSON `meta` fields. **One folder per video, four subfolders inside.**

```
./working/{rain-video-name}/
├── json/      ← machine-readable outputs (visual / suno / seo .json)
├── md/        ← human-readable outputs (visual / suno / seo .md)
├── images/    ← placeholder — Midjourney renders go here in a future pipeline step
└── videos/    ← placeholder — Runway clips and final cuts go here in a future pipeline step
```

**Always create all four subfolders** when the video folder is first created — even if `images/` and `videos/` start empty. This keeps the layout predictable for downstream automation that scans these folders. If `./working/` itself does not exist yet, create it first.

### Filename patterns inside `json/` and `md/`

```
json/
├── {YYYY-MM-DD}_rainfall_{theme-slug}_visual.json
├── {YYYY-MM-DD}_rainfall_{theme-slug}_suno.json
└── {YYYY-MM-DD}_rainfall_{theme-slug}_seo.json

md/
├── {YYYY-MM-DD}_rainfall_{theme-slug}_visual.md
├── {YYYY-MM-DD}_rainfall_{theme-slug}_suno.md
└── {YYYY-MM-DD}_rainfall_{theme-slug}_seo.md
```

`channel` is always `rainfall` for this skill. `theme-slug` is the kebab-case rain-video name. The `_visual` / `_suno` / `_seo` suffix tells the three workflows apart at a glance.

If you don't yet know the project root, treat it as the user's current working folder. If the workflow is invoked outside any obvious project, ask the user once where to put the `working/` folder.

After saving, present the prompts inline in chat as well — the user wants to copy-paste right away — then mention the saved file paths at the end so they have a record.

---

## Cross-file references

When workflows are chained, fill these references automatically so downstream automation can reconstruct the full package:

- `suno.meta.paired_visual_file` → path to the visual JSON if it exists
- `seo.meta.paired_visual_file` → path to the visual JSON if it exists
- `seo.meta.paired_suno_file` → path to the suno JSON if it exists

When a workflow runs standalone, ask the user whether a paired file already exists on disk. If yes, ask for the path and load it (the SEO workflow especially benefits from this — it can pull keywords, mood, and chapter cues from the paired files instead of re-asking the user).

---

## JSON schema preservation

The JSON schemas in `references/visual_prompt.md`, `references/suno_music.md`, and `references/seo_data.md` are hard contracts used by downstream import. **Do not modify these schemas.** They are aligned with the general `visual-video` skill so that both skills feed the same pipeline — the only rain-specific differences are in the *values* (channel is always `rainfall`, use_case is `sleep` / `study` / `focus` / `deep_work`), not in the *keys*.

If the user asks for a field that is not in the schema, add it as a Vietnamese note in the `.md` file — never invent new top-level JSON keys.

---

## Conversation style (applies to all three workflows)

- Keep questions short and concrete. The user is a creator who wants to ship videos, not a film student or a music-theory student.
- **Always establish the sleep-vs-focus intent first** (see "The intent question" above). Everything downstream branches on it.
- Offer 2–3 specific options for any step where decision fatigue is likely. ("What kind of rain?" → "Gentle even rain, heavy downpour, or rain + distant thunder?")
- When a user gives a vague answer ("something cozy"), pull a concrete proposal from the relevant rain preset and confirm it.
- Use `AskUserQuestion` for multiple-choice picks where 3–5 options can be enumerated. Use plain prose for free-text answers (channel references, length intent).
- For batch work ("give me 5 rain variations"), run the interview once for the *theme + intent*, then iterate the configuration steps for each variation while keeping theme and intent fixed.
- Always follow the language rule. If the user writes in Vietnamese, respond in Vietnamese. Never write a Midjourney / Runway / Suno / SEO prompt in Vietnamese.
- If the user pastes an existing prompt and asks for fixes, skip the interview. Identify the problems, propose a corrected version inline with a short bulleted "what changed and why" note.

---

## Final step — STOP and ask about the next stage

This skill's job ends when all requested workflow files are written to disk. **Do not start uploading, rendering, or publishing on your own** — that's a separate phase handled by the production-pipeline skill (`make-youtube-video` or the channel's `youtube-video-*` skill), which drives the AI Media Console pipeline.

After saving the files for the workflow(s) the user picked:

1. **Confirm what was produced.** List the absolute paths of every `.json` and `.md` file you wrote, grouped by `json/` and `md/` subfolder. If the user only ran one or two of the three workflows, list only what got written.

2. **Stop and ask the user via `AskUserQuestion`** whether they want to chain into the production pipeline. Use this framing (translate the labels to Vietnamese if the user has been speaking Vietnamese):

   - **Question:** "Files are saved at `working/{slug}/`. Continue into the make-youtube-video pipeline now?"
   - **Header:** "Next step"
   - **Options:**
     - "Yes — invoke `make-youtube-video` skill" — describes: hands off to the production-pipeline skill, which will upload the visual asset + thumbnail you provide, generate music + SFX, render the YouTube video with approval gates, and upload.
     - "Not yet — I'll review the files first" — describes: stops here so the user can inspect / tweak the JSON before running the pipeline.
     - "Stop here — different next step" — describes: don't auto-chain; user has another plan.

3. **Acting on the answer:**
   - **"Yes"** → invoke the `make-youtube-video` skill via the `Skill` tool with the slug as context. The downstream skill expects files at `working/{slug}/json/` matching the globs `*music.json` / `*visual.json` / `*seo.json`. **Important compatibility note:** this skill saves the music file as `..._suno.json` (its established convention). The `make-youtube-video` skill globs `*music.json` first, then falls back to `*suno.json`. Both patterns work — no rename needed. If the downstream skill cannot find the music file, point it at the actual path explicitly.
   - **"Not yet"** → end the conversation here. Tell the user how to invoke `make-youtube-video` later (a one-liner naming the slug is enough).
   - **"Stop here"** → end without any handoff. Don't volunteer additional next steps.

4. **Never** silently continue past file save into rendering or upload. Always pause for the question above. The pipeline is destructive (uploads videos to YouTube, consumes ElevenLabs / Runway / Topaz quota); the user must explicitly opt in.

### Quick reference — what each downstream skill needs

If the user picks "Yes — invoke `make-youtube-video`", they will additionally need to provide:
- A path to a local `visual.mp4` file (the background rain loop video — Runway export, stock footage, etc.)
- A path to a local `thumbnail.jpg` source image

The downstream skill asks for these via `AskUserQuestion` during execution; you do not need to gather them here. Just confirm the JSON files exist and hand off.
