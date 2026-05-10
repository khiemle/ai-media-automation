import importlib

import pytest


def test_audit_disabled_returns_none_sink(monkeypatch):
    monkeypatch.delenv("MCP_AUDIT_ENABLED", raising=False)
    # Force reimport so monkeypatched env is read fresh
    import console.mcp.activation as act
    importlib.reload(act)
    kw = act.audit_kwargs(transport="stdio")
    assert kw["audit_sink"] is None
    assert kw["transport"] == "stdio"


def test_audit_enabled_returns_db_sink(monkeypatch):
    monkeypatch.setenv("MCP_AUDIT_ENABLED", "1")
    import console.mcp.activation as act
    importlib.reload(act)
    from console.mcp.audit_db import DbAuditSink
    kw = act.audit_kwargs(transport="http")
    assert isinstance(kw["audit_sink"], DbAuditSink)
    assert kw["transport"] == "http"


def test_idempotency_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("MCP_IDEMPOTENCY_ENABLED", raising=False)
    import console.mcp.activation as act
    importlib.reload(act)
    from console.mcp.tools import upload
    upload.set_idempotency_store(None)  # ensure clean slate
    act.install_idempotency_store()
    assert upload._store is None


def test_idempotency_enabled_installs_store(monkeypatch):
    monkeypatch.setenv("MCP_IDEMPOTENCY_ENABLED", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    import console.mcp.activation as act
    importlib.reload(act)
    from console.mcp.tools import upload, youtube_video
    upload.set_idempotency_store(None)
    youtube_video.set_idempotency_store(None)
    act.install_idempotency_store()
    # redis.asyncio.from_url is lazy — no actual connection at construction time
    assert upload._store is not None
    assert youtube_video._store is not None
    # Reset to avoid polluting other tests
    upload.set_idempotency_store(None)
    youtube_video.set_idempotency_store(None)
