# Visual Prompt — Forest Stream · Morning Window · Study Focus

**Paired Suno track:** Study Focus · F Lydian · Mellotron & Stream  
**Reference channel:** Ambient Earth  
**Use case:** Study / focus · YouTube multi-hour (8+ hours)  
**Generated:** 2026-05-04  

---

## Scene Specification

| Field | Value |
|---|---|
| Subject | Rustic wooden cabin interior; large window looking out at a misty temperate forest with a gentle stream barely visible through the trees |
| POV framing | Inside-out through window — warm shadowed interior frames the luminous forest outside |
| Time of day | Early morning — pre-golden hour, soft diffused light |
| Weather / atmosphere | Mist rising from the forest floor and stream, golden-green morning haze filtering through the canopy |
| Season | Late spring / early summer — lush green, full foliage |
| Foreground anchors | None (clean environment — window frame itself is the anchor) |
| Style | Photoreal / cinematic — 35mm film, Kodak Portra 400 |
| Color palette | Deep forest green · soft morning gold · cool blue-grey mist · warm wood grain |
| Camera | Static — no movement |
| Motion elements | Rising mist · imperceptible leaf sway · distant stream glimmer · subtle light shift |
| Motion intensity | 2 / 10 |
| Loop strategy | Static-cinemagraph — window frame and interior are completely frozen; only mist, leaves, and water animate |

---

## Midjourney Prompt

```
interior view through a large rustic wooden window frame looking out at a misty temperate forest, a gentle stream barely visible through the trees below, early morning soft diffused light, mist rising gently from the forest floor, golden-green dawn haze filtering through the canopy, the wooden window frame sharp in the foreground, cool blue-grey shadowed interior, lush deep green forest outside, no people, no human figures, cinematic photography, 35mm film, Kodak Portra 400, shallow depth of field, soft bokeh across the midground trees, atmospheric morning light, Roger Deakins inspired, photorealistic, --ar 16:9 --style raw --v 6.1 --q 2
```

**Midjourney settings:**
- Version: v6.1 (upgrade to v7 if available for higher photorealism)
- Aspect ratio: 16:9 (YouTube horizontal)
- Style: raw (preserves natural film look, avoids AI-stylised sheen)
- Quality: 2 (higher render quality for hero image)

**Re-roll tip:** If the window frame doesn't appear prominently enough, add `wooden window frame close foreground, interior darkness framing the forest` before the style modifiers. If mist is too heavy, add `subtle mist, not fog`.

---

## Runway Gen-4 Prompt

```
Morning mist rises slowly and silently from the forest floor and the stream below, drifting upward through the tree trunks and dissolving into the canopy. The nearest leaves sway imperceptibly in a soft morning breeze, a gentle tremor rather than motion. The distant stream surface catches faint glimmers of morning light that shift slowly with the mist. The light through the canopy breathes subtly, brightening and softening as though clouds are passing far above. The wooden window frame and the interior hold completely still. Static camera, no camera movement whatsoever. Slow, peaceful, hypnotic — designed to loop seamlessly for hours.
```

**Runway Gen-4 settings:**
```
Motion intensity: 2/10
Duration: 5s (loop in editor — extend with crossfade)
Camera: Static (no movement)
Seed: Lock after first approved result for batch consistency
```

**Loop strategy — static-cinemagraph:**  
The window frame and interior are the frozen anchor. Only the mist, leaves, and distant water animate. In your video editor, export the 5s Runway clip and loop it with a 1-second crossfade. At 2/10 motion intensity, the loop join is effectively invisible — mist has no fixed direction that betrays the cut.

**Runway tip:** If the camera drifts even slightly, add `camera locked off, no drift, no push, no zoom` to the prompt. Runway Gen-4 occasionally introduces a micro push-in at this duration — the explicit lock-off phrase suppresses it.

---

## Creative Brief

The viewer is seated inside a warm wooden cabin at the start of a quiet morning, looking out through a large window at a temperate forest. A stream runs somewhere below the tree line — audible in the music, barely visible in the image, a silver glimmer between the trunks. The room behind is cool and shadowed; the forest outside is luminous with early light and rising mist. Nothing is happening, and that is entirely the point.

The scene is timed to the soft, pre-golden-hour window when the light is present but not yet harsh — a condition that is simultaneously "first thing in the morning" and temporally neutral enough to loop for eight hours without triggering a clock in the viewer's mind. The mist anchors that neutrality further: fog and mist belong to no hour.

Motion in the video is limited to three elements — rising mist, a near-imperceptible leaf tremor, and a slow glimmer on the distant water — all of which loop invisibly under a static-cinemagraph strategy. The Mellotron strings and drone synth in the paired Suno track occupy the same register as this visual: vintage-warm, atmospheric, and absent of any foreground hook that would demand attention. The visual and audio are designed to be noticed once on arrival, then fade into productive background.

---

## File record

**Midjourney image** → save as: `forest-stream-morning-window_MJ.png`  
**Runway clip** → save as: `forest-stream-morning-window_RW_5s.mp4`  
**Paired Suno prompt** → `suno-prompt_20260504-0948_study-focus_f-lydian_mellotron-stream.md`

---

*Built with the Relax Music Visual Prompt skill · 2026-05-04*
