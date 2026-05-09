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
async def test_import_json_not_implemented():
    client = AsyncMock()
    out = await channel_plan(action="import_json", confirm=True, _client=client)
    assert out["ok"] is False
    assert out["error"]["code"] == "not_implemented"
    client.post.assert_not_awaited()


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
    out = await channel_plan(action="ai_seo", plan_id=7, theme="forest rain ASMR", confirm=True, _client=client)
    assert out["ok"] is True
    client.post.assert_awaited_once_with(
        "/api/channel-plans/7/ai/seo",
        json={"theme": "forest rain ASMR", "context": ""},
    )


@pytest.mark.asyncio
async def test_ai_prompts():
    client = AsyncMock()
    client.post.return_value = {"prompts": []}
    out = await channel_plan(
        action="ai_prompts", plan_id=7, theme="calm nature",
        context="focus on birds", confirm=True, _client=client,
    )
    assert out["ok"] is True
    client.post.assert_awaited_once_with(
        "/api/channel-plans/7/ai/prompts",
        json={"theme": "calm nature", "context": "focus on birds"},
    )


@pytest.mark.asyncio
async def test_ai_autofill():
    client = AsyncMock()
    client.post.return_value = {"autofilled": True}
    out = await channel_plan(action="ai_autofill", plan_id=7, theme="lo-fi study", confirm=True, _client=client)
    assert out["ok"] is True
    client.post.assert_awaited_once_with(
        "/api/channel-plans/7/ai/autofill",
        json={"theme": "lo-fi study", "context": ""},
    )


@pytest.mark.asyncio
async def test_ai_seo_missing_theme():
    """ai_seo without theme returns validation error (required field)."""
    client = AsyncMock()
    out = await channel_plan(action="ai_seo", plan_id=7, confirm=True, _client=client)
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.invalid_args"
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai_ask():
    client = AsyncMock()
    client.post.return_value = {"answer": "x"}
    await channel_plan(action="ai_ask", plan_id=7, question="what niche?", confirm=True, _client=client)
    client.post.assert_awaited_with("/api/channel-plans/7/ai/ask", json={"question": "what niche?"})
