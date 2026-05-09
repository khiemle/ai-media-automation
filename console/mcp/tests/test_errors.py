import httpx
import pytest

from console.mcp.errors import ConsoleError, map_http_error


def test_404_maps_to_not_found():
    resp = httpx.Response(404, json={"detail": "no such video"})
    err = map_http_error(resp)
    assert isinstance(err, ConsoleError)
    assert err.code == "not_found"
    assert err.retryable is False
    assert "no such video" in err.message


def test_403_maps_to_forbidden():
    resp = httpx.Response(403, json={"detail": "needs admin"})
    err = map_http_error(resp)
    assert err.code == "auth.forbidden"


def test_429_maps_to_rate_limited_and_retryable():
    resp = httpx.Response(429, json={"detail": "quota exceeded"})
    err = map_http_error(resp)
    assert err.code == "dependency.rate_limited"
    assert err.retryable is True


def test_502_maps_to_upstream_unavailable_and_retryable():
    resp = httpx.Response(502, json={"detail": "bad gateway"})
    err = map_http_error(resp)
    assert err.code == "dependency.upstream_unavailable"
    assert err.retryable is True


def test_500_maps_to_console_api_error_and_retryable():
    resp = httpx.Response(500, text="internal error")
    err = map_http_error(resp)
    assert err.code == "console.api_error"
    assert err.retryable is True


def test_409_maps_to_conflict_invalid_status():
    resp = httpx.Response(409, json={"detail": "video already approved"})
    err = map_http_error(resp)
    assert err.code == "conflict.invalid_status"


def test_envelope_round_trip():
    err = ConsoleError("not_found", "missing", retryable=False, context={"id": 7})
    env = err.to_envelope()
    assert env == {
        "ok": False,
        "error": {
            "code": "not_found",
            "message": "missing",
            "retryable": False,
            "context": {"id": 7},
        },
    }
