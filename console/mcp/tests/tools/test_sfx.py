import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.sfx import sfx


@pytest.mark.asyncio
async def test_list_sound_types():
    client = AsyncMock()
    client.get.return_value = ["wind", "rain", "fire"]
    out = await sfx(action="list_sound_types", _client=client)
    client.get.assert_awaited_once_with("/api/sfx/sound-types", params={})


@pytest.mark.asyncio
async def test_list_with_filters():
    client = AsyncMock()
    client.get.return_value = []
    await sfx(action="list", sound_type="wind", limit=20, _client=client)
    client.get.assert_awaited_once_with("/api/sfx", params={"sound_type": "wind", "limit": 20})


@pytest.mark.asyncio
async def test_stream_url():
    client = AsyncMock()
    out = await sfx(action="get_stream_url", sfx_id=3, _client=client)
    assert out["data"]["url"] == "/api/sfx/3/stream"


@pytest.mark.asyncio
async def test_generate_sync():
    client = AsyncMock()
    client.post.return_value = {"id": 7, "title": "thunder crack", "file_path": "/sfx/7.mp3"}
    out = await sfx(action="generate", text="thunder", duration_seconds=4.0, confirm=True, _client=client)
    assert out["ok"] is True
    client.post.assert_awaited_once_with(
        "/api/sfx/generate",
        json={"text": "thunder", "duration_seconds": 4.0},
    )


@pytest.mark.asyncio
async def test_import_file_not_implemented():
    client = AsyncMock()
    out = await sfx(action="import_file", file_path="/tmp/x.wav", name="x", confirm=True, _client=client)
    assert out["ok"] is False
    assert out["error"]["code"] == "not_implemented"
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_destructive():
    client = AsyncMock()
    out = await sfx(action="delete", sfx_id=9, confirm=True, confirm_id=9, _client=client)
    client.delete.assert_awaited_once_with("/api/sfx/9")
