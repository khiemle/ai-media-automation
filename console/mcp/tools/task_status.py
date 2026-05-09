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


def register(server, *, client_factory):
    @server.tool(name="task_status")
    async def _task_status(task_id: str) -> dict:
        client = client_factory()
        return await task_status(task_id=task_id, _client=client)
