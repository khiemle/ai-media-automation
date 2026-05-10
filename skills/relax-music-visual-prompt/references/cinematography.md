# Cinematography Reference

The expert's menu of cinematography choices. Read this when guiding the user through Steps 5 (camera/light) and 7 (motion). The deeper why-it-works notes are here so you can defend recommendations and judge edge cases.

---

## Why cinematography matters for relax video

A relax video has a different cinematography goal than a film. Film holds attention by *changing* the frame. A relax video holds attention by *staying the same in a way that rewards staring*. Almost every choice below is in service of: depth, breath, calm rhythm, no surprises.

The viewer is mostly listening. The visual must not compete with the audio. The cinematography rule is therefore: **the eye should be able to rest anywhere in the frame and find something gentle to look at, but nothing should demand attention.**

---

## Camera height & angle

| Choice | Effect | Use when |
|---|---|---|
| **Eye-level (sitting)** | Default. Reads as "I am sitting next to the camera." Most calming. | Almost always. |
| **Slightly low** | Reads as "I am settled into a low chair / lying on a bed." Slightly cozier. | Bedroom, fireplace, hobbit hole. |
| **Slightly high (god view)** | Reads as "I am looking down at this scene." Detached, observational. | Map-like landscapes, libraries from a balcony. |
| **Worm's-eye / extreme low** | Dramatic, alien. Avoid for sleep content. | Surreal/fantasy soundscapes only. |
| **Aerial / drone** | Dynamic, awe-inspiring. Avoid for sleep. | Soundscapes meditation peak moments only. |

Avoid handheld. The implied micro-shake breaks calm.

---

## Lens feel (focal length)

In Midjourney, this is communicated through phrases like "shot on 35mm film", "85mm intimate portrait lens", "wide cinematic anamorphic". You don't need actual lens math, just the *look*.

| Lens feel | Look | Use when |
|---|---|---|
| **24-35mm wide** | Whole scene visible, environmental, mild distortion at edges | Landscapes, libraries, big rooms |
| **50mm "normal"** | Most natural. Default for first-person sitting POV. | Default for POV variant A (window) and C (cozy interior) |
| **85mm intimate** | Compresses background, creamy bokeh, foreground subject pops | Close fireplace, candle, teacup-as-anchor |
| **Anamorphic widescreen** | Cinematic letterbox feel, oval bokeh | Tokyo night, dramatic ASMR thunderstorm |

---

## Depth of field

Depth of field is the strongest single readability tool in your kit.

- **Shallow DoF** — subject sharp, background creamy bokeh. Reads as "intimate, calm, focused". Good for ASMR, café, library themes. The eye knows where to rest.
- **Medium DoF** — foreground readable, distant background softly blurred. Default for Soundscapes nature.
- **Deep DoF** — everything sharp. Reads as "documentary, alert, busy". **Avoid** for relax video — too much information for the eye to process when sleepy.

In Midjourney, communicate DoF with: "shallow depth of field", "creamy bokeh", "subject in sharp focus, background softly blurred".

---

## Composition

| Pattern | Effect | Use when |
|---|---|---|
| **Rule of thirds** | Generally pleasing, asymmetric balance | Most scenes |
| **Centered symmetry** | Meditative, formal, almost religious | Library halls, ocean horizons, fireplace + chair |
| **Leading lines into distance** | Pulls the eye into a vanishing point — dreamy | Forest paths, alleys, train tracks in rain |
| **Frame-within-frame** | Window or arch around the actual subject. Strong for "sitting indoors looking out" | POV variant A always |

---

## Light direction (the most important single choice)

Light direction tells the brain where the sun, fire, or lamp is — and that fills in the entire mood. Pick one *primary* source and one optional *fill* source.

### Primary source options

| Direction | Mood | Best for |
|---|---|---|
| **Top-back (window light, moonlight, skylight)** | Calm, neutral, "natural" | Almost all photoreal scenes |
| **Side warm (lamp, sconce, fireplace)** | Cozy, intimate, end-of-day | ASMR cozy interior, library |
| **Diffuse overcast (no clear direction)** | Meditative, soft, almost flat | Forest stream, snowy day, foggy morning |
| **Volumetric god-ray from one direction** | Magical, hopeful, dramatic | Soundscapes nature peak moments, fantasy library |
| **Backlit (light source behind subject)** | Silhouettes, rim light glow on edges | Sunset beach, distant fireplace through doorway |
| **Underlit / firelight from below** | Warm, intimate, slightly mysterious | Fireplace close-up, candle scenes |

### Fill / secondary

A weaker, color-contrasted light from a different direction. Common combos:

- Warm interior + cool moonlight outside (rain-window classic)
- Golden sunset rim + deep teal shadow (cinematic Soundscapes)
- Single fire + cold void (hobbit hole, cave fire)

---

## Color palette discipline

The strongest visual mistake is too many colors. Lock 2-3 palette colors + 1 accent.

ASMR signature palettes:
- Deep navy + charcoal + warm amber accent
- Black + steel blue + dim yellow practical
- Forest dark green + black + faint silver moon

Soundscapes signature palettes:
- Forest green + cream + golden hour sun
- Wet pavement teal + neon pink + warm window orange (Tokyo)
- Mist gray + sky blue + warm gold (mountain morning)
- Candle warm + deep mahogany + parchment cream (library)

Communicate to Midjourney: "color palette of {color1}, {color2}, {accent}", or pull from the channel preset's hex values.

---

## POV framing — extended

Step 2 picked one of A/B/C/D. Here's how to render each one well in the prompt:

### A. Inside-out through window

Always include in the prompt:
- The window itself (frame, sill, raindrops or condensation)
- A hint of the interior (warm light source, blurred bokeh of a lamp or a teacup edge)
- The exterior view, which is the main visual content

Cinematography signature: shallow DoF, foreground window slightly out of focus, background fully soft. The eye sits on the wet glass.

### B. Outside in landscape

Often no foreground anchor — but you can add one for warmth:
- A bench / log / rock at the bottom edge
- A walking stick leaning into frame
- A blanket corner

Cinematography signature: leading lines into distance, layered planes (foreground / mid / far), god-rays optional.

### C. Cozy interior

Foreground often dominates. Common elements:
- Fireplace as light source (warm side fill)
- Armchair just visible at edge of frame
- Teacup / open book on a table
- Bookshelves / stone walls receding

Cinematography signature: 50-85mm intimate, warm side light, deep shadows in corners, single light source.

### D. Floating / contemplative

No anchor. Pure environment. Use for underwater, space, abstract.

Cinematography signature: centered composition, slow vertical or radial pull, atmospheric particles drifting, depth via fog/water/dust.

---

## Motion direction & loop strategy

This decides whether the video can loop seamlessly or will have a visible "snap" at the end.

### Static camera + ambient motion only (DEFAULT, especially ASMR)

- The camera does not move at all.
- Only environmental elements move (rain, smoke, candle flicker, leaves).
- Each ambient element should have a *non-aligned cycle* — they don't all reset at the same time, so the loop point is invisible.
- This is the safest loop strategy. Almost every scene should default to this.

### Imperceptible push-in / pull-out (Soundscapes only)

- Camera moves over 5 seconds — total displacement maybe 2-3% of the frame.
- Loop strategy: hold the endpoint frame. The viewer's brain doesn't notice the snap because nothing visually changed at the end.
- Don't combine with parallax. Pick one motion direction.

### Slow parallax / drift

- Camera drifts horizontally or vertically, ~3% of the frame over 5 seconds.
- Loop strategy: editor uses a crossfade loop (clip + reversed clip with overlap) or the user generates a longer clip and finds a natural cut point.
- Risky for sleep content — can read as "ride" rather than "place". Prefer for Soundscapes only.

### Cinemagraph

- Specific subset of static-camera-ambient-motion: most of the frame is fully frozen, only one specific element animates. Loops perfectly by design.
- Examples: only the steam from the teacup moves, only the fireplace flickers, only one curtain billows.
- Reads as artful and intentional. Good when the user wants a "premium" feel.

---

## Common cinematography mistakes (and what to do instead)

| Mistake | Why it fails | Fix |
|---|---|---|
| Camera in motion *and* lots of ambient motion | Two motion centers compete. Eye darts. | Pick one. Static + ambient OR slow camera + still environment. |
| Top-down god view of a "sitting" scene | Breaks the "I am sitting in this place" illusion. | Eye-level. |
| Bright saturated highlights in a dark scene | Wakes up viewer at 2am. | Compress highlights. Soft glow only. |
| Sudden lightning every few seconds | Shocks viewer awake. | Maximum once per minute. Better: once every 2-3 minutes. |
| Sharp deep focus on a detailed scene | Eye has nowhere to rest. | Add shallow DoF and let some areas blur. |
| Smooth camera motion at consistent speed | Reads as "ride". | Either fully static OR ease in/ease out at the boundaries of imperceptible motion. |
| People in sharp focus | Triggers content disclosure rules + breaks meditative spell. | No people, or distant blurred silhouettes only. |

---

## Quick decision rubric

If the user is decision-fatigued and wants you to just pick:

1. **Camera height** — eye-level
2. **Lens feel** — 50mm intimate (or 35mm if the scene is wide nature)
3. **Depth of field** — shallow for cozy, medium for nature
4. **Composition** — centered for symmetry-heavy scenes, rule of thirds otherwise
5. **Light direction** — single primary source from the brightest natural element, warm for interior / cool for exterior
6. **Motion** — static camera, 2-3 ambient elements, cinemagraph loop
