# Runway Gen-4 Image-to-Video Reference

Read this before composing the final Runway prompt. Runway Gen-4 takes a still image plus a text prompt describing how the image should animate, and produces a 5-10 second clip. We then loop that clip in editing to fill the video duration.

The art is writing the motion prompt so the clip *can be looped seamlessly*. Most prompt failures aren't about motion quality — they're about a clip that snaps obviously when it loops.

---

## Runway prompt structure

```
[Per-element motion description with verbs and pacing adjectives]
[Camera motion clause — explicit "static camera" or specific slow-motion]
[Mood / pacing summary]
[Loop hint]
```

### Per-element motion description

For each thing in the still that should move, write one short sentence with:
- **What** moves
- **Verb** of motion
- **Pacing adjective** (slowly, gently, very slightly, occasionally)
- **Direction or limit** if relevant

Examples:
- "Rain droplets slowly run down the glass at varied speeds."
- "Steam rises gently from the teacup, occasionally drifting left."
- "Foreground leaves sway very slightly in a soft breeze."
- "Distant fog drifts subtly across the mid-ground from right to left."
- "Candle flame flickers softly without large jumps."
- "Water surface ripples in slow concentric circles."

Stack 2-4 of these. Each one is independently looping. Their combined effect is loop-friendly because no two reach a "snap point" at the same time.

### Camera motion clause (always be explicit)

Pick one and say it directly:
- `Static camera. Frame holds completely still.` — DEFAULT
- `Imperceptible 5-second push-in, ending on the same composition.`
- `Slow horizontal drift right to left over 5 seconds.`
- `Very gentle floating motion as if the viewer is breathing.`

Without an explicit camera clause, Runway will often add subtle camera motion you don't want.

### Mood / pacing summary

A short adjective stack that orients the model:
- `Hypnotic, slow, sleep-friendly.`
- `Peaceful, meditative, breathing pace.`
- `Cozy, intimate, quiet rhythm.`
- `Mysterious, magical, slow.`

### Loop hint

Always include one of:
- `Designed to loop seamlessly.`
- `Hypnotic loop.`
- `Endless ambient loop with no obvious cycle.`

This tells the model to avoid building toward a climactic frame.

---

## Full prompt examples

### ASMR rain-window

```
Rain droplets slowly run down the glass at varied speeds, with new drops occasionally appearing at the top. Steam rises gently from the teacup on the windowsill. The candle flame flickers softly. Outside, the warm city lights blur and shimmer faintly through the wet glass. Static camera, frame holds completely still. Hypnotic, slow, sleep-friendly. Designed to loop seamlessly without any obvious cycle.
```

Settings:
```
Motion intensity: 1-2 / 10
Duration: 5s
Camera: Static
Loop strategy: Cinemagraph (most of frame frozen)
```

### Soundscapes forest stream

```
Foreground ferns sway very slightly in a soft breeze. Sunlight through the canopy creates shifting dapples on the moss. The stream surface ripples gently and water moves toward the camera. Distant mist drifts subtly between the trees. Imperceptible 5-second push-in, ending on the same composition. Peaceful, meditative, breathing pace. Endless ambient loop.
```

Settings:
```
Motion intensity: 3-4 / 10
Duration: 5s
Camera: Imperceptible push-in
Loop strategy: Crossfade in editor
```

### Soundscapes Tokyo night

```
Distant blurred figures walk slowly through neon reflections on the wet pavement. Steam rises from a manhole cover. A red lantern sways very slightly. Rain falls steadily without growing harder. Static camera, no movement of the frame itself. Cinematic, melancholic, urban. Designed to loop seamlessly with no obvious cycle.
```

Settings:
```
Motion intensity: 3 / 10
Duration: 5s
Camera: Static
Loop strategy: Boomerang (forward then reversed)
```

### Fantasy library (painted)

```
Candle flames in the foreground flicker softly. Dust motes drift slowly through the volumetric god-rays. Pages of an open book ruffle very slightly as if from a draft. The fireplace embers glow and dim subtly. Static camera, completely still. Mysterious, magical, slow. Hypnotic loop.
```

Settings:
```
Motion intensity: 2-3 / 10
Duration: 5s
Camera: Static
Loop strategy: Cinemagraph
```

---

## Settings explained

### Motion intensity (1-10)

Runway exposes a motion slider. Pick:
- **1-2** — barely perceptible. ASMR sleep visuals.
- **3-4** — gentle ambient. Soundscapes default. Forest, stream, café.
- **5-6** — noticeable but slow. Only for hero moments. Reserved for opening 10 seconds.
- **7+** — too active for relax. Avoid.

### Duration

5 seconds is the sweet spot. Long enough to give the loop variety, short enough that the looping is invisible. Some Runway plans support 10s — use that only if the scene has more elements that need time to cycle.

### Seed

Lock seed when generating multiple takes of the same scene to allow A/B comparison. Otherwise leave free.

---

## Loop strategies — what they actually mean

The clip Runway generates is 5 seconds. The YouTube video is 8 hours. The clip needs to loop. Three strategies:

### 1. Cinemagraph loop (DEFAULT, easiest)

Most of the frame is fully frozen, only a few specific elements animate. Each animated element has a *natural cycle* (a candle flickers, smoke rises, rain falls). When the clip restarts, the audience doesn't notice because:
- The frozen parts are identical at frame 0 and frame 120
- The animated elements are continuous-flow types (rain, smoke, fire) where any frame looks like any other

In editing: just loop the clip end-to-end. Done.

### 2. Boomerang loop (forward + reversed)

Take the 5s clip, append a reversed copy, and loop the 10s result. Works when:
- Motion has a clear directional element (smoke rises, leaves sway one way) — reversal looks natural because reversed smoke and leaves still look like smoke and leaves
- Audio masks the symmetry (if there's strong rain audio, the visual symmetry is invisible)

Doesn't work when:
- Motion has irreversible visual events (a leaf falls — it doesn't fall up)
- Long moves where reversal looks obviously like rewinding

### 3. Crossfade loop (Adobe Premiere / CapCut)

In editing, place clip A end-to-end with itself, then crossfade the last 1 second of one copy with the first 1 second of the next. Works when:
- Camera has a slow drift (push-in / parallax) — crossfade hides the snap
- Animated elements are diffuse (mist, snow, dust)

This is the only strategy that preserves a slow camera move across a loop.

---

## Anti-patterns

| Anti-pattern | Why it fails | Fix |
|---|---|---|
| Vague motion ("things move", "scene comes alive") | Runway doesn't know what to animate. Often picks the wrong thing. | Name each moving element specifically. |
| No camera clause | Runway adds drift you didn't ask for. | Always say "Static camera" or specify the motion. |
| Motion building toward a climax ("storm grows stronger") | Loop has a discontinuity at the end. | Describe motion as steady-state. |
| Multiple competing camera moves | Runway can't combine "push-in" and "tilt up" smoothly in 5s. | Pick one camera motion or stay static. |
| Sudden events ("lightning flashes", "wave crashes") | Loops badly — the event happens every 5 seconds and breaks calm. | Either remove sudden events from Runway and add them sparsely in editing, or make them ambient ("distant lightning glows softly behind clouds"). |
| Strong motion intensity for sleep content | Visually exciting clip sabotages the audio's calming intent. | Stick to 1-2 / 10 for ASMR sleep. |
| Asking for >5s when not needed | Longer clips are harder to loop and burn more credits. | 5s is enough for 99% of scenes. |
| Animating people | Runway often produces uncanny faces and motion. | Distant blurred silhouettes only. |

---

## Quality check before sending to Runway

Before pasting the final Runway prompt, verify:

- [ ] Each moving element is named with a verb and pacing adjective
- [ ] There's an explicit camera clause
- [ ] There's a mood / pacing summary
- [ ] There's a loop hint
- [ ] No motion building toward a climax
- [ ] No sudden visual events (or at most one, very rare)
- [ ] No people in motion
- [ ] Motion intensity matches the channel preset (1-2 ASMR, 3-4 Soundscapes)
