"""LLMService — LLM mode config, Gemini quota, Ollama status."""
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MODES = {
    "gemini_only": {
        "label": "Gemini Only",
        "description": "All generation routed through Google Gemini. Highest quality, uses API quota.",
        "cost": "$$",
        "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
    },
    "ollama_only": {
        "label": "Ollama Only",
        "description": "All generation routed through local Ollama. No API cost, slower.",
        "cost": "Free",
        "models": ["llama3", "mistral"],
    },
    "hybrid": {
        "label": "Hybrid (Auto)",
        "description": "Short tasks use Ollama, complex/bulk tasks use Gemini. Balances cost and speed.",
        "cost": "$",
        "models": ["gemini-1.5-flash", "llama3"],
    },
    "hybrid_prefer_local": {
        "label": "Hybrid (Prefer Local)",
        "description": "Use Ollama by default, fall back to Gemini only when local model fails.",
        "cost": "¢",
        "models": ["llama3", "gemini-1.5-flash"],
    },
}


class LLMService:

    def get_status(self) -> dict:
        mode = self._current_mode()
        return {
            "mode":        mode,
            "mode_info":   MODES.get(mode, {}),
            "all_modes":   MODES,
            "gemini":      self._gemini_status(),
            "ollama":      self._ollama_status(),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }

    def set_mode(self, mode: str) -> dict:
        if mode not in MODES:
            raise ValueError(f"Mode must be one of: {list(MODES.keys())}")
        # In a real system this would write to config.py or DB
        os.environ["LLM_STRATEGY"] = mode
        logger.info(f"LLM mode changed to: {mode}")
        return {"mode": mode, "mode_info": MODES[mode]}

    def get_quota(self) -> dict:
        return {"gemini": self._gemini_status(), "ollama": self._ollama_status()}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _current_mode(self) -> str:
        return os.environ.get("LLM_STRATEGY", "hybrid")

    def _gemini_status(self) -> dict:
        try:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                return {"available": False, "error": "GEMINI_API_KEY not set"}
            genai.configure(api_key=api_key)
            models = [m.name for m in genai.list_models()]
            return {
                "available": True,
                "models":    models[:5],
                "api_key_set": True,
            }
        except ImportError:
            return {"available": False, "error": "google-generativeai not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _ollama_status(self) -> dict:
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"available": True, "models": models, "endpoint": "localhost:11434"}
            return {"available": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"available": False, "error": str(e)}
