# Suno Prompt System — Deep Sleep & Meditation Music

> A production-ready prompt framework for generating instrumental music in Suno (v4 / v4.5+) for deep sleep, meditation, Reiki, chakra, and study contexts. Written from the perspective of an instrumental composer / ambient producer. Every element is parameterised so a single template can produce hundreds of distinct, on-brand tracks.

---

## How to use this document

1. Read **Part 1** once — it explains the musical decisions that have to be made *before* you write any Suno prompt. Skipping this is why most generated meditation music sounds generic.
2. Use **Part 2** as the canonical prompt template. It has placeholders in `{{DOUBLE_BRACES}}`.
3. Use **Part 3** as the lookup table for what each placeholder accepts.
4. Use **Part 4** to populate the Suno *Exclude Styles* field — this is where most quality wins happen.
5. Pick a ready-to-paste preset from **Part 5** for fast generation.
6. Follow **Part 6** for Suno UI settings and the extension strategy used for 1-hour+ deliverables.
7. Run every output through the **Part 7** quality checklist before publishing.

---

## Part 1 — The Composer's Process

Before opening Suno, run through these eight decisions. The output of this checklist *is* the prompt. Generic prompts come from skipping these decisions; signature tracks come from making them deliberately.

### 1.1 Function (what is this track *for*?)

Sleep, meditation, Reiki, chakra, study, and stress relief are *not the same* musically. The function dictates everything downstream.

| Function | Listener state | Tempo target | Dynamic range | Melodic content |
|---|---|---|---|---|
| Sleep onset (first 20 min) | Falling | 50–60 BPM | Very narrow (±3 dB) | Minimal — drift, no hook |
| Deep sleep loop (hours 2–8) | Asleep | 40–55 BPM | Almost flat (±1 dB) | None — pure drone/pad |
| Meditation (active) | Awake, focused | 60–72 BPM | Narrow (±5 dB) | Sparse motifs, modal |
| Reiki / energy work | Receptive, still | 60–68 BPM | Narrow | Sustained tones, bowl strikes |
| Chakra session | Focused on body | 60–72 BPM | Narrow | Tone tied to chakra frequency |
| Study / focus | Awake, working | 60–80 BPM | Moderate | Repetitive, low-info melody |
| Stress relief | Awake, settling | 55–65 BPM | Narrow | Simple, consonant |

### 1.2 Tonal centre & mode

Choose a key first. The key choice carries 60% of the emotional payload before a single instrument is named.

- **Sleep & Reiki:** low keys feel grounding — **C major / A minor**, **D major**, **F major**. Avoid sharp keys (E, B) — they sit higher and pull attention.
- **Meditation:** **modal** is more interesting than major/minor. **Dorian** (mystical, neither sad nor happy), **Phrygian** (deep contemplation), **Lydian** (uplifting, dreamy).
- **Chakra-aligned tracks:** map to Solfeggio frequencies — **396 Hz** (root), **417 Hz** (sacral), **528 Hz** (heart), **639 Hz** (throat), **741 Hz** (third eye), **852 Hz** (crown). Suno cannot tune to these exactly, but stating the intent in the prompt biases the generation toward the right tonal region.

### 1.3 Tempo & pulse

For sleep, **avoid an audible pulse entirely** — no perceptible beat, no rhythmic motif. Tempo only matters for the rate at which harmonic clouds change. State BPM anyway because Suno uses it as a generation hint.

- 40–60 BPM: deep sleep, deep meditation
- 60–72 BPM: active meditation, Reiki, chakra
- 72–80 BPM: study, light focus

### 1.4 Harmonic palette

Movement happens through chord *colour*, not chord *progression*. Resolutions wake the listener up.

- Use **suspended chords** (sus2, sus4) — they don't resolve.
- Use **modal vamps** — two chords cycling forever, e.g. Dm9 ↔ Gmaj7 (D Dorian).
- Use **drones** — a single sustained low note under everything.
- Avoid V→I cadences, dominant 7ths, leading tones — these all create expectation/release that wakes the brain.

### 1.5 Instrumentation

Pick a **primary** voice (carries the melodic interest, sparse), a **harmonic bed** (the pad/drone underneath), and an optional **textural layer** (nature, bowls, breath).

| Slot | Common choices | What to avoid |
|---|---|---|
| Primary | Solo piano (felt, soft pedal), harp, kalimba, music box, hang drum, classical guitar (nylon, fingerstyle) | Anything bright, plucky, percussive |
| Harmonic bed | Warm analogue pad, string ensemble (con sordino), choir pad (wordless ahhs), Mellotron, drone synth | Bright leads, brass, bowed cellos with vibrato |
| Textural | Tibetan singing bowls, crystal bowls, gentle rain, ocean waves, forest birds (sparse), wind chimes, Tanpura, Shruti box | Thunder, animal cries, traffic, water *drops* (ASMR triggers) |

### 1.6 Texture & dynamics

- **Sustain over articulation.** Long bowed notes, not short bowed notes.
- **Slow attack** on every voice. No transients. No plucked-then-loud entries.
- **Compress dynamics tightly.** Tell Suno explicitly: "no crescendo, no climax, no dynamic build."
- **Layer count: 3–5 voices maximum.** More than five and the mix becomes busy. Less than three and it becomes thin.

### 1.7 Spatial / mix considerations

State these in the prompt — Suno responds to mix language.

- **Wide stereo field**, gentle panning only. No hard pans.
- **Long reverb tail** (hall or cathedral, 4–8 second decay).
- **Warm low end** (rolled off below 40 Hz to avoid speaker rumble).
- **Soft high end** (rolled off above 10 kHz — sibilance and presence wake people up).
- **No transients, no compression pumping.**

### 1.8 Form & duration — and the loop-safety rule

Suno generates ~3–4 minute clips. Sleep tracks need 1–11 hours. Length is NOT delivered through the prompt — it is delivered through extension and looping (Part 6.3).

**Hard rule: never put a duration in the prompt.** Tokens like `60 minutes`, `8 hour`, `extended`, `long-form` do not produce longer Suno output (Suno generates ~4-min clips regardless) and frequently waste prompt budget or actively confuse the model. The deliverable length lives in your composer's notes and your ffmpeg loop count, never in the Suno-pasted text.

**Loop-safety rule for any deliverable longer than ~10 minutes:** the seed must be designed to loop 50–150+ times without revealing the seam. This means:

- **Stable harmonic centre** — the clip ends on (or near) the chord/drone it began on. A 5-second crossfade from end-of-clip to start-of-clip should be inaudible.
- **No memorable melody** — anything you can hum back after one listen becomes a tic by the third loop. Push to drift, drone, or sparse-non-repeating motifs.
- **No fade-in / fade-out** — the seed starts mid-texture and ends mid-texture. Any fade creates a volume dip at every loop join.
- **No one-off events** — a single bowl strike, bird call, or thunder roll heard once will repeat 100+ times in an 8-hour video.
- **No time-of-day cues** — "dawn birds" loop into the next dawn within an hour. Use undated environmental textures (rain, ocean, wind).
- **No entropy build** — the seed must not get busier or quieter across its 4 minutes. Flat is the goal.

Append this loop-safety addendum to the Style of Music string for any long-form seed:

```text
…continuous ambient texture, no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly
```

**Per function:**
- **Sleep:** through-composed drift. No sections. No "intro / build / outro."
- **Meditation (active):** if the deliverable is short (≤10 min), an optional gentle arc — settle (1–2 min) → sustain → release — is OK. If the deliverable is long-form looped, drop the arc and stay flat.
- **Reiki / chakra session:** mark phases if the user is following a session protocol — but very subtly, e.g. a single bowl strike per phase change. Do NOT mark phases for long-form looped content; those marks become tics.

---

## Part 2 — The Master Prompt Template

Suno *Custom Mode* has three fields:

1. **Style of Music** (≈200 characters) — the most important field. Genre tags + key descriptors only.
2. **Lyrics** — set the *Instrumental* toggle ON. Leave empty.
3. **Title** — descriptive, used by Suno as a soft prompt hint.

### 2.1 Style of Music field — Master Template

Paste into Suno's *Style of Music* field. Replace placeholders.

```text
{{FUNCTION_TAG}}, {{PRIMARY_INSTRUMENT}} with {{HARMONIC_BED}}, {{TEXTURAL_LAYER}}, {{KEY_AND_MODE}}, {{TEMPO_BPM}} BPM, {{DYNAMIC_RULE}}, {{REVERB_DESCRIPTOR}}, {{TIMBRE_DESCRIPTOR}}, no vocals, no percussion, no drums, no climax, continuous ambient texture
```

**Worked example** (Deep Sleep — Felt Piano):
```text
deep sleep music, soft felt piano with warm analog pad, distant ocean waves, A minor key, 52 BPM, no dynamic build, long cathedral reverb, warm and dark, no vocals, no percussion, no drums, no climax, continuous ambient texture
```

### 2.2 Title field — Template

```text
{{FUNCTION}} · {{KEY}} · {{PRIMARY_INSTRUMENT}} · {{DURATION_HINT}}
```

Example: `Deep Sleep · A minor · Felt Piano · 8 Hours`

### 2.3 Lyrics field

Leave empty. Toggle **Instrumental: ON**.

If the model still produces vocal-like sounds (humming, choir "ahhs" interpreted as words), put this single line in lyrics:

```text
[Instrumental] [No Vocals] [Wordless]
```

---

## Part 3 — Configuration Variables Reference

Every placeholder, every option. Mix and match.

### 3.1 `{{FUNCTION_TAG}}` — start the prompt with this

| Value | Use for |
|---|---|
| `deep sleep music` | Sleep onset & sleep loop |
| `meditation music` | General meditation |
| `reiki healing music` | Reiki sessions |
| `chakra meditation music` | Chakra-focused work |
| `study music` | Focus, low-information background |
| `stress relief music` | Daytime calm, anxiety reduction |
| `binaural ambient` | When pairing with binaural beats in post |
| `cinematic ambient` | Stylised, more produced |
| `new age music` | Genre-tagged for SEO discoverability |

### 3.2 `{{PRIMARY_INSTRUMENT}}` — carries melodic interest

| Value | Character |
|---|---|
| `soft felt piano` | Intimate, warm, the modern sleep-music default |
| `grand piano with soft pedal` | Slightly brighter than felt, classical feel |
| `concert harp` | Ethereal, harp glissandi (use sparingly) |
| `kalimba` | African thumb piano, gentle plucks |
| `music box` | Childlike, nostalgic — pairs with deep pad |
| `hang drum` | Resonant, mystical, modal |
| `nylon-string classical guitar` | Spanish-tinged calm, fingerstyle |
| `crystal singing bowls` | Pure tones, healing context |
| `Tibetan singing bowls` | Earthier, deeper, meditation context |
| `tanpura` | Indian classical drone — for raga-leaning tracks |
| `shakuhachi flute` | Japanese, breathy, meditative |
| `cello drone` | Warm, sustained, no vibrato |

### 3.3 `{{HARMONIC_BED}}` — the underneath pad

| Value | Character |
|---|---|
| `warm analog pad` | Default — universally good |
| `string ensemble con sordino` | Muted strings, classical sleep |
| `wordless choir pad` | "Ahhs," ethereal — risk of sounding like vocals |
| `Mellotron strings` | Vintage, slightly tape-warped |
| `drone synth` | Pure synthesis, sci-fi calm |
| `harmonium drone` | Hindustani devotional flavour |
| `dark cinematic pad` | More tension — avoid for pure sleep |

### 3.4 `{{TEXTURAL_LAYER}}` — optional, adds environment

| Value | Notes |
|---|---|
| `distant ocean waves` | Universally calming, low-frequency |
| `gentle rain on leaves` | No thunder, no drops on metal |
| `forest birds at dawn` | Sparse only — avoid dawn-chorus density |
| `mountain stream` | Avoid if track is for sleep — water can wake |
| `wind through trees` | Subtle, non-rhythmic |
| `crackling fireplace` | Cosy, study-friendly |
| `Tibetan bowl strikes` | Once every 30–60s, marks meditative breath |
| `wind chimes` | Sparse, randomised |
| `singing bowl shimmer` | Continuous, layered with bowls |
| *(omit)* | Pure music — no environment |

### 3.5 `{{KEY_AND_MODE}}` — the tonal centre

| Value | Mood |
|---|---|
| `A minor key` | Default melancholy-calm |
| `C major key` | Open, bright-but-soft |
| `D major key` | Warm, grounded |
| `F major key` | Pastoral, gentle |
| `D Dorian mode` | Modal, neither happy nor sad |
| `E Phrygian mode` | Deep contemplation, slightly mystical |
| `F Lydian mode` | Dreamy, uplifting |
| `Solfeggio 528 Hz tuning` | Heart-chakra healing context |
| `Solfeggio 432 Hz tuning` | New-age "natural" tuning claim |

### 3.6 `{{TEMPO_BPM}}`

Use a number. `40 BPM`, `52 BPM`, `60 BPM`, `66 BPM`, `72 BPM`. See Part 1.3 for selection.

### 3.7 `{{DYNAMIC_RULE}}` — pick one

- `no dynamic build` (sleep)
- `no crescendo, no climax` (sleep, meditation)
- `gentle dynamic arc` (meditation if you want a mild settle/release shape)
- `flat dynamics throughout` (deep sleep loop)

### 3.8 `{{REVERB_DESCRIPTOR}}`

- `long cathedral reverb` — biggest space, default for sleep
- `warm hall reverb` — slightly tighter
- `intimate room reverb` — for solo piano focus
- `infinite reverb tail` — drone work
- `analog plate reverb` — vintage character

### 3.9 `{{TIMBRE_DESCRIPTOR}}` — pick 1–2

- `warm and dark` — sleep default
- `soft and intimate` — solo piano
- `lush and atmospheric` — pad-forward
- `crystalline and pure` — bowls, healing
- `earthy and grounded` — Tibetan, harmonium
- `ethereal and weightless` — choir pad, harp

---

## Part 4 — Suno Rules & Exclude Styles

Suno v4+ has an **Exclude Styles** field. This is where the largest quality gains are. Paste this block into *Exclude Styles* on every meditation/sleep generation:

```text
vocals, lyrics, singing, choir words, percussion, drums, beat, kick, snare, hi-hat, bass guitar, electric guitar, distortion, brass, trumpet, saxophone, climax, drop, build-up, crescendo, EDM, pop, rock, hip hop, lo-fi beats, jazz swing, dramatic strings, trailer music, dubstep, trap, sudden volume change, hard pan, sharp transient, sibilance, white noise hiss
```

### 4.1 Hard rules Suno must follow

The output must satisfy ALL of the following. If it doesn't, regenerate with a stronger negative prompt.

1. **No discernible vocals** — no humming, no choir words, no breathing samples that read as voice.
2. **No percussion of any kind** — no drum, no shaker, no clap, no rhythmic pulse.
3. **No melodic hook** that repeats memorably (this would catch the brain).
4. **No abrupt dynamic changes** — peak-to-trough must stay within ±5 dB.
5. **No bright high frequencies** above ~10 kHz — these wake light sleepers.
6. **No sub-bass below ~40 Hz** — these rumble through speakers and trigger startle.
7. **No genre bleed** — must not drift into lo-fi beats, neo-classical with crescendo, or cinematic trailer.
8. **Continuous texture** — no gaps, no silence longer than 0.5 seconds.
9. **Stable stereo image** — no hard panning, no sudden L/R movement.
10. **Loop-friendly tail** — final 5 seconds should be quiet sustain that can crossfade into a new clip without a seam.

### 4.2 Soft preferences (regenerate if grossly violated)

- Reverb tail audible — not a dry mix
- Layer count 3–5 voices, not 1 or 8+
- Tonal centre matches the requested key
- Tempo within ±5 BPM of requested

---

## Part 5 — Ready-to-Use Presets

Each preset is a complete copy-paste set: Style field, Title field, Exclude Styles (use Part 4 default unless stated otherwise).

### Preset A — Deep Sleep, Felt Piano

**Style:**
```text
deep sleep music, soft felt piano with warm analog pad, distant ocean waves, A minor key, 52 BPM, no dynamic build, long cathedral reverb, warm and dark, no vocals, no percussion, no drums, no climax, continuous ambient texture
```
**Title:** `Deep Sleep · A minor · Felt Piano`

### Preset B — Theta Meditation, Singing Bowls

**Style:**
```text
meditation music, Tibetan singing bowls with drone synth, occasional bowl strikes, D Dorian mode, 60 BPM, flat dynamics throughout, infinite reverb tail, earthy and grounded, no vocals, no percussion, no drums, no climax, continuous ambient texture
```
**Title:** `Theta Meditation · D Dorian · Singing Bowls`

### Preset C — Reiki Session, Crystal Bowls

**Style:**
```text
reiki healing music, crystal singing bowls with wordless choir pad, singing bowl shimmer, Solfeggio 528 Hz tuning, 60 BPM, no crescendo no climax, long cathedral reverb, crystalline and pure, no vocals, no percussion, no drums, continuous ambient texture
```
**Title:** `Reiki Healing · 528 Hz · Crystal Bowls`

### Preset D — Stress Relief, Solo Piano (Satie-inspired)

**Style:**
```text
stress relief music, grand piano with soft pedal, no other instruments, F Lydian mode, 60 BPM, gentle dynamic arc, intimate room reverb, soft and intimate, no vocals, no percussion, no drums, no climax, sparse Erik Satie inspired
```
**Title:** `Stress Relief · F Lydian · Solo Piano`

### Preset E — Chakra (Heart), Harp + Pad

**Style:**
```text
chakra meditation music, concert harp with warm analog pad, Tibetan bowl strikes, Solfeggio 528 Hz tuning, 66 BPM, no dynamic build, long cathedral reverb, ethereal and weightless, no vocals, no percussion, no drums, continuous ambient texture
```
**Title:** `Heart Chakra · 528 Hz · Harp & Pad`

### Preset F — Study Focus, Kalimba + Rain

**Style:**
```text
study music, kalimba with warm analog pad, gentle rain on leaves, C major key, 72 BPM, gentle dynamic arc, warm hall reverb, soft and intimate, no vocals, no percussion, no drums, no climax, continuous ambient texture
```
**Title:** `Focus Flow · C major · Kalimba & Rain`

### Preset G — Sleep Loop (long-form bed), Pure Drone

**Style:**
```text
deep sleep music, drone synth with cello drone, no melodic instrument, A minor key, 40 BPM, flat dynamics throughout, infinite reverb tail, warm and dark, no vocals, no percussion, no drums, no climax, no melody, pure sustained drone, no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly
```
**Title:** `Sleep Drone · A minor · Pure Drone`

(Note: the Title intentionally omits "8 Hour" — Suno generates ~4 min regardless; length is built via Part 6.3's extension + loop workflow.)

### Preset H — Forest Meditation, Shakuhachi

**Style:**
```text
meditation music, shakuhachi flute with string ensemble con sordino, forest birds at dawn, E Phrygian mode, 64 BPM, no crescendo no climax, warm hall reverb, earthy and grounded, no vocals, no percussion, no drums, continuous ambient texture
```
**Title:** `Forest Meditation · E Phrygian · Shakuhachi`

---

## Part 6 — Suno Operation

### 6.1 Model selection

- **v4 / v4.5** — current best for ambient and sustained textures. Use this.
- **v3.5** — acceptable for shorter pieces; tends to introduce unwanted percussion on long ambient.
- Do **not** use Simple Mode — it ignores most of the structure above.

### 6.2 Custom Mode settings

| Field | Value |
|---|---|
| Custom Mode | ON |
| Instrumental | ON |
| Style of Music | (Part 2.1 template) |
| Title | (Part 2.2 template) |
| Lyrics | empty (or `[Instrumental] [No Vocals] [Wordless]` if vocals leak) |
| Exclude Styles | (Part 4 block) |
| Persona | (see 6.4) |

### 6.3 Extension strategy — going from 4 minutes to 1+ hour

Suno generates ~4-minute clips. For a 1-hour sleep track:

1. Generate the seed clip with the prompt above.
2. Use Suno's **Extend** feature, starting from ~3:30 of the seed. This carries forward the timbral identity.
3. Repeat extension 12–15 times until you have 60+ minutes.
4. Download the full extended track as MP3/WAV.
5. In post (ffmpeg or your DAW), trim hard cuts and apply a 2-second crossfade between major join points if any seam is audible.
6. For the loop point: fade the last 5 seconds to silence, then loop back to the start with a 5-second fade-in. The drone-style presets (G) loop cleanest.

For 8-hour sleep videos: generate 1 hour of unique audio, then loop 8× in post. Listeners are asleep — the loop is undetectable.

### 6.4 Persona feature — for series consistency

If you publish a *series* (e.g. "Felt Piano Sleep" weekly), use Suno's **Persona** feature:

1. Generate one ideal seed track.
2. Save as Persona ("Felt Piano Sleep Persona").
3. For every subsequent track in the series, attach the persona — Suno will preserve timbre, mix, and instrument character across episodes. This is what gives a channel a recognisable sound identity.

### 6.5 Cost / generation budget

- Each generation costs credits. For sleep tracks, expect 12–15 generations per 1-hour deliverable (one seed + 12–15 extensions).
- Budget 2–3 *re-rolls* per seed before extending — the seed quality determines everything downstream.

---

## Part 7 — Post-Generation Quality Checklist

Listen on **headphones** and **speakers** before publishing. Run every track through this list. If any HIGH item fails, regenerate. MEDIUM items can be fixed in post.

### High — must pass (regenerate if fails)

- [ ] No vocals, no humming, no breath samples
- [ ] No drum, shaker, clap, or audible rhythmic pulse
- [ ] No memorable melodic hook that loops
- [ ] No sudden volume jump greater than ~6 dB
- [ ] Tonal centre matches the requested key (test by humming the requested root note over the track — should feel resolved)
- [ ] No genre drift (no lo-fi beats, no cinematic build, no jazz swing)
- [ ] Tail of clip is quiet sustain that can crossfade

### Medium — should pass (fix in post if not)

- [ ] Stereo image stable, no hard panning
- [ ] No bright highs above ~10 kHz (run a low-pass at 10 kHz if needed)
- [ ] No sub-bass rumble below ~40 Hz (high-pass at 40 Hz)
- [ ] Reverb tail present, not dry
- [ ] Loudness target around **-23 LUFS integrated** for sleep, **-18 LUFS** for meditation/study (quieter than typical streaming masters — sleep tracks must not be loud)
- [ ] No clipping, no peaks above -3 dBFS

### Low — preference

- [ ] 3–5 distinct voices audible in the mix
- [ ] Tempo within ±5 BPM of target (doesn't matter much for non-pulsed ambient)
- [ ] Textural layer present at the requested level (background, never foreground)

---

## Part 8 — Iteration & Refinement Tips

### 8.1 If the output sounds too generic

- Add a **named reference** to the *Style* field: `…in the style of Brian Eno's Music for Airports`, `…inspired by Hiroshi Yoshimura`, `…Nils Frahm felt piano character`. Suno responds to artist references for ambient.
- Make the textural layer more specific: not `nature sounds` but `distant Pacific Northwest rainforest at dusk`.

### 8.2 If the output is too busy

- Cut one voice from the prompt. Three voices > five voices for sleep.
- Add `minimal`, `sparse`, `negative space` to the *Style* field.
- Lower the BPM by 8–10.

### 8.3 If the output drifts into the wrong genre

- Strengthen the *Exclude Styles* field with the offending genre.
- Move the function tag to the very front of the prompt — Suno weights early tokens more heavily.
- Drop any instrument that has strong genre association (electric piano → jazz; acoustic guitar → folk; synth lead → trance).

### 8.4 If vocals keep leaking through

- Add `[Instrumental] [No Vocals] [Wordless]` in the Lyrics field.
- Remove `wordless choir pad` from the prompt (most common vocal-leak source).
- Add `purely instrumental` to the *Style* field.

### 8.5 If the track has no arc at all and feels static

- This is correct for sleep. Static is the goal. Resist the urge to add motion.
- For meditation, swap `flat dynamics throughout` → `gentle dynamic arc`.

### 8.6 Versioning prompts

When a generation works, save the **exact** prompt and seed/persona ID alongside the audio file. This is the only way to reproduce or evolve a track later. Suggested filename convention:

```text
{{date}}_{{function}}_{{key}}_{{primary}}_{{seed_or_persona_id}}.wav
```

Example: `2026-05-03_deep-sleep_a-minor_felt-piano_persona-007.wav`

---

## Part 9 — Wellness-claim guardrails

This applies to the *titles, descriptions, and metadata* you publish alongside the audio — not the audio itself. The audio is just sound. Anything that *claims an effect* needs care.

- Prefer experiential verbs: **rest, unwind, settle, drift, slow down**.
- Avoid medical verbs as effect claims: **heal, cure, treat, fix, reverse**.
- Frame Reiki / chakra / Solfeggio as **inspiration** for the music, not as a guaranteed mechanism: "Reiki-inspired ambient", not "Reiki energy session that opens your root chakra."
- Add a one-line disclaimer to your channel About: *"This music is for relaxation only and is not a substitute for medical advice or treatment."*
- Cite a real source if you make a sleep claim — Cochrane reviews of music-assisted sleep are the most defensible.

---

*Last updated: May 2026. Designed for the AI Media Automation pipeline (Suno seed → extend → render → upload workflow).*
