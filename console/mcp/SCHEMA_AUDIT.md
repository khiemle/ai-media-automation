# Schema audit — `feat/mcp-server`

For each tool, comparing what `console/mcp/tools/<tool>.py` sends to the real
backend Pydantic schema.

Legend:
- ✅ = match (or harmlessly ignored extra fields)
- ⚠️ = field-name or type mismatch that causes a 422 or wrong behavior
- 🚫 = endpoint doesn't exist or structural mismatch (multipart vs JSON, no-body route)

---

## music ✅ FIXED in commit 898b2ad

Post-Phase A status: all actions that POST a body now match the real backend schemas.

| MCP action | Body sent | Backend schema | Status |
|---|---|---|---|
| generate | `{idea, niches, moods, genres, provider, is_vocal, title, expand_only}` | `GenerateBody` | ✅ |
| elevenlabs_plan | `{input, music_length_ms}` | `ElevenLabsPlanBody` | ✅ |
| elevenlabs_compose | `{composition_plan, title, niches, moods, genres, output_format, respect_sections_durations}` | `ElevenLabsComposeBody` | ✅ |
| update | `fields` dict passthrough | `UpdateBody` (all fields optional) | ✅ |
| upload | removed (was JSON, backend is multipart) | n/a | ✅ |

---

## sfx

Router: `console/backend/routers/sfx.py`

| MCP action | MCP body fields | Backend schema | Status | Notes |
|---|---|---|---|---|
| list | `{sound_type, limit, offset}` as query params | query params: `sound_type, search` | ✅ `sound_type` matches; `limit/offset` silently ignored (backend doesn't accept them) |
| list_sound_types | GET only | GET only | ✅ |
| get_stream_url | no HTTP call | no HTTP call | ✅ |
| generate | `{prompt, duration_s, sound_type}` as JSON | `GenerateBody { text, loop, duration_seconds, title }` | ⚠️ **3 mismatches** |
| import_file | `{file_path, name, sound_type}` as JSON | multipart form-data `(file, title, sound_type, source)` | 🚫 **structural: JSON vs multipart** |
| delete | no body | no body | ✅ |

### generate mismatches
1. `prompt` → should be `text` (required string). Current code sends `prompt`; backend expects `text`. **Causes 422**.
2. `duration_s` → should be `duration_seconds` (float, 0.5–22.0). Current code sends `duration_s`. Extra field silently ignored; `duration_seconds` defaults to None.
3. `sound_type` → not in `GenerateBody` at all. Silently ignored by backend.
4. `loop` → not sent by MCP. Defaults to `False` (acceptable).
5. Backend endpoint is **synchronous** (returns the created SFX row, not a `task_id`). MCP wraps it in `_confirmed_async` with `task_kind="sfx_generate"` and tries to read `data.get("task_id")` — this will return `task_id: None` because the response is the SFX object, not a Celery task envelope.

### import_file mismatches
- MCP sends JSON `{file_path, name, sound_type}` but backend is `POST /sfx/import` accepting multipart `(file: UploadFile, title: Form, sound_type: Form, source: Form)`. Cannot call this via JSON. **Causes 422 / 415**.

---

## visual_asset

Router: `console/backend/routers/production.py`

| MCP action | MCP body fields | Backend schema | Status | Notes |
|---|---|---|---|---|
| list | query params `{niche, limit, offset}` | query params `{keywords, niche, source, min_duration, asset_type, page, per_page}` | ⚠️ `limit/offset` not valid; `niche` accepted as query param (single value, not list) |
| get | no body | no body | ✅ |
| stream_url | no HTTP call | no HTTP call | ✅ |
| get_thumbnail | no HTTP call | no HTTP call | ✅ |
| upload | `{file_path, title, niche, tags, duration_s}` as JSON | multipart form-data `(file: UploadFile, source: Form, title: Form, description: Form, keywords: Form, asset_type: Form, generation_prompt: Form)` | 🚫 **structural: JSON vs multipart** |
| update | `fields` dict passthrough | `UpdateAssetBody { description, keywords, niche, quality_score }` | ⚠️ passthrough is fine if caller provides correct fields, but undocumented |
| animate | `{prompt, duration_s, model}` | `AnimateBody { prompt, video_type }` | ⚠️ **2 mismatches** |
| upscale | `{target, model}` as JSON | `POST /assets/{id}/upscale` — **no request body** | ⚠️ extra JSON body silently ignored by FastAPI; but `target` and `model` have no effect |
| delete | no body | no body | ✅ |

### upload mismatches
MCP sends `{file_path, title, niche, tags, duration_s}` as JSON. Backend requires multipart with an actual binary file upload. The `file_path` field doesn't exist on the backend; there is no route that accepts a server-side file path. **Causes 422 / 415**. This action cannot be implemented via JSON alone.

### animate mismatches
1. `duration_s` → not in `AnimateBody`. Silently ignored.
2. `model` → not in `AnimateBody`. Silently ignored.
3. `video_type` → MCP never sends this. Defaults to `"loop"` (acceptable default).
4. No 422, but `video_type` is unconfigurable from the MCP tool.

### upscale mismatches
Backend `POST /assets/{id}/upscale` takes no body. MCP sends `{target, model}` which FastAPI will silently ignore (no body schema defined). Fields have no effect; the endpoint always upscales to 4K with Topaz. Status: functionally OK but exposes misleading parameters to the LLM.

---

## channel_plan

Router: `console/backend/routers/channel_plans.py`

| MCP action | MCP body fields | Backend schema | Status | Notes |
|---|---|---|---|---|
| list | GET only | GET only | ✅ |
| get | GET only | GET only | ✅ |
| import_json | `payload` dict as JSON | `POST /channel-plans/import` accepts `UploadFile` (`.md` file) | 🚫 **structural: JSON dict vs file upload** |
| update | `fields` dict | `UpdatePlanBody { md_content: str, channel_id? }` | ⚠️ passthrough — caller must provide `md_content` key |
| delete | no body | no body | ✅ |
| ai_seo | `{}` (empty) | `AIThemeBody { theme: str, context: str = "" }` | ⚠️ **`theme` is required but never sent — causes 422** |
| ai_prompts | `{"hints": kw["hints"]}` | `AIThemeBody { theme: str, context: str = "" }` | ⚠️ **wrong field `hints` vs required `theme` — causes 422** |
| ai_autofill | `{"hints": kw["hints"]}` | `AIThemeBody { theme: str, context: str = "" }` | ⚠️ **same as ai_prompts — causes 422** |
| ai_ask | `{"question": q}` | `AIQuestionBody { question: str }` | ✅ |

### import_json mismatches
`POST /api/channel-plans/import` accepts a multipart file upload (`.md` file only). MCP calls it with a JSON dict as the body. **Causes 415 / 422**. The action name `import_json` implies JSON but the backend only accepts `.md` file uploads.

### ai_seo / ai_prompts / ai_autofill mismatches
All three AI endpoints use `AIThemeBody { theme: str, context: str = "" }`:
- `ai_seo` sends `{}` → `theme` is required → **422**.
- `ai_prompts` sends `{"hints": hints}` → `theme` is required and wrong field name → **422**.
- `ai_autofill` sends `{"hints": hints}` → same as above → **422**.

The `register()` function exposes a `hints: dict` parameter but the backend expects `theme: str` (a plain string, not a dict). The MCP tool has no `theme` or `context` parameters at all.

---

## channel

Router: `console/backend/routers/channels.py`

| MCP action | MCP body fields | Backend schema | Status | Notes |
|---|---|---|---|---|
| list | GET query params `{}` | `platform, status` query params | ✅ (no filter params exposed but no 422) |
| get | GET only | GET only | ✅ |
| create | `fields` dict passthrough | `ChannelBody { name, platform, credential_id, account_email, category, default_language, monetized, status, subscriber_count, video_count }` | ✅ passthrough works if caller provides correct fields |
| update | `fields` dict | `ChannelUpdateBody` (all optional) | ✅ passthrough works |
| delete | no body | no body | ✅ |
| get_defaults | GET only | GET only | ✅ |
| set_defaults | `kw.get("fields")` passthrough | `DefaultsBody { channel_ids: list[int] }` | ⚠️ **caller must pass `fields={"channel_ids": [...]}` — not documented; wrong if caller passes `fields={"channels": [...]}`** |
| credential_status | GET only | GET `/api/credentials/{platform}` | ✅ |

### set_defaults concern
MCP sends `kw.get("fields") or {}` to `PUT /api/channels/defaults/{template}`. Backend expects `DefaultsBody { channel_ids: list[int] }`. This works only if the caller passes `fields={"channel_ids": [1, 2]}` — but the tool has no explicit `channel_ids` parameter, so the LLM has no way to know the expected structure. No 422 if caller provides the right dict, but easily misused.

---

## youtube_video

Router: `console/backend/routers/youtube_videos.py`

| MCP action | MCP body fields | Backend schema | Status | Notes |
|---|---|---|---|---|
| list | query params `{status, niche, limit, offset}` | `status, template_id` query params | ⚠️ `niche/limit/offset` not accepted; silently ignored |
| get | GET only | GET only | ✅ |
| list_templates | GET only | GET only | ✅ |
| get_template | GET only | GET only | ✅ |
| get_render_state | GET only | GET only | ✅ |
| create | `fields` dict | `YoutubeVideoCreate { title, template_id, theme, music_track_id, ... }` | ✅ passthrough, `title` and `template_id` are required |
| update | `fields` dict | `YoutubeVideoUpdate` (all optional) | ✅ passthrough |
| delete | no body | no body | ✅ |
| render_audio_preview | no body | no body | ✅ |
| approve_audio_preview | no body | no body | ✅ |
| reject_audio_preview | no body | no body | ✅ |
| render_video_preview | no body | no body | ✅ |
| approve_video_preview | no body | no body | ✅ |
| reject_video_preview | no body | no body | ✅ |
| render_final | no body | no body | ✅ |
| cancel_render | no body | no body | ✅ |
| resume_render | no body | no body | ✅ |

No body-schema 422s. The `niche/limit/offset` params on `list` are silently ignored (backend only accepts `status` and `template_id`). Mostly clean.

---

## youtube_thumbnail

Router: `console/backend/routers/youtube_videos.py`

| MCP action | MCP body fields | Backend schema | Status | Notes |
|---|---|---|---|---|
| upload_image | `{"file_path": fp}` as JSON | multipart `image: UploadFile` | 🚫 **structural: JSON vs multipart file upload** |
| generate_with_text | `{text, style?, font?, color?}` | `ThumbnailGenerateRequest { text: str \| None }` | ⚠️ `style/font/color` silently ignored; `text` is correct |
| get_current | no HTTP call | no HTTP call | ✅ |
| get_source | no HTTP call | no HTTP call | ✅ |

### upload_image mismatches
MCP sends JSON `{"file_path": fp}` to `POST /api/youtube-videos/{video_id}/thumbnail-image`. Backend expects multipart `image: UploadFile`. **Causes 422**. No route accepts a server-side file path for this operation.

### generate_with_text notes
`style`, `font`, `color` are silently ignored by the backend (`ThumbnailGenerateRequest` only has `text`). No 422 but the LLM is misled into thinking these parameters do something.

Also note: `generate_with_text` is wrapped in `_confirmed_async` expecting a `task_id` in the response, but the backend endpoint at `POST /{video_id}/thumbnail-generate` is **synchronous** — it does not dispatch a Celery task; it generates the thumbnail inline and returns `{"thumbnail_url": "..."}`. The MCP wraps this as an async task with `task_kind="youtube_thumbnail_generate"` and reads `data.get("task_id")` which will be None (thumbnail_url is present, not task_id). The integration test mocks the response as `{"task_id": "thumb-1"}` which masks this.

---

## upload

Router: `console/backend/routers/uploads.py`

| MCP action | MCP body fields | Backend schema | Status | Notes |
|---|---|---|---|---|
| list_videos | query params `{status, niche, limit, offset}` | `{platform, status, video_format, page, per_page}` | ⚠️ `niche/limit/offset` not valid; silently ignored. `page/per_page` not exposed. |
| set_targets | `{"channels": channels}` | `SetTargetsBody { channel_ids: list[int] }` | ⚠️ **field name mismatch: `channels` vs `channel_ids` — causes 422** |
| upload_one | `{}` (empty JSON body) | no request body | ✅ extra body silently ignored |
| upload_all | `{"filter": {...}}` | no request body | ✅ extra body silently ignored |
| delete_target | no body | no body | ✅ |
| stream_url | no HTTP call | no HTTP call | ✅ |

### set_targets mismatch
MCP sends `{"channels": channels}` but backend `SetTargetsBody` has field `channel_ids`. This will cause a **422** because `channel_ids` is required and `channels` is not a recognized field.

---

## Summary

### Mismatch count by tool

| Tool | Clean actions | ⚠️ Mismatch (422 or wrong behavior) | 🚫 Structural (multipart/no-body) |
|---|---|---|---|
| music | all ✅ (fixed) | 0 | 0 |
| sfx | list, list_sound_types, get_stream_url, delete | **generate** (prompt→text, task vs sync) | **import_file** (JSON vs multipart) |
| visual_asset | get, stream_url, get_thumbnail, update, delete | **animate** (unknown params), **upscale** (params ignored), **list** (limit/offset ignored) | **upload** (JSON vs multipart) |
| channel_plan | list, get, delete, ai_ask | **ai_seo** (missing required `theme`), **ai_prompts** (wrong field), **ai_autofill** (wrong field), **update** (undocumented required structure) | **import_json** (JSON vs .md file upload) |
| channel | list, get, create, update, delete, get_defaults, credential_status | **set_defaults** (undocumented field structure) | — |
| youtube_video | all render gates, get, list_templates, get_template, get_render_state, create, update, delete | **list** (niche/limit/offset silently ignored) | — |
| youtube_thumbnail | get_current, get_source | **generate_with_text** (sync endpoint exposed as async; style/font/color ignored) | **upload_image** (JSON vs multipart) |
| upload | upload_one, upload_all, delete_target, stream_url | **list_videos** (wrong params), **set_targets** (channels vs channel_ids → 422) | — |

### Tools with 422-causing mismatches (highest priority to fix)
1. **upload.set_targets** — `channels` vs `channel_ids`. Direct 422 every call.
2. **sfx.generate** — `prompt` vs `text`. Direct 422 every call.
3. **channel_plan.ai_seo** — missing required `theme`. Direct 422 every call.
4. **channel_plan.ai_prompts** — `hints` vs required `theme`. Direct 422 every call.
5. **channel_plan.ai_autofill** — same as above. Direct 422 every call.

### Tools with structural mismatches (cannot be fixed by field rename alone)
1. **sfx.import_file** — backend is multipart; no JSON equivalent exists.
2. **visual_asset.upload** — backend is multipart; no JSON equivalent exists.
3. **channel_plan.import_json** — backend only accepts `.md` file upload, not JSON.
4. **youtube_thumbnail.upload_image** — backend is multipart file upload.

### Tools with silent-ignore mismatches (no 422, but parameters have no effect)
1. **visual_asset.upscale** — `target` and `model` are sent but ignored; endpoint always 4K Topaz upscale.
2. **visual_asset.animate** — `duration_s` and `model` are silently ignored; `video_type` unconfigurable.
3. **youtube_thumbnail.generate_with_text** — `style`, `font`, `color` silently ignored. Also: endpoint is synchronous but MCP wraps it as async task.
4. **channel.set_defaults** — works only if caller happens to send the exact right dict structure; easy to misuse.

### Recommended fix order
1. **upload.set_targets** — one-line rename `channels` → `channel_ids`
2. **sfx.generate** — rename `prompt` → `text`, `duration_s` → `duration_seconds`; also change from `_confirmed_async` to `_confirmed_sync` (endpoint is synchronous)
3. **channel_plan.ai_seo/ai_prompts/ai_autofill** — add `theme: str` parameter; rename `hints` → `context`
4. **visual_asset.animate** — drop `duration_s`/`model`; add `video_type` param
5. **visual_asset.upscale** — remove body params that have no effect
6. **youtube_thumbnail.generate_with_text** — change from `_confirmed_async` to `_confirmed_sync`; drop style/font/color from `_pick`
7. All multipart structural mismatches — document as "not supported via MCP JSON transport" or implement via a different mechanism (pre-upload endpoint, etc.)
