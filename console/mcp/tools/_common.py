"""Decorators shared by every MCP tool.

- @requires_confirm: write tools demand confirm=true.
- @destructive: extends @requires_confirm with confirm_id matching.
- @returns_task: wraps async-kicking tool responses into the standard envelope.
"""
from __future__ import annotations

import functools
from typing import Any, Callable


def requires_confirm(*, summary_fmt: str) -> Callable:
    """Tool stays read-only unless caller passes confirm=true.

    summary_fmt is formatted with the call's keyword args so the agent sees
    a human-readable description of what it's about to do.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(**kwargs):
            if not kwargs.get("confirm", False):
                summary = summary_fmt.format(**{k: v for k, v in kwargs.items() if not _is_secret(k)})
                return {
                    "ok": False,
                    "needs_confirmation": True,
                    "intent": {"summary": summary, "args": _safe_args(kwargs)},
                    "to_proceed": "call again with confirm=true",
                }
            return await fn(**kwargs)

        return wrapper

    return decorator


def destructive(*, id_arg: str, summary_fmt: str) -> Callable:
    """Like @requires_confirm but also requires confirm_id == kwargs[id_arg]."""

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(**kwargs):
            if not kwargs.get("confirm", False):
                summary = summary_fmt.format(**{k: v for k, v in kwargs.items() if not _is_secret(k)})
                return {
                    "ok": False,
                    "needs_confirmation": True,
                    "intent": {"summary": summary, "args": _safe_args(kwargs)},
                    "to_proceed": f"call again with confirm=true and confirm_id={kwargs.get(id_arg)}",
                }
            expected = kwargs.get(id_arg)
            confirm_id = kwargs.get("confirm_id")
            if confirm_id != expected:
                return {
                    "ok": False,
                    "error": {
                        "code": "validation.confirm_id_mismatch",
                        "message": f"confirm_id ({confirm_id!r}) must equal {id_arg} ({expected!r})",
                        "retryable": False,
                        "context": {id_arg: expected, "confirm_id": confirm_id},
                    },
                }
            return await fn(**kwargs)

        return wrapper

    return decorator


def returns_task(*, task_kind: str, poll_hint: str) -> Callable:
    """Wrap a tool result `{task_id: str}` into the standard async envelope.

    Pass-through on `{ok: false, ...}` envelopes.
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(**kwargs):
            result = await fn(**kwargs)
            if isinstance(result, dict) and result.get("ok") is False:
                return result
            task_id = result.get("task_id") if isinstance(result, dict) else None
            return {
                "ok": True,
                "task_id": task_id,
                "status_tool": "task_status",
                "task_kind": task_kind,
                "poll_hint": poll_hint,
            }

        return wrapper

    return decorator


def _is_secret(name: str) -> bool:
    return name in {"password"} or name.endswith(("_token", "_key", "_secret"))


def _safe_args(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {k: ("***" if _is_secret(k) else v) for k, v in kwargs.items()}
