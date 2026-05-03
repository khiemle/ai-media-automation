# Ready-Made Presets

Eight bundled preset configurations. Use these for the Quickstart path in Phase 1, or as a starting candidate to mutate during Phase 3.

Each preset is a complete copy-paste set: Style of Music string, Title string, and a one-line "best for" hint. The default Exclude Styles block from `prompt-templates.md` applies to all presets unless otherwise noted.

**No duration in any preset.** None of the Style strings or Titles below contain `60 min`, `8 hour`, `extended`, or any length token — Suno generates ~4-min clips regardless of what you write, and duration tokens waste prompt budget. Length is delivered through the extension-and-looping workflow in `prompt-templates.md` §extension-strategy.

**Loop-safety note for long-form deliverables.** If the user is heading to a 30-min+ standalone track or a 1–11 hour YouTube video, append the loop-safety addendum to the preset's Style string before generating:

```text
…continuous ambient texture, no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly
```

Preset G (pure drone) is the safest choice for long-form because it has nothing to become tedious. The melodic presets (A, D, F) need extra loop-safety care because their hooks repeat audibly under long loop.

---

## A — Deep Sleep, Felt Piano

**Best for:** Adults falling asleep, intimate playlist context, podcast outro.

**Style:**
```text
deep sleep music, soft felt piano with warm analog pad, distant ocean waves, A minor key, 52 BPM, no dynamic build, long cathedral reverb, warm and dark, no vocals, no percussion, no drums, no climax, continuous ambient texture
```

**Title:** `Deep Sleep · A minor · Felt Piano`

---

## B — Theta Meditation, Singing Bowls

**Best for:** Active 20–60 min seated meditation, Tibetan-leaning practice.

**Style:**
```text
meditation music, Tibetan singing bowls with drone synth, occasional bowl strikes, D Dorian mode, 60 BPM, flat dynamics throughout, infinite reverb tail, earthy and grounded, no vocals, no percussion, no drums, no climax, continuous ambient texture
```

**Title:** `Theta Meditation · D Dorian · Singing Bowls`

---

## C — Reiki Session, Crystal Bowls

**Best for:** 60-min Reiki sessions, energy work, salon/spa context.

**Style:**
```text
reiki healing music, crystal singing bowls with wordless choir pad, singing bowl shimmer, Solfeggio 528 Hz tuning, 60 BPM, no crescendo no climax, long cathedral reverb, crystalline and pure, no vocals, no percussion, no drums, continuous ambient texture
```

**Title:** `Reiki Healing · 528 Hz · Crystal Bowls`

**Note:** add `choir words` to Exclude Styles if vocal-like leakage occurs (the choir pad is the most common offender).

---

## D — Stress Relief, Solo Piano (Satie-inspired)

**Best for:** Daytime calm, after-work decompression, anxiety reduction during waking hours.

**Style:**
```text
stress relief music, grand piano with soft pedal, no other instruments, F Lydian mode, 60 BPM, gentle dynamic arc, intimate room reverb, soft and intimate, no vocals, no percussion, no drums, no climax, sparse Erik Satie inspired
```

**Title:** `Stress Relief · F Lydian · Solo Piano`

---

## E — Heart Chakra, Harp + Pad

**Best for:** Chakra-focused practice, especially heart-opening sessions.

**Style:**
```text
chakra meditation music, concert harp with warm analog pad, Tibetan bowl strikes, Solfeggio 528 Hz tuning, 66 BPM, no dynamic build, long cathedral reverb, ethereal and weightless, no vocals, no percussion, no drums, continuous ambient texture
```

**Title:** `Heart Chakra · 528 Hz · Harp & Pad`

---

## F — Study Focus, Kalimba + Rain

**Best for:** Long-form study sessions, low-information background, daytime work.

**Style:**
```text
study music, kalimba with warm analog pad, gentle rain on leaves, C major key, 72 BPM, gentle dynamic arc, warm hall reverb, soft and intimate, no vocals, no percussion, no drums, no climax, continuous ambient texture
```

**Title:** `Focus Flow · C major · Kalimba & Rain`

---

## G — Sleep Loop (8-hour bed), Pure Drone

**Best for:** 1–8 hour sleep tracks, YouTube long-form sleep videos. Pure drone — no melodic identity, easy to extend and loop.

**Style:**
```text
deep sleep music, drone synth with cello drone, no melodic instrument, A minor key, 40 BPM, flat dynamics throughout, infinite reverb tail, warm and dark, no vocals, no percussion, no drums, no climax, no melody, pure sustained drone
```

**Title:** `Sleep Drone · A minor · Pure Drone`

---

## H — Forest Meditation, Shakuhachi

**Best for:** Nature-themed meditation, forest-bathing audio guides, Eastern-leaning practice.

**Style:**
```text
meditation music, shakuhachi flute with string ensemble con sordino, forest birds at dawn, E Phrygian mode, 64 BPM, no crescendo no climax, warm hall reverb, earthy and grounded, no vocals, no percussion, no drums, continuous ambient texture
```

**Title:** `Forest Meditation · E Phrygian · Shakuhachi`

---

## How to use this file

In Phase 1 of the workflow, list these eight presets to the user using `AskUserQuestion` (or numbered list if multi-select is needed). Show the title + the one-line "best for" hint, not the full Style string. If the user picks one, lift the entire row into the candidate set for Phase 4 — but still ask in Phase 4 whether they want to tweak any element before finalising.

If the user's brief doesn't match any preset cleanly, skip the preset offer and go through the full interview from Phase 2.
