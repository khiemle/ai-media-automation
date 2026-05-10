# Make-a-YouTube-Video Workflow Prompt

Drive the full create-render-upload pipeline of a YouTube video using the
`ai-media-console` MCP server, given three JSON files plus a local visual
video file and a local thumbnail source image.

---

## Inputs

Three JSON files plus two media files. All paths below are relative to the
working folder (e.g. `working/<slug>/`):

```
working/<slug>/
├── seo.json           # SEO + thumbnail + channel targeting
├── visual.json        # path to background video + visual config
├── suno.json          # music generation parameters
├── visual.mp4         # the background video to upload
└── thumbnail.jpg      # source image for the thumbnail
```

### `seo.json`
```jsonc
{
  "title": "Forest Rain ASMR | 8 Hours of Deep Sleep",
  "seo_title": "Forest Rain ASMR | 8 Hours of Deep Sleep",
  "seo_description": "8 hours of forest rain for deep sleep...",
  "seo_tags": ["asmr", "rain", "sleep", "forest"],
  "thumbnail_text": "8 HOURS · DEEP SLEEP",
  "thumbnail_image_path": "thumbnail.jpg",   // relative to this seo.json
  "channel_ids": [1],                         // YouTube channels to upload to
  "target_duration_h": 8.0,
  "output_quality": "1080p"
}
```

### `visual.json`
```jsonc
{
  "file_path": "visual.mp4",       // relative to this visual.json
  "title": "Forest Rain Loop 4K",
  "niche": "forest",
  "theme": "forest",
  "keywords": ["forest", "rain", "loop"],
  "visual_clip_durations_s": [12.0, 8.0, 16.0]
}
```

### `suno.json`
```jsonc
{
  "idea": "morning breakfast chill with jazz",
  "niches": ["lofi", "morning"],
  "moods": ["chill", "warm"],
  "genres": ["jazz", "lo-fi"],
  "provider": "lyria-clip",        // sunoapi | lyria-clip | lyria-pro
  "is_vocal": false,
  "title": "Morning Jazz Chill"
}
```

---

## The prompt

Copy from here to the end of the file and paste into Claude Code, replacing
`<slug>` with the actual subdirectory name:

````
You are creating a YouTube video end-to-end via the `ai-media-console` MCP server.

Working folder: working/<slug>/

Read these three JSON files first:
- working/<slug>/seo.json
- working/<slug>/visual.json
- working/<slug>/suno.json

Resolve every relative path inside those JSON files relative to the JSON file's
own folder. So `visual.json:file_path = "visual.mp4"` means
`working/<slug>/visual.mp4`.

## Decision points where you MUST ask me

Whenever you need input or a decision, use the AskUserQuestion tool. Specifically:

- Before calling `youtube_video(action="render_final", ...)`: ask me to confirm.
  Show me the video_id, the title, and that audio + video previews were approved.
- Before calling `upload(action="upload_one", ...)`: ask me to confirm.
  Show me the video_id, the channel_ids it will publish to, and the final output_path.
- If any JSON field is missing or ambiguous (e.g. `channel_ids` not present, or
  `provider` is not one of `sunoapi`/`lyria-clip`/`lyria-pro`): ask me to choose.
- If a tool returns an error envelope (`ok=false`): show me the full error
  envelope and ask whether to retry, skip, or abort.
- Anywhere else you'd otherwise have to guess: ask me.

## Steps — execute in order

### 1. Upload the visual asset (background video)

Call:
```
visual_asset(
  action="upload",
  file_path=<absolute path to visual.json:file_path>,
  title=visual.json:title,
  niche=visual.json:niche,
  keywords=visual.json:keywords,
  asset_type="video",
  confirm=true
)
```
Capture the new `asset_id`. Save it as `visual_asset_id` for later steps.

### 2. Generate music from suno.json

Call:
```
music(
  action="generate",
  idea=suno.json:idea,
  niches=suno.json:niches,
  moods=suno.json:moods,
  genres=suno.json:genres,
  provider=suno.json:provider,
  is_vocal=suno.json:is_vocal,
  title=suno.json:title,
  confirm=true
)
```
Capture the returned `task_id`. Then poll:
```
task_status(task_id=<task_id>)
```
Every 30 seconds. Loop until `status` is `SUCCESS` or `FAILURE`. On SUCCESS,
capture the resulting `track_id` from `result`. On FAILURE, show me the
error and ask how to proceed.

Maximum wait: 15 minutes. If still PROGRESS after that, ask me whether to
keep waiting or abort.

### 3. Create the YouTube video record

Call:
```
youtube_video(
  action="create",
  fields={
    "title": seo.json:title,
    "theme": visual.json:theme,
    "music_track_id": <track_id from step 2>,
    "visual_asset_id": <visual_asset_id from step 1>,
    "thumbnail_text": seo.json:thumbnail_text,
    "seo_title": seo.json:seo_title,
    "seo_description": seo.json:seo_description,
    "seo_tags": seo.json:seo_tags,
    "target_duration_h": seo.json:target_duration_h,
    "output_quality": seo.json:output_quality,
    "visual_clip_durations_s": visual.json:visual_clip_durations_s
  },
  confirm=true
)
```
Capture the returned `video_id`.

### 4. Upload the thumbnail source image

Call:
```
youtube_thumbnail(
  action="upload_image",
  video_id=<video_id>,
  file_path=<absolute path to seo.json:thumbnail_image_path>,
  confirm=true
)
```

### 5. Generate the final thumbnail with text overlay

Call:
```
youtube_thumbnail(
  action="generate_with_text",
  video_id=<video_id>,
  text=seo.json:thumbnail_text,
  confirm=true
)
```
This is synchronous — no task polling.

### 6. Render the audio preview, then approve

```
youtube_video(action="render_audio_preview", video_id=<video_id>, confirm=true)
```
Poll task_status until SUCCESS. Then:
```
youtube_video(action="approve_audio_preview", video_id=<video_id>, confirm=true)
```

If audio preview FAILS, show the error and ask how to proceed.

### 7. Render the video preview, then approve

```
youtube_video(action="render_video_preview", video_id=<video_id>, confirm=true)
```
Poll task_status until SUCCESS. Then:
```
youtube_video(action="approve_video_preview", video_id=<video_id>, confirm=true)
```

### 8. CONFIRM with me before render_final

Use AskUserQuestion. Show:
- video_id
- title
- That both audio and video previews have been approved

Wait for my approval. If I say no, stop and report.

### 9. Render final

```
youtube_video(action="render_final", video_id=<video_id>, confirm=true)
```
Poll task_status until SUCCESS. Capture `output_path` from `result`.

### 10. CONFIRM with me before upload

Use AskUserQuestion. Show:
- video_id
- title
- output_path
- channel_ids it will publish to (from seo.json:channel_ids)

Wait for my approval. If I say no, stop and report.

### 11. Set upload targets

```
upload(
  action="set_targets",
  video_id=<video_id>,
  channel_ids=seo.json:channel_ids,
  confirm=true
)
```

### 12. Upload to YouTube

```
upload(
  action="upload_one",
  video_id=<video_id>,
  confirm=true,
  confirm_id=<same as video_id>
)
```
Poll task_status until SUCCESS. Capture the result (URL, etc.).

## Final report

When all 12 steps succeed, summarize:
- video_id
- final output_path
- upload task_id
- the YouTube URL(s) once `task_status` returns SUCCESS for the upload

## Hard rules

- Do not skip any step. The render pipeline strictly requires
  audio_preview → approve → video_preview → approve → final.
- Do not retry destructive operations automatically. If a render or upload
  fails, ask me first.
- Do not invent field values. If a field isn't in the JSON files, ask.
- For each polling loop, after 15 minutes of PROGRESS without progress,
  ask me whether to keep waiting.
- Do not call any tool with `confirm=false` for write operations — that
  just returns the intent envelope without doing anything; always pass
  `confirm=true` when you actually want to execute.
- Do not move on past a tool result with `ok=false`. Show me the error
  envelope and ask.
````

---

## Notes

- The MCP tool `visual_asset(action="upload")` uses multipart upload — the
  agent reads the local file and the MCP client streams it to the backend.
  Same for `youtube_thumbnail(action="upload_image")`.
- The `confirm_id` requirement on `upload_one` is the destructive-op safety
  guard: caller has to repeat the resource ID. The prompt above tells the
  agent to set `confirm_id` equal to `video_id`.
- `youtube_thumbnail(action="generate_with_text")` is synchronous — it
  returns the thumbnail URL directly with no `task_id`. Don't poll it.
- The `working/<slug>/` convention matches the existing folders
  (`beach-sunset-ambience`, `rainy-tokyo-night`, `thunderstorm-deep-sleep`).
  Drop your three JSON files plus `visual.mp4` and `thumbnail.jpg` into a
  new subfolder, then point the agent at it.
