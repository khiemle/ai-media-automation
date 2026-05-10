# Style Packs

Modifier blocks for the four supported visual style families. After Step 4 of the interview, read this and pull the matching block into the Midjourney prompt. Each pack also has *what works* and *what doesn't* notes that should shape the rest of the prompt.

---

## 1. Photoreal / Cinematic

The default for both ASMR and Soundscapes. Reads as "real place captured with intentional cinematography".

### Modifier block

```
photorealistic cinematic 35mm film look, Kodak Portra 400 color grade, shot on Arri Alexa,
Roger Deakins-style lighting, shallow depth of field with creamy bokeh,
volumetric haze, subtle film grain, atmospheric, ultra-detailed
--style raw --v 6.1 --q 2 --ar 16:9
```

Trim modifiers to taste — 4-5 is plenty.

### What works
- Realistic light direction (named light sources, not vague "soft light")
- Specific real-world locations as anchors ("Tokyo back street", "Cotswolds cottage", "Pacific Northwest forest")
- Named time-of-day ("blue hour", "golden hour", "predawn")
- Real weather phenomena described with verbs ("rain streaks running down glass", "fog drifting between trees")
- Specific film stock or cinematographer references

### What doesn't
- Cartoonish exaggeration ("super magical", "incredibly cozy")
- Anime-style facial proportions if any human is hinted
- Fluorescent neon colors (unless in cyberpunk Tokyo context)
- Multiple competing color palettes

### Best fit themes
ASMR rain-window, thunderstorm, fireplace, ocean. Soundscapes forest stream, mountain waterfall, beach sunset, Tokyo night.

---

## 2. Anime / Studio Ghibli

Hand-painted anime warmth. Especially good for forest, garden, library, and cozy interior themes. Less appropriate for ASMR sleep content (anime's color saturation is slightly stimulating).

### Modifier block

```
Studio Ghibli anime style, hand-painted backgrounds in the style of Hayao Miyazaki,
warm watercolor textures, soft cel-shaded foreground, painterly brushstrokes,
gentle hand-drawn linework, nostalgic anime film still, Makoto Shinkai-style atmospheric light
--s 250 --v 6.1 --ar 16:9
```

Drop `--style raw` for anime. You want stylization on.

### What works
- "Gentle" everything — gentle wind, gentle light, gentle ripples
- Lush plant detail described in painterly terms ("ferns rendered with painted brushstrokes")
- Warm sun-filtered atmospheres
- Magical-realistic touches (a tiny spirit creature, a glowing dust mote — sparingly)
- Storybook geometry (rounded windows, curved paths, cozy hobbit-hole interiors)

### What doesn't
- Photorealistic film stock references — they fight the anime look
- Hyperdetailed micro-textures
- Cyberpunk or industrial aesthetics (different anime tradition)
- Sharp dramatic shadows (anime is about diffuse warm light)

### Best fit themes
Soundscapes bamboo forest, forest stream (anime variant), Japanese garden, hobbit hole, fantasy library, spring cherry blossom.

---

## 3. Painted / Digital Matte Painting

Mid-realism, dreamy, idealized. Sits between photoreal and surreal. Especially good for fantasy themes that need to feel "real but elevated".

### Modifier block

```
digital matte painting, concept art trending on ArtStation,
Maxfield Parrish luminism, oil painting texture with painterly brushstrokes,
dreamy idealized atmosphere, romantic painted light, ultra-detailed,
cinematic composition
--v 6.1 --q 2 --ar 16:9
```

Skip `--style raw` — let the painted style come through.

### What works
- Romantic-era painter references (Caspar David Friedrich, Albert Bierstadt, Maxfield Parrish, Thomas Cole)
- Idealized light (god-rays, glowing horizons, candle-warmth)
- Mythological / literary settings (wizard's library, ancient ruin, hobbit hole, observatory)
- Painted texture description ("oil painting brushstrokes visible", "watercolor washes in the sky")

### What doesn't
- Modern urban environments (matte painting is about timeless / fantasy)
- Strong photo-grain or film-stock references
- Anime cel-shading
- Sharp glassy CG-render look

### Best fit themes
Soundscapes wizard's library, hobbit hole, fantasy garden, ancient ruin, mythical mountain. Some ASMR fireplace scenes can lean painted for warmth.

---

## 4. Surreal / Unreal World

For dreamscape, fantasy, sci-fi themes that should feel "impossible". Use sparingly — surreal can be over-stimulating for sleep content. Best for Soundscapes "fantasy" tier.

### Modifier block

```
surreal dreamscape, Beksinski atmospheric painting, Moebius-style fantasy landscape,
floating islands and impossible architecture, bioluminescent ambient light,
volumetric fog, otherworldly cosmic scale, painterly with sci-fi precision
--v 6.1 --q 2 --ar 16:9
```

Skip `--style raw`.

### What works
- Impossible geometry (floating islands, inverted waterfalls, spiral staircases into clouds)
- Bioluminescence (glowing plants, water, particles)
- Cosmic / underwater / inside-a-crystal environments
- Single dominant color in an unexpected way (the whole scene is teal-green from underwater glow)

### What doesn't
- Realistic earthly detail next to impossible elements (creates mismatch)
- Sleep-themed content (too stimulating to fall asleep to)
- Crowds, dense detail, overstimulating composition

### Best fit themes
Soundscapes underwater coral garden, space station, inside-a-crystal cave, floating sky islands, dream library that defies physics.

---

## Style mixing — when it works

Generally don't mix styles. But two intentional combinations work:

### Photoreal + cinematic painted touch
Adding `painterly atmospheric haze` or `cinematic painted color grade` to a photoreal prompt. Result: a real-feeling scene with a slightly elevated dreamy quality. Good for hero thumbnails.

### Anime + matte painting backgrounds
Foreground in anime style, background in painted matte style. Add: `anime foreground subjects with painted matte background, soft gradient transition`. Used in many Studio Ghibli films. Good for fantasy library, hobbit hole.

Otherwise — one style at a time. Mixing more than this dilutes both.

---

## Style decision rubric

If the user is unsure which style to pick, ask one filtering question: **"Should this scene feel like a real place I might actually visit, or a dream / story-world?"**

- "Real place" → Photoreal
- "Real but slightly dreamy / elevated" → Photoreal or Painted
- "Storybook / cozy / nostalgic" → Anime / Ghibli or Painted
- "Pure fantasy / impossible" → Painted (if grounded fantasy) or Surreal (if dreamlike)
