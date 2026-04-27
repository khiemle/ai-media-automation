#!/usr/bin/env python3
"""
One-time build script: fetches ElevenLabs voice names for given IDs,
writes the elevenlabs section of config/tts_voices.json.

Usage:
    python scripts/build_elevenlabs_voices.py

Requires: ElevenLabs API key in config/api_keys.json
"""
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
VOICES_PATH = ROOT / "config" / "tts_voices.json"
KEYS_PATH   = ROOT / "config" / "api_keys.json"


def fetch_voice_name(api_key: str, voice_id: str) -> str:
    try:
        resp = httpx.get(
            f"https://api.elevenlabs.io/v1/voices/{voice_id}",
            headers={"xi-api-key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("name", "Unknown")
    except Exception as e:
        print(f"  WARN: {voice_id} — {e}", file=sys.stderr)
        return "Unknown"


def main():
    api_key = json.loads(KEYS_PATH.read_text())["elevenlabs"]["api_key"]
    if not api_key:
        print("ERROR: ElevenLabs API key not set in config/api_keys.json", file=sys.stderr)
        sys.exit(1)

    data = json.loads(VOICES_PATH.read_text())
    el = data["elevenlabs"]

    for lang, genders in el.items():
        for gender, voices in genders.items():
            print(f"Fetching {lang}/{gender}...")
            for voice in voices:
                name = fetch_voice_name(api_key, voice["id"])
                voice["name"] = name
                print(f"  {voice['id']} → {name}")

    VOICES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nDone. Written to {VOICES_PATH}")


if __name__ == "__main__":
    main()
