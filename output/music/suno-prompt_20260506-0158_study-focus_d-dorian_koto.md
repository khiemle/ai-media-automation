# Suno Prompt — Study Focus · D Dorian · Koto & Wind

**Brief:** Bamboo Forest Wind — Japanese Ambience for Study
**Generated:** 2026-05-06 01:58

---

**Suno Custom Mode settings**
- Model: v4 (or v4.5 if available)
- Custom Mode: ON
- Instrumental: ON

---

### Style of Music (paste into Style field)
```text
study music, koto with warm analog pad, wind through trees, D Dorian mode, 70 BPM, no crescendo, no climax, warm hall reverb, lush and atmospheric, sparse non-repeating koto motifs, long silences between phrases, no vocals, no percussion, no drums, continuous ambient texture, no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly
```

---

### Title (paste into Title field)
```text
Study Focus · D Dorian · Koto & Wind
```

---

### Lyrics field
Leave empty. If vocal-like sounds leak into the output, paste this single line:
```text
[Instrumental] [No Vocals] [Wordless]
```

---

### Exclude Styles (paste into Exclude Styles field)
```text
vocals, lyrics, singing, choir words, percussion, drums, beat, kick, snare, hi-hat, bass guitar, electric guitar, distortion, brass, trumpet, saxophone, climax, drop, build-up, crescendo, EDM, pop, rock, hip hop, lo-fi beats, jazz swing, dramatic strings, trailer music, dubstep, trap, sudden volume change, hard pan, sharp transient, sibilance, white noise hiss
```

---

### Composer's notes

- **Function:** study_focus — low-information background for extended work sessions (2–8 hrs YouTube)
- **Key / mode:** D Dorian — warm modal centre, neither melancholic nor bright, avoids the emotional drama that pulls focus from work
- **Tempo:** 70 BPM
- **Primary:** koto (Japanese zither) · **Bed:** warm analog pad · **Texture:** wind through trees
- **Loop-safety:** Stable harmonic centre on D (begins and ends on D Dorian tonal centre). Sparse, non-repeating koto motifs with long silences between phrases — no hook you can hum, nothing that becomes a tic on the 50th loop. Mid-texture start and end — no fade-in or fade-out. Wind layer is continuous and non-rhythmic (no gusts, no rustling events). Safe to loop 100+ times for an 8-hour YouTube video.
- **Why this works for study listeners:** D Dorian's modal warmth provides tonal colour without emotional narrative; koto's sparse phrasing gives the ear a gentle foreground anchor without creating a recognisable melody; wind through trees covers the loop seam and keeps the bamboo-forest atmosphere without time-of-day cues.

---

### Post-generation quality check

Listen on **headphones** first, then **speakers**. Before publishing, verify:

**Must pass (regenerate if fails):**
- [ ] No vocals, humming, or breath interpreted as voice
- [ ] No drum, shaker, clap, or audible rhythmic pulse
- [ ] No memorable koto phrase you can hum back after one listen — if you can, regenerate (this is the main loop risk with koto)
- [ ] No sudden volume jump greater than ~6 dB
- [ ] Tonal centre matches D Dorian — hum the note D over the track; it should feel resolved
- [ ] No genre drift — no lo-fi beats creeping in, no cinematic build, no jazz swing

**Loop-safety (must pass for 2–8 hr YouTube deliverable):**
- [ ] **Crossfade test:** cue the last 5 seconds next to the first 5 seconds, crossfade — the join must be inaudible
- [ ] **No fade-in / fade-out:** the clip must start mid-texture and end mid-texture
- [ ] **No one-off events:** no single koto flourish, no wind gust, no isolated sound that occurs only once per clip
- [ ] **Stable harmonic centre:** the pad/koto ends where it began — no drift to a new key
- [ ] **No entropy build:** the seed must not get busier or quieter end-to-end — flat is the goal

---

### Extension and looping strategy — 2–8 hour YouTube deliverable

Suno generates ~4-min clips regardless of what you write in the prompt. Length is built in three layers:

**Layer 1 — Find the loop-safe seed (2–3 re-rolls)**
Generate 2–3 variants. Pick the one where:
- The koto phrasing is most sparse and non-repeating
- The clip starts and ends on the same pad texture (no fade-in or fade-out)
- There is no single event you'd notice if it happened every 4 minutes for 8 hours

**Layer 2 — Extend to ~60 min unique audio (12–15 Suno extensions)**
1. Open the seed in Suno's editor
2. Set extend point to ~3:30 (not the very end — timbre carry-over is more stable here)
3. Extend → Suno generates ~4 more minutes of continuous texture
4. Repeat 12–15 times → ~60 min of unique audio
5. Download as WAV or MP3

**Layer 3 — Loop in post-production to reach 2–8 hours**
```bash
# ffmpeg — loop the 60-min file N times with a 3-second crossfade at each join
# For an 8-hour video: LOOP_COUNT=8, TOTAL_SECS=28800
ffmpeg -stream_loop 7 -i input_60min.wav \
  -af "afade=t=in:st=0:d=3,afade=t=out:st=28797:d=3" \
  -c:a pcm_s16le output_8hr.wav
```
Adjust `-stream_loop` and the fade timestamps for your target length.
Listeners are studying — the loop seam at a crossfaded join is undetectable.

**Total Suno generation budget:** ~15–18 generations per deliverable (2–3 seed rolls + 12–15 extensions).

---

### Series note
If this becomes a recurring channel series (e.g. "Japanese Study Ambience" weekly), save your best seed as a **Suno Persona** after the first successful generation. Attaching the Persona to each new weekly track preserves the koto timbre and pad character across episodes — giving the channel a recognisable sound identity.
