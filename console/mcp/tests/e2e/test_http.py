"""HTTP transport e2e: launch the SSE server in a thread, hit /sse, call tool."""
import asyncio
import os
import threading

import httpx
import pytest

from console.mcp.auth.tokens import InMemoryApiKeyRegistry
from console.mcp.http import build_http_app


@pytest.mark.asyncio
async def test_http_lists_tools_with_valid_api_key(monkeypatch):
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://nonexistent:1")
    registry = InMemoryApiKeyRegistry()
    registry.register("cron-bot", "secret", service_jwt="svc-jwt")
    app = build_http_app(registry=registry)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/healthz")
        assert resp.status_code == 200
        # Reject missing API key
        resp = await c.get("/mcp/tools")
        assert resp.status_code == 401
        # Accept valid API key
        resp = await c.get("/mcp/tools", headers={"X-API-Key": "secret"})
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()["tools"]]
        assert "system_health" in names
