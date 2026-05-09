import pytest
from unittest.mock import AsyncMock

from console.mcp.audit import wrap_with_audit_log


@pytest.mark.asyncio
async def test_audit_logs_success_call():
    sink = AsyncMock()

    async def my_tool(*, action: str, **kw):
        return {"ok": True, "data": {"action": action}}

    wrapped = wrap_with_audit_log(
        my_tool, tool_name="t",
        sink=sink, transport="stdio", actor_jwt_sub="42",
    )
    out = await wrapped(action="list", api_token="secret")
    assert out["ok"] is True
    sink.write.assert_awaited_once()
    row = sink.write.await_args.kwargs
    assert row["tool_name"] == "t"
    assert row["action"] == "list"
    assert row["ok"] is True
    assert row["args_redacted"]["api_token"] == "***"
    assert row["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_audit_logs_failure_call_with_error_code():
    sink = AsyncMock()

    async def my_tool(*, action: str, **kw):
        return {"ok": False, "error": {"code": "not_found", "message": "x", "retryable": False, "context": {}}}

    wrapped = wrap_with_audit_log(my_tool, tool_name="t", sink=sink, transport="http", actor_jwt_sub="0")
    await wrapped(action="get", id=1)
    row = sink.write.await_args.kwargs
    assert row["ok"] is False
    assert row["error_code"] == "not_found"


@pytest.mark.asyncio
async def test_audit_captures_task_id_when_present():
    sink = AsyncMock()
    async def my_tool(**kw):
        return {"ok": True, "task_id": "xyz", "task_kind": "k"}
    wrapped = wrap_with_audit_log(my_tool, tool_name="t", sink=sink, transport="stdio", actor_jwt_sub="0")
    await wrapped(action="render_final", video_id=7)
    assert sink.write.await_args.kwargs["task_id"] == "xyz"
