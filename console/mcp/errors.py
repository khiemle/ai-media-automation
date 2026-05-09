"""Error envelope used by every MCP tool result.

Business errors NEVER raise. They are returned as `{ok: false, error: {...}}`
so the agent can branch on `error.code` without parsing exceptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


_HTTP_TO_CODE: dict[int, tuple[str, bool]] = {
    400: ("validation.invalid_args", False),
    401: ("auth.unauthorized", False),
    403: ("auth.forbidden", False),
    404: ("not_found", False),
    409: ("conflict.invalid_status", False),
    422: ("validation.invalid_args", False),
    429: ("dependency.rate_limited", True),
    502: ("dependency.upstream_unavailable", True),
    503: ("dependency.upstream_unavailable", True),
    504: ("dependency.upstream_unavailable", True),
}


@dataclass
class ConsoleError(Exception):
    code: str
    message: str
    retryable: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_envelope(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
                "context": self.context,
            },
        }


def map_http_error(resp: httpx.Response) -> ConsoleError:
    code, retryable = _HTTP_TO_CODE.get(resp.status_code, ("console.api_error", resp.status_code >= 500))
    message = _extract_detail(resp)
    return ConsoleError(code=code, message=message, retryable=retryable, context={"status": resp.status_code})


def _extract_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and "detail" in data:
            return str(data["detail"])
    except Exception:
        pass
    return resp.text or f"HTTP {resp.status_code}"
