# Render Glitch Investigation — "audio glitch from 5 min, sustained"

> Active investigation. Three fixes (v1.2.1–v1.2.3) shipped to prod, symptom
> persists. This doc captures everything we know, what we've ruled out, the
> current hypothesis, and the exact diagnostic commands to run on the
> production Windows host to confirm or rule out the next theory.

---

## Status: blocked on production-host diagnostics

We need real `ffprobe` output from the actual deployed `final.mp4` to make
further progress. See §6 for the commands to run.

---

## 1 · Symptom (as reported by user)

- Long-form 3-hour 4K render. Template: `soundscape`. Templates with chunked
  render path.
- **First 5 minutes: clean.** Audio + video play correctly.
- **From 5:00 onward: sustained audio glitch.** Persists for the rest of the
  video. Not a per-seam click — a continuous wrong-sound throughout chunks 1–35.
- Symptom is **content-dependent**: broadband / ambient music
  (Rocky Tide Loop, Mellotron + Stream) is fine; tonal / melodic music
  (warm pad + drone + sparse koto, in this case) exposes the glitch clearly.
- Persists across v1.2.0 → v1.2.3, including this specific render which was
  produced entirely under v1.2.3 code (timing verified, see §3).

---

## 2 · What we've shipped already

| Tag | Fix | Targeted hypothesis | Did it resolve symptom? |
|-----|-----|---------------------|-------------------------|
| v1.2.1 | Video-only chunks (`include_audio=False`) + `render_full_audio_track` + `concat_video_and_mux_audio` | AAC priming gap at each chunk seam | No |
| v1.2.2 | Chunk filename suffix `.video.mp4` + orchestrator invalidates legacy chunks + concat-task ffprobe safety net | Stale `chunk.mp4` from before v1.2.1 being re-used | No |
| v1.2.3 | `_build_music_playlist_wav` replicates the playlist N times with `acrossfade` at every boundary instead of `aloop=-1` | Hard music loop boundary at track length | No |

Three failed fixes → architecture / diagnosis is wrong, not the next patch.

---

## 3 · Evidence gathered (via ai-media-console MCP — YoutubeVideo id 6)

`Bamboo Forest Wind · Japanese Study Music · 3 Hours` (status: `done`):

| Field | Value | Implication |
|-------|-------|-------------|
| `template_label` | `Soundscape` | Goes through chunked path |
| `target_duration_h` | `3.0` | 36 chunks × 300 s |
| `music_track_ids` | `[3]` — one track | Single-track music playlist |
| Music track #3 `duration_s` | **`600.032625`** | 10-min track, **NOT** 5 min |
| Music character | "warm analog pad + sustained D tonic drone + sparse koto plucks" | Tonal — would expose any loop seam |
| `sound_layers.background` | **NOT SET** | "background loop" hypothesis is dead |
| `sound_layers.midground` | pool `[12, 14]`, interval `12–30 s` | Random, not periodic |
| `sound_layers.random_sfx` | pool `[17, 20, 23]`, interval `60–100 s` | Random, not periodic |
| `black_from_seconds` | `1800` | Blackout at 30 min — not 5 |
| `render_parts[*].file_path` | all end with `chunk.video.mp4` | v1.2.2 invalidator worked |
| Chunk render window | `2026-05-20T22:17:05` to `22:51:24` UTC | After v1.2.3 deploy |
| v1.2.3 deploy completed | `2026-05-20T21:55:55` UTC (gh run) | Render ran under v1.2.3 |
| `output_path` | `/app/assets/output/youtube_6/final_v1779317488.mp4` | timestamp = `2026-05-20T23:31:28` UTC |

**Key conclusion from evidence:** This render WAS produced under v1.2.3 code.
The music track is 10 min — its loop boundary (if any) would be at min 10/20/30,
not min 5. There is **no periodic source at 5 min** anywhere in the audio pipeline.

---

## 4 · Hypotheses ruled out by evidence

Each of these *could* produce a glitch every 5 min in some scenario, but the
evidence above rules them out for this specific render:

- ❌ **AAC priming at chunk seams** — chunks are video-only (verified by
  filename suffix). Audio is one continuous AAC. There are no audio seams.
- ❌ **Background SFX hard loop** — `sound_layers.background` is not set for
  this video.
- ❌ **Music loop boundary at 5 min** — music is 10 min long. Any loop
  boundary would be at min 10/20/30, not 5.
- ❌ **Music loop boundary at 10 min reaching v1.2.3 path** — render ran
  under v1.2.3; `_build_music_playlist_wav` should have used the seamless
  acrossfade path. (If `_probe_duration` returned 0.0 we'd fall back to
  legacy aloop, in which case the seam would be at min 10. The user
  reports min 5, which doesn't match this.)
- ❌ **Foreground SFX schedule** — not configured for this video.
- ❌ **Per-boundary click (the v1.2.x family of bugs)** — symptom is
  *sustained*, not a brief click at each boundary.

---

## 5 · Current leading hypothesis

> **At 5:00 we cross the first chunk boundary in the concatenated video.
> Stream-copy concat of video-only MP4s is introducing a timing offset
> between audio and video that begins at 5:00 and stays constant for the
> rest of the file — producing a sustained "wrong audio" perception
> throughout chunks 1–35.**

Specifically the most likely mechanism:

1. Each chunk is encoded with `-t 300` plus encoder defaults (NVENC or libx264)
   that produce a `tkhd` / `mdhd` container duration which may be slightly
   off from 300.000 s (frame-quantization round-up; or non-zero start PTS
   from B-frame reorder offset / encoder priming).
2. `ffmpeg -f concat -c copy` does not normalize timestamps across the chunk
   boundary — it just appends chunks. Chunk 0 plays from 0 to its container
   duration; chunk 1's timestamps start at that container-duration value.
3. The audio (from `audio_full.m4a`) plays at its own clock, exactly
   10800.000 s long, starting at PTS 0.
4. From the player's point of view: by the time it's playing chunk 1, audio
   and video clocks have diverged by however many milliseconds chunk 0's
   container duration drifted from 300.000.
5. The divergence accumulates / stays constant for the rest of the file →
   sustained "audio doesn't match video" perception.

This matches the symptom shape (clean → break at first seam → sustained
break) better than any of the earlier hypotheses.

---

## 6 · Diagnostic commands — run these on the Windows render host

Goal: confirm or rule out the chunk-timing hypothesis with direct evidence.

### 6.1 — Inspect the final muxed output

```cmd
ffprobe -v error ^
  -show_entries stream=index,codec_type,codec_name,time_base,start_pts,start_time,duration,nb_frames ^
  -show_entries format=duration ^
  -of default=noprint_wrappers=1 ^
  "C:\render\output\youtube_6\final_v1779317488.mp4"
```

Look for:
- Two streams (one video + one audio).
- Both `start_time` should be `0.000000`. If video's is non-zero, that's a
  finding.
- Video `duration` vs audio `duration` — exact match or off by some ms?
- `nb_frames` for video should be `324000` (30 fps × 10800 s).

### 6.2 — Inspect chunk 0 and chunk 1 individually

```cmd
ffprobe -v error ^
  -show_entries stream=codec_name,time_base,start_pts,start_time,duration,nb_frames ^
  -show_entries format=duration ^
  -of default=noprint_wrappers=1 ^
  "C:\render\output\youtube_6\chunk_0\chunk.video.mp4"

ffprobe -v error ^
  -show_entries stream=codec_name,time_base,start_pts,start_time,duration,nb_frames ^
  -show_entries format=duration ^
  -of default=noprint_wrappers=1 ^
  "C:\render\output\youtube_6\chunk_1\chunk.video.mp4"
```

Look for:
- `format.duration` for each chunk. Is it **exactly** `300.000000`?
- `start_pts` and `start_time` — non-zero means the chunk has an edit list
  or encoder priming that concat-copy won't honor cleanly.
- `nb_frames` per chunk should be `9000` (30 fps × 300 s).

### 6.3 — Confirm the chunks really have no audio stream

```cmd
ffprobe -v error -select_streams a -show_entries stream=codec_type ^
  -of default=noprint_wrappers=1:nokey=1 ^
  "C:\render\output\youtube_6\chunk_0\chunk.video.mp4"
ffprobe -v error -select_streams a -show_entries stream=codec_type ^
  -of default=noprint_wrappers=1:nokey=1 ^
  "C:\render\output\youtube_6\chunk_5\chunk.video.mp4"
```

Both should print **nothing**. If anything is printed, the chunk has an
audio stream which would re-introduce the v1.2.0 era bug.

### 6.4 — Inspect the audio file the concat task built

The audio M4A is normally deleted after a successful concat (`audio_path.unlink`),
so it may not be on disk. If it is, probe it:

```cmd
ffprobe -v error ^
  -show_entries stream=codec_name,time_base,start_pts,start_time,duration,sample_rate,channels ^
  -show_entries format=duration ^
  -of default=noprint_wrappers=1 ^
  "C:\render\output\youtube_6\audio_full_v*.m4a"
```

If it isn't on disk, the next render of this video will regenerate it.

### 6.5 — Look for packet-level discontinuities at the chunk-0/chunk-1 seam in the final file

```cmd
ffprobe -v error -select_streams v -show_packets ^
  -show_entries packet=pts_time,dts_time,duration_time,flags ^
  -read_intervals 295%305 ^
  -of csv=p=0 ^
  "C:\render\output\youtube_6\final_v1779317488.mp4" > seam_video.csv

ffprobe -v error -select_streams a -show_packets ^
  -show_entries packet=pts_time,dts_time,duration_time,flags ^
  -read_intervals 295%305 ^
  -of csv=p=0 ^
  "C:\render\output\youtube_6\final_v1779317488.mp4" > seam_audio.csv
```

Open both CSVs and look at the packets between 299.9 s and 300.1 s:
- Video should have a steady stream with `pts_time` incrementing by ~0.0333.
  Look for a packet flagged `K` (keyframe) at the seam — expected.
- A gap or duplicated PTS in video packets across the seam is the smoking gun.
- Audio should have continuous AAC packets (~0.0232 s each, no flags).

### 6.6 — Verify which code is actually running in the celery-render container

```cmd
docker compose exec celery-render python -c "import pipeline.youtube_ffmpeg as y, inspect; src = inspect.getsource(y._build_music_playlist_wav); print('SEAMLESS' if 'seamless' in src.lower() or 'n_iters' in src else 'LEGACY ALOOP')"
```

If this prints `LEGACY ALOOP`, the container has stale code despite v1.2.3
deploy succeeding. Force a rebuild with no cache:

```cmd
docker compose pull
docker compose up -d --force-recreate celery-render
```

### 6.7 — Listen to the audio file alone (rules out video-side issue)

```cmd
ffmpeg -y -i "C:\render\output\youtube_6\final_v1779317488.mp4" -vn -c:a copy audio_only.m4a
```

Play `audio_only.m4a` in a media player. Does the glitch from 5:00 onward
still happen?

- **Yes, still glitchy:** the audio file itself is bad. The glitch is real
  audio, not A/V sync drift. We're chasing the wrong layer; the
  `render_full_audio_track` output has the problem.
- **No, plays clean:** the audio file is fine. The problem is A/V sync drift
  introduced by the video concat. Hypothesis §5 confirmed.

---

## 7 · Interpretation matrix → next action

| Diagnostic outcome | Diagnosis | Fix |
|---|---|---|
| §6.2 shows chunk 0 `format.duration` ≠ 300.000 OR `start_pts` ≠ 0 | Chunks are not frame-exact; concat introduces A/V drift at first seam | v1.2.4: force frame-exact chunks via `-frames:v $((target_dur*30))` + `-vf …,setpts=PTS-STARTPTS` instead of `-t target_dur`; reset PTS at chunk start; consider `-fflags +genpts` on the concat step |
| §6.3 shows ANY audio codec in a chunk | A chunk leaked audio despite `include_audio=False` | Find the code path that bypassed the flag and add `-an` in that branch |
| §6.6 prints `LEGACY ALOOP` | Worker still running v1.2.2 or earlier code | Force `--force-recreate` and `docker compose pull` (cache issue) |
| §6.7 audio-only file IS glitchy | Glitch is in `audio_full.m4a` itself | Investigate `render_full_audio_track` — log the actual ffmpeg command + intermediate WAV sizes, ffprobe both intermediates for periodic anomalies |
| §6.7 audio-only file is CLEAN | A/V sync drift from concat | Same as first row — fix chunk timing |
| §6.1 video / audio `start_time` differ by ~msec amount | Container edit list / TFDT mismatch between video and audio | Add `-output_ts_offset 0 -avoid_negative_ts make_zero` to the mux step; also force `-c:v copy -bsf:v "h264_mp4toannexb,h264_metadata=tick_rate=60"` if hardware encoder produced a weird timebase |
| §6.5 video packets show a duplicated/skipped PTS at the seam | Concat demuxer is not normalising timestamps | Use intermediate TS / MKV concat instead of MP4 concat, OR add `-fflags +genpts` to the mux, OR re-encode the seam region |
| All diagnostics look clean | Hypothesis §5 wrong; revisit | See §8 — propose the single-pass architecture instead |

---

## 8 · Fallback if diagnostics are inconclusive

Switch this video to the **single-pass render path** that user already
discussed:

- One ffmpeg invocation that renders full video + full audio together for
  10800 s, no chunking, no concat, no mux step.
- Zero chunk-boundary anything is possible because there are no chunks.
- Trade-off: no resume if the worker dies mid-render (1.5–3 h render).

Code-wise this is a small addition to the orchestrator — when
`template.slug == "soundscape"` and `skip_previews == True` (and maybe a new
`render_mode == "single_pass"` flag on the video), dispatch the existing
`render_youtube_video_task` instead of `render_youtube_chunked_orchestrator_task`.

This sidesteps the entire problem space these three fixes have been chasing.

---

## 9 · Code references (for in-flight investigation)

| Concern | File / line |
|---------|-------------|
| Chunked orchestrator + chord dispatch | `console/backend/tasks/youtube_render_task.py:533+` |
| Per-chunk video render (video-only path) | `console/backend/tasks/youtube_render_task.py:277+` calling `pipeline/youtube_ffmpeg.py:render_landscape` with `include_audio=False` |
| Concat + mux (where A/V join happens) | `pipeline/concat.py:concat_video_and_mux_audio` |
| Full-duration audio render | `pipeline/youtube_ffmpeg.py:render_full_audio_track` (~line 1194) |
| Music playlist (v1.2.3 seamless loop) | `pipeline/youtube_ffmpeg.py:_build_music_playlist_wav` (~line 301) |
| Sound layers | `pipeline/youtube_ffmpeg.py:_build_sound_layers_wav` (~line 463) |
| SFX schedule (deterministic) | `pipeline/sfx_scheduler.py:schedule_sfx_layer` |
| Encoder params keyed off FULL duration | `pipeline/youtube_ffmpeg.py:render_landscape` — preset selection block, around the `_nvenc_available()` check |

---

## 10 · How to update this doc as we learn more

After running the diagnostics on the production host:

1. Append the actual `ffprobe` output to a new `## Evidence — round 2` section.
2. Mark the rows in §7 that the evidence confirmed/refuted.
3. If §5 is confirmed, document the v1.2.4 fix design before coding.
4. If §5 is refuted, re-enter §1 of the systematic-debugging skill and form
   a new hypothesis from the new evidence.

This file is meant to survive across sessions / contributors — every fact
should be falsifiable, every claim should cite either the MCP data, the
git history, or a specific ffprobe output.
