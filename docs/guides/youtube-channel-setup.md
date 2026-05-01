# YouTube Channel Setup Guide

This guide covers connecting one or more YouTube channels to the console so the
pipeline can automatically upload Long-form and Shorts videos.

---

## Recommended path: In-App Wizard

Open the console → **Uploads** tab → **Credentials** sub-tab → click **"+ Add YouTube Channel"**.

The wizard walks through all 7 steps with links and forms. Run it once per Google account.

---

## Manual path: CLI script

For automation, CI, or headless setups:

```bash
cd /path/to/ai-media-automation

python3 scripts/setup_youtube_oauth.py \
  --client-id  "YOUR_CLIENT_ID.apps.googleusercontent.com" \
  --client-secret "YOUR_CLIENT_SECRET" \
  --channel-name "MyChannel"
```

Run once per channel account.

---

## Prerequisites

- Python 3.11+ with `httpx`, `cryptography`, `python-dotenv`, `sqlalchemy`
- Console backend running with a valid PostgreSQL connection (`console/.env` configured)
- A Google account that owns the target YouTube channel

---

## Step 1 — Create a Google Cloud Project

[Open Google Cloud Console →](https://console.cloud.google.com/projectcreate)

Click **Select a project** → **New Project**. Name it (e.g. `ai-media-pipeline`) → **Create**.

---

## Step 2 — Enable YouTube Data API v3

[Open YouTube Data API v3 →](https://console.cloud.google.com/apis/library/youtube.googleapis.com)

Click **Enable**.

---

## Step 3 — Create OAuth 2.0 Credentials

[Open Credentials Page →](https://console.cloud.google.com/apis/credentials)

1. **Create Credentials → OAuth client ID**
2. Configure OAuth consent screen if prompted:
   - User Type: **External**
   - App name: anything (e.g. `AI Media Pipeline`)
   - Add your Google account as a **Test user** (required while in Testing mode)
3. Application type: **Web Application**
4. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:8080/api/credentials/youtube/callback
   ```
   *(Replace port if your backend runs on a different port.)*
5. Copy the **Client ID** and **Client Secret**.

> **Testing mode note:** While your OAuth app is in Testing mode, only accounts listed as
> Test Users can authorize. To add users: [OAuth consent screen → Test users](https://console.cloud.google.com/apis/credentials/consent).
> For production use (>100 users), submit the app for verification.

---

## Step 4 — Authorize & Connect

**In-app wizard:** Enter Client ID, Client Secret, and a nickname. Click "Open Google Authorization →", sign in, then the wizard auto-advances.

**CLI:** Run the script above. It opens a browser, handles the OAuth flow on `http://localhost:8888/callback`, and stores encrypted tokens in PostgreSQL.

---

## Multiple Channels

Run the wizard (or CLI script) **once per Google account**. Each run creates a separate
`PlatformCredential` row and a `Channel` row. Channels from different Google accounts
each need their own OAuth consent.

If both channels share the same Google OAuth app but different Google accounts, add each
account as a Test User in the OAuth consent screen.

---

## Token Refresh

Access tokens expire after ~1 hour. The pipeline auto-refreshes using the stored
refresh token. The Celery beat task `refresh_expiring_tokens` runs every 30 minutes.

If a refresh fails (user revoked access): re-run the wizard or CLI script with the same
channel name to re-authorize in place.

---

## Uploading

1. Go to **Uploads** tab → **Videos** sub-tab
2. Filter by format (Short or YouTube Long)
3. Use the channel picker to select the target channel
4. Click **Upload** — a Celery task is queued

Videos are uploaded as **Unlisted**. To publish:
1. Open [YouTube Studio](https://studio.youtube.com/) → Content
2. Find the video → Edit → Visibility → **Public** → Save
