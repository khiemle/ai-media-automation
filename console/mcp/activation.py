"""Activation helpers — build audit + idempotency kwargs from env."""

import os
from typing import Any


def audit_kwargs(*, transport: str, actor_jwt_sub: "str | None" = None) -> dict:
    """Returns kwargs to pass to each tool's register() function.

    Honors MCP_AUDIT_ENABLED env var. When disabled (or unset),
    audit_sink=None is returned and tools run without wrapping —
    matching test/dev behavior.
    """
    enabled = os.environ.get("MCP_AUDIT_ENABLED", "").lower() in ("1", "true", "yes")
    if not enabled:
        return {"audit_sink": None, "transport": transport, "actor_jwt_sub": actor_jwt_sub}
    from console.mcp.audit_db import DbAuditSink
    return {"audit_sink": DbAuditSink(), "transport": transport, "actor_jwt_sub": actor_jwt_sub}


def install_idempotency_store() -> None:
    """Install a Redis-backed IdempotencyStore on upload + youtube_video tools.

    Honors MCP_IDEMPOTENCY_ENABLED env var. When disabled (or unset), no-op
    — modules keep their _store=None default and idempotency_key args are
    silently ignored.
    """
    enabled = os.environ.get("MCP_IDEMPOTENCY_ENABLED", "").lower() in ("1", "true", "yes")
    if not enabled:
        return
    import redis.asyncio as aioredis
    from console.mcp.idempotency import IdempotencyStore
    from console.mcp.tools import upload, youtube_video

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    ttl_s = int(os.environ.get("MCP_IDEMPOTENCY_TTL_S", "86400"))
    store = IdempotencyStore(redis=aioredis.from_url(redis_url), ttl_s=ttl_s)
    upload.set_idempotency_store(store)
    youtube_video.set_idempotency_store(store)
