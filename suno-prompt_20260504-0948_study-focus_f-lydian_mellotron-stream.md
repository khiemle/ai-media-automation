# Suno Prompt — Study Focus · F Lydian · Mellotron & Stream

**Brief:** Forest Stream Sounds — Study & Focus Ambience  
**Reference channel:** Ambient Earth  
**Generated:** 2026-05-04  

---

**Suno Custom Mode settings**
- Model: v4 (or v4.5 if available)
- Custom Mode: ON
- Instrumental: ON

---

### Style of Music (paste into Style field)
```text
study music, Mellotron strings with drone synth, gentle forest stream texture, F Lydian mode, 68 BPM, flat dynamics throughout, warm hall reverb, lush and atmospheric, no vocals, no percussion, no drums, no climax, continuous ambient texture, no intro, no outro, mid-texture start, mid-texture end, stable harmonic centre, loop-friendly, in the style of Ambient Earth
```

### Title (paste into Title field)
```text
Study Focus · F Lydian · Mellotron & Stream
```

### Lyrics field
Leave empty. If vocal-like sounds leak into the output, paste this single line:
```text
[Instrumental] [No Vocals] [Wordless]
```

### Exclude Styles (paste into Exclude Styles field)
```text
vocals, lyrics, singing, choir words, percussion, drums, beat, kick, snare, hi-hat, bass guitar, electric guitar, distortion, brass, trumpet, saxophone, climax, drop, build-up, crescendo, EDM, pop, rock, hip hop, lo-fi beats, jazz swing, dramatic strings, orchestral swell, cinematic build, string section swell, trailer music, dubstep, trap, sudden volume change, hard pan, sharp transient, sibilance, white noise hiss
```

---

### Composer's notes
- **Function:** study_focus
- **Key / mode:** F Lydian — dreamy, uplifting quality without being cheerful; sits in the background without demanding attention
- **Tempo:** 68 BPM — upper edge of active meditation range, keeps the ambient texture from feeling static
- **Primary texture:** Mellotron strings (vintage tape-warped warmth) + drone synth foundation
- **Nature layer:** Gentle forest stream — continuous flowing water, music-forward balance (stream audible but behind pads)
- **Dynamic rule:** Flat dynamics throughout — no arc, no build, no release; loop-safe
- **Loop-safety:** Stable harmonic centre in F Lydian, no melodic instrument = nothing to hum back, mid-texture start/end, flat dynamics. Safe to loop 100+ times for an 8-hour YouTube video.
- **Why this works for study / YouTube multi-hour:** The absence of a melodic instrument removes the brain's most common "distraction hook." Mellotron strings give the pad a warm, slightly imperfect character that sits closer to the Ambient Earth aesthetic than a clean synth pad. The forest stream registers subconsciously — present but never foregrounded. F Lydian's raised fourth creates a gentle lift that keeps the texture from feeling oppressive during long work sessions.
- **Reference anchor:** Ambient Earth — lush, produced ambient with nature texture; Mellotron character matches their slightly vintage, non-clinical pad approach.

---

### Post-generation quality check
Before publishing, listen on **headphones then speakers** and verify:

**Must pass (regenerate if fails):**
- No vocals, humming, or breath samples interpreted as voice
- No drum, shaker, clap, or audible rhythmic pulse
- No memorable melodic phrase (if you can hum something back after one listen → regenerate)
- No sudden volume jump > ~6 dB
- Tonal centre resolves to F (hum F over the track — should feel settled)
- No genre drift into cinematic build, orchestral swell, or dramatic strings
- Mellotron stays as texture, not as a lead line

**Loop-safety — must pass (multi-hour YouTube deliverable):**
- **Crossfade test:** cue last 5 sec next to first 5 sec, apply 5-sec crossfade, listen — seam should be inaudible
- **No fade-in / fade-out:** clip must start and end mid-texture at consistent volume
- **No memorable melody:** pure drift and sustain only
- **Stable harmonic centre:** clip ends on same pad/drone chord it began on
- **No one-off events:** no single bird call, water drop accent, or other event that will tick every 4 minutes for 8 hours
- **No time-of-day cues:** "forest stream" is undated ✓ — avoid any dawn bird sounds if they leak in
- **No entropy build:** texture at minute 3:50 should feel identical in density to minute 0:10

---

### Extension and looping strategy — 8-hour YouTube deliverable

Suno generates ~4-minute clips regardless of what the prompt says. Length is built in three layers:

**Layer 1 — Generate the loop-safe seed (2–3 re-rolls)**
Re-roll the seed until you get one that:
- Starts and ends on the same pad chord (no harmonic drift)
- Has no fade-in or fade-out (must start and end at full texture volume)
- Has no audible melodic phrase you can hum
- Has no one-off water or string accent event

Invest the re-rolls here — fixing a bad seed after 15 extensions wastes an hour.

**Layer 2 — Extend in Suno (12–15 generations → ~60 min unique audio)**
1. Open the seed in Suno's editor
2. Set the extend point to **~3:30** of the clip (not the very end — better timbre carry-over)
3. Extend → ~4 more minutes of continuous texture
4. Repeat 12–15 times
5. Download the full extended track as WAV

**Layer 3 — Loop in post (DAW or ffmpeg → 3–11 hours)**

DAW: drop the 60-min file 8× end-to-end, apply 3-second crossfade at each join, export.

ffmpeg (for the AI Media Automation pipeline):
```bash
ffmpeg -stream_loop 7 -i input_60min.wav \
  -af "afade=t=in:st=0:d=3,afade=t=out:st=28797:d=3" \
  -c:a pcm_s16le output_8hr.wav
```
(8-hour target: 7 loops after the first = `stream_loop 7`. Adjust `st=` to `total_seconds - 3`.)

**Total Suno generation budget:** ~15–18 generations per 8-hour deliverable.

---

### Series / Persona recommendation
If this becomes a recurring study-music series (e.g., weekly uploads), save your best seed as a **Suno Persona** ("Ambient Earth Study — Mellotron F Lydian"). Attach the persona to every subsequent generation — Suno preserves the Mellotron timbre, pad character, and mix identity across episodes, giving your channel a recognisable sound without re-engineering each track from scratch.

---

*Built with the Suno Relax Music Prompt Builder · 2026-05-04*
