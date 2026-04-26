"""LLMService — Gemini-only provider with extensible PROVIDER_REGISTRY."""
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROVIDER_REGISTRY = {
    "gemini": {
        "label": "Google Gemini",
        "description": "Cloud LLM via Google AI Studio API.",
        "fetch_models_method": "_fetch_gemini_models",
    },
    # To add a new provider: add an entry here and a corresponding
    # _fetch_<provider>_models() method below.
}


class LLMService:

    def get_status(self) -> dict:
        provider = self._current_provider()
        model    = self._current_model()
        gemini   = self._gemini_status()
        return {
            "provider":          provider,
            "model":             model,
            "providers_metadata": PROVIDER_REGISTRY,
            "gemini":            gemini,
            "timestamp":         datetime.now(timezone.utc).isoformat(),
        }

    def set_model(self, provider: str, model_name: str) -> dict:
        if provider not in PROVIDER_REGISTRY:
            raise ValueError(f"Unknown provider '{provider}'. Available: {list(PROVIDER_REGISTRY.keys())}")
        os.environ["LLM_PROVIDER"] = provider
        os.environ["LLM_MODEL"]    = model_name
        # Also update the env var that rag/llm_router.py reads
        os.environ["GEMINI_MODEL"] = model_name
        logger.info(f"LLM model set to: {provider}/{model_name}")
        return {"provider": provider, "model": model_name}

    def get_quota(self) -> dict:
        try:
            from rag.rate_limiter import get_gemini_limiter
            return {"gemini": get_gemini_limiter().usage()}
        except Exception as e:
            return {"gemini": {"error": str(e)}}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _current_provider(self) -> str:
        return os.environ.get("LLM_PROVIDER", "gemini")

    def _current_model(self) -> str:
        return os.environ.get("LLM_MODEL", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))

    def _gemini_status(self) -> dict:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"available": False, "error": "GEMINI_API_KEY not set", "api_key_set": False, "models": []}
        try:
            models = self._fetch_gemini_models(api_key)
            return {"available": True, "api_key_set": True, "models": models}
        except Exception as e:
            return {"available": False, "api_key_set": True, "error": str(e), "models": []}

    def _fetch_gemini_models(self, api_key: str | None = None) -> list[str]:
        """Fetch available Gemini models that support generateContent."""
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        try:
            from google import genai
            client = genai.Client(api_key=key)
            names = []
            for m in client.models.list():
                name = getattr(m, 'name', '') or ''
                # Filter to text-generation models; skip embedding/vision-only
                supported = getattr(m, 'supported_actions', None)
                if supported is None:
                    supported = getattr(m, 'supportedActions', None)
                if supported is not None:
                    if 'generateContent' not in supported:
                        continue
                elif 'gemini' not in name.lower() or 'embedding' in name.lower():
                    continue
                # Strip "models/" prefix if present
                short = name.replace("models/", "")
                names.append(short)
            return sorted(set(names))
        except Exception as e:
            logger.warning(f"Could not fetch Gemini model list: {e}")
            # Return safe defaults if API call fails
            return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
