"""Redis-backed idempotency cache for write-amplifying tools."""

import json
from typing import Any, Awaitable, Callable


class IdempotencyStore:
    def __init__(self, *, redis, ttl_s: int) -> None:
        self._r = redis
        self._ttl = ttl_s

    async def run_once(
        self,
        *,
        key: str,
        run: Callable[[], Awaitable[dict]],
    ) -> dict:
        full_key = f"mcp:idem:{key}"
        cached = await self._r.get(full_key)
        if cached:
            return json.loads(cached)
        result = await run()
        await self._r.set(full_key, json.dumps(result), ex=self._ttl)
        return result
