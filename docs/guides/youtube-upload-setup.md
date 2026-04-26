# YouTube Shorts Upload — Setup Guide

This guide walks you through connecting a YouTube channel to the console so
the pipeline can automatically upload Shorts videos.

---

## Prerequisites

- Python 3.11+ with `httpx`, `cryptography`, `python-dotenv`, `sqlalchemy` installed
- The console backend running with a valid PostgreSQL connection (`console/.env` configured)
- A Google account that owns the target YouTube channel

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it (e.g. `ai-media-pipeline`) and click **Create**

---

## Step 2: Enable YouTube Data API v3

1. In your project, go to **APIs & Services → Library**
2. Search for **YouTube Data API v3** and click **Enable**

---

## Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. If prompted, configure the OAuth consent screen first:
   - User type: **External**
   - App name: anything (e.g. `AI Media Pipeline`)
   - Add your Google account as a **Test user** (required while in Testing mode)
4. Back in Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: `pipeline-desktop`
   - Click **Create**
5. Copy the **Client ID** and **Client Secret** — you'll need these next

---

## Step 4: Run the OAuth Setup Script

With the console database running, execute:

```bash
cd /path/to/ai-media-automation

python3 scripts/setup_youtube_oauth.py \
  --client-id  "YOUR_CLIENT_ID.apps.googleusercontent.com" \
  --client-secret "YOUR_CLIENT_SECRET" \
  --channel-name "RunningTips"
```

What it does:
- Opens a browser window to Google's OAuth consent screen
- You sign in with the Google account that owns the channel
- After consent, a local server on port 8888 captures the authorization code
- Exchanges the code for access + refresh tokens
- Stores encrypted tokens in `platform_credentials` (PostgreSQL)
- Creates a `Channel` row in `channels` named `RunningTips`

You'll see output like:

```
✓ Credential row ready (id=1)
Opening browser for Google OAuth consent...
Waiting for OAuth callback on http://localhost:8888/callback ...
✓ Received auth code
✓ Tokens stored and encrypted (TTL: 3599s)
✓ Channel created: 'RunningTips' (id=1)

Setup complete!
  Credential ID : 1
  Channel ID    : 1
  Channel Name  : RunningTips
  Language      : en
  Token TTL     : 3599s
```

---

## Step 5: Verify in the Console

1. Open the console → **Uploads** tab → **Channels** sub-tab
2. You should see `RunningTips` listed as `active`
3. Click **Edit** — the **OAuth Credential** dropdown should show `YouTube (connected)`

---

## Step 6: Upload a Video

1. Go to **Uploads** tab → **Videos** sub-tab
2. Find a video with status `completed`
3. Use the channel picker to select `RunningTips`
4. Click **Upload** — a Celery task is queued
5. Watch the pipeline job log or the video row status update to `published`

---

## Step 7: Publish on YouTube

Videos are uploaded as **Unlisted**. To make them public:

1. Go to [YouTube Studio](https://studio.youtube.com/)
2. Find the video (it appears in **Content** as Unlisted)
3. Click **Edit** → change **Visibility** to **Public** → **Save**

---

## Token Refresh

Access tokens expire after ~1 hour. The pipeline auto-refreshes using the stored
refresh token (via `google.auth` in `youtube_uploader.py`). The Celery beat task
`refresh_expiring_tokens` also runs every 30 minutes to proactively refresh tokens
expiring within the hour.

If a refresh fails (e.g. the user revoked access), the upload task marks the target
as `failed`. Re-run the setup script with the same `--channel-name` to re-authorize —
it will update the existing credential row in place.

---

## Running Multiple Channels

Run the script once per channel account. Each run creates or updates one
`PlatformCredential` row and one `Channel` row. If you have two channels on
**different Google accounts**, run the script twice (once per account). If both
channels share the same Google OAuth app but different Google accounts, you'll
need to add each account as a Test user in the OAuth consent screen.

> **Note:** The current schema stores one YouTube `PlatformCredential` per platform.
> If you need tokens for two separate Google accounts simultaneously, you will need
> to extend the model to allow multiple credentials per platform (Sprint 3 scope).
