---
name: make-youtube-video
description: Drive the full end-to-end "create a YouTube video" pipeline of the AI Media Console using the ai-media-console MCP server. Reads three template JSON files (`*music.json`, `*visual.json`, `*seo.json`) from `working/<slug>/json/`, uploads a user-provided visual video and thumbnail image, generates ElevenLabs music + layered SFX, assembles sound layers, creates the YouTube video record, and walks through the audio-preview → video-preview → final-render → upload sequence with explicit user confirmation at each destructive step. Use when the user asks to "make a youtube video", "build a youtube video from json", "import template and produce a video", "render a relax/ambient/asmr video end to end", "push my [theme] video to youtube", "run the make-video workflow", or any phrasing that means "take my JSON templates and produce + publish a finished YouTube video via the console". Strongly prefer over manually orchestrating the underlying MCP tools — this skill encodes the choreography, the field-name correctness (sound_layers vs sfx_overrides, channel_ids vs channels, idea vs prompt), and the render-gate ordering that's easy to get wrong by hand.
---

# Make YouTube Video — End-to-End Workflow

This skill executes the full create-render-upload pipeline using the
`ai-media-console` MCP server. The detailed workflow lives in a separate
prompt file — this skill is the entry point that tells you when and how to
invoke it.

## Pre-flight (verify before starting)

1. The user has the `ai-media-console` MCP server registered. Quickest check:
   call `system_health` with `action="health"`. If it isn't available or
   returns an error, the MCP server isn't reachable — stop and tell the user
   to restart Claude Code or run `claude mcp list` to verify the server is
   registered.

2. The console FastAPI must be running on `:8080`. If `system_health` fails
   with a connection error, ask the user to run `./console/start.sh`.

3. The user must give you a slug — the subfolder under `working/` that
   contains their three JSON template files. If they haven't said which slug,
   ask via `AskUserQuestion`.

## Read the workflow

The full step-by-step workflow — including JSON schemas, tool calls, decision
gates, and hard rules — is in:

**`console/mcp/prompts/MAKE_YOUTUBE_VIDEO.md`**

**Use the Read tool to load that file now.** Then follow it exactly. It is the
source of truth — do not summarize, paraphrase, or skip steps.

## What the workflow does (high-level summary)

```
1. Glob `working/<slug>/json/*music.json` (or `*suno.json` as fallback —
   the visual-video skill saves the music file with `_suno` suffix),
   `*visual.json`, `*seo.json` — disambiguate via AskUserQuestion if
   multiple/zero matches
2. Validate each JSON (parseMusicJson / parseSfxJson / parseSeoJson rules)
3. AskUserQuestion for visual.mp4 path and thumbnail.jpg path
4. visual_asset(action="upload", ...) — multipart upload of the .mp4
5. If music.json present:
   - Build music prompt from `composer` (preferred) or `suno.style_of_music`
   - music(action="elevenlabs_plan", input=..., music_length_ms=600000)
   - music(action="elevenlabs_compose", composition_plan=..., title=..., confirm=true)
   - Poll task_status until SUCCESS, capture result.track_id
6. If visual.json present:
   - Flatten sfx.{background, midground, foreground, random_sfx} via collectSfxItems
   - For each non-automation_only item: sfx(action="generate", text=..., loop=..., title=..., confirm=true)
   - Build `sound_layers` dict with per-layer volumes (bg 0.4, mid 0.5, fg 0.7, random 0.6)
     and parsed interval bounds (foreground 45-60 default; others 10-25)
7. Extract SEO via fallback chain: extractSeoFromSeoJson → extractSeoFromSfxJson → AskUserQuestion
8. youtube_video(action="create", fields={...}) with sound_layers (NOT sfx_overrides),
   music_track_id, visual_asset_id, seo_*, thumbnail_text, target_duration_h, etc.
9. youtube_thumbnail(action="upload_image", video_id=..., file_path=...)
10. youtube_thumbnail(action="generate_with_text", video_id=..., text=...) — synchronous
11. Render audio preview → poll → approve_audio_preview
12. Render video preview → poll → approve_video_preview
13. AskUserQuestion: confirm before render_final
14. Render final → poll → capture output_path
15. AskUserQuestion: confirm before upload (show video_id, channel_ids, output_path)
16. upload(action="set_targets", channel_ids=...)
17. upload(action="upload_one", video_id=..., confirm=true, confirm_id=<same video_id>)
    → poll → final URL
```

## File upload workaround (MCP runs in Docker)

The `ai-media-console` MCP server runs as a Docker container
(`docker run -i --rm --env-file ~/.mcp/ai-media-console.env ...`).
It has **no access to host filesystem paths** — `/Volumes/`, `/tmp/`, or
anywhere else on the host. Any MCP tool that reads a local file
(`visual_asset(action="upload")`, `youtube_thumbnail(action="upload_image")`)
will fail with `"file not found"` even if the file clearly exists on disk.

**Workaround: upload directly via `curl` from the shell.**

The env file `~/.mcp/ai-media-console.env` contains:
```
MCP_API_TOKEN=<jwt>
MCP_CONSOLE_API_BASE=http://<LAN-IP>:8080
```
Use that IP (not `localhost`) for all curl calls — the Docker container
connects via the LAN address, and `localhost` from the shell also resolves
correctly via that IP.

### Visual asset upload (step 3)

```bash
TOKEN="<MCP_API_TOKEN from ~/.mcp/ai-media-console.env>"
curl -s --max-time 120 -X POST "http://<MCP_CONSOLE_API_BASE>/api/production/assets/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/video.mp4;type=video/mp4" \
  -F "title=<title>" \
  -F "keywords=<comma,separated>" \
  -F "asset_type=video" \
  -F "source=manual"
```

Capture `id` from the JSON response as `visual_asset_id`.

### Thumbnail upload (step 9)

```bash
curl -s --max-time 60 -X POST "http://<MCP_CONSOLE_API_BASE>/api/youtube-videos/<video_id>/thumbnail-image" \
  -H "Authorization: Bearer $TOKEN" \
  -F "image=@/path/to/thumbnail.png;type=image/png"
```

Note the form field is **`image`**, not `file`. Capture `asset_id` from the response.

After uploading via curl, continue with the MCP tool for
`youtube_thumbnail(action="generate_with_text", ...)` — that step reads from
the DB record, not from the filesystem, so the MCP tool works fine.

### Filename spaces

Files with spaces in their names (e.g. Runway exports like
`Runway_Media Processing V2_051426 4K.mp4`) cause the `file not found`
error even via curl on some systems. Rename to remove spaces before uploading:
```bash
mv "path/with spaces/file.mp4" "path/with spaces/file_clean.mp4"
```

### Polling music tasks

`task_status(task_id=...)` routes to `/api/pipeline/jobs/{job_id}` which
expects an **integer**. Music compose tasks return a Celery UUID — use
`/api/music/tasks/{task_id}` instead:
```bash
curl -s "http://<MCP_CONSOLE_API_BASE>/api/music/tasks/<uuid>" \
  -H "Authorization: Bearer $TOKEN"
```
States: `PENDING` → `PROGRESS` → `SUCCESS` (with `result.track_id`) or `FAILURE`.

Render task UUIDs (audio preview, video preview, render_final) also use this
same endpoint — the `/api/music/tasks/` path accepts any Celery task UUID, not
just music tasks.

## ElevenLabs quota failures

If `music(action="elevenlabs_compose")` returns FAILURE with empty `info {}`,
run the task synchronously via the shell to get the real error:
```bash
.venv/bin/python -c "
from console.backend.tasks.music_tasks import generate_elevenlabs_music_task
# ... (create test track, call task directly)
"
```

Common failure: **quota exceeded** — `"You have X credits remaining, while Y
credits are required"`. Fix: reduce `music_length_ms` and drop sections.
A 600 000 ms (10-min) plan needs ~8 242 credits; 480 000 ms (8-min) needs
~6 594. Calculate: `available / required * original_ms` to find a safe length,
then drop sections from the end of the plan before retrying compose.

## Hard rules (do not skip — these are easy to get wrong)

- **Field name `sound_layers`**, not `sfx_overrides`. Both columns exist on
  the YoutubeVideo model. The frontend writes to `sound_layers`. Use that.
- **Field name `channel_ids`**, not `channels`, on `upload(action="set_targets")`.
  Schema audit caught this — wrong name returns 422.
- **`elevenlabs_compose` returns `task_id` only** — the MCP wrapper strips
  `track_id` from the immediate response. Get `track_id` from the polled
  `/api/music/tasks/<uuid>` SUCCESS payload at `result.track_id`.
- **`youtube_thumbnail.generate_with_text` is synchronous** — the backend
  endpoint returns the URL directly, not a `task_id`. Don't poll it.
- **`youtube_thumbnail.generate_with_text` text limit** — 5 words or fewer.
  The `·` separator character counts as a word. Strip separators or shorten
  the text if the API returns 400.
- **`sfx.generate` is synchronous** — also returns the asset row directly,
  no task polling.
- **Render gates must run in order**: `render_audio_preview → approve →
  render_video_preview → approve → render_final`. Never skip.
- **`confirm_id` for `upload.upload_one` must equal `video_id`.** This is
  the destructive-op safety guard.
- **Never call write tools without `confirm=true`.** Without it you only get
  back the intent envelope, not the actual operation.
- **`automation_only` SFX items are SKIPPED** during generation — they're
  preserved as definitions but no asset is generated.
- **Items in `working/<slug>/json/`**, not the slug folder root. The .mp4 and
  .jpg paths come from the user during execution, not from the folder.
- **AskUserQuestion before every destructive ramp**: render_final, upload_one.
  Also AskUserQuestion whenever a JSON field is missing or ambiguous, or a
  tool returns `ok=false`.

## What success looks like

When the workflow completes, report:

- `video_id` (the YouTube video record ID)
- `output_path` (the rendered .mp4 path)
- The `task_id` for the upload, plus the YouTube URL once `task_status`
  returns SUCCESS

## What to do on failure

If any tool returns `ok=false`:
1. Show the user the full error envelope (`error.code`, `error.message`,
   `error.context`, `error.retryable`).
2. AskUserQuestion: retry / skip / abort.
3. Do not retry destructive operations automatically.

If a polling loop sits in `PROGRESS` for more than 15 minutes without
progress update, AskUserQuestion: keep waiting / abort.

## Notes

- The full prompt at `console/mcp/prompts/MAKE_YOUTUBE_VIDEO.md` mirrors the
  logic of the frontend's `ImportFromTemplateModal` — `parseMusicJson`,
  `parseSfxJson`, `parseSeoJson`, `buildMusicPrompt`, `collectSfxItems`,
  `assembleSoundLayers`, `extractSeoFromSeoJson`, `extractSeoFromSfxJson`.
  If the modal evolves, that prompt should evolve in lockstep — and so should
  this skill's hard-rules list.
- The MCP server's tool catalog and confirmation pattern is documented in
  `console/mcp/README.md`. Operational runbook at `console/mcp/RUNBOOK.md`.
- Known limitations (multipart upload streaming, audit/idempotency activation,
  per-key service tokens) are tracked in `console/mcp/FOLLOWUPS.md`.
