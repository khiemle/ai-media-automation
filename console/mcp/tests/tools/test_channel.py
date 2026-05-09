import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.channel import channel


@pytest.mark.asyncio
async def test_list_get_create_update_delete():
    c = AsyncMock()
    c.get.return_value = []
    await channel(action="list", _client=c)
    c.get.assert_awaited_with("/api/channels", params={})

    c.get.return_value = {"id": 5}
    await channel(action="get", channel_id=5, _client=c)
    c.get.assert_awaited_with("/api/channels/5", params={})

    c.post.return_value = {"id": 5}
    await channel(action="create", fields={"name": "n", "platform": "youtube"}, confirm=True, _client=c)
    c.post.assert_awaited_with("/api/channels", json={"name": "n", "platform": "youtube"})

    c.put.return_value = {"id": 5}
    await channel(action="update", channel_id=5, fields={"name": "x"}, confirm=True, _client=c)
    c.put.assert_awaited_with("/api/channels/5", json={"name": "x"})

    out = await channel(action="delete", channel_id=5, confirm=True, confirm_id=5, _client=c)
    c.delete.assert_awaited_once_with("/api/channels/5")


@pytest.mark.asyncio
async def test_defaults():
    c = AsyncMock()
    c.get.return_value = {}
    await channel(action="get_defaults", template="ambient", _client=c)
    c.get.assert_awaited_with("/api/channels/defaults/ambient", params={})

    await channel(action="set_defaults", template="ambient",
                  fields={"music_track_id": 7}, confirm=True, _client=c)
    c.put.assert_awaited_with("/api/channels/defaults/ambient", json={"music_track_id": 7})


@pytest.mark.asyncio
async def test_credential_status_read_only():
    c = AsyncMock()
    c.get.return_value = {"connected": True, "expires_at": "..."}
    out = await channel(action="credential_status", platform="youtube", _client=c)
    c.get.assert_awaited_once_with("/api/credentials/youtube", params={})
    assert out["ok"] is True
