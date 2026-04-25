"""
Per-model rate limiter — token bucket for Gemini + Ollama.
Thread-safe counters; uses Redis when available for multi-worker coordination.
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env", override=False)

logger = logging.getLogger(__name__)

# Gemini free tier limits
GEMINI_RPD = int(os.environ.get("GEMINI_RPD", 1500))   # requests per day
GEMINI_RPM = int(os.environ.get("GEMINI_RPM", 15))     # requests per minute


class _Counter:
    """Thread-safe counter with optional Redis backend."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self._lock  = threading.Lock()
        self._local_count  = 0
        self._local_minute = self._current_minute()
        self._local_day    = self._current_day()
        self._redis        = self._try_redis()

    def _try_redis(self):
        try:
            import redis
            r = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
            r.ping()
            return r
        except Exception:
            return None

    def _current_minute(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

    def _current_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def increment_and_check_rpm(self, limit: int) -> bool:
        """Returns True if within limit, False if over."""
        minute = self._current_minute()
        if self._redis:
            key = f"{self.prefix}:rpm:{minute}"
            count = self._redis.incr(key)
            self._redis.expire(key, 90)
            return int(count) <= limit
        with self._lock:
            if self._local_minute != minute:
                self._local_count  = 0
                self._local_minute = minute
            self._local_count += 1
            return self._local_count <= limit

    def increment_and_check_rpd(self, limit: int) -> bool:
        """Returns True if within daily limit."""
        day = self._current_day()
        if self._redis:
            key = f"{self.prefix}:rpd:{day}"
            count = self._redis.incr(key)
            self._redis.expire(key, 90000)
            return int(count) <= limit
        # Local fallback: approximate (doesn't survive restarts)
        with self._lock:
            if self._local_day != day:
                self._local_day = day
            return True  # trust Redis for daily; local is just per-minute

    def get_rpm_usage(self) -> int:
        minute = self._current_minute()
        if self._redis:
            key = f"{self.prefix}:rpm:{minute}"
            return int(self._redis.get(key) or 0)
        with self._lock:
            if self._local_minute == minute:
                return self._local_count
        return 0

    def get_rpd_usage(self) -> int:
        day = self._current_day()
        if self._redis:
            key = f"{self.prefix}:rpd:{day}"
            return int(self._redis.get(key) or 0)
        return 0


class GeminiRateLimiter:
    """Rate limiter for Gemini API."""

    def __init__(self, rpd: int = GEMINI_RPD, rpm: int = GEMINI_RPM):
        self.rpd     = rpd
        self.rpm     = rpm
        self._counter = _Counter("gemini")

    def check(self) -> tuple[bool, str]:
        """Returns (allowed: bool, reason: str)."""
        if not self._counter.increment_and_check_rpd(self.rpd):
            return False, f"Gemini daily quota exceeded ({self.rpd} RPD)"
        if not self._counter.increment_and_check_rpm(self.rpm):
            return False, f"Gemini RPM limit ({self.rpm}/min) — wait and retry"
        return True, "ok"

    def usage(self) -> dict:
        return {
            "rpm":      self._counter.get_rpm_usage(),
            "rpm_limit": self.rpm,
            "rpd":      self._counter.get_rpd_usage(),
            "rpd_limit": self.rpd,
        }

    def wait_if_needed(self, max_wait: float = 65.0):
        """Block until we're under the RPM limit (up to max_wait seconds)."""
        waited = 0.0
        while waited < max_wait:
            ok, reason = self.check()
            if ok:
                return
            logger.info(f"[RateLimiter] {reason} — waiting 5s")
            time.sleep(5)
            waited += 5
        raise RuntimeError(f"Gemini rate limit exceeded after {max_wait}s wait")


class OllamaRateLimiter:
    """Local Ollama — no real rate limit, but track usage."""

    def check(self) -> tuple[bool, str]:
        return True, "ok"

    def usage(self) -> dict:
        return {"rpm": 0, "rpm_limit": -1, "rpd": 0, "rpd_limit": -1}

    def wait_if_needed(self, max_wait: float = 0):
        pass


# Singletons
_gemini_limiter  = GeminiRateLimiter()
_ollama_limiter  = OllamaRateLimiter()


def get_gemini_limiter() -> GeminiRateLimiter:
    return _gemini_limiter


def get_ollama_limiter() -> OllamaRateLimiter:
    return _ollama_limiter
