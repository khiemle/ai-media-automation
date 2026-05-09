"""task_status — poll any task_id returned by an async-kicking tool."""

from typing import Any

from console.mcp.errors import ConsoleError


async def task_status(*, task_id: str, _client: Any) -> dict:
    """Poll a Celery task by task_id.

    Status values: PENDING | PROGRESS | SUCCESS | FAILURE | REVOKED.
    On SUCCESS, `result` carries the task's payload. On FAILURE, `error` is a
    short string suitable for display.
    """
    try:
        data = await _client.get(f"/api/pipeline/jobs/{task_id}")
    except ConsoleError as e:
        return e.to_envelope()
    return {
        "ok": True,
        "task_id": task_id,
        "status": data.get("status"),
        "progress": data.get("progress"),
        "result": data.get("result"),
        "error": data.get("error"),
        "started_at": data.get("started_at"),
        "elapsed_s": data.get("elapsed_s"),
    }


def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(task_id: str):
        client = client_factory()
        return await task_status(task_id=task_id, _client=client)

    if audit_sink is not None:
        async def _wrapped(**kw):
            return await _core(**kw)
        _audit_wrapped = wrap_with_audit_log(
            _wrapped, tool_name="task_status",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="task_status")
    async def _task_status(task_id: str) -> dict:
        if _audit_wrapped is not None:
            return await _audit_wrapped(task_id=task_id)
        return await _core(task_id=task_id)
