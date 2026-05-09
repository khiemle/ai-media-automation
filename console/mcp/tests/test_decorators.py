import pytest

from console.mcp.tools._common import (
    requires_confirm,
    destructive,
    returns_task,
)


@pytest.mark.asyncio
async def test_requires_confirm_returns_intent_when_unconfirmed():
    @requires_confirm(summary_fmt="delete video {video_id}")
    async def tool(video_id: int, confirm: bool = False, **_):
        return {"ok": True, "data": {"deleted": True, "video_id": video_id}}

    result = await tool(video_id=7)
    assert result["ok"] is False
    assert result["needs_confirmation"] is True
    assert result["intent"]["summary"] == "delete video 7"
    assert "confirm=true" in result["to_proceed"]


@pytest.mark.asyncio
async def test_requires_confirm_executes_when_confirmed():
    @requires_confirm(summary_fmt="x")
    async def tool(confirm: bool = False, **_):
        return {"ok": True, "data": {"ran": True}}

    result = await tool(confirm=True)
    assert result == {"ok": True, "data": {"ran": True}}


@pytest.mark.asyncio
async def test_destructive_requires_confirm_id_match():
    @destructive(id_arg="video_id", summary_fmt="delete {video_id}")
    async def tool(video_id: int, confirm: bool = False, confirm_id: int | None = None, **_):
        return {"ok": True, "data": {"deleted": True}}

    out = await tool(video_id=7, confirm=True)
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.confirm_id_mismatch"

    out = await tool(video_id=7, confirm=True, confirm_id=8)
    assert out["error"]["code"] == "validation.confirm_id_mismatch"

    out = await tool(video_id=7, confirm=True, confirm_id=7)
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_returns_task_wraps_async_response():
    @returns_task(task_kind="youtube_render_final", poll_hint="every 10s, ~5min")
    async def tool(**_):
        return {"task_id": "abc-123"}

    out = await tool()
    assert out["ok"] is True
    assert out["task_id"] == "abc-123"
    assert out["status_tool"] == "task_status"
    assert out["task_kind"] == "youtube_render_final"
    assert out["poll_hint"] == "every 10s, ~5min"


@pytest.mark.asyncio
async def test_returns_task_passes_through_error_envelope():
    @returns_task(task_kind="x", poll_hint="y")
    async def tool(**_):
        return {"ok": False, "error": {"code": "not_found", "message": "x", "retryable": False, "context": {}}}

    out = await tool()
    assert out["ok"] is False
    assert out["error"]["code"] == "not_found"
