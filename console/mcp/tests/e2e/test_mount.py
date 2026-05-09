import os
import httpx
import pytest

from console.backend.main import app


@pytest.mark.asyncio
async def test_mount_serves_mcp_tools_under_existing_app(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "stub")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://localhost:8080")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Mount provides a chat surface — real test will pass forwarded user JWT;
        # for now just check the route is reachable and rejects unauth'd.
        resp = await c.get("/mcp/tools")
        assert resp.status_code in (401, 403)
