# YouTube Shorts Upload — Design Spec

**Date:** 2026-04-26  
**Status:** Approved

---

## Problem

The existing upload pipeline has all the plumbing wired (Celery task, upload service, OAuth storage, channel model), but several gaps prevent real end-to-end YouTube uploads:

1. `youtube_uploader.py` hardcodes language to `"vi"` and privacy to `"public"` — wrong for English Shorts channels
2. No `#Shorts` tag is added — YouTube won't classify the video as a Short
3. The channel Create/Edit modal in the frontend has no `credential_id` field — without this link the upload task has no OAuth tokens to use
4. No tooling exists to perform the one-time OAuth authorization for a channel (the backend callback endpoint exists but nothing drives the browser through it)
5. No developer setup guide for Google Cloud → OAuth app → upload

---

## Scope

- Any number of YouTube channels (not limited to `@RunningTips-z2n`)
- Channels are created in the console Channels manager and linked to their OAuth credential
- All uploads are treated as Shorts (always `#Shorts`)
- Uploads default to `unlisted` privacy status; the operator publishes manually on YouTube
- Language is driven per-channel via `Channel.default_language`

Out of scope:
- TikTok or Instagram uploads (separate task)
- Scheduled/delayed publishing
- YouTube Shorts thumbnail customization

---

## Architecture

No new tables or services required. Changes stay within existing boundaries:

```
Uploads tab (frontend)
  └─ ChannelsTab: Add credential_id dropdown to channel modal
  └─ CredentialsTab: unchanged (already has OAuth Flow button)

upload_tasks.py (Celery)
  └─ Passes channel.default_language + is_shorts=True in metadata dict

youtube_uploader.py (core uploader)
  └─ Uses metadata["language"] and metadata["privacy_status"]
  └─ Always injects #Shorts tag + appends to title

scripts/setup_youtube_oauth.py (one-time CLI)
  └─ Drives OAuth flow in a local browser + temporary HTTP server
  └─ Stores credential + channel in DB
```

---

## Component Changes

### 1. `uploader/youtube_uploader.py`

**Changes:**
- `defaultLanguage`: use `metadata.get("language", "en")` — no longer hardcoded to `"vi"`
- `privacyStatus`: use `metadata.get("privacy_status", "unlisted")` — default `unlisted` instead of `public`
- `#Shorts` tag: always prepend `"Shorts"` to the tags list and append `" #Shorts"` to the description
- Add `"running"` niche to `_niche_to_category` → category `"17"` (Sports)

### 2. `console/backend/tasks/upload_tasks.py`

**Changes:**
- After fetching the `channel` row, inject into `video_meta`:
  - `language`: `channel.default_language or "en"`
  - `privacy_status`: `"unlisted"`

### 3. `console/frontend/src/pages/UploadsPage.jsx`

**Changes in `ChannelsTab`:**
- On modal open, fetch `GET /api/credentials` to populate a credential dropdown
- Add `credential_id` field to the Create/Edit channel form (`<Select>` listing credential name + platform)
- Default value: first credential for the selected platform, or blank

### 4. `scripts/setup_youtube_oauth.py`

New CLI script. Usage:
```bash
python3 scripts/setup_youtube_oauth.py \
  --client-id YOUR_CLIENT_ID \
  --client-secret YOUR_CLIENT_SECRET \
  --channel-name "RunningTips"
```

Behavior:
1. Reads `console/.env` for `DATABASE_URL` and `FERNET_KEY`
2. Creates/updates `PlatformCredential` for `youtube` with the given app credentials
3. Sets `redirect_uri = "http://localhost:8888/callback"`
4. Builds Google OAuth URL and opens it in the default browser
5. Starts a temporary `http.server` on `localhost:8888` to catch the callback code
6. Exchanges the code for `access_token` + `refresh_token` via `POST https://oauth2.googleapis.com/token`
7. Encrypts both tokens with Fernet and stores in `platform_credentials`
8. Creates a `Channel` row (`platform=youtube`, `name=<channel-name>`, `credential_id=<new_cred_id>`, `default_language=en`, `status=active`) unless a channel with the same name already exists
9. Prints a summary: credential ID, channel ID, token TTL

### 5. `docs/guides/youtube-upload-setup.md`

Step-by-step guide covering:
- Google Cloud Console: create project, enable YouTube Data API v3, create OAuth 2.0 credentials (Desktop app type), add test user
- Running `setup_youtube_oauth.py`
- Verifying the channel appears in the console Channels tab
- Assigning the channel to a video and triggering upload
- Why uploads start as unlisted and how to publish

---

## Data Flow (end-to-end)

```
1. Admin runs setup_youtube_oauth.py
   → PlatformCredential row created (encrypted tokens)
   → Channel row created (default_language=en, credential_id=N)

2. Script reaches "completed" status in production pipeline
   → output_path set on generated_scripts row

3. Operator opens Uploads tab → Videos sub-tab
   → Selects channel(s) via ChannelPicker → PUT /api/uploads/videos/{id}/targets

4. Operator clicks Upload
   → POST /api/uploads/videos/{id}/upload
   → UploadService dispatches upload_to_channel_task.delay(video_id, channel_id)

5. Celery worker executes upload_to_channel_task
   → Fetches Channel + PlatformCredential
   → Decrypts tokens with Fernet
   → Injects language="en", privacy_status="unlisted", is_shorts=True into metadata
   → Calls youtube_uploader.upload(video_path, metadata, credentials_dict)
   → youtube_uploader builds request body with #Shorts, unlisted, correct language
   → Resumable upload via YouTube Data API v3
   → Stores returned video_id in upload_targets.platform_id
   → Marks target as "published"

6. Operator opens YouTube Studio → sets video to Public
```

---

## Error Handling

- Token expired at upload time: `google.auth` auto-refreshes if `refresh_token` is present
- Missing `output_path`: task raises `ValueError`, marks target `failed`, job tracked in `pipeline_jobs`
- Missing credential: task raises `ValueError` early — no partial state
- OAuth exchange failure in setup script: prints error, exits non-zero, does not write to DB

---

## Testing

- Unit test `_build_tags` — verify `"Shorts"` always appears first
- Unit test `_build_description` — verify `#Shorts` appended
- Unit test `_niche_to_category("running")` returns `"17"`
- Integration: run `setup_youtube_oauth.py` against local DB (mock token exchange)
- Manual: trigger upload for a test video → verify `upload_targets.platform_id` populated and status = `published`
