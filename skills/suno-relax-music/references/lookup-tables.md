# Lookup Tables — Suno Relax Music Placeholders

Every value the prompt builder can plug in. Each row has a one-line note on *when it fits* so you can pre-filter before offering options to the user.

---

## §1 — Function → musical-properties matrix

This is the master decision. The function picked here constrains every other choice. If a downstream pick (instrument, tempo, dynamic) violates the function's constraints, push back.

| Function | Tempo | Dynamic range | Melody | Pulse | Typical deliverable length |
|---|---|---|---|---|---|
| `sleep_onset` | 50–60 BPM | ±3 dB | Minimal drift, no hook | None | 20–30 min |
| `sleep_loop` | 40–55 BPM | ±1 dB | None — pure drone | None | 1–11 hours (YouTube) |
| `meditation_active` | 60–72 BPM | ±5 dB | Sparse motifs, modal | None | 10–60 min |
| `reiki_session` | 60–68 BPM | Narrow | Sustained tones, bowl strikes | None | ~60 min |
| `chakra_session` | 60–72 BPM | Narrow | Tone tied to chakra freq | None | 7–60 min |
| `study_focus` | 60–80 BPM | Moderate | Repetitive, low-info | Optional, very soft | 30 min – 4 h |
| `stress_relief` | 55–65 BPM | Narrow | Simple, consonant | None | 10–30 min |

**The "deliverable length" column is for picking loop-safety constraints in Phase 2.5 — it never goes into the Suno prompt.** Suno generates ~4-min clips regardless. Length is built via Suno's Extend feature (~60 min unique audio) plus post-production looping (multiplies to 1–11 h). See `prompt-templates.md` §extension-strategy. If the deliverable is >10 min, append the loop-safety addendum to the Style of Music string.

---

## §2 — Function tag (opening token of the prompt)

| Token | Use for |
|---|---|
| `deep sleep music` | sleep_onset, sleep_loop |
| `meditation music` | meditation_active |
| `reiki healing music` | reiki_session |
| `chakra meditation music` | chakra_session |
| `study music` | study_focus |
| `stress relief music` | stress_relief |
| `binaural ambient` | when pairing with binaural beats in post |
| `cinematic ambient` | stylised, more produced |
| `new age music` | SEO-tagged for discoverability |

---

## §3 — Key and mode

| Token | Mood | Best fits |
|---|---|---|
| `A minor key` | Default melancholy-calm | sleep, stress relief |
| `C major key` | Open, bright-but-soft | study, daytime |
| `D major key` | Warm, grounded | meditation, Reiki |
| `F major key` | Pastoral, gentle | sleep, study |
| `D Dorian mode` | Modal, neither happy nor sad | meditation, Reiki |
| `E Phrygian mode` | Deep contemplation, slightly mystical | meditation |
| `F Lydian mode` | Dreamy, uplifting | meditation, study |
| `Solfeggio 528 Hz tuning` | Heart-chakra context | chakra (heart), Reiki |
| `Solfeggio 432 Hz tuning` | New-age "natural" tuning | meditation, sleep |
| `Solfeggio 396 Hz tuning` | Root-chakra context | chakra (root) |
| `Solfeggio 741 Hz tuning` | Third-eye context | chakra (third eye) |

**Note:** Solfeggio frequencies are *intent* in the Suno prompt — the model can't tune precisely. Frame them as inspiration in the composer's notes, not as a delivered spec.

---

## §4 — Tempo (BPM)

State as a number, e.g. `52 BPM`.

| Range | Use for |
|---|---|
| 40–50 BPM | Sleep loop, deep drone |
| 50–60 BPM | Sleep onset, deep meditation |
| 60–72 BPM | Active meditation, Reiki, chakra |
| 72–80 BPM | Study, light focus |

If the user requested an audible pulse (rare for these niches), still keep the BPM in these ranges — the pulse should be *implied*, not banged out.

---

## §5 — Primary instrument

| Token | Character | Avoid for |
|---|---|---|
| `soft felt piano` | Intimate, warm — modern sleep default | (none) |
| `grand piano with soft pedal` | Slightly brighter, classical feel | sleep_loop |
| `concert harp` | Ethereal, glissandi | sleep_loop |
| `kalimba` | Plucky, gentle — best at low tempo | sleep_loop, sleep_onset |
| `music box` | Childlike, nostalgic | adult Reiki |
| `hang drum` | Resonant, mystical, modal | sleep_loop |
| `nylon-string classical guitar` | Spanish-tinged calm, fingerstyle | chakra |
| `crystal singing bowls` | Pure tones, healing | study |
| `Tibetan singing bowls` | Earthy, deep | study |
| `tanpura` | Indian classical drone | study |
| `shakuhachi flute` | Japanese, breathy | sleep_loop |
| `cello drone` | Warm sustained, no vibrato | (none) |

---

## §6 — Harmonic bed (the pad/drone underneath)

| Token | Character | Risk |
|---|---|---|
| `warm analog pad` | Universal default | low |
| `string ensemble con sordino` | Muted strings, classical sleep | low |
| `wordless choir pad` | Ethereal "ahhs" | medium — vocal-leak risk; consider exclude `choir words` |
| `Mellotron strings` | Vintage, tape-warped | low |
| `drone synth` | Pure synthesis | low |
| `harmonium drone` | Hindustani devotional | low |
| `dark cinematic pad` | More tension | high — avoid for sleep |

---

## §7 — Textural layer (optional)

Skip this slot entirely if the user wants pure music. For sleep, water/wind textures must be steady — no thunder, no drops on metal, no birds with sharp calls.

| Token | Notes |
|---|---|
| `distant ocean waves` | Universal calm, low-frequency |
| `gentle rain on leaves` | No thunder, no drops on metal |
| `forest birds at dawn` | Sparse only — never dense dawn chorus |
| `mountain stream` | Avoid for sleep — water can wake |
| `wind through trees` | Subtle, non-rhythmic |
| `crackling fireplace` | Cosy, study-friendly |
| `Tibetan bowl strikes` | Once every 30–60s, marks meditative breath |
| `wind chimes` | Sparse, randomised |
| `singing bowl shimmer` | Continuous layered with bowls |
| *(omit)* | Pure music, no environment |

---

## §8 — Dynamic rule

| Token | Use for |
|---|---|
| `flat dynamics throughout` | sleep_loop |
| `no dynamic build` | sleep_onset, Reiki, chakra |
| `no crescendo, no climax` | meditation_active, stress_relief |
| `gentle dynamic arc` | study_focus, optional for meditation if a settle/release shape is wanted |

---

## §9 — Reverb descriptor

| Token | Character |
|---|---|
| `long cathedral reverb` | Largest space — sleep default |
| `warm hall reverb` | Slightly tighter than cathedral |
| `intimate room reverb` | Solo piano focus, dry-ish |
| `infinite reverb tail` | Drone work |
| `analog plate reverb` | Vintage character |

---

## §10 — Timbre descriptor (pick 1–2)

| Token | Use for |
|---|---|
| `warm and dark` | Sleep default |
| `soft and intimate` | Solo piano |
| `lush and atmospheric` | Pad-forward |
| `crystalline and pure` | Bowls, healing |
| `earthy and grounded` | Tibetan, harmonium |
| `ethereal and weightless` | Choir pad, harp |

---

## How to use these tables in Phase 3

1. Look at the function picked in Phase 2.
2. For each slot (§2 → §10), filter the rows by *fits this function* and *doesn't conflict with already-picked slots*.
3. Present the filtered options to the user — usually 2-4 candidates per slot.
4. Briefly explain what the choice does to the listening experience.
5. Ask via `AskUserQuestion`.
