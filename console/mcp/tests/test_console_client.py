import httpx
import pytest
import respx

from console.mcp.client.console_client import ConsoleClient
from console.mcp.errors import ConsoleError


@pytest.mark.asyncio
@respx.mock
async def test_get_attaches_bearer_and_actor_metadata():
    route = respx.get("http://test/api/youtube-videos").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    client = ConsoleClient(
        base_url="http://test",
        token_provider=lambda: "tok",
        actor_metadata={"transport": "stdio", "host": "h"},
    )
    out = await client.get("/api/youtube-videos")
    assert out == {"items": [], "total": 0}
    assert route.calls.last.request.headers["Authorization"] == "Bearer tok"
    assert "transport" in route.calls.last.request.headers["X-Mcp-Actor-Metadata"]


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_console_error_not_found():
    respx.get("http://test/api/youtube-videos/99").mock(
        return_value=httpx.Response(404, json={"detail": "missing"})
    )
    client = ConsoleClient(base_url="http://test", token_provider=lambda: "tok")
    with pytest.raises(ConsoleError) as exc:
        await client.get("/api/youtube-videos/99")
    assert exc.value.code == "not_found"
    assert "missing" in exc.value.message


@pytest.mark.asyncio
@respx.mock
async def test_post_sends_json_body():
    route = respx.post("http://test/api/youtube-videos").mock(
        return_value=httpx.Response(201, json={"id": 7})
    )
    client = ConsoleClient(base_url="http://test", token_provider=lambda: "tok")
    out = await client.post("/api/youtube-videos", json={"title": "x"})
    assert out == {"id": 7}
    assert route.calls.last.request.content == b'{"title": "x"}'


@pytest.mark.asyncio
@respx.mock
async def test_401_calls_refresh_then_retries_once():
    calls = []
    def provider():
        calls.append("p")
        return f"tok-{len(calls)}"

    refresh_called = []
    def refresh():
        refresh_called.append(True)

    respx.get("http://test/api/x").mock(side_effect=[
        httpx.Response(401, json={"detail": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ])
    client = ConsoleClient(
        base_url="http://test",
        token_provider=provider,
        on_unauthorized=refresh,
    )
    out = await client.get("/api/x")
    assert out == {"ok": True}
    assert refresh_called == [True]
