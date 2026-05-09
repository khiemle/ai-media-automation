import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.system_health import system_health


@pytest.mark.asyncio
async def test_health_action():
    client = AsyncMock()
    client.get.return_value = {"status": "ok", "db": "up", "redis": "up"}
    out = await system_health(action="health", _client=client)
    assert out == {"ok": True, "data": {"status": "ok", "db": "up", "redis": "up"}}
    client.get.assert_awaited_once_with("/api/system/health")


@pytest.mark.asyncio
async def test_llm_quota_action():
    client = AsyncMock()
    client.get.return_value = {"ollama_rpd_used": 4, "gemini_rpd_used": 12}
    out = await system_health(action="llm_quota", _client=client)
    assert out["ok"] is True
    client.get.assert_awaited_once_with("/api/llm/quota")


@pytest.mark.asyncio
async def test_unknown_action_returns_error_envelope():
    client = AsyncMock()
    out = await system_health(action="bogus", _client=client)
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.invalid_args"
