#!/usr/bin/env python3
"""
One-time build script: fetches name/metadata for each specific ElevenLabs voice ID,
writes the elevenlabs section of config/tts_voices.json.

Usage:
    python scripts/build_elevenlabs_voices.py

Requires: ElevenLabs API key in config/api_keys.json
"""
import json
import sys
from pathlib import Path

import httpx

ROOT        = Path(__file__).parent.parent
VOICES_PATH = ROOT / "config" / "tts_voices.json"
KEYS_PATH   = ROOT / "config" / "api_keys.json"

# Hardcoded voice IDs grouped by language + gender
VOICE_IDS = {
    "en": {
        "male": [
            "UgBBYS2sOqTuMpoF3BR0",
            "NOpBlnGInO9m6vDvFkFC",
            "EkK5I93UQWFDigLMpZcX",
            "uju3wxzG5OhpWcoi3SMy",
            "NFG5qt843uXKj4pFvR7C",
        ],
        "female": [
            "56AoDkrOh6qfVPDXZ7Pt",
            "tnSpp4vdxKPjI9w0GnoV",
            "Z3R5wn05IrDiVCyEkUrK",
            "kPzsL2i3teMYv0FxEYQ6",
            "aMSt68OGf4xUZAnLpTU8",
            "RILOU7YmBhvwJGDGjNmP",
            "flHkNRp1BlvT73UL6gyz",
            "KoVIHoyLDrQyd4pGalbs",
            "yj30vwTGJxSHezdAGsv9",
        ],
    },
    "vi": {
        "female": [
            "A5w1fw5x0uXded1LDvZp",
            "d5HVupAWCwe4e6GvMCAL",
            "DvG3I1kDzdBY3u4EzYh6",
            "foH7s9fX31wFFH2yqrFa",
            "jdlxsPOZOHdGEfcItXVu",
            "BlZK9tHPU6XXjwOSIiYA",
            "a3AkyqGG4v8Pg7SWQ0Y3",
            "HQZkBNMmZF5aISnrU842",
            "qByVAGjXwGlkcRDJoiHg",
        ],
        "male": [
            "3VnrjnYrskPMDsapTr8X",
            "aN7cv9yXNrfIR87bDmyD",
            "ueSxRO0nLF1bj93J2hVt",
            "UsgbMVmY3U59ijwK5mdh",
            "XBDAUT8ybuJTTCoOLSUj",
            "9EE00wK5qV6tPtpQIxvy",
        ],
    },
}


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
    result: dict = {}

    for lang, genders in VOICE_IDS.items():
        result[lang] = {}
        for gender, ids in genders.items():
            print(f"Fetching {lang}/{gender} ({len(ids)} voices)...")
            voices = []
            for voice_id in ids:
                name = fetch_voice_name(api_key, voice_id)
                voices.append({"id": voice_id, "name": name})
                print(f"  {voice_id} → {name}")
            result[lang][gender] = voices

    data["elevenlabs"] = result
    VOICES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nDone. Written to {VOICES_PATH}")


if __name__ == "__main__":
    main()
