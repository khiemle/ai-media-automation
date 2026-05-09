import os
import pytest

from console.mcp.auth.adapters import StdioAuth, HttpAuth, ChatAuth
from console.mcp.errors import ConsoleError


def test_stdio_reads_env_token(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "env-tok")
    a = StdioAuth.from_env()
    assert a.token() == "env-tok"
    assert a.actor_metadata()["transport"] == "stdio"
    assert "host" in a.actor_metadata()


def test_stdio_missing_env_raises_clear_error(monkeypatch):
    monkeypatch.delenv("MCP_API_TOKEN", raising=False)
    with pytest.raises(ConsoleError) as exc:
        StdioAuth.from_env()
    assert exc.value.code == "auth.unauthorized"


def test_http_resolves_known_api_key(api_key_registry):
    api_key_registry.register("cron-bot", "secret123", service_jwt="svc-jwt-1")
    a = HttpAuth(registry=api_key_registry, header_value="secret123")
    assert a.token() == "svc-jwt-1"
    md = a.actor_metadata()
    assert md["transport"] == "http"
    assert md["api_key_name"] == "cron-bot"


def test_http_unknown_api_key_raises(api_key_registry):
    with pytest.raises(ConsoleError) as exc:
        HttpAuth(registry=api_key_registry, header_value="nope").token()
    assert exc.value.code == "auth.unauthorized"


def test_chat_forwards_user_jwt():
    a = ChatAuth(forwarded_jwt="user-jwt-1", username="alice")
    assert a.token() == "user-jwt-1"
    md = a.actor_metadata()
    assert md["transport"] == "chat"
    assert md["via"] == "mcp"
