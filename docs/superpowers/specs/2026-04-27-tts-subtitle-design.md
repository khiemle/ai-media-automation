# TTS Fix + Word-by-Word Subtitle System — Design Spec

**Date:** 2026-04-27
**Status:** Approved

---

## Problem

1. **ElevenLabs silent audio**: `generate_tts_elevenlabs()` requests `output_format="pcm_44100"` and interprets the response bytes directly with `np.frombuffer(..., dtype=np.int16)`. When the SDK or model returns bytes that are not raw 16-bit signed PCM (e.g. a container format or MP3), the frombuffer call produces silence or garbage audio with no exception raised.

2. **No subtitle system**: Videos have no timed subtitles. The existing `caption_gen.py` (Whisper → SRT) is not wired into the composition pipeline. The `overlay_builder.py` renders static per-scene PNGs — not timed word-level text.

---

## Design

### Overview

- Fix ElevenLabs audio by switching to the `convert_with_timestamps()` SDK endpoint, which returns base64 MP3 + character-level word alignment. MP3 is decoded to WAV via ffmpeg.
- For Kokoro TTS, obtain word timing post-hoc via faster-whisper (`extract_word_timing()`).
- A new `pipeline/subtitle_builder.py` converts word timing lists into an ASS subtitle file with one of five built-in visual styles.
- The composer wires timing data through `_process_scene()` → `_assemble()` → `subtitles.ass`.
- The renderer auto-detects `subtitles.ass` in the output directory and burns it in via ffmpeg.
- The script editor gets a `subtitle_style` dropdown stored in `script_json.video.subtitle_style`.

---

### 1. `pipeline/elevenlabs_tts.py`

#### Fix silent audio (non-timing path)

Replace `output_format="pcm_44100"` + raw numpy decode with MP3 + ffmpeg decode:

```python
audio_gen = client.text_to_speech.convert(
    voice_id=voice_id, text=text, model_id=model_id,
    output_format="mp3_44100_128",
    voice_settings=VoiceSettings(...),
)
mp3_bytes = b"".join(audio_gen)
_mp3_to_wav(mp3_bytes, output_path)
```

`_mp3_to_wav(mp3_bytes, output_path)` — writes bytes to a temp `.mp3` file, converts to WAV via `ffmpeg -i tmp.mp3 output.wav`, then deletes the temp file.

#### New: `generate_tts_elevenlabs_with_timing(text, voice_id, speed, output_path) -> tuple[Path, list[dict]]`

Uses `convert_with_timestamps()` — one API call returns both audio and alignment:

```python
response = client.text_to_speech.convert_with_timestamps(
    voice_id=voice_id,
    text=text,
    model_id=model_id,
)
mp3_bytes = base64.b64decode(response.audio_base64)
_mp3_to_wav(mp3_bytes, output_path)

words = _chars_to_words(
    response.alignment.characters,
    response.alignment.character_start_times_seconds,
    response.alignment.character_end_times_seconds,
)
return output_path, words
```

`_chars_to_words(chars, starts, ends) -> list[dict]` — reconstructs word boundaries from character timing:
- Iterates characters; accumulates non-space characters into a word buffer
- On space: flushes buffer as `{"word": str, "start": float, "end": float}`
- Last word flushed at end of iteration

#### Signature unchanged

`generate_tts_elevenlabs(text, voice_id, speed, output_path) -> Path` keeps its signature. Internally uses MP3 path (silent audio fix applied).

---

### 2. `pipeline/caption_gen.py`

Add `extract_word_timing(audio_path, language="vi") -> list[dict]`:

```python
def extract_word_timing(audio_path, language="vi"):
    model = _get_model()
    if model is None:
        return []
    segments, _ = model.transcribe(
        str(audio_path), language=language, word_timestamps=True
    )
    return [
        {"word": w.word.strip(), "start": w.start, "end": w.end}
        for seg in segments
        for w in (seg.words or [])
        if w.word.strip()
    ]
```

No new dependencies — reuses the already-loaded faster-whisper model singleton.

---

### 3. `pipeline/tts_router.py`

Add `generate_tts_with_timing(text, voice_id, speed, language, output_path, tts_service="") -> tuple[Path, list[dict]]`:

```python
def generate_tts_with_timing(text, voice_id, speed, language, output_path, tts_service=""):
    # Resolve engine (same logic as generate_tts)
    if tts_service == "kokoro" or not _use_elevenlabs(tts_service, language):
        audio = _kokoro_generate(text, voice_id, speed, output_path)
        lang_code = "vi" if language == "vietnamese" else "en"
        from pipeline.caption_gen import extract_word_timing
        return audio, extract_word_timing(audio, lang_code)

    # ElevenLabs path
    cfg = get_config()
    voice = _resolve_elevenlabs_voice(cfg, voice_id, tts_service, language)
    from pipeline.elevenlabs_tts import generate_tts_elevenlabs_with_timing
    return generate_tts_elevenlabs_with_timing(text, voice, speed, output_path)
```

`_use_elevenlabs()` and `_resolve_elevenlabs_voice()` are extracted from the existing `generate_tts()` body to avoid duplication.

---

### 4. `pipeline/subtitle_builder.py` (new file)

#### Style definitions

```python
SUBTITLE_STYLES = {
    "tiktok_yellow": {
        "font": "Arial Black", "font_size": 90,
        "primary_color": "&H0000FFFF",   # yellow (ASS ABGR)
        "outline_color": "&H00000000",   # black
        "outline_width": 5, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,  # bottom-center, 400px from bottom
        "words_per_entry": 1,
    },
    "tiktok_white": {
        "font": "Arial Black", "font_size": 90,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 5, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "bold_orange": {
        "font": "Arial Black", "font_size": 80,
        "primary_color": "&H0000A5FF",   # orange
        "outline_color": "&H00000000",
        "outline_width": 4, "shadow": 0,
        "bold": True, "uppercase": True,
        "alignment": 2, "margin_v": 400,
        "words_per_entry": 1,
    },
    "caption_dark": {
        "font": "Arial", "font_size": 50,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 2, "shadow": 1,
        "bold": False, "uppercase": False,
        "alignment": 2, "margin_v": 80,
        "words_per_entry": 4,
    },
    "minimal": {
        "font": "Arial", "font_size": 40,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 1, "shadow": 1,
        "bold": False, "uppercase": False,
        "alignment": 2, "margin_v": 120,
        "words_per_entry": 4,
    },
}
```

ASS color format note: `&HAABBGGRR` where AA=alpha (00=opaque), and the remaining bytes are Blue, Green, Red. Yellow (R=255,G=255,B=0) → `&H0000FFFF`.

#### `build_ass(scene_word_timings, output_path, style_name) -> Path`

```
scene_word_timings: list[tuple[float, list[dict]]]
    Each tuple: (scene_start_offset_seconds, word_list)
    word_list: [{"word": str, "start": float, "end": float}, ...]
               where start/end are relative to the scene start
output_path: path to write the .ass file
style_name: key in SUBTITLE_STYLES
```

Steps:
1. Look up style config (fall back to `"tiktok_yellow"` if unknown)
2. Write ASS `[Script Info]` header with `PlayResX: 1080`, `PlayResY: 1920`
3. Write `[V4+ Styles]` section with one `Style:` line for the chosen style
4. For each scene, offset each word's `start`/`end` by `scene_start_offset`
5. Group words into chunks of `words_per_entry`
6. Apply uppercase transform if `style["uppercase"]`
7. Write one `Dialogue:` line per chunk with ASS timecode format `H:MM:SS.cc`
8. Return `Path(output_path)`

If `scene_word_timings` is empty or all word lists are empty, write an empty ASS file (returns path, renderer skips empty files).

#### `_fmt_ass_time(seconds: float) -> str`

```python
# Returns e.g. "0:00:01.45" (ASS format: H:MM:SS.cc where cc = centiseconds)
```

---

### 5. `pipeline/composer.py`

#### `_process_scene()` change

```python
subtitle_style = video_cfg.get("subtitle_style") or ""
if subtitle_style:
    from pipeline.tts_router import generate_tts_with_timing
    audio_path, word_timing = generate_tts_with_timing(
        text=scene.get("narration", ""),
        voice_id=video_cfg.get("voice", ""),
        speed=float(video_cfg.get("voice_speed", 1.1)),
        language=meta.get("language", "vietnamese"),
        output_path=str(audio_path),
        tts_service=video_cfg.get("tts_service", ""),
    )
else:
    # existing generate_tts() call (unchanged)
    word_timing = None
```

`scene_assets` dict gets `"word_timing": list | None`.

#### `_assemble()` change

After all scenes are composited, before writing `raw_video.mp4`:

```python
subtitle_style = video_cfg.get("subtitle_style") or ""
if subtitle_style:
    from pipeline.subtitle_builder import build_ass
    # Compute cumulative scene start offsets
    scene_offsets = []
    offset = 0.0
    for idx in range(len(scenes)):
        scene_offsets.append(offset)
        offset += scene_assets.get(idx, {}).get("duration", 5)

    scene_word_timings = [
        (scene_offsets[idx], scene_assets[idx].get("word_timing") or [])
        for idx in range(len(scenes))
    ]
    ass_path = output_path.parent / "subtitles.ass"
    build_ass(scene_word_timings, ass_path, subtitle_style)
```

---

### 6. `pipeline/renderer.py`

`render_final()` auto-detects `subtitles.ass` in the same directory as `raw_video_path`:

```python
# After existing srt_path handling:
ass_candidate = Path(raw_path_obj).parent / "subtitles.ass"
subtitle_file = None
if srt_path and Path(srt_path).exists() and Path(srt_path).stat().st_size > 0:
    subtitle_file = Path(srt_path)
elif ass_candidate.exists() and ass_candidate.stat().st_size > 0:
    subtitle_file = ass_candidate

if subtitle_file and _check_subtitles_filter():
    escaped = subtitle_file.resolve().as_posix().replace(":", "\\:")
    vf_filters.append(f"subtitles=filename='{escaped}'")
```

ffmpeg's `subtitles` filter auto-detects ASS vs SRT format from the file extension and content. No codec change needed.

---

### 7. Frontend — Script editor

Add a `subtitle_style` select field to the video config section of the script editor, near the TTS service and voice fields:

```
Subtitle Style:  [None ▼]
                  TikTok Yellow
                  TikTok White
                  Bold Orange
                  Caption Dark
                  Minimal
```

Values map to: `null`, `"tiktok_yellow"`, `"tiktok_white"`, `"bold_orange"`, `"caption_dark"`, `"minimal"`.

Saved to `script_json.video.subtitle_style`. When `null`, no subtitle file is generated and the renderer does nothing subtitle-related.

---

## Files Changed

| File | Action | Change |
|---|---|---|
| `pipeline/elevenlabs_tts.py` | Modify | Fix silent audio (MP3+ffmpeg); add `generate_tts_elevenlabs_with_timing()`, `_mp3_to_wav()`, `_chars_to_words()` |
| `pipeline/caption_gen.py` | Modify | Add `extract_word_timing()` |
| `pipeline/tts_router.py` | Modify | Add `generate_tts_with_timing()`; extract `_use_elevenlabs()` and `_resolve_elevenlabs_voice()` helpers |
| `pipeline/subtitle_builder.py` | Create | `SUBTITLE_STYLES`, `build_ass()`, `_fmt_ass_time()` |
| `pipeline/composer.py` | Modify | `_process_scene()` calls `generate_tts_with_timing()` when subtitle_style set; `_assemble()` calls `build_ass()` |
| `pipeline/renderer.py` | Modify | Auto-detect `subtitles.ass`; unify subtitle file handling |
| Frontend script editor | Modify | Add subtitle_style dropdown |

No new pip dependencies. No DB changes. No new API endpoints.
