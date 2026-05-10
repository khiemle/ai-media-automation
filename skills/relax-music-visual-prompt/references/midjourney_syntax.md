# Midjourney Syntax Reference

Read this before composing the final Midjourney prompt. Covers v6.1 / v7 syntax, parameters, prompt order, and anti-patterns specific to relax-video visuals.

---

## Prompt structure (recommended order)

Midjourney weights tokens roughly by position. Put what matters most near the front. The order that consistently works for relax-video stills:

```
[Subject + scene clause]
[POV / framing / composition]
[Time of day + weather + atmospheric elements]
[Light direction + color palette]
[Style modifiers]
[Camera / lens / DoF cues]
[Negative clauses (no people, etc.)]
[Parameters]
```

Example assembled prompt (ASMR rain-window):

```
dark bedroom window at night with heavy rain streaks running down the glass, blurred warm-orange city lights in the distance, viewer's POV from inside next to a softly lit bedside lamp, frame-within-frame composition with the window edge in shallow foreground focus, late-night thunderstorm atmosphere with faint distant lightning, single warm amber practical light from a bedside lamp inside, cool deep navy and charcoal tones outside, color palette of deep navy charcoal and warm amber, photorealistic cinematic 35mm film look, shallow depth of field with creamy bokeh on far city, no people --ar 16:9 --style raw --v 6.1 --q 2
```

That single line is the kind of output we're targeting.

---

## Parameters cheat sheet

Always use:
- `--ar 16:9` — YouTube horizontal aspect ratio. Without this, MJ defaults to square and you lose the ability to use the image directly as a video frame.

Usually use:
- `--style raw` — less stylization, more photographic. Default for photoreal scenes. Skip for anime/painted/surreal.
- `--v 6.1` (or `--v 7` if specifically requested) — model version. v6.1 is the current sweet spot for atmospheric scenes; v7 is sharper but sometimes over-detailed.

Sometimes use:
- `--q 2` — higher render quality, useful for hero scenes / thumbnails. Burns more GPU credits, fine for one image per video.
- `--s 50` to `--s 250` — stylization. Lower for documentary realism, higher for painterly. Default 100. For anime/Ghibli try `--s 250`.
- `--seed N` — lock seed when generating variations of a scene to keep consistency.

Avoid:
- `--chaos N` — adds randomness. Bad for relax visuals where we want predictable mood.
- `--weird N` — same problem.
- `--niji 6` — anime model. Only use for explicit anime style choice. Otherwise mainline `--v 6.1`/`--v 7` does anime well enough with style modifiers.

---

## Style modifier vocabulary

For each style family from `style_packs.md`, here are the high-mileage modifier phrases:

### Photoreal / cinematic
- `cinematic 35mm film look`, `Kodak Portra 400 film stock`, `shot on Arri Alexa`
- `photorealistic`, `hyperrealistic`
- `Roger Deakins cinematography`, `golden hour lighting`
- `shallow depth of field`, `creamy bokeh`
- `volumetric god-rays`, `atmospheric haze`
- `subtle film grain`, `cinematic color grade`
- `ultra-detailed`, `4k`, `8k` (sparingly — already implied by quality params)

### Anime / Studio Ghibli
- `Studio Ghibli anime style`, `Hayao Miyazaki style`, `hand-painted anime`
- `Mamoru Hosoda atmosphere`, `Makoto Shinkai light` (for more cinematic anime)
- `soft watercolor textures`, `painted backgrounds`
- `warm sunlit palette`, `gentle hand-drawn lines`
- `nostalgic anime film still`, `cel-shaded`

### Painted / matte painting
- `digital matte painting`, `concept art`, `ArtStation trending`
- `Maxfield Parrish style`, `Thomas Kinkade luminism`, `Caspar David Friedrich romanticism`
- `oil painting texture`, `painterly brushstrokes`
- `dreamy idealized atmosphere`

### Surreal / unreal
- `Beksinski surreal painting`, `Moebius comic art`, `Roger Dean fantasy landscape`
- `floating islands`, `impossible architecture`, `dreamscape`
- `bioluminescent`, `otherworldly`
- `volumetric fog`, `cosmic scale`

---

## Phrasing tips that consistently improve output

- **Be concrete with numbers when possible.** "Three small candles on the windowsill" beats "some candles".
- **Specify the *quality* of motion or texture in the still.** "Rain streaks running down the glass" reads better than "raindrops on glass" — the verb shapes the image.
- **Anchor mood with one named atmosphere.** "Late-night thunderstorm atmosphere", "predawn quiet", "golden hour stillness" — these compact whole moods.
- **Describe light by *what it does* to the scene**, not just direction. "Single warm amber practical light from a bedside lamp casting a soft glow on the wall" beats "warm light from inside".
- **Repeat the no-people clause** if the scene is the kind MJ likes to populate. For interiors and cafés especially: `no people, empty interior` near the end.

---

## Anti-patterns (do not do these)

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| `camera slowly pushes in, leaves rustle, water flows` | MJ generates *stills*, not video. Verbs of motion get interpreted weirdly. | Save camera/motion language for the Runway prompt. In MJ, describe the *frozen instant*: "leaves caught mid-sway", "water frozen in ripple". |
| `photorealistic anime fantasy painted` | Contradictory style stack. MJ averages and produces muddy output. | Pick one style family. The other modifiers should support it, not compete. |
| `--chaos 50 --weird 100` | Randomness is the enemy of calm consistency. | Drop both. |
| `8k 16k ultra-realistic hyperrealistic photorealistic detailed sharp 4k` | Spamming quality words past 2-3 doesn't help and crowds out scene description. | Use 1-2 quality cues max. |
| Long over-specified subject lists | "A cup, a book, a pen, a candle, a fountain pen, a journal, a bookmark, a scarf..." MJ ignores half. | 3 props max for foreground anchor. |
| Camera-motion verbs (`drifts`, `pushes`, `moves`) | MJ is a still generator. | Describe the frozen frame. |
| Time-of-day contradictions | "Sunset moonlight golden hour midnight" | Pick one. |
| Adjective-heavy with no nouns | "Beautiful stunning amazing magnificent peaceful calm tranquil" | Replace with concrete imagery. |

---

## Hero-frame vs. background-loop frame

A common need: the user wants both a *thumbnail-quality hero frame* AND a *visually quieter frame to use as the loop base*. They're slightly different prompts:

- **Hero frame (for thumbnail):** higher contrast, slightly richer colors, one strong focal element (a candle, a lit window, a flash of lightning). `--q 2` worth using.
- **Loop base (for Runway animation):** flatter contrast, less attention-grabbing, no flash/lightning/strong focal point. The loop is meant to be ignored, not to grab attention every cycle.

If the user wants both, generate both with the same seed and only the focal-element clause changes.

---

## When user pastes an existing prompt for review

Common fixes you'll find:
1. Camera-motion verbs in the MJ prompt — move them to the Runway prompt.
2. Missing `--ar 16:9` — they'll get a square image.
3. Style stack contradictions — pick one.
4. No light direction specified — image will be flat.
5. People accidentally implied (cafés, libraries, streets) — add `no people, empty interior` at the end.
6. Modifiers in the wrong order — subject/scene should come first.
