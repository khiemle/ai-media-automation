"""LLMService — config CRUD + per-provider status and quota."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path as _Path
from typing import Any, Optional

from pydantic import BaseModel

import httpx

from config import api_config

logger = logging.getLogger(__name__)

_VOICES_PATH = _Path(__file__).parent.parent.parent.parent / "config" / "tts_voices.json"


def _mask(key: str) -> str:
    if not key:
        return ""
    return "••••" + key[-4:] if len(key) > 4 else "••••"


def _mask_config(cfg: dict) -> dict:
    import copy
    masked = copy.deepcopy(cfg)
    for use_case in ("script", "media", "music"):
        if use_case in masked.get("gemini", {}):
            masked["gemini"][use_case]["api_key"] = _mask(
                cfg["gemini"][use_case].get("api_key", "")
            )
    for provider in ("elevenlabs", "sunoapi", "pexels"):
        if provider in masked:
            masked[provider]["api_key"] = _mask(
                cfg[provider].get("api_key", "")
            )
    return masked


class LLMService:

    def get_config_masked(self) -> dict:
        return _mask_config(api_config.get_config())

    def get_config_raw(self) -> dict:
        return api_config.get_config()

    def save_config(self, data: dict) -> None:
        api_config.save_config(data)

    def get_status(self) -> dict:
        cfg = api_config.get_config()
        g = cfg.get("gemini", {})
        return {
            "gemini": {
                "script": self._gemini_script_status(g.get("script", {})),
                "media":  self._simple_status(g.get("media", {}).get("api_key", ""), g.get("media", {}).get("model", "")),
                "music":  self._simple_status(g.get("music", {}).get("api_key", ""), g.get("music", {}).get("model", "")),
            },
            "elevenlabs": self._simple_status(cfg.get("elevenlabs", {}).get("api_key", "")),
            "sunoapi":   self._simple_status(cfg.get("sunoapi", {}).get("api_key", "")),
            "pexels":     self._simple_status(cfg.get("pexels", {}).get("api_key", "")),
            "kokoro":     {"available": True},
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }

    def get_voices(self) -> dict:
        try:
            return json.loads(_VOICES_PATH.read_text())
        except Exception:
            return {}

    def get_quota(self, db=None) -> dict:
        cfg = api_config.get_config()
        result = {}

        # Gemini script — Redis-based rate limiter
        try:
            from rag.rate_limiter import get_gemini_limiter
            result["gemini_script"] = get_gemini_limiter().usage()
        except Exception as e:
            result["gemini_script"] = {"error": str(e)}

        # ElevenLabs — try /user/subscription, then /user; TTS-only keys
        # lack user_read scope and can't access either endpoint.
        el_key = cfg.get("elevenlabs", {}).get("api_key", "")
        if el_key:
            try:
                for url in (
                    "https://api.elevenlabs.io/v1/user/subscription",
                    "https://api.elevenlabs.io/v1/user",
                ):
                    resp = httpx.get(url, headers={"xi-api-key": el_key}, timeout=10)
                    if resp.status_code not in (401, 403):
                        break

                if resp.status_code in (401, 403):
                    # Key is valid but lacks user_read scope (e.g. TTS-only key)
                    result["elevenlabs"] = {"scope_restricted": True}
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    subscription = data.get("subscription", data)
                    result["elevenlabs"] = {
                        "characters_used":  subscription.get("character_count", 0),
                        "characters_limit": subscription.get("character_limit", 0),
                    }
            except Exception as e:
                result["elevenlabs"] = {"error": str(e)}
        else:
            result["elevenlabs"] = {"error": "API key not configured"}

        # Suno — real API credits
        suno_key = cfg.get("sunoapi", {}).get("api_key", "")
        if suno_key:
            try:
                resp = httpx.get(
                    "https://api.sunoapi.org/api/v1/generate/credit",
                    headers={"Authorization": f"Bearer {suno_key}"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                result["sunoapi"] = {"credits": data.get("credits", 0)}
            except Exception as e:
                result["sunoapi"] = {"error": str(e)}
        else:
            result["sunoapi"] = {"error": "API key not configured"}

        # Pexels — lightweight ping
        pexels_key = cfg.get("pexels", {}).get("api_key", "")
        if pexels_key:
            try:
                resp = httpx.get(
                    "https://api.pexels.com/v1/search",
                    params={"query": "nature", "per_page": 1},
                    headers={"Authorization": pexels_key},
                    timeout=10,
                )
                resp.raise_for_status()
                result["pexels"] = {"status": "ok"}
            except Exception as e:
                result["pexels"] = {"status": str(e)}
        else:
            result["pexels"] = {"status": "API key not configured"}

        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _gemini_script_status(self, script_cfg: dict) -> dict:
        api_key = script_cfg.get("api_key", "")
        model   = script_cfg.get("model", "")
        if not api_key:
            return {"api_key_set": False, "available": False, "model": model, "models": []}
        try:
            models = self._fetch_gemini_models(api_key)
            return {"api_key_set": True, "available": True, "model": model, "models": models}
        except Exception as e:
            return {"api_key_set": True, "available": False, "model": model, "models": [], "error": str(e)}

    def _simple_status(self, api_key: str, model: str = "") -> dict:
        key_set = bool(api_key)
        result = {"api_key_set": key_set, "available": key_set}
        if model:
            result["model"] = model
        return result

    def _fetch_gemini_models(self, api_key: str) -> list[str]:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            names = []
            for m in client.models.list():
                name = getattr(m, "name", "") or ""
                supported = getattr(m, "supported_actions", None) or getattr(m, "supportedActions", None)
                if supported is not None:
                    if "generateContent" not in supported:
                        continue
                elif "gemini" not in name.lower() or "embedding" in name.lower():
                    continue
                names.append(name.replace("models/", ""))
            return sorted(set(names))
        except Exception as e:
            logger.warning("Could not fetch Gemini model list: %s", e)
            return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]


# ── Autofill helpers ───────────────────────────────────────────────────────────


class _MusicAutofill(BaseModel):
    title: Optional[str] = None
    niches: Optional[list[str]] = None
    moods: Optional[list[str]] = None
    genres: Optional[list[str]] = None
    volume: Optional[float] = None
    quality_score: Optional[float] = None
    is_vocal: Optional[bool] = None


class _SFXAutofill(BaseModel):
    title: Optional[str] = None
    sound_type: Optional[str] = None


class _AssetAutofill(BaseModel):
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    source: Optional[str] = None


_MUSIC_PROMPT = """\
You are a music metadata assistant. Given information about an audio file, suggest appropriate metadata.

File information:
- Filename: {filename}
- File size: {file_size_bytes} bytes
- MIME type: {mime_type}
- Duration: {duration}

User's current input (treat as strong hints):
{form_section}

Return ONLY valid JSON — no prose, no markdown fences:
{{
  "title": "descriptive track title",
  "niches": [],
  "moods": [],
  "genres": [],
  "volume": 0.15,
  "quality_score": 80,
  "is_vocal": false
}}

Allowed moods (only pick from this list): uplifting, calm_focus, energetic, dramatic, neutral
Allowed genres (only pick from this list): pop, rock, electronic, jazz, classical, hip-hop, ambient, cinematic

Rules:
- Use filename and any user hints to infer title, moods, genres, and niches
- Niches are free-form strings (e.g. study, sleep, fitness, gaming, meditation, relaxation)
- Keep volume at 0.15 and quality_score at 80 unless the filename strongly implies otherwise
- Set is_vocal to true only if the filename contains words like vocal, voice, singer, lyrics, acapella
"""

_SFX_PROMPT = """\
You are a sound effects metadata assistant. Given information about a sound file, suggest metadata.

File information:
- Filename: {filename}
- File size: {file_size_bytes} bytes
- MIME type: {mime_type}

User's current input (treat as strong hints):
{form_section}

Return ONLY valid JSON — no prose, no markdown fences:
{{
  "title": "descriptive sound title",
  "sound_type": "category_type"
}}

Known sound types: rain_heavy, rain_light, rain_drizzle, thunder, thunder_rumble,
stream, ocean_waves, river, waterfall, fire_crackle, fire_roar,
forest_ambience, birds, birds_morning, wind_light, wind_heavy,
city_ambience, traffic, crowd_murmur, cafe_ambience, keyboard_typing,
pink_noise, white_noise, brown_noise, lfo_pulse

Rules:
- Use the filename as the primary signal for both title and sound_type
- Pick the closest match from the known list; if none fits, create a descriptive snake_case type
"""

_ASSET_PROMPT = """\
You are a media asset metadata assistant. Given information about a media file, suggest metadata.

File information:
- Filename: {filename}
- File size: {file_size_bytes} bytes
- MIME type: {mime_type}
- Asset type: {asset_type}

User's current input (treat as strong hints):
{form_section}

Return ONLY valid JSON — no prose, no markdown fences:
{{
  "description": "brief description of what the asset likely shows",
  "keywords": ["keyword1", "keyword2"],
  "source": "manual"
}}

Allowed sources: manual, midjourney, runway, pexels, veo, stock

Rules:
- Infer description and keywords from the filename
- Use 3-7 concise keywords
- Only suggest a non-"manual" source if the filename clearly contains midjourney, pexels, veo, or runway
"""


class AutofillPromptBuilder:
    def build(self, modal_type: str, metadata: dict[str, Any], form_values: dict[str, Any]) -> str:
        form_section = "\n".join(
            f"- {k}: {v}" for k, v in form_values.items() if v not in (None, "", [], {})
        ) or "(none yet)"

        if modal_type == "music":
            dur = f"{metadata['duration_s']}s" if metadata.get("duration_s") else "unknown"
            return _MUSIC_PROMPT.format(
                filename=metadata["filename"],
                file_size_bytes=metadata["file_size_bytes"],
                mime_type=metadata["mime_type"],
                duration=dur,
                form_section=form_section,
            )
        if modal_type == "sfx":
            return _SFX_PROMPT.format(
                filename=metadata["filename"],
                file_size_bytes=metadata["file_size_bytes"],
                mime_type=metadata["mime_type"],
                form_section=form_section,
            )
        if modal_type == "asset":
            asset_type = "image" if (metadata.get("mime_type") or "").startswith("image/") else "video"
            return _ASSET_PROMPT.format(
                filename=metadata["filename"],
                file_size_bytes=metadata["file_size_bytes"],
                mime_type=metadata["mime_type"],
                asset_type=asset_type,
                form_section=form_section,
            )
        raise ValueError(f"Unknown modal_type: {modal_type}")


class AutofillResponseParser:
    _SCHEMAS: dict[str, type[BaseModel]] = {
        "music": _MusicAutofill,
        "sfx": _SFXAutofill,
        "asset": _AssetAutofill,
    }

    def parse(self, modal_type: str, raw: dict | str) -> dict:
        schema_cls = self._SCHEMAS.get(modal_type)
        if schema_cls is None:
            return {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return {}
        if not isinstance(raw, dict):
            return {}
        try:
            return schema_cls.model_validate(raw).model_dump()
        except Exception:
            return {}
