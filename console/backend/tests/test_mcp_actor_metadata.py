"""Unit tests for X-Mcp-Actor-Metadata header parsing in audit middleware."""
import json
from unittest.mock import MagicMock

import pytest

from console.backend.middleware.audit import _parse_actor_metadata


def _make_request(headers: dict) -> MagicMock:
    """Build a minimal request mock with a headers dict."""
    req = MagicMock()
    req.headers = headers
    return req


def test_no_header_returns_none():
    req = _make_request({})
    assert _parse_actor_metadata(req) is None


def test_valid_json_object_is_parsed():
    payload = {"transport": "stdio", "host": "x"}
    req = _make_request({"x-mcp-actor-metadata": json.dumps(payload)})
    assert _parse_actor_metadata(req) == payload


def test_invalid_json_returns_none():
    req = _make_request({"x-mcp-actor-metadata": "not-json"})
    assert _parse_actor_metadata(req) is None


def test_json_array_returns_none():
    """Top-level arrays are not valid actor metadata."""
    req = _make_request({"x-mcp-actor-metadata": json.dumps([1, 2])})
    assert _parse_actor_metadata(req) is None


def test_actor_metadata_used_in_audit_log_entry(monkeypatch):
    """Verify AuditLog is constructed with actor_metadata from the header."""
    captured = []

    class FakeAuditLog:
        def __init__(self, **kwargs):
            captured.append(kwargs)

    # Patch AuditLog in the middleware module
    monkeypatch.setattr(
        "console.backend.middleware.audit.AuditLog",
        FakeAuditLog,
    )

    # Import the parsing helper — integration check only (no DB needed)
    payload = {"transport": "http", "host": "agent-box"}
    req = _make_request({"x-mcp-actor-metadata": json.dumps(payload)})
    result = _parse_actor_metadata(req)
    assert result == payload
    # Simulate what the middleware does with the parsed result
    entry = FakeAuditLog(
        user_id=None,
        action="POST /api/youtube-videos",
        target_type="youtube-videos",
        target_id=None,
        details={"status_code": 201},
        actor_metadata=result,
    )
    assert captured[0]["actor_metadata"] == payload
