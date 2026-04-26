# YouTube Shorts Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five gaps that prevent real end-to-end YouTube Shorts uploads: Shorts metadata, unlisted privacy, per-channel language, credential linking in the channel UI, and a one-time OAuth setup tool.

**Architecture:** Changes stay entirely within existing files — no new tables, services, or routers. The uploader reads `language` and `privacy_status` from the metadata dict; the Celery task injects those from the channel record; the frontend channel modal gains a credential dropdown. A new CLI script handles the one-time OAuth flow using a temporary local HTTP server.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Celery, React 18, `google-api-python-client`, `cryptography` (Fernet), `python-dotenv`, `pytest`

---

## File Map

| Action | File | What changes |
|--------|------|--------------|
| Modify | `uploader/youtube_uploader.py` | `#Shorts` tag/description, `unlisted` default, language from metadata, `running` niche |
| Modify | `console/backend/tasks/upload_tasks.py` | Inject `language` + `privacy_status` from channel row into metadata |
| Modify | `console/frontend/src/pages/UploadsPage.jsx` | `ChannelsTab` — add credential dropdown; change language default to `en` |
| Create | `scripts/setup_youtube_oauth.py` | One-time CLI: OAuth browser flow → encrypted tokens → DB rows |
| Create | `docs/guides/youtube-upload-setup.md` | Step-by-step Google Cloud + script usage guide |
| Create | `tests/test_youtube_uploader.py` | Unit tests for `_build_tags`, `_build_description`, `_niche_to_category` |

---

## Task 1: Fix `youtube_uploader.py` — Shorts metadata

**Files:**
- Modify: `uploader/youtube_uploader.py`
- Test: `tests/test_youtube_uploader.py`

- [ ] **Step 1.1: Create the test file**

```python
# tests/test_youtube_uploader.py
import pytest
from uploader.youtube_uploader import _build_tags, _build_description, _niche_to_category


def test_build_tags_always_has_shorts_first():
    tags = _build_tags({"hashtags": ["running", "fitness"], "niche": "running"})
    assert tags[0] == "Shorts"


def test_build_tags_no_duplicate_shorts():
    tags = _build_tags({"hashtags": ["Shorts", "running"], "niche": "running"})
    assert tags.count("Shorts") == 1


def test_build_tags_empty_metadata():
    tags = _build_tags({})
    assert tags[0] == "Shorts"


def test_build_description_appends_shorts_hashtag():
    desc = _build_description({"description": "Great run!", "hashtags": ["running"]})
    assert "#Shorts" in desc


def test_build_description_shorts_appended_when_no_hashtags():
    desc = _build_description({"description": "Great run!"})
    assert "#Shorts" in desc


def test_niche_to_category_running():
    assert _niche_to_category("running") == "17"


def test_niche_to_category_fitness():
    assert _niche_to_category("fitness") == "17"


def test_niche_to_category_unknown_defaults_to_people_blogs():
    assert _niche_to_category("unknown_niche") == "22"
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```bash
cd /path/to/ai-media-automation
pytest tests/test_youtube_uploader.py -v
```

Expected: all 8 tests FAIL (wrong tags order, no `#Shorts`, no `running` niche)

- [ ] **Step 1.3: Update `uploader/youtube_uploader.py`**

Replace the entire file content with:

```python
"""
YouTube Data API v3 uploader.
Uses OAuth credentials stored (Fernet-encrypted) in the console DB.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SIZE = 10 * 1024 * 1024   # 10MB resumable upload chunks


def upload(
    video_path:  str | Path,
    metadata:    dict,
    credentials: dict,
) -> str:
    """
    Upload a video to YouTube using the Data API v3.

    Args:
        video_path:  Path to video_final.mp4
        metadata:    dict with keys: title, description, hashtags, niche, template,
                     language (default "en"), privacy_status (default "unlisted")
        credentials: dict with keys: client_id, client_secret, access_token, refresh_token

    Returns: YouTube video ID (e.g. 'dQw4w9WgXcQ')
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise RuntimeError(
            "google-api-python-client not installed. "
            "Run: pip install google-api-python-client google-auth"
        )

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    creds = Credentials(
        token=credentials.get("access_token"),
        refresh_token=credentials.get("refresh_token"),
        client_id=credentials.get("client_id"),
        client_secret=credentials.get("client_secret"),
        token_uri="https://oauth2.googleapis.com/token",
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        logger.info("[YouTube] Token refreshed")

    youtube = build("youtube", "v3", credentials=creds)

    title          = metadata.get("title", video_path.stem)[:100]
    description    = _build_description(metadata)
    tags           = _build_tags(metadata)
    category_id    = _niche_to_category(metadata.get("niche", "lifestyle"))
    language       = metadata.get("language", "en")
    privacy_status = metadata.get("privacy_status", "unlisted")

    body = {
        "snippet": {
            "title":           title,
            "description":     description,
            "tags":            tags,
            "categoryId":      category_id,
            "defaultLanguage": language,
        },
        "status": {
            "privacyStatus":           privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=CHUNK_SIZE,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.info(f"[YouTube] Upload progress: {progress}%")

    video_id = response.get("id", "")
    logger.info(f"[YouTube] Uploaded: https://youtube.com/watch?v={video_id}")
    return video_id


def _build_description(metadata: dict) -> str:
    desc      = metadata.get("description", "")
    hashtags  = metadata.get("hashtags", [])
    affiliate = metadata.get("affiliate_links", [])

    parts = [desc]
    if affiliate:
        parts.append("\n🔗 Links:\n" + "\n".join(affiliate))

    # Build hashtag line — always include #Shorts
    ht_tags = [f"#{h.lstrip('#')}" for h in hashtags[:14]]
    if "#Shorts" not in ht_tags:
        ht_tags.append("#Shorts")
    parts.append("\n" + " ".join(ht_tags))

    return "\n\n".join(p for p in parts if p).strip()[:5000]


def _build_tags(metadata: dict) -> list[str]:
    # Shorts must be first so YouTube reliably classifies the video
    tags = ["Shorts"]
    for h in metadata.get("hashtags", []):
        tag = h.lstrip("#")
        if tag != "Shorts":
            tags.append(tag)
    niche = metadata.get("niche", "")
    if niche and niche not in tags:
        tags.append(niche)
    return tags[:500]


def _niche_to_category(niche: str) -> str:
    mapping = {
        "health":       "26",   # Howto & Style
        "fitness":      "17",   # Sports
        "running":      "17",   # Sports
        "lifestyle":    "26",   # Howto & Style
        "finance":      "27",   # Education
        "food":         "26",   # Howto & Style
        "productivity": "27",   # Education
    }
    return mapping.get(niche, "22")   # 22 = People & Blogs


# Legacy alias used by console upload task
def upload_to_youtube(video_path, metadata, credentials) -> str:
    return upload(video_path, metadata, credentials)
```

- [ ] **Step 1.4: Run tests to confirm they pass**

```bash
pytest tests/test_youtube_uploader.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 1.5: Commit**

```bash
git add uploader/youtube_uploader.py tests/test_youtube_uploader.py
git commit -m "feat: youtube uploader — Shorts tags, unlisted default, language from metadata, running niche

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 2: Fix `upload_tasks.py` — inject channel language + privacy

**Files:**
- Modify: `console/backend/tasks/upload_tasks.py:54-61`

- [ ] **Step 2.1: Open `console/backend/tasks/upload_tasks.py` and find the metadata block**

Locate these lines (around line 54–57):

```python
        # Fetch video metadata from the script
        from database.models import GeneratedScript
        script = db.query(GeneratedScript).filter(GeneratedScript.id == video_id).first()
        video_meta = script.script_json.get("video", {}) if script else {}
        video_path = script.output_path if script and hasattr(script, "output_path") else None
```

- [ ] **Step 2.2: Add channel metadata injection after `video_meta` is set**

Replace that block with:

```python
        # Fetch video metadata from the script
        from database.models import GeneratedScript
        script = db.query(GeneratedScript).filter(GeneratedScript.id == video_id).first()
        video_meta = dict(script.script_json.get("video", {})) if script else {}
        video_path = script.output_path if script and hasattr(script, "output_path") else None

        # Inject channel-specific upload settings
        video_meta["language"]       = channel.default_language or "en"
        video_meta["privacy_status"] = "unlisted"
```

- [ ] **Step 2.3: Verify the file looks correct around that block**

```bash
grep -n "language\|privacy_status\|video_meta" console/backend/tasks/upload_tasks.py
```

Expected output includes:
```
56:        video_meta = dict(script.script_json.get("video", {})) if script else {}
59:        video_meta["language"]       = channel.default_language or "en"
60:        video_meta["privacy_status"] = "unlisted"
```

- [ ] **Step 2.4: Commit**

```bash
git add console/backend/tasks/upload_tasks.py
git commit -m "feat: upload task — inject channel language and unlisted privacy into metadata

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 3: Frontend — add credential dropdown to channel modal

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx`

The `ChannelsTab` component starts at line 345. These are the three surgical changes:
1. Add a `credentials` state + fetch on mount
2. Add `credential_id` to form defaults; change `default_language` default to `'en'`
3. Add a `<Select>` for `credential_id` in the modal, showing only credentials for the chosen platform

- [ ] **Step 3.1: Add credentials state and fetch to `ChannelsTab`**

Find the block at the top of `ChannelsTab` (lines 347–366):

```javascript
  const [channels, setChannels]   = useState([])
  const [loading,  setLoading]    = useState(true)
  const [modal,    setModal]      = useState(false)
  const [editing,  setEditing]    = useState(null)
  const [form,     setForm]       = useState({})
  const [toast,    setToast]      = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchApi('/api/channels')
      setChannels(data)
      onChannelsLoaded?.(data)
    } catch { setChannels([]) }
    finally { setLoading(false) }
  }, [onChannelsLoaded])

  useEffect(() => { load() }, [load])
```

Replace with:

```javascript
  const [channels,    setChannels]    = useState([])
  const [credentials, setCredentials] = useState([])
  const [loading,     setLoading]     = useState(true)
  const [modal,       setModal]       = useState(false)
  const [editing,     setEditing]     = useState(null)
  const [form,        setForm]        = useState({})
  const [toast,       setToast]       = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [chData, credData] = await Promise.all([
        fetchApi('/api/channels'),
        fetchApi('/api/credentials'),
      ])
      setChannels(chData)
      setCredentials(credData)
      onChannelsLoaded?.(chData)
    } catch { setChannels([]) }
    finally { setLoading(false) }
  }, [onChannelsLoaded])

  useEffect(() => { load() }, [load])
```

- [ ] **Step 3.2: Update `openCreate` to use `en` default and include `credential_id`**

Find:
```javascript
  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', platform: 'youtube', status: 'active', default_language: 'vi', monetized: false })
    setModal(true)
  }
```

Replace with:
```javascript
  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', platform: 'youtube', status: 'active', default_language: 'en', monetized: false, credential_id: null })
    setModal(true)
  }
```

- [ ] **Step 3.3: Add credential dropdown to the channel modal**

Find the modal's `<div className="space-y-3">` block — specifically the `<Select label="Status" ...>` element (around line 469):

```javascript
          <Select label="Status" value={form.status || 'active'} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
          </Select>
```

Replace with:

```javascript
          <Select label="Status" value={form.status || 'active'} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
          </Select>
          <Select
            label="OAuth Credential"
            value={form.credential_id ?? ''}
            onChange={e => setForm(f => ({ ...f, credential_id: e.target.value ? Number(e.target.value) : null }))}
          >
            <option value="">— None —</option>
            {credentials
              .filter(c => c.platform === (form.platform || 'youtube'))
              .map(c => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.status})
                </option>
              ))}
          </Select>
```

- [ ] **Step 3.4: Verify the app builds without errors**

```bash
cd console/frontend
npm run build 2>&1 | tail -20
```

Expected: build exits 0, no errors about `credentials` or `credential_id`

- [ ] **Step 3.5: Commit**

```bash
git add console/frontend/src/pages/UploadsPage.jsx
git commit -m "feat: channels modal — add OAuth credential dropdown, default language en

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 4: Create `scripts/setup_youtube_oauth.py`

**Files:**
- Create: `scripts/__init__.py` (empty, for import clarity)
- Create: `scripts/setup_youtube_oauth.py`

- [ ] **Step 4.1: Create the `scripts/` package**

```bash
mkdir -p scripts
touch scripts/__init__.py
```

- [ ] **Step 4.2: Create `scripts/setup_youtube_oauth.py`**

```python
#!/usr/bin/env python3
"""
One-time YouTube OAuth setup tool.

Usage:
    python3 scripts/setup_youtube_oauth.py \
        --client-id YOUR_CLIENT_ID \
        --client-secret YOUR_CLIENT_SECRET \
        --channel-name "RunningTips"

Steps:
1. Reads console/.env for DATABASE_URL and FERNET_KEY
2. Creates/updates the YouTube PlatformCredential row
3. Opens a browser to Google's OAuth consent screen
4. Starts a local HTTP server on localhost:8888 to catch the callback
5. Exchanges the auth code for access + refresh tokens
6. Encrypts tokens with Fernet and stores in platform_credentials
7. Creates a Channel row linked to the credential (skips if name already exists)
8. Prints a summary
"""
import argparse
import http.server
import json
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

# ── Env setup ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

env_file = ROOT / "console" / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

DATABASE_URL = os.environ.get("DATABASE_URL")
FERNET_KEY   = os.environ.get("FERNET_KEY")

if not DATABASE_URL:
    sys.exit("ERROR: DATABASE_URL not set. Check console/.env")
if not FERNET_KEY:
    sys.exit("ERROR: FERNET_KEY not set. Check console/.env")

# ── OAuth constants ───────────────────────────────────────────────────────────
REDIRECT_URI   = "http://localhost:8888/callback"
AUTH_ENDPOINT  = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# ── Local callback server ─────────────────────────────────────────────────────
_auth_code: list[str] = []   # shared between server thread and main


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if code:
            _auth_code.append(code)
            body = b"<html><body><h2>Authorization successful! You can close this tab.</h2></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter")

    def log_message(self, *args):
        pass   # suppress server access logs


def _start_callback_server() -> http.server.HTTPServer:
    server = http.server.HTTPServer(("localhost", 8888), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ── DB helpers ────────────────────────────────────────────────────────────────
def _get_db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


def _encrypt(value: str) -> str:
    from cryptography.fernet import Fernet
    return Fernet(FERNET_KEY.encode()).encrypt(value.encode()).decode()


# ── Main flow ─────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Set up YouTube OAuth for a channel")
    parser.add_argument("--client-id",     required=True,  help="Google OAuth2 client ID")
    parser.add_argument("--client-secret", required=True,  help="Google OAuth2 client secret")
    parser.add_argument("--channel-name",  required=True,  help="Display name for this channel in the console")
    parser.add_argument("--language",      default="en",   help="Default language for uploads (default: en)")
    args = parser.parse_args()

    db = _get_db_session()

    try:
        from console.backend.models.credentials import PlatformCredential
        from console.backend.models.channel import Channel

        # 1. Upsert PlatformCredential for youtube
        cred = db.query(PlatformCredential).filter(PlatformCredential.platform == "youtube").first()
        if not cred:
            cred = PlatformCredential(
                platform="youtube",
                name="YouTube",
                auth_type="oauth2",
                auth_endpoint=AUTH_ENDPOINT,
                token_endpoint=TOKEN_ENDPOINT,
                scopes=SCOPES,
                status="disconnected",
            )
            db.add(cred)

        cred.client_id     = args.client_id
        cred.client_secret = _encrypt(args.client_secret)
        cred.redirect_uri  = REDIRECT_URI
        db.flush()
        print(f"✓ Credential row ready (id={cred.id})")

        # 2. Build OAuth URL and open browser
        params = {
            "client_id":     args.client_id,
            "redirect_uri":  REDIRECT_URI,
            "response_type": "code",
            "scope":         " ".join(SCOPES),
            "access_type":   "offline",
            "prompt":        "consent",   # force refresh_token to be issued every time
        }
        url = f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

        server = _start_callback_server()
        print(f"\nOpening browser for Google OAuth consent...\n{url}\n")
        webbrowser.open(url)

        # 3. Wait for callback (timeout 120s)
        print("Waiting for OAuth callback on http://localhost:8888/callback ...")
        deadline = time.time() + 120
        while not _auth_code and time.time() < deadline:
            time.sleep(0.5)
        server.shutdown()

        if not _auth_code:
            sys.exit("ERROR: Timed out waiting for OAuth callback (120s)")

        code = _auth_code[0]
        print(f"✓ Received auth code")

        # 4. Exchange code for tokens
        resp = httpx.post(
            TOKEN_ENDPOINT,
            data={
                "code":          code,
                "client_id":     args.client_id,
                "client_secret": args.client_secret,
                "redirect_uri":  REDIRECT_URI,
                "grant_type":    "authorization_code",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            sys.exit(f"ERROR: Token exchange failed ({resp.status_code}): {resp.text}")

        tokens = resp.json()
        if "access_token" not in tokens:
            sys.exit(f"ERROR: No access_token in response: {tokens}")

        # 5. Store encrypted tokens
        cred.access_token  = _encrypt(tokens["access_token"])
        cred.refresh_token = _encrypt(tokens["refresh_token"]) if "refresh_token" in tokens else cred.refresh_token
        expires_in         = tokens.get("expires_in", 3600)
        cred.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        cred.last_refreshed   = datetime.now(timezone.utc)
        cred.status           = "connected"
        db.flush()
        print(f"✓ Tokens stored and encrypted (TTL: {expires_in}s)")

        # 6. Upsert Channel row
        channel = db.query(Channel).filter(Channel.name == args.channel_name).first()
        if not channel:
            channel = Channel(
                name=args.channel_name,
                platform="youtube",
                credential_id=cred.id,
                default_language=args.language,
                status="active",
            )
            db.add(channel)
            db.flush()
            print(f"✓ Channel created: '{args.channel_name}' (id={channel.id})")
        else:
            channel.credential_id  = cred.id
            channel.default_language = args.language
            print(f"✓ Channel updated: '{args.channel_name}' (id={channel.id})")

        db.commit()

        print(f"""
Setup complete!
  Credential ID : {cred.id}
  Channel ID    : {channel.id}
  Channel Name  : {channel.name}
  Language      : {channel.default_language}
  Token TTL     : {expires_in}s

Next steps:
  1. Open the console → Uploads tab → Channels
  2. You should see '{args.channel_name}' listed with status 'active'
  3. Assign it as an upload target for a completed video and click Upload
""")

    except Exception as e:
        db.rollback()
        sys.exit(f"ERROR: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4.3: Make it executable**

```bash
chmod +x scripts/setup_youtube_oauth.py
```

- [ ] **Step 4.4: Smoke-test argument parsing (no DB needed)**

```bash
python3 scripts/setup_youtube_oauth.py --help
```

Expected: shows usage with `--client-id`, `--client-secret`, `--channel-name`, `--language`

```bash
python3 scripts/setup_youtube_oauth.py
```

Expected: exits with error `the following arguments are required: --client-id, --client-secret, --channel-name`

- [ ] **Step 4.5: Commit**

```bash
git add scripts/__init__.py scripts/setup_youtube_oauth.py
git commit -m "feat: add setup_youtube_oauth.py — one-time OAuth CLI setup tool

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Task 5: Write `docs/guides/youtube-upload-setup.md`

**Files:**
- Create: `docs/guides/youtube-upload-setup.md`

- [ ] **Step 5.1: Create the guide**

```bash
mkdir -p docs/guides
```

Create `docs/guides/youtube-upload-setup.md` with the following content:

````markdown
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
````

- [ ] **Step 5.2: Commit**

```bash
git add docs/guides/youtube-upload-setup.md
git commit -m "docs: add YouTube Shorts upload setup guide

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `#Shorts` tag always prepended | Task 1 |
| `#Shorts` appended to description | Task 1 |
| `privacyStatus = unlisted` | Task 1 (uploader default) + Task 2 (task injection) |
| Language from `channel.default_language` | Task 1 (metadata key) + Task 2 (injection) |
| `running` niche → category 17 | Task 1 |
| `credential_id` in channel modal | Task 3 |
| `default_language` defaults to `en` | Task 3 |
| OAuth setup CLI | Task 4 |
| Google Cloud setup guide | Task 5 |
| Unit tests for uploader helpers | Task 1 |

All spec requirements covered. ✓
