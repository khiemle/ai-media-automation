"""Strip secret-looking fields from MCP tool args before logging."""
from __future__ import annotations

from typing import Any

_SECRET_SUFFIXES = ("_token", "_key", "_secret")
_SECRET_NAMES = {"password", "passwd", "authorization"}


def _is_secret_key(name: str) -> bool:
    lower = name.lower()
    if lower in _SECRET_NAMES:
        return True
    return any(lower.endswith(s) for s in _SECRET_SUFFIXES)


def redact_args(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if _is_secret_key(k) else redact_args(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_args(v) for v in value]
    return value
