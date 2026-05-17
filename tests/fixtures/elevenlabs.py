"""Canned ElevenLabs music/SFX responses."""
from __future__ import annotations


def music_generation_response(track_id: str = "music-1") -> dict:
    """Shape returned by ElevenLabs music generation REST endpoint."""
    return {
        "id": track_id,
        "status": "completed",
        "audio_url": f"https://example.test/audio/{track_id}.mp3",
        "duration_s": 180.0,
    }


def sfx_generation_response(sfx_id: str = "sfx-1") -> dict:
    """Shape returned by ElevenLabs SFX generation endpoint."""
    return {
        "id": sfx_id,
        "status": "completed",
        "audio_url": f"https://example.test/sfx/{sfx_id}.mp3",
        "duration_s": 4.0,
    }
