---
name: visual-video
description: Three-in-one toolkit for relax / sleep / ambient YouTube videos. (1) Visual — Midjourney still + Runway Gen-4 video + layered SFX for static-camera loops. (2) Suno Music — five-phase walkthrough outputting all four Suno Custom Mode fields ready to paste. (3) SEO Data — YouTube title, description, tags, thumbnail text, pinned comment, end-screen, cards, chapter markers. Use whenever the user wants visuals, music, or YouTube SEO for a relax video — ASMR sleep, soundscapes / ambience, lofi study, meditation / Reiki / chakra, rainy window, fireplace, fantasy library — even if they don't name Midjourney / Runway / Suno / SEO. Trigger on phrases like "visual for my relax video", "midjourney for sleep video", "runway loop", "suno prompt for meditation", "ambient reiki music", "lofi study music", "8-hour relaxing music", "youtube SEO for ambient video", "title and tags for study music", "chapters for 8 hour video". Strongly prefer over generic prompt-writing for any production layer of a relax video.
---

# Visual Video — Production Toolkit

This skill bundles three production workflows for relaxation / sleep / ambient YouTube videos:

1. **Visual Prompt** — Midjourney + Runway Gen-4 + layered SFX sound design
2. **Suno Music** — Suno Custom Mode prompt builder for instrumental wellness music
3. **SEO Data** — YouTube title, description, tags, thumbnail text, pinned comment, end-screen, cards, chapters

Every workflow produces both a human-readable `.md` file (for the user to read and copy-paste from) and a machine-readable `.json` file. The `.json` files are the source of truth for downstream automation — a video pipeline, an audio engine, scheduled tasks, or anything else the user imports them into. **Both files are always required — never save one without the other.**

The three workflows are designed to chain (Visual → Suno → SEO), but each can also run standalone. The SEO workflow in particular is much sharper when it can read the paired visual + suno JSON files for context.

---

## When to use which workflow

| User wants… | Run workflow |
|---|---|
| Midjourney image, Runway loop, ambient SFX layers, scene/sound design | **Visual Prompt** |
| Style of Music + Title + Exclude Styles for Suno Custom Mode | **Suno Music** |
| YouTube title, description, tags, thumbnail text, pinned comment, chapter markers | **SEO Data** |
| Complete package for one video | **Chained** — Visual → Suno → SEO |

If the user's request is ambiguous, ask which workflow they want before starting. **Never silently default to all three** — running the wrong workflow wastes their time. A short clarifying question is cheap.

### Routing cues

- "make a visual / midjourney / runway / scene / SFX / sound design / loop" → **Visual Prompt**
- "make music / suno / instrumental / ambient track / sleep music / meditation music / reiki / chakra / lofi study" → **Suno Music**
- "youtube SEO / title / tags / description / thumbnail text / pinned comment / chapters / end screen" → **SEO Data**
- "give me everything for [theme]" / "complete package" / "all three" → **Chained run**

For the chained run: complete each workflow fully (including saving its files) before starting the next. The Suno workflow can pull theme / use-case context from the Visual session; the SEO workflow pulls from both. When chaining, fill the cross-file references (`paired_visual_file`, `paired_suno_file`) automatically.

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

- `references/visual_prompt.md` — full Visual Prompt workflow (7-step interview + SFX design + Midjourney/Runway prompt composition + canonical JSON schema). Read when the user wants visuals, scene design, or sound design.
- `references/suno_music.md` — full Suno Music workflow (5-phase composer's interview + canonical JSON schema). Read when the user wants instrumental music.
- `references/seo_data.md` — full SEO Data workflow (interview + assembly rules + canonical JSON schema). Read when the user wants YouTube metadata.

For a chained run, read all three in order (visual first, suno second, SEO last).

---

## Output folder convention

All outputs land in the **current project's local path**, under a top-level `working/` folder, inside a single subfolder named after the visual video. The visual-video name is the kebab-case theme slug (e.g., `bamboo-engawa-rain`) — the same slug used inside JSON `meta` fields. **One folder per video, four subfolders inside.**

```
./working/{visual-video-name}/
├── json/      ← machine-readable outputs (visual / suno / seo .json)
├── md/        ← human-readable outputs (visual / suno / seo .md)
├── images/    ← placeholder — Midjourney renders go here in a future pipeline step
└── videos/    ← placeholder — Runway clips and final cuts go here in a future pipeline step
```

**Always create all four subfolders** when the visual-video folder is first created — even if `images/` and `videos/` start empty. This keeps the layout predictable for downstream automation that scans these folders. If `./working/` itself does not exist yet, create it first.

### Filename patterns inside `json/` and `md/`

```
json/
├── {YYYY-MM-DD}_{channel}_{theme-slug}_visual.json
├── {YYYY-MM-DD}_{channel}_{theme-slug}_suno.json
└── {YYYY-MM-DD}_{channel}_{theme-slug}_seo.json

md/
├── {YYYY-MM-DD}_{channel}_{theme-slug}_visual.md
├── {YYYY-MM-DD}_{channel}_{theme-slug}_suno.md
└── {YYYY-MM-DD}_{channel}_{theme-slug}_seo.md
```

`channel` is `asmr` / `soundscapes` / `custom`. `theme-slug` is the kebab-case visual-video name. The `_visual` / `_suno` / `_seo` suffix tells the three workflows apart at a glance.

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

The JSON schemas in `references/visual_prompt.md` and `references/suno_music.md` are unchanged from the original `relax-music-visual-prompt` and `suno-relax-music` skills. **Do not modify these schemas.** They are the contract used by downstream import. The new SEO schema in `references/seo_data.md` follows the same convention and is also a hard contract.

If the user asks for a field that is not in the schema, add it as a Vietnamese note in the `.md` file — never invent new top-level JSON keys.

---

## Conversation style (applies to all three workflows)

- Keep questions short and concrete. The user is a creator who wants to ship videos, not a film student or a music-theory student.
- Offer 2–3 specific options for any step where decision fatigue is likely. ("What time of day?" → "Pre-dawn, golden hour, or 3 am storm?")
- When a user gives a vague answer ("something cozy"), pull a concrete proposal from the relevant preset and confirm it.
- Use `AskUserQuestion` for multiple-choice picks where 3–5 options can be enumerated. Use plain prose for free-text answers (artist references, channel names, length intent).
- For batch work ("give me 5 variations"), run the interview once for the *theme*, then iterate the configuration steps for each variation while keeping the theme fixed.
- Always follow the language rule. If the user writes in Vietnamese, respond in Vietnamese. Never write a Midjourney / Runway / Suno / SEO prompt in Vietnamese.
- If the user pastes an existing prompt and asks for fixes, skip the interview. Identify the problems, propose a corrected version inline with a short bulleted "what changed and why" note.
