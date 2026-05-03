# Post-Generation Quality Checklist

Run every Suno output through this list on **headphones** AND **speakers** before publishing. If a HIGH item fails, regenerate. MEDIUM items can be fixed in post.

When emitting the final prompt block in Phase 5, copy the relevant HIGH-priority bullets into the "Post-generation quality check" section of the output, tailored to the specific function (e.g., for sleep tracks pull the sleep-specific items, for study pull the study-relevant ones).

---

## High priority — must pass (regenerate if fails)

- No vocals, no humming, no breath samples interpreted as voice
- No drum, shaker, clap, or audible rhythmic pulse (study music: a *very* soft implied pulse is OK only if requested)
- No memorable melodic hook that loops in a wake-the-brain way
- No sudden volume jump greater than ~6 dB
- Tonal centre matches the requested key (test by humming the requested root note over the track — should feel resolved)
- No genre drift (no lo-fi beats, no cinematic build, no jazz swing, no trance arpeggios)
- Tail of clip is quiet sustain that can crossfade — for extension and looping

## High priority — loop-safety (must pass for ANY deliverable longer than ~10 minutes, including all 1–11 hour YouTube content)

For the relax-music YouTube niche, every Suno seed becomes a loop played 50–150+ times. Anything that survives a single play but reveals itself on repeat is a regenerate trigger.

- **Crossfade test passes:** a 5-second fade from clip-end into clip-start is inaudible. Test it: cue the last 5 sec next to the first 5 sec, crossfade, listen — if you hear a seam, regenerate.
- **No fade-in / fade-out:** the clip must start mid-texture and end mid-texture. A fade-in at 0:00 means every loop join has an audible volume dip.
- **No memorable melody:** if you can hum the melody back after one listen, it will become a tic by the third loop. The seed must be drift, drone, or sparse-non-repeating.
- **Stable harmonic centre:** the chord/drone the clip ends on is the same one (or very close to) the chord/drone it began on. Modal vamps that drift to a new key are fail.
- **No one-off events:** no single bowl strike, bird call, thunder roll, or thumb-piano pluck that occurs once. Anything that happens once will happen 100+ times in an 8-hour video and become a clock-tic.
- **No time-of-day cues:** "dawn birds" loop into the next dawn within an hour. Use undated environmental textures (steady rain, ocean swell, wind, room tone) instead.
- **No entropy build:** the seed must not get busier or quieter from start to end. Flat is the goal.

## Medium priority — should pass (fixable in post)

- Stereo image stable, no hard panning, no sudden L/R movement
- No bright highs above ~10 kHz (apply a low-pass at 10 kHz if needed)
- No sub-bass rumble below ~40 Hz (high-pass at 40 Hz)
- Reverb tail audible — not a dry mix
- Loudness target around **-23 LUFS integrated** for sleep, **-18 LUFS** for meditation/study (quieter than typical streaming masters — sleep tracks must not be loud)
- No clipping, no peaks above -3 dBFS
- For Reiki / chakra: bowl strikes (if used) sit *behind* the music, not on top

## Low priority — preference (nice to have)

- 3–5 distinct voices audible in the mix (1 = thin, 8+ = busy)
- Tempo within ±5 BPM of target (matters less for non-pulsed ambient)
- Textural layer present at the requested level (background, never foreground)
- Reverb tail decays gradually — no abrupt cutoffs

---

## Quick listening protocol

1. Play the track on headphones at low volume. If it's *too quiet to hear*, that's a feature for sleep — don't crank it up. For meditation/study, it should be audible at low listening levels.
2. Listen to the first 30 seconds. Note: any genre-bleed warning signs (a beat sneaking in, a bright lead jumping out)?
3. Listen to a middle 30 seconds. Note: dynamic stability — is it staying within ±5 dB?
4. Listen to the last 10 seconds. Note: does the tail decay cleanly enough to crossfade or loop?
5. Switch to speakers. Re-check for any sub-bass rumble or harsh-high sibilance the headphones masked.

If the track passes this 90-second protocol, it's safe to publish. If not, regenerate or fix.

---

## When to fix in post vs. regenerate

**Regenerate when:**
- Vocals leaked through
- A drum or beat is present
- The genre is wrong (lo-fi beats, cinematic build, etc.)
- The key doesn't match the request
- There's a memorable hook that will wake light sleepers

**Fix in post when:**
- High frequencies are slightly too bright → low-pass at 10 kHz
- Sub-bass rumble → high-pass at 40 Hz
- Loudness is too high → re-master to target LUFS
- One audible seam at an extension join → 2-second crossfade in DAW or ffmpeg

Regenerating is cheap in Suno credits compared to fixing fundamental music problems in post.
