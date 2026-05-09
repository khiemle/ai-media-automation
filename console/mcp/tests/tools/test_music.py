import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.music import music


@pytest.mark.asyncio
async def test_list_tracks():
    client = AsyncMock()
    client.get.return_value = {"items": [{"id": 1, "title": "calm"}], "total": 1}
    out = await music(action="list_tracks", _client=client)
    client.get.assert_awaited_once_with("/api/music", params={})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_list_templates():
    client = AsyncMock()
    client.get.return_value = [{"id": "ambient_1"}]
    out = await music(action="list_templates", _client=client)
    client.get.assert_awaited_once_with("/api/music/templates", params={})


@pytest.mark.asyncio
async def test_get_track():
    client = AsyncMock()
    client.get.return_value = {"id": 7}
    out = await music(action="get", track_id=7, _client=client)
    client.get.assert_awaited_once_with("/api/music/7", params={})


@pytest.mark.asyncio
async def test_stream_url_returns_url():
    client = AsyncMock()
    out = await music(action="stream_url", track_id=7, _client=client)
    assert out["ok"] is True
    assert out["data"]["url"].endswith("/api/music/7/stream")


@pytest.mark.asyncio
async def test_generate_returns_task_envelope():
    client = AsyncMock()
    client.post.return_value = {"task_id": "music-1"}
    out = await music(action="generate", prompt="forest dawn", duration_s=480, confirm=True, _client=client)
    assert out["ok"] is True
    assert out["task_id"] == "music-1"
    assert out["task_kind"] == "music_generate"
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_requires_confirm():
    client = AsyncMock()
    out = await music(action="generate", prompt="x", duration_s=60, _client=client)
    assert out["ok"] is False
    assert out["needs_confirmation"] is True


@pytest.mark.asyncio
async def test_delete_requires_confirm_and_id():
    client = AsyncMock()
    # missing confirm
    out = await music(action="delete", track_id=7, _client=client)
    assert out["needs_confirmation"] is True
    # confirm but wrong id
    out = await music(action="delete", track_id=7, confirm=True, confirm_id=8, _client=client)
    assert out["error"]["code"] == "validation.confirm_id_mismatch"
    # confirm + match
    out = await music(action="delete", track_id=7, confirm=True, confirm_id=7, _client=client)
    client.delete.assert_awaited_once_with("/api/music/7")


@pytest.mark.asyncio
async def test_update():
    client = AsyncMock()
    client.put.return_value = {"id": 7, "title": "new"}
    out = await music(action="update", track_id=7, fields={"title": "new"}, confirm=True, _client=client)
    client.put.assert_awaited_once_with("/api/music/7", json={"title": "new"})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_elevenlabs_plan_and_compose():
    client = AsyncMock()
    client.post.return_value = {"plan_id": 1, "sections": []}
    out = await music(action="elevenlabs_plan", prompt="rain", _client=client)
    client.post.assert_awaited_with("/api/music/elevenlabs/plan", json={"prompt": "rain"})

    client.post.reset_mock()
    client.post.return_value = {"task_id": "elv-1"}
    out = await music(action="elevenlabs_compose", plan_id=1, confirm=True, _client=client)
    client.post.assert_awaited_with("/api/music/elevenlabs/compose", json={"plan_id": 1})
    assert out["task_kind"] == "music_elevenlabs_compose"
