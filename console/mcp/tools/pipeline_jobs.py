"""pipeline_jobs — list/get/retry/cancel/get_logs/stats over the Celery job table."""

from typing import Any

from console.mcp.errors import ConsoleError


async def pipeline_jobs(*, action: str, _client: Any, **kwargs: Any) -> dict:
    """Pipeline jobs ops surface.

    Actions:
      - list:      query params {status, limit, offset}
      - get:       requires job_id
      - get_logs:  requires job_id
      - retry:     requires job_id + confirm=true
      - cancel:    requires job_id + confirm=true
      - stats:     overall queue stats
    """
    try:
        if action == "list":
            params = {k: v for k, v in kwargs.items() if k in {"status", "limit", "offset"} and v is not None}
            data = await _client.get("/api/pipeline/jobs", params=params)
            return {"ok": True, "data": data}

        if action == "get":
            job_id = _require(kwargs, "job_id")
            data = await _client.get(f"/api/pipeline/jobs/{job_id}")
            return {"ok": True, "data": data}

        if action == "get_logs":
            job_id = _require(kwargs, "job_id")
            data = await _client.get(f"/api/pipeline/jobs/{job_id}/logs")
            return {"ok": True, "data": data}

        if action == "stats":
            data = await _client.get("/api/pipeline/stats")
            return {"ok": True, "data": data}

        if action in ("retry", "cancel"):
            if not kwargs.get("confirm", False):
                job_id = kwargs.get("job_id")
                return {
                    "ok": False,
                    "needs_confirmation": True,
                    "intent": {
                        "summary": f"{action} job {job_id}",
                        "args": {k: v for k, v in kwargs.items() if k != "_client"},
                    },
                    "to_proceed": "call again with confirm=true",
                }
            job_id = _require(kwargs, "job_id")
            data = await _client.patch(f"/api/pipeline/jobs/{job_id}/{action}")
            return {"ok": True, "data": data}

        return ConsoleError(
            code="validation.invalid_args",
            message=f"unknown action {action!r}",
            retryable=False,
            context={"action": action},
        ).to_envelope()
    except ConsoleError as e:
        return e.to_envelope()


def _require(kwargs: dict, name: str) -> Any:
    if name not in kwargs or kwargs[name] is None:
        raise ConsoleError(
            code="validation.invalid_args",
            message=f"missing required arg: {name}",
            retryable=False,
            context={"missing": name},
        )
    return kwargs[name]


def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(**kw):
        client = client_factory()
        return await pipeline_jobs(_client=client, **kw)

    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="pipeline_jobs",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )
    else:
        _audit_wrapped = None

    @server.tool(name="pipeline_jobs")
    async def _pipeline_jobs(
        action: str,
        job_id: str = None,
        status: str = None,
        limit: int = None,
        offset: int = None,
        confirm: bool = False,
    ) -> dict:
        kw = dict(
            action=action, job_id=job_id, status=status,
            limit=limit, offset=offset, confirm=confirm,
        )
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        return await _core(**kw)
