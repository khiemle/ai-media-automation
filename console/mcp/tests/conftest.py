"""Shared fixtures for MCP tests."""
from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def _mcp_test_env(monkeypatch):
    """Default env for tests."""
    monkeypatch.setenv("MCP_API_TOKEN", "test-token")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://test")
    monkeypatch.setenv("MCP_LOG_LEVEL", "debug")
    monkeypatch.setenv("MCP_IDEMPOTENCY_TTL_S", "3600")
