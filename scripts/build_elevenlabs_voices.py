#!/usr/bin/env python3
"""
One-time build script: fetches ElevenLabs voices from the account,
rebuilds the elevenlabs section of config/tts_voices.json grouped by language+gender.

Usage:
    python scripts/build_elevenlabs_voices.py

Requires: ElevenLabs API key in config/api_keys.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
VOICES_PATH = ROOT / "config" / "tts_voices.json"
KEYS_PATH   = ROOT / "config" / "api_keys.json"

# Languages to include. Voices with no language label are treated as English.
INCLUDE_LANGUAGES = {"en", "vi"}
GENDER_FALLBACK   = "other"


def fetch_all_voices(api_key: str) -> list[dict]:
    resp = httpx.get(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("voices", [])


def main():
    api_key = json.loads(KEYS_PATH.read_text())["elevenlabs"]["api_key"]
    if not api_key:
        print("ERROR: ElevenLabs API key not set in config/api_keys.json", file=sys.stderr)
        sys.exit(1)

    print("Fetching account voices from ElevenLabs...")
    voices = fetch_all_voices(api_key)
    print(f"  Found {len(voices)} voices")

    # Group by language → gender
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for v in voices:
        labels = v.get("labels", {})
        lang   = labels.get("language", "en").lower()
        gender = labels.get("gender", GENDER_FALLBACK).lower()
        if lang not in INCLUDE_LANGUAGES:
            continue
        grouped[lang][gender].append({"id": v["voice_id"], "name": v["name"]})

    # Print summary
    for lang in sorted(grouped):
        for gender in sorted(grouped[lang]):
            print(f"  {lang}/{gender}: {len(grouped[lang][gender])} voices")

    # Update the tts_voices.json elevenlabs section
    data = json.loads(VOICES_PATH.read_text())
    data["elevenlabs"] = {lang: dict(genders) for lang, genders in grouped.items()}

    VOICES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nDone. Written to {VOICES_PATH}")


if __name__ == "__main__":
    main()
