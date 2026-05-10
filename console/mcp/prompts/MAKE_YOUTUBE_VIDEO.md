# Make-a-YouTube-Video Workflow Prompt

Drive the full create-render-upload pipeline of a YouTube video using the
`ai-media-console` MCP server. This workflow replicates the logic of the
**Import From Template** modal in the Management Console frontend
(`YouTubeVideosPage.jsx → ImportFromTemplateModal`).

---

## Working-folder convention

```
working/<slug>/
├── json/
│   ├── *music.json    (or *suno.json — filename suffix varies)
│   ├── *visual.json
│   └── *seo.json
└── (no media files pre-staged — agent asks for paths at runtime)
```

All three JSON files are independently optional. The agent discovers them
by glob pattern, disambiguates via `AskUserQuestion` when multiple or zero
matches, and asks the user for `visual.mp4` and `thumbnail.jpg` paths at
runtime via `AskUserQuestion`.

---

## JSON schemas

### `*music.json` — two valid forms

**Form A — `composer` (preferred; drives ElevenLabs prompt)**

```json
{
  "meta": { "title": "Forest Rain Theme" },
  "composer": {
    "function_tag": "ambient pad",
    "key_mode": "C major",
    "bpm": 60,
    "primary_instrument": "rhodes piano",
    "harmonic_bed": "warm strings",
    "textural_layer": "rain noise",
    "dynamic_rule": "gentle swell",
    "reverb": "long hall",
    "timbre": "soft, intimate"
  }
}
```

Validation rule: `parsed.composer` OR `parsed.suno.style_of_music` must exist.
If neither is present, the JSON is invalid — ask the user.

**Form B — `suno`**

```json
{
  "meta": { "title": "Lo-fi Forest Chill" },
  "suno": { "style_of_music": "lo-fi jazz, chill, soft piano, no vocals" }
}
```

---

### `*visual.json` — all four layers

Required field: `sfx` (top-level key). Everything else is optional but
the schema below is what the parser expects.

```json
{
  "meta": {
    "theme": "forest-rain",
    "video_length_hours": 8.0,
    "title": "Forest Rain ASMR | 8 Hours",
    "use_case": "deep sleep",
    "channel": "ambient asmr"
  },
  "scene": {
    "pov": "third-person, looking through a forest canopy",
    "time_of_day": "night",
    "weather": "heavy rain",
    "atmosphere": "peaceful, dark"
  },
  "sfx": {
    "background": {
      "name_en": "Steady Forest Rain",
      "name_vi": "Mưa rừng đều",
      "english_prompt": "constant heavy rain on leaves, deep low rumble"
    },
    "midground": [
      {
        "name_en": "Distant Thunder",
        "english_prompt": "soft distant thunder rolling slowly",
        "interval_seconds": "60-120"
      }
    ],
    "foreground": [
      {
        "name_en": "Owl Hoot",
        "english_prompt": "single owl hoot, close, clear",
        "interval_seconds": "180-300"
      }
    ],
    "random_sfx": {
      "trigger_interval_seconds": "60-100",
      "items": [
        {
          "name_en": "Rustling Leaves",
          "english_prompt": "leaves rustling in a gentle breeze"
        },
        {
          "name_en": "Skip",
          "english_prompt": "do not generate",
          "automation_only": true
        }
      ]
    }
  },
  "runway": {
    "prompt": "slow drift through rainy forest at night, cinematic, shallow depth"
  },
  "midjourney": {
    "full_prompt": "rainy forest at night, canopy view, moonlight through leaves --ar 16:9 --v 6"
  }
}
```

`automation_only: true` items are skipped during generation (no asset is
created) but their definition is preserved for runtime automation logic.

---

### `*seo.json` — validation requires `titles.recommended` OR `description.full`

```json
{
  "meta": { "video_length_hours": 8.0 },
  "titles": {
    "recommended": "Forest Rain ASMR | 8 Hours of Deep Sleep",
    "alternatives": [
      "8 Hours Forest Rain for Deep Sleep",
      "Heavy Rain Forest ASMR | Sleep & Relaxation"
    ]
  },
  "description": {
    "full": "8 hours of forest rain for deep sleep, study, and meditation. Soothing heavy rain on leaves with distant thunder and owls."
  },
  "tags": {
    "all": ["asmr", "rain", "sleep", "forest", "8 hours", "deep sleep", "nature sounds"]
  }
}
```

---

## The prompt

Copy from here to the end of the file and paste into Claude Code, replacing
`<slug>` with the actual subdirectory name:

````
You are creating a YouTube video end-to-end via the `ai-media-console` MCP server.

Working folder: working/<slug>/

This workflow mirrors the logic of the Import From Template modal in the
Management Console. Follow every step exactly. Do not skip, reorder, or
auto-complete any step that requires user input.

---

## Decision-point rules (read first)

- Whenever any JSON field is missing or ambiguous, use `AskUserQuestion`.
- Before calling `youtube_video(action="render_final", ...)`: use `AskUserQuestion` to confirm.
- Before calling `upload(action="upload_one", ...)`: use `AskUserQuestion` to confirm.
- If a tool returns `ok=false`: show the full error envelope and use `AskUserQuestion` to ask whether to retry, skip, or abort. Do not proceed past an error automatically.
- Anywhere you would otherwise have to guess a value: use `AskUserQuestion`.

---

## Step 1 — Discover and read JSON files

Use glob patterns to find each file:

- Music JSON: `working/<slug>/json/*music.json` OR `working/<slug>/json/*suno.json`
- Visual JSON:   `working/<slug>/json/*visual.json`
- SEO JSON:   `working/<slug>/json/*seo.json`

For each pattern:
- If **zero matches**: the file is absent. Proceed without it (all three are optional).
- If **one match**: read and parse it.
- If **multiple matches**: use `AskUserQuestion` to ask the user which file to use.

If zero matches for ALL THREE patterns, use `AskUserQuestion` to ask the user
to provide file paths. Do not abort silently.

### Validate each JSON after reading

**Music JSON validation** — must satisfy: `parsed.composer` exists OR `parsed.suno.style_of_music` exists.
If neither is present, use `AskUserQuestion` to report the problem and ask how to proceed.

**Visual JSON validation** — must have a top-level `sfx` key.
If missing, use `AskUserQuestion`.

**SEO JSON validation** — must have `titles.recommended` OR `description.full`.
If neither is present, use `AskUserQuestion`.

---

## Step 2 — Ask user for visual.mp4 and thumbnail.jpg paths

Use `AskUserQuestion` to ask:

> "Please provide:
> 1. Absolute path (or path relative to working/<slug>/) to the background video file (visual.mp4 or similar).
> 2. Absolute path (or path relative to working/<slug>/) to the thumbnail source image (thumbnail.jpg or similar)."

Resolve relative paths relative to `working/<slug>/`. Record both as
`visual_path` and `thumbnail_path`.

---

## Step 3 — Upload the visual asset

Call:
```
visual_asset(
  action="upload",
  file_path=<absolute visual_path>,
  title=<visual.json:meta.title if present, else ask user>,
  niche=<visual.json:meta.theme if present, else ask user>,
  keywords=<list from visual.json:meta.theme split by "-" if present, else []>,
  asset_type="video",
  confirm=true
)
```

Capture the returned `asset_id` as `visual_asset_id`.

---

## Step 4 — Generate music via ElevenLabs (if music.json is present)

Skip this step entirely if no music JSON was found.

### 4a. Build the composition prompt

Replicate `buildMusicPrompt()` from the frontend exactly:

If `parsed.composer` exists:
- Concatenate these fields with `, ` (omit any that are null/undefined):
  `function_tag`, `key_mode`, `<bpm> BPM` (only if bpm is set), `primary_instrument`,
  `harmonic_bed`, `textural_layer`, `dynamic_rule`, `reverb`, `timbre`,
  then always append the literals `instrumental` and `no vocals`.
- Example result: `"ambient pad, C major, 60 BPM, rhodes piano, warm strings, rain noise, gentle swell, long hall, soft intimate, instrumental, no vocals"`

If `parsed.composer` is absent, use `parsed.suno.style_of_music` as-is.

### 4b. Generate composition plan

Call:
```
music(
  action="elevenlabs_plan",
  input=<composition prompt from 4a>,
  music_length_ms=600000
)
```

This is read-only (no confirm needed). On success, capture `data.composition_plan`.
If `ok=false`, show the error and use `AskUserQuestion`.

### 4c. Compose the music track

Call:
```
music(
  action="elevenlabs_compose",
  composition_plan=<composition_plan from 4b>,
  title=<music.json:meta.title, or "Music Track" if absent>,
  niches=[],
  moods=[],
  genres=[],
  confirm=true
)
```

Capture the returned `task_id`.

**Important:** The MCP wrapper does NOT return `track_id` directly.
You must poll `task_status` and extract `track_id` from the task result.

### 4d. Poll until music is ready

```
task_status(task_id=<task_id>)
```

Poll every 10 seconds. The task result states are: `PENDING`, `PROGRESS`,
`SUCCESS`, `FAILURE`.

- On `SUCCESS`: capture `result.track_id` as `music_track_id`. This is the
  integer ID of the saved music track.
- On `FAILURE`: show the error and use `AskUserQuestion` to ask whether to
  retry (go back to 4c), skip music entirely, or abort.
- After 15 minutes of non-SUCCESS: use `AskUserQuestion` to ask whether to
  keep waiting or abort.

---

## Step 5 — Generate SFX assets (if visual.json is present)

Skip this step entirely if no Visual JSON was found.

### 5a. Flatten SFX items from visual.json

Replicate `collectSfxItems()` exactly. Process in this order:

**Background** (single object, not an array):
```
If sfx.background exists:
  item = {
    layer: "background",
    title: sfx.background.name_en OR sfx.background.name_vi OR "Background Ambience",
    prompt: sfx.background.english_prompt,
    loop: true,
    automation_only: false,
    interval_seconds: null,
    trigger_interval: null
  }
```

**Midground** (array):
```
For each item in sfx.midground (or [] if absent):
  item = {
    layer: "midground",
    title: item.name_en OR item.name_vi OR first 60 chars of item.english_prompt,
    prompt: item.english_prompt,
    loop: false,
    automation_only: false,
    interval_seconds: item.interval_seconds OR null,
    trigger_interval: null
  }
```

**Foreground** (array):
```
For each item in sfx.foreground (or [] if absent):
  item = {
    layer: "foreground",
    title: item.name_en OR item.name_vi OR first 60 chars of item.english_prompt,
    prompt: item.english_prompt,
    loop: false,
    automation_only: false,
    interval_seconds: item.interval_seconds OR null,
    trigger_interval: null
  }
```

**Random SFX** (object with `items` array):
```
trigger_interval = sfx.random_sfx.trigger_interval_seconds OR "60-100"
For each item in sfx.random_sfx.items (or [] if absent):
  item = {
    layer: "random_sfx",
    title: item.name_en OR item.name_vi OR first 60 chars of item.english_prompt OR "SFX",
    prompt: item.english_prompt OR "",
    loop: false,
    automation_only: !!item.automation_only,
    interval_seconds: null,
    trigger_interval: <trigger_interval from above>
  }
```

### 5b. Generate each non-automation-only item

For each item where `automation_only` is false (and `prompt` is non-empty):

Call:
```
sfx(
  action="generate",
  text=<item.prompt>,
  loop=<item.loop>,
  title=<item.title>,
  confirm=true
)
```

This is **synchronous** — no task polling. On success, `data` is the full SFX
asset row. Capture `data.id` as the asset ID for this item.

Items with `automation_only: true` are skipped entirely. Do not call
`sfx(action="generate")` for them. But record that they exist (for the
sound_layers automation pool entry — see 5c).

If any item fails (`ok=false`): show the error and use `AskUserQuestion`
to ask whether to retry, skip this item, or abort.

Do not invent prompts. Generate exactly the items defined in visual.json,
using `english_prompt` verbatim.

### 5c. Assemble sound_layers

Replicate `assembleSoundLayers()` exactly. After all items are generated,
build the `sound_layers` dict as follows:

**Interval parsing rule** — for any `interval_seconds` string like `"60-120"`:
- Split on `-`, parse both parts as integers → `{min: 60, max: 120}`.
- If the string is missing, malformed, or not two valid integers: use `{min: 10, max: 25}`.
- Exception: for foreground items with no interval, use `{min: 45, max: 60}`.

**Background** (if a background item was generated):
```json
"background": {
  "asset_id": <bg_asset_id as integer>,
  "volume": 0.4
}
```

**Midground** (if any midground items were generated):
- Collect all generated midground asset IDs into `pool`.
- Parse interval_seconds for each item that has one; take `min` of all mins, `max` of all maxes.
- If no item has interval_seconds, default to `{min: 10, max: 25}`.
```json
"midground": {
  "pool": [<asset_ids>],
  "volume": 0.5,
  "interval_min_s": <minimum of all parsed mins>,
  "interval_max_s": <maximum of all parsed maxes>
}
```

**Foreground** (if any foreground items were generated):
- Same structure as midground.
- If no item has interval_seconds, default to `{min: 45, max: 60}`.
```json
"foreground": {
  "pool": [<asset_ids>],
  "volume": 0.7,
  "interval_min_s": <minimum of all parsed mins>,
  "interval_max_s": <maximum of all parsed maxes>
}
```

**Random SFX** (if any random_sfx items were generated):
- Use `trigger_interval` from the first random_sfx item (they all share the same value).
- Parse it using the interval parsing rule above; default `{min: 60, max: 100}` if missing.
- Include only items where an asset was actually generated (not automation_only).
```json
"random_sfx": {
  "pool": [<asset_ids>],
  "volume": 0.6,
  "interval_min_s": <parsed min>,
  "interval_max_s": <parsed max>
}
```

Omit any layer that has zero generated items (don't include empty `pool: []` entries).

Record the assembled dict as `sound_layers`.

---

## Step 6 — Extract SEO data

Follow this fallback chain exactly (mirrors the frontend):

**If seo.json is present** — use `extractSeoFromSeoJson()` mapping:
```
seo_title         = seoJson.titles.recommended  (or null)
seo_description   = seoJson.description.full     (or null)
seo_tags          = seoJson.tags.all joined with ", "  (or null if absent/empty)
target_duration_h = seoJson.meta.video_length_hours   (or null)
theme             = null  (seo.json does not carry theme)
```

**Else if visual.json is present** — use `extractSeoFromSfxJson()` mapping:
```
theme             = visualJson.meta.theme  (or null)
target_duration_h = visualJson.meta.video_length_hours  (or null)
seo_title         = visualJson.meta.title  (or null)

seo_description: Join non-empty parts with ". ":
  - visualJson.scene.pov
  - visualJson.scene.time_of_day + ", " + visualJson.scene.weather  (only if either is present)
  - visualJson.scene.atmosphere
  Strip trailing dots, then add a single trailing "." 
  (or null if no scene fields present)

seo_tags: Collect and deduplicate, lowercase, trimmed:
  - visualJson.meta.theme split by "-", keep only tokens longer than 2 chars
  - visualJson.meta.use_case
  - visualJson.meta.channel
  Join with ", "  (or null if all empty)
```

**Else (neither seo.json nor visual.json)** — use `AskUserQuestion` to ask the user for:
- seo_title (required)
- seo_description
- seo_tags (comma-separated)
- target_duration_h (number, e.g. 8.0)
- theme

Also: if `theme` is still null after extracting SEO (only seo.json was present), use `AskUserQuestion` to ask the user for the video theme.

---

## Step 7 — Ask user for remaining required fields

Use `AskUserQuestion` to confirm or collect:
- `template_id` — ask: "Which video template should this video use? Call `youtube_video(action='list_templates')` and show the options."
- `output_quality` — ask: "Output quality: `1080p` or `4K`?" (default: `1080p`)
- `thumbnail_text` — ask: "Thumbnail text overlay (5 words max, or leave blank for none)."
- `channel_ids` — ask: "Which YouTube channel IDs should this video be uploaded to? (e.g. [1, 2])"

If `target_duration_h` was extracted from JSON, show it to the user and ask to confirm or change it.

---

## Step 8 — Create the YouTube video record

Call:
```
youtube_video(
  action="create",
  fields={
    "title": <seo_title if present, else "<theme> — <template_label>">,
    "template_id": <template_id>,
    "theme": <theme>,
    "music_track_id": <music_track_id from step 4, or null if skipped>,
    "visual_asset_id": <visual_asset_id from step 3>,
    "sound_layers": <sound_layers from step 5, or null if step 5 was skipped>,
    "seo_title": <seo_title>,
    "seo_description": <seo_description>,
    "seo_tags": <seo_tags as array — split comma-separated string into list>,
    "target_duration_h": <target_duration_h>,
    "output_quality": <output_quality>,
    "thumbnail_text": <thumbnail_text or null>
  },
  confirm=true
)
```

**Field notes:**
- `sound_layers` is the correct field name on the YoutubeVideo model (not `sfx_overrides`).
  `sfx_overrides` is a separate legacy column — do not use it here.
- `seo_tags` must be a JSON array of strings, not a comma-separated string.
  If you have a comma-separated string, split on `,` and trim each element.
- Pass `sound_layers: null` (not `{}`) if no SFX was generated.

Capture the returned `id` as `video_id`.

---

## Step 9 — Upload the thumbnail source image

Call:
```
youtube_thumbnail(
  action="upload_image",
  video_id=<video_id>,
  file_path=<absolute thumbnail_path>,
  confirm=true
)
```

---

## Step 10 — Generate the thumbnail with text overlay

Call:
```
youtube_thumbnail(
  action="generate_with_text",
  video_id=<video_id>,
  text=<thumbnail_text or null>,
  confirm=true
)
```

This is synchronous — no task polling required.

---

## Step 11 — Render the audio preview, then approve

```
youtube_video(action="render_audio_preview", video_id=<video_id>, confirm=true)
```

Poll `task_status(task_id=...)` every 10 seconds until `SUCCESS` or `FAILURE`.

On `SUCCESS`:
```
youtube_video(action="approve_audio_preview", video_id=<video_id>, confirm=true)
```

On `FAILURE`: show the error and use `AskUserQuestion` to ask how to proceed.

---

## Step 12 — Render the video preview, then approve

```
youtube_video(action="render_video_preview", video_id=<video_id>, confirm=true)
```

Poll `task_status` every 10 seconds until `SUCCESS` or `FAILURE`.

On `SUCCESS`:
```
youtube_video(action="approve_video_preview", video_id=<video_id>, confirm=true)
```

On `FAILURE`: show the error and use `AskUserQuestion`.

---

## Step 13 — CONFIRM before render_final

Use `AskUserQuestion`. Show the user:
- video_id
- title
- confirmation that both audio preview and video preview have been approved

Wait for explicit approval. If the user says no, stop and report current state.

---

## Step 14 — Render final

```
youtube_video(action="render_final", video_id=<video_id>, confirm=true)
```

Poll `task_status` every 10 seconds until `SUCCESS` or `FAILURE`.
On `SUCCESS`, capture `result.output_path`.
On `FAILURE`: show the error and use `AskUserQuestion`.
After 30 minutes of non-SUCCESS: use `AskUserQuestion` to ask whether to keep waiting.

---

## Step 15 — CONFIRM before upload

Use `AskUserQuestion`. Show the user:
- video_id
- title
- output_path
- channel_ids that will be targeted

Wait for explicit approval. If the user says no, stop and report current state.

---

## Step 16 — Set upload targets

```
upload(
  action="set_targets",
  video_id=<video_id>,
  channel_ids=<channel_ids>,
  confirm=true
)
```

---

## Step 17 — Upload to YouTube

```
upload(
  action="upload_one",
  video_id=<video_id>,
  confirm=true,
  confirm_id=<video_id>
)
```

`confirm_id` must equal `video_id` — this is the destructive-op safety guard.

Poll `task_status` every 10 seconds until `SUCCESS` or `FAILURE`.
On `SUCCESS`, capture the YouTube URL from `result`.

---

## Final report

When all steps succeed, summarize:
- video_id
- title
- output_path (local render file)
- YouTube URL(s) from the upload task result
- music_track_id used
- Number of SFX assets generated
- Any items that were skipped or failed

---

## Hard rules

1. **Do not skip any step.** The render pipeline strictly requires:
   `render_audio_preview → approve_audio_preview → render_video_preview → approve_video_preview → render_final`.

2. **Do not skip the ElevenLabs plan step.** The compose API requires a
   `composition_plan`. You must call `music(action="elevenlabs_plan")` first
   and use its output.

3. **Do not invent SFX prompts.** Generate exactly the items defined in
   visual.json using `english_prompt` verbatim. Skipping `automation_only` items
   is correct — do not generate assets for them.

4. **Do not use `music(action="generate")`.** That is the Suno/Lyria path.
   This workflow always uses `elevenlabs_plan` → `elevenlabs_compose`.

5. **Do not retry destructive operations automatically.** Render and upload
   failures must be escalated to the user via `AskUserQuestion`.

6. **Do not call any write tool with `confirm=false`.** That returns an intent
   envelope without executing. Always pass `confirm=true` for write operations.

7. **Do not move past `ok=false`.** Show the full error envelope and ask.

8. **Field name is `sound_layers`, not `sfx_overrides`.** Use the exact model
   field name shown in step 8.

9. **`track_id` comes from `task_status` result, not from `elevenlabs_compose`.**
   The compose call returns only `task_id`. Poll `task_status` and extract
   `result.track_id` on SUCCESS.

10. **`seo_tags` must be an array.** Split any comma-separated string before
    passing to `youtube_video(action="create")`.

11. **When parsing `interval_seconds` strings** like `"60-120"`, take the two
    integers as min and max. Default to `{min: 10, max: 25}` for midground and
    random_sfx, `{min: 45, max: 60}` for foreground, if missing or malformed.

````

---

## Notes

### Key divergences between the modal and MCP

- **`track_id` from compose**: The frontend calls `musicApi.elevenlabsCompose()`
  and reads `resp.track_id` directly from the HTTP response (which returns
  `{task_id, track_id}`). The MCP `_confirmed_async` wrapper strips `track_id`
  and only passes `task_id` through. Agents must poll `task_status` and read
  `result.track_id` from the SUCCESS state.

- **`sound_layers` vs `sfx_overrides`**: The YoutubeVideo model has both
  columns. The frontend's `handleSubmit` sends `sound_layers` (not
  `sfx_overrides`) in the create body. The agent must use `sound_layers`.

- **SFX generate is synchronous**: `sfx(action="generate")` calls
  `_confirmed_sync`, which returns the SFX asset row directly as `data`.
  No task_id is returned. The asset ID is at `data.id`. Do not poll.

- **Visual asset upload**: The `visual_asset(action="upload")` call uses
  multipart upload — the MCP client streams the local file to the backend.

- **Thumbnail upload**: `youtube_thumbnail(action="upload_image")` is also a
  multipart upload. `youtube_thumbnail(action="generate_with_text")` is
  synchronous with no task_id.

- **`confirm_id` on `upload_one`**: The upload tool requires `confirm_id`
  to equal `video_id` as a destructive-op safety guard.

### Working-folder examples

Existing slugs follow the `<theme>-<descriptor>` pattern:
`beach-sunset-ambience`, `rainy-tokyo-night`, `thunderstorm-deep-sleep`.

Drop your JSON files into `working/<slug>/json/` and provide the video and
thumbnail paths when the agent asks.
