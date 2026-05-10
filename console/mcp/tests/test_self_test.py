"""Tests for `python -m console.mcp.stdio --self-test`."""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_self_test_success(capsys, monkeypatch):
    """200 from /api/system/health → exit 0, OK message on stdout."""
    monkeypatch.setenv("MCP_API_TOKEN", "fake-token")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://backend.test:8080")

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value={"status": "ok"})
    fake_client.aclose = AsyncMock()

    with patch("console.mcp.stdio.ConsoleClient", return_value=fake_client):
        from console.mcp.stdio import _self_test
        rc = await _self_test()

    assert rc == 0
    captured = capsys.readouterr()
    assert "OK" in captured.out
    assert "http://backend.test:8080" in captured.out
    fake_client.get.assert_awaited_once_with("/api/system/health")
    fake_client.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_self_test_unauthorized(capsys, monkeypatch):
    """401 → exit 1, message tells user to re-mint."""
    monkeypatch.setenv("MCP_API_TOKEN", "fake-token")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://backend.test:8080")

    from console.mcp.errors import ConsoleError
    # ConsoleError dataclass: code, message, retryable, context
    # status is stored in context dict, not as a direct attribute.
    # The implementation checks e.code == "auth.unauthorized" (OR getattr(e, "status") == 401),
    # so using the canonical 401 error code is sufficient.
    err = ConsoleError(
        code="auth.unauthorized",
        message="invalid token",
        retryable=False,
        context={"status": 401},
    )
    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=err)
    fake_client.aclose = AsyncMock()

    with patch("console.mcp.stdio.ConsoleClient", return_value=fake_client):
        from console.mcp.stdio import _self_test
        rc = await _self_test()

    assert rc == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.err
    assert "401" in captured.err
    assert "re-mint" in captured.err.lower() or "system tab" in captured.err.lower()


@pytest.mark.asyncio
async def test_self_test_connection_error(capsys, monkeypatch):
    """Any non-401 failure → exit 1, message names the URL."""
    monkeypatch.setenv("MCP_API_TOKEN", "fake-token")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://nope.invalid:8080")

    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=ConnectionError("name resolution failed"))
    fake_client.aclose = AsyncMock()

    with patch("console.mcp.stdio.ConsoleClient", return_value=fake_client):
        from console.mcp.stdio import _self_test
        rc = await _self_test()

    assert rc == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.err
    assert "http://nope.invalid:8080" in captured.err


@pytest.mark.asyncio
async def test_self_test_missing_token(capsys, monkeypatch):
    """MCP_API_TOKEN unset → exit 1 with a clear FAIL message on stderr (no traceback)."""
    monkeypatch.delenv("MCP_API_TOKEN", raising=False)
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://backend.test:8080")

    from console.mcp.stdio import _self_test
    rc = await _self_test()

    assert rc == 1
    captured = capsys.readouterr()
    assert "FAIL" in captured.err
    # No raw Python traceback in stderr
    assert "Traceback" not in captured.err


def test_main_dispatches_self_test(monkeypatch):
    """`main()` invoked with --self-test in argv calls _self_test, not the JSON-RPC server."""
    monkeypatch.setattr(sys, "argv", ["console.mcp.stdio", "--self-test"])
    monkeypatch.setenv("MCP_API_TOKEN", "fake-token")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://backend.test:8080")

    fake_self_test = MagicMock(return_value=0)
    with patch("console.mcp.stdio._run_self_test_sync", fake_self_test) as runner:
        with pytest.raises(SystemExit) as excinfo:
            from console.mcp.stdio import main
            main()
        assert excinfo.value.code == 0
        runner.assert_called_once()
