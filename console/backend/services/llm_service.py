"""LLMService — config CRUD + per-provider status and quota."""
import logging
from datetime import datetime, timezone

import httpx

from config import api_config

logger = logging.getLogger(__name__)


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
    for provider in ("elevenlabs", "suno", "pexels"):
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
            "suno":       self._simple_status(cfg.get("suno", {}).get("api_key", "")),
            "pexels":     self._simple_status(cfg.get("pexels", {}).get("api_key", "")),
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }

    def get_quota(self, db=None) -> dict:
        cfg = api_config.get_config()
        result = {}

        # Gemini script — Redis-based rate limiter
        try:
            from rag.rate_limiter import get_gemini_limiter
            result["gemini_script"] = get_gemini_limiter().usage()
        except Exception as e:
            result["gemini_script"] = {"error": str(e)}

        # ElevenLabs — subscription endpoint
        el_key = cfg.get("elevenlabs", {}).get("api_key", "")
        if el_key:
            try:
                resp = httpx.get(
                    "https://api.elevenlabs.io/v1/user/subscription",
                    headers={"xi-api-key": el_key},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                result["elevenlabs"] = {
                    "characters_used":  data.get("character_count", 0),
                    "characters_limit": data.get("character_limit", 0),
                }
            except Exception as e:
                result["elevenlabs"] = {"error": str(e)}
        else:
            result["elevenlabs"] = {"error": "API key not configured"}

        # Suno — count from DB
        if db is not None:
            try:
                from database.models import MusicTrack
                count = db.query(MusicTrack).filter(MusicTrack.provider == "suno").count()
                result["suno"] = {"tracks_generated": count}
            except Exception as e:
                result["suno"] = {"error": str(e)}
        else:
            result["suno"] = {"tracks_generated": None}

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
