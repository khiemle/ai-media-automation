"""
LLM Router — Gemini 2.5 Flash only.
Raises RuntimeError on any failure — no silent fallback.
"""
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env", override=False)

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")

try:
    from google import genai
except ImportError:
    genai = None


class GeminiRouter:
    """Generates text via Gemini. Raises RuntimeError on any failure."""

    def __init__(self):
        from rag.rate_limiter import get_gemini_limiter
        self._limiter = get_gemini_limiter()

    def generate(self, prompt: str, template: str | None = None, expect_json: bool = True) -> dict | str:
        """
        Call Gemini and return parsed dict (expect_json=True) or raw string.
        Raises RuntimeError if Gemini is unavailable or returns an error.
        """
        if not GEMINI_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        if genai is None:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")

        client = genai.Client(api_key=GEMINI_KEY)
        logger.info(f"[GeminiRouter] model={GEMINI_MODEL} template={template}")

        for attempt in range(3):
            try:
                self._limiter.wait_if_needed()
                config = genai.types.GenerateContentConfig(temperature=0.8)
                if expect_json:
                    config = genai.types.GenerateContentConfig(
                        temperature=0.8,
                        response_mime_type="application/json",
                    )
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=config,
                )
                raw = response.text
                if expect_json:
                    return self._parse_json(raw)
                return raw
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"[GeminiRouter] Attempt {attempt + 1} failed: {e}, retrying")
                    time.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Gemini failed after 3 attempts: {e}") from e
        return {}  # unreachable

    def status(self) -> dict:
        return {
            "model":           GEMINI_MODEL,
            "gemini_key_set":  bool(GEMINI_KEY),
            "gemini_usage":    self._limiter.usage(),
        }

    def _parse_json(self, raw: str) -> dict | str:
        if not raw:
            return {}
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[GeminiRouter] Failed to parse JSON response, returning raw string")
            return raw


# Singleton — reuse across the process lifetime
_router: GeminiRouter | None = None


def get_router() -> GeminiRouter:
    global _router
    if _router is None:
        _router = GeminiRouter()
    return _router


# Backwards compatibility alias
LLMRouter = GeminiRouter
