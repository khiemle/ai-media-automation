import copy
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "api_keys.json"
_CACHE_TTL = 30.0
_cache: dict = {}
_cache_time: float = 0.0

_DEFAULT: dict = {
    "gemini": {
        "script": {"api_key": "", "model": "gemini-2.5-flash"},
        "media":  {"api_key": "", "model": "gemini-2.0-flash-exp"},
        "music":  {"api_key": "", "model": "lyria-3-clip-preview"},
    },
    "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": "eleven_flash_v2_5"},
    "suno":   {"api_key": "", "model": "V4_5"},
    "pexels": {"api_key": ""},
    "kokoro": {"default_voice_en": "af_heart"},
}


def get_config() -> dict:
    global _cache, _cache_time
    now = time.monotonic()
    if _cache and now - _cache_time < _CACHE_TTL:
        return copy.deepcopy(_cache)
    if not _CONFIG_PATH.exists():
        logger.warning("config/api_keys.json not found — all API keys will be empty")
        return copy.deepcopy(_DEFAULT)
    try:
        data = json.loads(_CONFIG_PATH.read_text())
        _cache = data
        _cache_time = now
        return copy.deepcopy(_cache)
    except Exception as e:
        logger.error("Failed to read config/api_keys.json: %s", e)
        return copy.deepcopy(_cache) if _cache else copy.deepcopy(_DEFAULT)


def save_config(data: dict) -> None:
    global _cache, _cache_time
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))
    _cache = copy.deepcopy(data)
    _cache_time = time.monotonic()
