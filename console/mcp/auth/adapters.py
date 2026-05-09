"""Per-transport auth adapters.

Each adapter knows how to provide:
  - .token()          → JWT to attach as Bearer
  - .actor_metadata() → JSON written to audit_log + tool_call log
"""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from typing import Any

from console.mcp.auth.tokens import InMemoryApiKeyRegistry
from console.mcp.errors import ConsoleError


@dataclass
class StdioAuth:
    _token: str
    _host: str

    @classmethod
    def from_env(cls) -> "StdioAuth":
        tok = os.environ.get("MCP_API_TOKEN")
        if not tok:
            raise ConsoleError(
                code="auth.unauthorized",
                message="MCP_API_TOKEN not set in environment",
                retryable=False,
            )
        return cls(_token=tok, _host=socket.gethostname())

    def token(self) -> str:
        return self._token

    def actor_metadata(self) -> dict[str, Any]:
        return {"transport": "stdio", "host": self._host}


@dataclass
class HttpAuth:
    registry: InMemoryApiKeyRegistry
    header_value: str

    def token(self) -> str:
        entry = self.registry.lookup(self.header_value)
        if entry is None:
            raise ConsoleError(
                code="auth.unauthorized",
                message="Unknown or revoked API key",
                retryable=False,
            )
        return entry.service_jwt

    def actor_metadata(self) -> dict[str, Any]:
        entry = self.registry.lookup(self.header_value)
        return {
            "transport": "http",
            "api_key_name": entry.name if entry else "unknown",
        }


@dataclass
class ChatAuth:
    forwarded_jwt: str
    username: str | None = None

    def token(self) -> str:
        return self.forwarded_jwt

    def actor_metadata(self) -> dict[str, Any]:
        md: dict[str, Any] = {"transport": "chat", "via": "mcp"}
        if self.username:
            md["username"] = self.username
        return md
