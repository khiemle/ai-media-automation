"""mcp_tool_calls audit logging.

Wraps a tool function so each call writes a row describing what was called,
who called it, what (redacted) args were passed, whether it succeeded, and
how long it took.

The default sink is ``None`` — wrapping is opt-in per ``register()``. A real
DbAuditSink lives in ``audit_db.py``.
"""

import time
from typing import Any, Callable, Protocol

from console.mcp.redact import redact_args


class AuditSink(Protocol):
    async def write(
        self,
        *,
        called_at_ms: int,
        transport: str,
        actor_jwt_sub: "str | None",
        tool_name: str,
        action: "str | None",
        args_redacted: dict,
        ok: bool,
        error_code: "str | None",
        duration_ms: int,
        task_id: "str | None",
    ) -> None: ...


def wrap_with_audit_log(
    fn: Callable,
    *,
    tool_name: str,
    sink: AuditSink,
    transport: str,
    actor_jwt_sub: "str | None",
) -> Callable:
    async def wrapper(**kwargs: Any) -> Any:
        start = time.monotonic()
        result: dict = {}
        try:
            result = await fn(**kwargs)
            return result
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            ok = bool(result.get("ok", False)) if isinstance(result, dict) else False
            err = result.get("error") if isinstance(result, dict) else None
            error_code = err.get("code") if isinstance(err, dict) else None
            task_id = result.get("task_id") if isinstance(result, dict) else None
            await sink.write(
                called_at_ms=int(time.time() * 1000),
                transport=transport,
                actor_jwt_sub=actor_jwt_sub,
                tool_name=tool_name,
                action=kwargs.get("action"),
                args_redacted=redact_args(
                    {k: v for k, v in kwargs.items() if k != "_client"}
                ),
                ok=ok,
                error_code=error_code,
                duration_ms=duration_ms,
                task_id=task_id,
            )

    return wrapper
