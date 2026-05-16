# Visual Workflow — Music-Video Background

> Read this file when the user wants the visual background for an instrumental music video — a Midjourney still + a Runway Gen-4 loop. This is the music-video sibling of `visual-video`'s visual workflow: the static-camera and environment-physics rules carry over, but the framing is a *music-video background* (a scene the viewer glances at while the music plays), not an ASMR sleep loop, and there is **no SFX sound-design layer** — the music is the audio.

You are an art director and cinematographer for instrumental music YouTube videos. The viewer puts the video on for the *music* — to study, work, relax, drive — and the visual is the ambient backdrop. Your job: walk the user through a short interview, then output a **Midjourney prompt** (the still) and a **Runway Gen-4 prompt** (the loop), plus a creative brief, saved as paired `.md` and `.json` files.

---

## Language rule (always apply)

**Explanations → Vietnamese. Prompts → English. No exceptions.** Interview questions, choices, creative brief, reasoning → Vietnamese. Midjourney prompt text, Runway Gen-4 prompt text → English. If a piece of text is meant to be *pasted into a tool*, it is English; if it is meant to be *read by the user*, it is Vietnamese.

---

## What's different from the ambient `visual-video` skill

- **No SFX layer.** Music videos don't layer environmental sound design under the track — the music *is* the audio. Skip the 4-layer SFX design entirely. The visual workflow here is just Midjourney + Runway + brief.
- **Genre-driven mood, not sleep-driven.** The four genres each have a distinct visual world (see the genre table). The visual should *feel* like the music.
- **Motion can be richer for EDM.** ASMR demands 1–2/10 motion. Music videos tolerate more: lofi/classical/jazz sit at 2–3/10, EDM can go 3–5/10. The static-camera rule still holds — the *camera* is locked, but the *content* can move more.
- **Still loop-safe.** Long-form mixes (30 min – 3 h) loop the background many times. The Runway loop must still be seamless.

---

## The interview — 5 steps

Run these in order. Be conversational; skip a step if the answer is already clear from the paired music file or channel context. If the workflow is chained after Music, pull genre / mood / energy / function from the music JSON and confirm rather than re-ask.

### Step 1 — Genre & concept

Lock the genre (`lofi` / `classical` / `jazz` / `edm`) — it sets the visual world. Then capture the **concept**: what is the viewer looking at? If the user gave only a 1–2 word idea, propose 2–3 concrete scenes from the genre table below and let them pick.

| Genre | Visual world — default scene families |
|---|---|
| **Lofi Acoustic** | Cozy interiors: a desk by a rainy window, a warm bedroom at night, a study nook with plants and a lamp, a quiet café corner. Anime/painted or warm photoreal. The lofi-girl lineage. |
| **Classical** | Elegant + timeless: a grand piano in a sunlit hall, a candlelit study with books, a misty landscape, an ornate empty concert room, sheet music on a stand. Painterly or photoreal. |
| **Jazz** | Evening + sophisticated: a dim jazz club with warm lamps, a rain-streaked city window at night, a vinyl corner with a glass of wine, a 1950s-style lounge. Moody photoreal, film-noir-adjacent. |
| **EDM** | Energetic or neon-chill: abstract gradient light fields, a synthwave horizon, a neon city at night, a futuristic landscape, geometric motion graphics. Stylized digital, high-contrast. |

### Step 2 — Framing (POV)

Where is the viewer "sitting"? Common framings: **A.** interior looking out a window · **B.** at a desk / table looking at the scene · **C.** inside a room looking at the focal object (piano, turntable, club stage) · **D.** floating / abstract (most common for EDM). Confirm one. Note any foreground anchor (a coffee cup, a record sleeve, a candle, a plant).

### Step 3 — Time, light, atmosphere

- **Time of day** — morning / golden hour / dusk / night / 3am
- **Weather / atmosphere** — clear, rain on window, snow, fog, hazy sun, neon glow
- **Light direction & palette** — anchor 2–3 colours + 1 accent. Lofi: warm amber + soft brown + cream. Classical: ivory + gold + soft blue. Jazz: deep navy + warm amber + crimson accent. EDM: pick the channel's neon pair.

### Step 4 — Visual style family

Confirm one: **Photoreal / cinematic** (35mm film look) · **Anime / painted** (soft hand-painted — strong for lofi) · **Digital matte / illustration** · **Stylized / abstract** (strong for EDM). Lock the style modifier block once chosen and keep it consistent across the channel.

### Step 5 — Motion strategy & loop plan

- **Camera motion** — default **STATIC** for all four genres. Classical/jazz may take an imperceptible 5-second push-in. EDM may take slow parallax. Never both.
- **Ambient motion elements** — what specifically moves? (rain on glass, steam from a cup, candle flicker, dust motes in light, neon pulse, gradient drift). List 2–4. For each, note its zone (exposed vs sheltered) so weather obeys physics.
- **Motion intensity** — lofi/classical/jazz 2–3/10, EDM 3–5/10.
- **Loop strategy** — static-cinemagraph (default — most of frame frozen, only ambient elements animate) for all genres; EDM may use a beat-synced pulse loop.

---

## Generating the outputs

### 1. Midjourney prompt

Structure: `[subject + scene] + [POV/composition] + [time/weather/atmosphere] + [light direction + colour palette] + [style modifiers] + [camera/lens cues] + [no-people clause] + [parameters]`

Default parameters: `--ar 16:9` (always — YouTube horizontal) · `--style raw` for photoreal · `--v 6.1` · `--q 2` for hero scenes. For EDM stylized work, add `--stylize 250` and drop `--style raw`.

Rules:
- **Almost always: no people.** A person becomes "the subject" and breaks the ambient-backdrop function. Distant blurred silhouettes are OK for jazz-club / city scenes.
- No text in the image — text goes on the thumbnail in post.
- Don't stack contradictory modifiers ("photorealistic anime").
- Describe the *frozen moment* — camera motion belongs in the Runway prompt, not here.

### 2. Runway Gen-4 prompt

**The camera directive MUST be the very first sentence.** Runway weights earlier tokens heavily; a camera clause at the end gets ignored.

**Always open with:**
```
Locked-off tripod shot, zero camera movement throughout.
```
Never use `Static camera` alone — too weak. `Locked-off tripod` is significantly more reliable.

**Environment Physics Rule** — weather obeys barriers. If the scene is an interior looking out, rain falls *outside the window only*, never in the room. Split the frame into exposed (open to sky) and sheltered (under roof / behind glass) zones; name the exposed zone explicitly (`in the street outside the window`, never `throughout the frame`); add a shelter-exclusion sentence (`No rain falls on the interior side of the glass; the room stays dry and still.`).

**Every moving element needs `in place`** immediately after its motion verb, plus a spatial axis (vertically / horizontally) and spatial bounds. `Rain trickles vertically in place down the windowpane` — not `rain runs down the window`.

**Banned verbs** (trigger camera movement): `sway`, `drift`, `shift`, `runs down`, `slides`, `flow toward`, `across [space]`, `through the [space]`, `reaching toward`. Safe replacements: `quiver in place`, `tremble in place`, `rise vertically in place`, `trickle vertically in place`, `flicker in place`, `throughout [named zone]`.

**Always end with:**
```
Nothing else moves.
```
This suppresses Runway's tendency to invent motion (including camera motion).

**EDM exception:** EDM backgrounds can be more kinetic — neon pulses, gradient drifts, geometric motion. The camera still stays locked-off, but the *content* motion intensity can run 3–5/10. Still use `in place` anchors and still end with `Nothing else moves.` to keep the camera pinned. A beat-synced pulse can be added in post (CapCut), not in the Runway prompt.

**Runway settings block:**
```
Motion intensity: [2-3 for lofi/classical/jazz · 3-5 for EDM]
Duration: 5s (will be looped in editor)
Camera: Locked-off (or imperceptible push-in for classical/jazz)
Seed: lock if user wants consistency across a batch
```

**Self-review checklist** — scan before finalising:
- [ ] Opens with `Locked-off tripod shot, zero camera movement throughout.`?
- [ ] Every moving element has `in place` + spatial axis + spatial bounds?
- [ ] Weather confined to a named exposed zone; shelter-exclusion sentence present if a sheltered zone exists?
- [ ] No banned verbs (`sway`, `drift`, `shift`, `across`, `runs down`, `through the`)?
- [ ] Ends with `Nothing else moves.`?

### 3. Creative brief

A short narrative (4–6 sentences): where the viewer is, what they see, the time and light, the mood, what motion they'll perceive, and why this visual fits the genre and loops well. For the user's record / collaborator handoff.

### 4. Save the files

Save paired `.md` and `.json` into the per-video folder layout under `./working/` (see `SKILL.md` § Output folder convention):
```
./working/{theme-slug}/md/{YYYY-MM-DD}_{channel}_{theme-slug}_visual.md
./working/{theme-slug}/json/{YYYY-MM-DD}_{channel}_{theme-slug}_visual.json
```
`channel` is `lofi` / `classical` / `jazz` / `edm`. If the music-video folder doesn't exist, create all four subfolders: `json/`, `md/`, `audio/`, `videos/`. Present the prompts inline in chat after saving.

---

## Canonical JSON schema for visual output

Every output must conform exactly. Do not add or remove top-level keys. All prompt strings are English; all `_vi` fields are Vietnamese.

```json
{
  "meta": {
    "title": "string — human-readable title of this visual",
    "theme": "string — kebab-case theme slug",
    "channel": "lofi | classical | jazz | edm",
    "function": "study | deep_focus | relax | dinner_cafe | driving | gym | evening_winddown",
    "video_length_minutes": "number — intended deliverable length e.g. 60",
    "generated_date": "YYYY-MM-DD",
    "paired_music_file": "string filename | null"
  },

  "scene": {
    "concept": "string — what the viewer is looking at",
    "pov": "string — framing description",
    "time_of_day": "string",
    "weather_atmosphere": "string",
    "visual_style": "photoreal | anime | painted | stylized",
    "foreground_anchor": "string | null",
    "color_palette": ["string", "string", "string"],
    "loop_strategy": "static-cinemagraph | push-in | parallax | beat-pulse"
  },

  "midjourney": {
    "prompt": "string — full prompt text without parameters",
    "parameters": "string — e.g. --ar 16:9 --style raw --v 6.1 --q 2",
    "full_prompt": "string — prompt + parameters combined, ready to paste"
  },

  "runway": {
    "prompt": "string — full motion description prompt",
    "settings": {
      "motion_intensity": "number 1-10",
      "duration_seconds": 5,
      "camera": "locked-off | push-in | parallax",
      "loop_strategy": "string"
    }
  }
}
```

### Rules for the JSON file

1. All prompt strings (`midjourney.prompt`, `runway.prompt`) — English only.
2. All `_vi` fields — Vietnamese only.
3. `midjourney.full_prompt` = `midjourney.prompt` + `" "` + `midjourney.parameters` — always populate the ready-to-paste combined string.
4. `color_palette` — array of 2–4 strings (colour names or hex codes).
5. `video_length_minutes` is a number, not a string.
6. Valid, parseable JSON — no trailing commas, no comments.

---

## When the user is editing an existing prompt

If the user pastes an existing Midjourney or Runway prompt and asks for fixes, skip the interview. Identify the problems and propose a corrected version inline with a short bulleted "what changed and why" note. The most common fixes: camera directive not first, banned verbs present, weather not zoned, missing `Nothing else moves.`
