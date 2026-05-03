# Prompt Templates and Suno Field Map

The master template, the default Exclude Styles block, and the field-by-field map of how the output gets pasted into Suno's Custom Mode UI.

---

## Master Style of Music template

Paste into Suno's *Style of Music* field. Replace placeholders with values from `lookup-tables.md`.

```text
{{FUNCTION_TAG}}, {{PRIMARY_INSTRUMENT}} with {{HARMONIC_BED}}, {{TEXTURAL_LAYER_OR_OMIT}}, {{KEY_AND_MODE}}, {{TEMPO_BPM}} BPM, {{DYNAMIC_RULE}}, {{REVERB_DESCRIPTOR}}, {{TIMBRE_DESCRIPTOR}}, no vocals, no percussion, no drums, no climax, continuous ambient texture
```

The trailing `no vocals, no percussion, no drums, no climax, continuous ambient texture` is a fixed safety phrase that should appear in the *positive* prompt for every output, even though the same concepts are also in Exclude Styles. Belt and braces — Suno is more reliable when both are present.

**Never include duration tokens** (`60 minutes`, `8 hour`, `extended`, `long-form`) in this string. Suno generates ~4-minute clips no matter what — duration claims either get truncated or actively confuse the model. See §extension-strategy below for how length is actually delivered.

**Loop-safety addendum (for any deliverable longer than ~10 minutes):** append this phrase to make the seed loop-tight:

```text
…continuous ambient texture, no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly
```

This biases Suno away from arc-shaped composition (intro → build → outro) and toward the steady-state texture that survives 100+ loops in an 8-hour YouTube video without revealing the seam.

If the user requested a named-artist or named-channel style anchor, append it at the end:
```text
…continuous ambient texture, in the style of {{REFERENCE_NAME}}
```

If the user wants pure drone with no melodic instrument (sleep loop), drop the primary instrument line and use:
```text
{{FUNCTION_TAG}}, {{HARMONIC_BED}} with cello drone, no melodic instrument, {{KEY_AND_MODE}}, {{TEMPO_BPM}} BPM, flat dynamics throughout, infinite reverb tail, {{TIMBRE_DESCRIPTOR}}, no vocals, no percussion, no drums, no climax, no melody, pure sustained drone
```

---

## Title field template

```text
{{FUNCTION_HUMANISED}} · {{KEY_HUMANISED}} · {{PRIMARY_HUMANISED}}
```

Examples:
- `Deep Sleep · A minor · Felt Piano`
- `Heart Chakra · 528 Hz · Harp & Pad`
- `Sleep Drone · A minor · Pure Drone`

Keep titles short — Suno uses the title as a soft prompt hint, so brevity helps. Avoid medicalised verbs (`heal`, `cure`) per the wellness-claim guardrail.

**Never include a duration in the Title** — `8 Hour Loop`, `60 Min`, `Extended`, `Long Version` all confuse Suno (which generates ~4-min clips regardless) and waste prompt budget. Duration lives in the YouTube video title you publish later, not in the Suno-side title.

---

## Lyrics field

Always set the **Instrumental** toggle ON and leave Lyrics empty.

If the generated output contains vocal-like sounds (humming, "ahhs" interpreted as words), regenerate with this single line in Lyrics:

```text
[Instrumental] [No Vocals] [Wordless]
```

This is most often needed when the prompt includes `wordless choir pad` — consider switching the harmonic bed if leaks persist.

---

## Default Exclude Styles block

Paste this verbatim into Suno's *Exclude Styles* field on every generation:

```text
vocals, lyrics, singing, choir words, percussion, drums, beat, kick, snare, hi-hat, bass guitar, electric guitar, distortion, brass, trumpet, saxophone, climax, drop, build-up, crescendo, EDM, pop, rock, hip hop, lo-fi beats, jazz swing, dramatic strings, trailer music, dubstep, trap, sudden volume change, hard pan, sharp transient, sibilance, white noise hiss
```

**Per-preset additions:**

- For Reiki / chakra presets that use a choir pad (Preset C, E), add `choir words` as an extra exclude — already in the default block but worth re-emphasising verbally to the user.
- For study music with a soft pulse, optionally remove `beat` from the exclude list — but keep `kick`, `snare`, `hi-hat` to prevent it turning into a lo-fi beats track.

---

## Suno Custom Mode field map

| Suno field | What goes there | Source |
|---|---|---|
| Custom Mode toggle | ON | Always |
| Instrumental toggle | ON | Always |
| Style of Music | Master template, fully populated | This file §1 |
| Title | Title template | This file §2 |
| Lyrics | Empty (or `[Instrumental] [No Vocals] [Wordless]` if leak) | This file §3 |
| Exclude Styles | Default block | This file §4 |
| Persona | Optional — attach for series consistency | See main SKILL.md Phase 5 |
| Model | v4 (or v4.5 if available) | Avoid v3.5 for ambient |

---

## Extension and looping strategy — turning a 4-min Suno clip into a 3–11 hour YouTube video

**Suno hard limit:** the model generates ~4-minute clips per generation, regardless of what you put in the prompt. Writing "60 minutes" or "8 hour" in the Style or Title field does not change this. Length is built in three layers, in this order:

### Layer 1 — Generate the loop-safe seed (1 generation, ~4 min audio)

Prompt with the loop-safety addendum from §1 above (`no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly`). Re-roll the seed 2–3 times if needed until you get a clip that:

- Starts and ends on the same harmonic centre (no resolution drift)
- Has no fade-in or fade-out
- Has no recognisable melodic phrase (a phrase you can hum back is a phrase that becomes a tic on loop)
- Has no one-off events (single bowl strikes, bird calls, thunder)

The seed quality determines everything downstream — it is cheaper to re-roll the seed 5 times than to extend a bad seed and discover the problem an hour later.

### Layer 2 — Extend the seed in Suno (12–15 generations, ~60 min unique audio)

Use Suno's **Extend** feature to grow the seed:

1. Open the seed in Suno's editor.
2. Set the extend point to **~3:30** of the seed (not the very end — extending from too close to the end produces less stable timbre carry-over).
3. Extend. Suno generates ~4 more minutes that continues the timbre identity.
4. Repeat 12–15 times. You'll have ~60 minutes of unique audio.
5. Download the full extended track as MP3 or WAV.

**Why ~60 min and not the full deliverable length:** Suno's timbre drift accumulates across many extensions. Beyond ~15 extensions, the texture starts wandering. 60 min of high-quality unique audio + post-production looping is more reliable than 8 hours of slowly-drifting Suno output.

### Layer 3 — Loop in post-production (DAW or ffmpeg, multiplies to 3–11 hours)

For a 3–11 hour YouTube video, loop the 60-min unique audio in post:

- **DAW workflow:** drop the 60-min file onto a track 3–11 times back-to-back. Apply a 3-second crossfade between each loop join. Export as the final video audio track.
- **ffmpeg workflow** (for the AI Media Automation pipeline):
  ```bash
  ffmpeg -stream_loop {{LOOP_COUNT-1}} -i input_60min.wav -af "afade=t=in:st=0:d=2,afade=t=out:st={{TOTAL-2}}:d=2" -c:a copy output.wav
  ```
  Where `LOOP_COUNT` = `target_hours * 60 / 60`. For an 8-hour video, `LOOP_COUNT=8`.

**Why looping is undetectable:** sleep listeners are asleep within 5–20 minutes; meditation listeners are introspective; study listeners are working. None of these are doing close-listening for the loop seam. With a loop-safe seed and a 3-second crossfade, even the most attentive listener won't catch the join.

### Cost / generation budget

For a 3–11 hour deliverable:
- 2–3 seed re-rolls (find the loop-safest seed)
- 12–15 extensions (build to ~60 min)
- Total Suno generations: ~15–18 per deliverable

If you're publishing weekly, attach a **Persona** (saved from your best seed) to every subsequent week — Suno will preserve the timbre identity across deliverables, giving the channel a recognisable sound.

### Preset recommendation for long-form

The drone-style **Preset G** (pure sustained drone, no melodic instrument) is by far the safest choice for 3–11 hour videos — there is nothing to become tedious because there is nothing memorable. The trade-off is lower discoverability (no melodic hook = lower thumbnail-stopping power). For brand-building, mix: pad-led seeds for the first half of the video (acts as the "thumbnail bait" first 30 sec), drone seed for the rest.

---

## When to recommend the Persona feature

If the user is producing a *series* (e.g. "Felt Piano Sleep" weekly), recommend Suno's Persona feature in Phase 5:

1. Generate one ideal seed track.
2. Save as Persona ("Felt Piano Sleep Persona").
3. For every subsequent track in the series, attach the persona — Suno preserves timbre, mix, and instrument character across episodes.

This is what gives a channel a recognisable sound identity — flag it whenever the user mentions a recurring channel or series.
