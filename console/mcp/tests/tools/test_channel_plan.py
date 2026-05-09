import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.channel_plan import channel_plan


@pytest.mark.asyncio
async def test_list_and_get():
    client = AsyncMock()
    client.get.return_value = {"items": [], "total": 0}
    await channel_plan(action="list", _client=client)
    client.get.assert_awaited_with("/api/channel-plans", params={})

    client.get.return_value = {"id": 7}
    await channel_plan(action="get", plan_id=7, _client=client)
    client.get.assert_awaited_with("/api/channel-plans/7", params={})


@pytest.mark.asyncio
async def test_import_json():
    client = AsyncMock()
    client.post.return_value = {"plan_id": 7}
    out = await channel_plan(action="import_json", payload={"channel": "x"}, confirm=True, _client=client)
    client.post.assert_awaited_once_with("/api/channel-plans/import", json={"channel": "x"})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_update():
    client = AsyncMock()
    client.put.return_value = {"id": 7}
    await channel_plan(action="update", plan_id=7, fields={"name": "n"}, confirm=True, _client=client)
    client.put.assert_awaited_once_with("/api/channel-plans/7", json={"name": "n"})


@pytest.mark.asyncio
async def test_delete_destructive():
    client = AsyncMock()
    out = await channel_plan(action="delete", plan_id=7, confirm=True, confirm_id=7, _client=client)
    client.delete.assert_awaited_once_with("/api/channel-plans/7")


@pytest.mark.asyncio
async def test_ai_seo():
    client = AsyncMock()
    client.post.return_value = {"title": "...", "description": "...", "tags": []}
    out = await channel_plan(action="ai_seo", plan_id=7, confirm=True, _client=client)
    client.post.assert_awaited_once_with("/api/channel-plans/7/ai/seo", json={})


@pytest.mark.asyncio
async def test_ai_autofill_and_prompts_and_ask():
    client = AsyncMock()
    client.post.return_value = {"answer": "x"}
    await channel_plan(action="ai_autofill", plan_id=7, confirm=True, _client=client)
    client.post.assert_awaited_with("/api/channel-plans/7/ai/autofill", json={})
    await channel_plan(action="ai_prompts", plan_id=7, hints={"theme": "calm"}, confirm=True, _client=client)
    client.post.assert_awaited_with("/api/channel-plans/7/ai/prompts", json={"hints": {"theme": "calm"}})
    await channel_plan(action="ai_ask", plan_id=7, question="what niche?", confirm=True, _client=client)
    client.post.assert_awaited_with("/api/channel-plans/7/ai/ask", json={"question": "what niche?"})
