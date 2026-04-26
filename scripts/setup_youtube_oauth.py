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
            channel.credential_id    = cred.id
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
