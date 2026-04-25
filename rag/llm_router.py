"""
LLM Router — dispatches generation requests to local (Ollama/Qwen) or cloud (Gemini).

Modes:
  local   — Qwen2.5 via Ollama only
  gemini  — Gemini 2.5 Flash only
  auto    — Gemini if quota available, else Ollama fallback
  hybrid  — route by template: hook/cta → Gemini, body → local
"""
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# Load env files before reading any env vars (handles direct module import)
_root = Path(__file__).parent.parent
load_dotenv(_root / ".env", override=False)

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL    = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL  = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
GEMINI_MODEL  = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_KEY    = os.environ.get("GEMINI_API_KEY", "")
LLM_MODE      = os.environ.get("LLM_MODE", "auto")

# Templates that benefit most from Gemini quality
GEMINI_TEMPLATES = {"tiktok_viral", "shorts_hook"}
LOCAL_TEMPLATES  = {"tiktok_30s", "youtube_clean"}


class LLMRouter:
    """Main LLM dispatch class. Instantiate once and reuse."""

    def __init__(self, mode: str | None = None):
        self.mode = mode or LLM_MODE
        from rag.rate_limiter import get_gemini_limiter, get_ollama_limiter
        self._gemini_limiter = get_gemini_limiter()
        self._ollama_limiter = get_ollama_limiter()

    # ── Public API ─────────────────────────────────────────────────────────

    def generate(self, prompt: str, template: str | None = None, expect_json: bool = True) -> dict | str:
        """
        Generate text from the appropriate LLM.
        Returns parsed dict if expect_json=True and LLM returns valid JSON,
        otherwise returns raw string.
        """
        backend = self._select_backend(template)
        logger.info(f"[LLMRouter] mode={self.mode} backend={backend} template={template}")

        if backend == "gemini":
            raw = self._call_gemini(prompt)
        else:
            raw = self._call_ollama(prompt, expect_json=expect_json)

        if expect_json:
            return self._parse_json(raw)
        return raw

    def is_ollama_available(self) -> bool:
        try:
            resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def status(self) -> dict:
        return {
            "mode":            self.mode,
            "ollama_url":      OLLAMA_URL,
            "ollama_model":    OLLAMA_MODEL,
            "ollama_up":       self.is_ollama_available(),
            "gemini_model":    GEMINI_MODEL,
            "gemini_key_set":  bool(GEMINI_KEY),
            "gemini_usage":    self._gemini_limiter.usage(),
        }

    # ── Backend selection ──────────────────────────────────────────────────

    def _select_backend(self, template: str | None) -> str:
        if self.mode == "local":
            return "ollama"
        if self.mode == "gemini":
            return "gemini"
        if self.mode == "hybrid":
            if template in LOCAL_TEMPLATES:
                return "ollama"
            return "gemini" if GEMINI_KEY else "ollama"
        # auto mode
        if GEMINI_KEY:
            ok, _ = self._gemini_limiter.check()
            if ok:
                return "gemini"
        return "ollama"

    # ── Gemini ──────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, retries: int = 3) -> str:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            logger.warning("google-genai not installed, falling back to Ollama")
            return self._call_ollama(prompt)

        client = genai.Client(api_key=GEMINI_KEY)

        for attempt in range(retries):
            try:
                self._gemini_limiter.wait_if_needed()
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.8,
                        response_mime_type="application/json",
                    ),
                )
                return response.text
            except Exception as e:
                if "quota" in str(e).lower() or "rate" in str(e).lower():
                    logger.warning(f"[LLMRouter] Gemini quota hit, falling back to Ollama: {e}")
                    return self._call_ollama(prompt)
                if attempt < retries - 1:
                    logger.warning(f"[LLMRouter] Gemini attempt {attempt+1} failed: {e}, retrying")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"[LLMRouter] Gemini failed after {retries} attempts: {e}")
                    return self._call_ollama(prompt)
        return ""

    # ── Ollama ──────────────────────────────────────────────────────────────

    def _call_ollama(self, prompt: str, expect_json: bool = True, retries: int = 2) -> str:
        payload = {
            "model":  OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
        if expect_json:
            payload["format"] = "json"

        for attempt in range(retries):
            try:
                resp = httpx.post(
                    f"{OLLAMA_URL}/api/generate",
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
            except Exception as e:
                if attempt < retries - 1:
                    logger.warning(f"[LLMRouter] Ollama attempt {attempt+1} failed: {e}, retrying")
                    time.sleep(3)
                else:
                    logger.error(f"[LLMRouter] Ollama failed after {retries} attempts: {e}")
                    raise RuntimeError(f"Both Gemini and Ollama unavailable: {e}")
        return ""

    # ── JSON parsing ────────────────────────────────────────────────────────

    def _parse_json(self, raw: str) -> dict | str:
        if not raw:
            return {}
        raw = raw.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[LLMRouter] Failed to parse JSON response, returning raw string")
            return raw


# Singleton
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
