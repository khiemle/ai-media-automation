# Visual Prompt — Quiet Cafe with Cat at Cashier

> **Channel:** Soundscapes  ·  **Date:** 2026-05-03  ·  **Use case:** Work / focus / study background  ·  **Video length:** 3 hours

---

## Scene specification

| Field | Value |
|---|---|
| Theme | Empty quiet coffee shop, sunny mid-morning, viewer working at a cafe table, sleeping cat at the cashier counter |
| POV framing | Cozy interior (Variant C) — viewer seated at a cafe table looking across the room toward the cashier |
| Time of day | Mid-morning to early afternoon |
| Weather | Sunny clear day outside, warm and bright |
| Atmospheric elements | Volumetric god-rays through side windows, dust motes drifting, faint steam in the air |
| Style family | Photoreal / cinematic |
| Camera height / lens | Eye-level seated, 35mm slightly wide |
| Depth of field | Medium — foreground mug and notebook sharp, cat softly readable, far back of cafe gently blurred |
| Composition | Leading lines through tables/chairs into the cashier counter, rule of thirds with cat as soft focal point |
| Light direction | Warm directional sunlight from the right-side windows, soft bounce fill, hint of cool sky blue from the glass |
| Color palette | Warm cream, honey gold, muted brown wood, soft sky blue accent |
| Foreground anchor | Steaming ceramic mug + open notebook on the wooden cafe table (sells the "viewer is working here" feel) |
| Camera motion | Static, frame holds completely still |
| Ambient motion elements | Steam rising from mug, dust motes drifting in god-rays, cat breathing + tail flicks, leaves swaying outside, notebook pages fluttering faintly |
| Motion intensity | 3 / 10 (Soundscapes baseline — gentle ambient, study-friendly) |
| Loop strategy | Static-cinemagraph (most of frame frozen, ambient elements cycle independently) |

---

## Creative brief

You're sitting at a wooden cafe table in a quiet, empty coffee shop on a sunny mid-morning. The space is washed in golden sunlight pouring in through tall side windows, with dust motes drifting lazily through the volumetric light beams. On the table in front of you are a steaming ceramic mug and an open notebook — the soft tools of working-from-anywhere. Across the room, the cashier counter is unattended, but a small cat is curled up there, breathing slowly, its tail flicking once in a while. There are no people in the cafe — just the warmth, the light, and the quiet companionship of the cat. Motion is minimal: steam rising, dust drifting, the cat breathing, leaves swaying outside. This loops invisibly across a 3-hour focus session because every animated element cycles on its own rhythm, so your eye keeps finding new small things to rest on without ever being snapped out of focus by an obvious repeat.

---

## Midjourney prompt

```
empty quiet coffee shop interior on a sunny mid-morning, viewer's POV from a wooden cafe table looking across the room toward the cashier counter where a small tabby cat is curled up sleeping, foreground edge of the cafe table with a steaming ceramic mug of coffee and an open notebook in shallow sharp focus, leading lines through wooden tables and rattan chairs toward the cashier in the mid-ground, tall side windows on the right pouring warm volumetric sunlight god-rays into the room with dust motes drifting in the beams, sunny clear day outside with soft green leaves visible through the glass, color palette of warm cream, honey gold, muted brown wood, and soft sky blue, photorealistic cinematic 35mm film look, Kodak Portra 400 color grade, shot on Arri Alexa, Roger Deakins-style natural directional light, painterly atmospheric haze, 35mm slightly wide lens with medium depth of field, the cat softly readable in the mid-ground, far back of cafe gently blurred in creamy bokeh, subtle film grain, no people, empty cafe interior --ar 16:9 --style raw --v 6.1 --q 2
```

**Parameters:** `--ar 16:9 --style raw --v 6.1 --q 2`

---

## Runway Gen-4 prompt (image-to-video)

```
Steam rises gently from the ceramic mug on the cafe table, drifting upward in slow swirls. Dust motes drift slowly through the volumetric sun beams streaming through the side windows. The cat at the cashier breathes slowly and rhythmically — its chest rises and falls, and its tail occasionally flicks once or twice. Outside the window, distant tree leaves sway very slightly in a soft breeze. The pages of the open notebook on the table flutter barely perceptibly from a faint draft. Static camera, frame holds completely still. Peaceful, meditative, study-focused, breathing pace. Designed to loop seamlessly with no obvious cycle.
```

**Settings:**
- Motion intensity: 3 / 10
- Duration: 5s (loop in editor)
- Camera: Static
- Loop strategy: Static-cinemagraph
- Seed: free (lock only if generating a series of variations)

---

## Production notes

- **Loop assembly:** Place the 5s Runway clip end-to-end. The cat's breathing rhythm is the trickiest motion — if Runway gives you a clearly directional inhale-only clip, use a boomerang loop (forward + reversed) so the breathing reads naturally in both directions. The dust + steam + leaves are continuous-flow and loop invisibly on their own.
- **Hero frame variant** (for thumbnail): Regenerate the Midjourney with `, single sharp god-ray illuminating the sleeping cat, slightly higher contrast` added before the parameters. The illuminated cat becomes the click-magnet focal point for the thumbnail without breaking the calm in the loop version.
- **Variations to try:**
  1. **Anime / Ghibli variant** — same scene, swap the style block to: `Studio Ghibli anime style, hand-painted backgrounds in the style of Hayao Miyazaki, soft watercolor textures, warm sunlit palette, gentle hand-drawn linework, nostalgic anime film still, Makoto Shinkai-style atmospheric light` and drop `--style raw`. A cat in an empty sunny cafe is *extremely* Ghibli — strong candidate for an A/B test on the channel.
  2. **Rainy-day variant** — change "sunny mid-morning" → "soft rainy afternoon, gentle rain streaks on the windows, warm interior tungsten lamps glowing". Same cat, same POV. Pairs well with a rainy-cafe Suno track.
  3. **Sunset variant** — change time to "golden hour late afternoon, low orange sun streaming through windows". The cat's fur catches a warm rim light at the cashier. More cinematic, fewer dust motes.
  4. **Cat closer to camera** — move the cat from the cashier to a chair at a nearby table. Brings the foreground anchor closer and changes the composition from "leading lines into deep cafe" to "two-anchor (mug + cat)". Different mood; more intimate.
- **Audio pairing suggestion:** A Suno prompt with `[Instrumental] indie cafe morning, soft espresso machine in distance, gentle rain or cicadas outside, warm lo-fi piano bed, occasional ceramic cup sounds, [No Vocals], studious and calm, intimate interior acoustics, [Cafe Ambient]` (adapted from your Channel_Launch_Plan_Soundscapes.md template). Skip the rain layer if you keep the sunny version.
