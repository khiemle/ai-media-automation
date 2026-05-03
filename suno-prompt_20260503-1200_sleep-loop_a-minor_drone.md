---
generated: 2026-05-03
brief: sleep music · rainy day · cozy house · YouTube long-form
function: sleep_loop
---

## Suno Prompt — Sleep Drone · Rain · A minor

**Suno Custom Mode settings**
- Model: v4 (or v4.5 if available)
- Custom Mode: ON
- Instrumental: ON

---

### Style of Music (paste into Style field)
```
deep sleep music, drone synth with cello drone, no melodic instrument, gentle rain on leaves, A minor key, 45 BPM, flat dynamics throughout, infinite reverb tail, warm and dark, no vocals, no percussion, no drums, no climax, no melody, pure sustained drone, no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly
```

---

### Title (paste into Title field)
```
Sleep Drone · Rain · A minor
```

---

### Lyrics field
Leave empty. If vocal-like sounds leak into the output, paste this single line:
```
[Instrumental] [No Vocals] [Wordless]
```

---

### Exclude Styles (paste into Exclude Styles field)
```
vocals, lyrics, singing, choir words, percussion, drums, beat, kick, snare, hi-hat, bass guitar, electric guitar, distortion, brass, trumpet, saxophone, climax, drop, build-up, crescendo, EDM, pop, rock, hip hop, lo-fi beats, jazz swing, dramatic strings, trailer music, dubstep, trap, sudden volume change, hard pan, sharp transient, sibilance, white noise hiss
```

---

### Composer's notes
- **Function:** sleep_loop (YouTube long-form, 1–8 hours)
- **Key / mode:** A minor
- **Tempo:** 45 BPM
- **Primary:** drone synth + cello drone (no melodic instrument)
- **Texture:** gentle rain on leaves (steady — no thunder, no drops on metal, no rhythmic variations)
- **Harmonic bed:** drone synth sustain
- **Loop-safety:** Stable harmonic centre, no melodic instrument, no fade-in/fade-out, mid-texture start and end. No one-off events. Safe to loop 100+ times for an 8-hour YouTube video.
- **Why this works for YouTube sleep content:** There is nothing memorable to become tedious — no piano hook, no bowl strike, no bird call. The rain and cello-drone warmth carry the full runtime. The cozy-house feeling comes from the low-frequency warmth and the rain-on-leaves texture rather than a melody.

---

### Post-generation quality check
Before publishing, verify the output passes ALL of the following on headphones + speakers:

**Must pass (regenerate if fails):**
- [ ] No vocals, humming, or breath samples interpreted as voice
- [ ] No drum, shaker, clap, or audible rhythmic pulse
- [ ] No memorable melodic phrase (nothing you can hum back)
- [ ] No sudden volume jump greater than ~6 dB
- [ ] Tonal centre resolves to A minor root — hum the note over the track, it should feel settled
- [ ] No genre drift (no lo-fi beats, cinematic build, jazz, trance arpeggios)
- [ ] Rain texture is steady — no thunder crack, no rhythmic drip pattern, no crescendo into storm

**Loop-safety (must pass — this is going on a long-form YouTube video):**
- [ ] **Crossfade test:** cue the last 5 sec next to the first 5 sec, apply a 5-second fade — the join is inaudible
- [ ] **No fade-in / fade-out:** clip starts mid-texture and ends mid-texture (no volume ramp at 0:00 or end)
- [ ] **No one-off events:** nothing happens once that would repeat every 4 minutes for 8 hours
- [ ] **Stable harmonic centre:** the drone at the end is the same tone as the drone at the start
- [ ] **No entropy build:** the clip is not getting busier or quieter from start to end — flat is the goal

**Fix in post (not a regenerate):**
- [ ] Highs too bright → low-pass at 10 kHz
- [ ] Sub-bass rumble → high-pass at 40 Hz
- [ ] Too loud → re-master to –23 LUFS integrated (sleep tracks should be quiet)

---

### Extension and looping strategy — building the 1–8 hour YouTube video

**Step 1 — Find the best seed (2–3 re-rolls)**
Generate the prompt above 2–3 times. Pick the seed that:
- Has the steadiest rain (not building or fading)
- Starts and ends on the same drone tone
- Has no one-off event you'd notice repeating every 4 minutes

**Step 2 — Extend to ~60 min unique audio (12–15 extensions)**
1. Open the winning seed in Suno's editor
2. Set the extend point to **~3:30** (not the very end — extending from 3:30 preserves timbre stability)
3. Extend → Suno generates ~4 more minutes continuing the drone identity
4. Repeat 12–15 times → you'll have ~60 minutes of unique audio
5. Download the full extended track as MP3 or WAV

**Step 3 — Loop to final video length (DAW or ffmpeg)**

For an 8-hour YouTube video, loop the 60-min file 8× in post:

```bash
# ffmpeg loop — replace LOOP_COUNT with target_hours (e.g. 8)
ffmpeg -stream_loop 7 -i sleep_rain_drone_60min.wav \
  -af "afade=t=in:st=0:d=3,afade=t=out:st=28797:d=3" \
  -c:a pcm_s16le sleep_rain_drone_8hr.wav
```

Or in any DAW: drop the 60-min file onto a track 8× back-to-back, apply a 3-second crossfade at each join, export.

**Why the loop is undetectable:** sleep listeners are asleep within 5–20 minutes. With a loop-safe drone seed and a 3-second crossfade, even an awake listener won't catch the seam — there's no melodic marker to betray the restart.

**Total Suno generation budget for one video:** ~15–18 clips (2–3 seed re-rolls + 12–15 extensions)

---

### Series tip
If this becomes a recurring channel upload (e.g. weekly rain-sleep videos), generate one ideal seed, save it as a **Suno Persona** ("Rain Sleep Drone Persona"), and attach that persona to every subsequent generation. Suno will carry the timbre and mix character across the series, giving the channel a recognisable sound.
