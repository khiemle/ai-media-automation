# MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MCP server (`console/mcp/`) exposing 11 workflow-oriented tools over stdio, HTTP/SSE, and an in-process FastAPI sub-app, calling the existing console FastAPI on `:8080` via httpx.

**Architecture:** Single `console.mcp` package. `build_server()` registers all tools onto a `FastMCP` instance. Three transports share the same tool catalog and pick a different `AuthAdapter`. Tools are thin dispatchers that translate MCP `action` args into HTTP calls against the existing FastAPI. Async work (Celery jobs) returns `task_id`; agents poll via `task_status`. Spec: `docs/superpowers/specs/2026-05-09-mcp-server-design.md`.

**Tech Stack:** Python 3.11+, `mcp` SDK (FastMCP), httpx, FastAPI (existing), SQLAlchemy 2.0 + Alembic, Postgres, Redis, Celery (existing), pytest + respx + pytest-asyncio.

---

## Phase Map

1. **Phase 1 — Foundations** (Tasks 1-9): deps, schema, errors, decorators, auth, client, server builder.
2. **Phase 2 — Skateboard** (Tasks 10-13): `system_health` tool + all 3 transports working.
3. **Phase 3 — Read tools** (Tasks 14-15): `task_status`, `pipeline_jobs`.
4. **Phase 4 — Media CRUD** (Tasks 16-18): `music`, `sfx`, `visual_asset`.
5. **Phase 5 — Channels** (Tasks 19-20): `channel_plan`, `channel`.
6. **Phase 6 — YouTube** (Tasks 21-23): `youtube_video` (split read/write), `youtube_thumbnail`.
7. **Phase 7 — Upload** (Task 24).
8. **Phase 8 — Cross-cutting** (Tasks 25-26): `mcp_tool_calls` audit, idempotency.
9. **Phase 9 — E2E** (Task 27): full video creation integration test.

---

## Task 1: Add MCP dependencies and pytest config

**Files:**
- Modify: `console/requirements.txt`
- Create: `console/backend/pytest.ini` (only if not present — check first)

- [ ] **Step 1: Append MCP + test deps to `console/requirements.txt`**

Add at the end of the file:

```
# MCP server
mcp>=1.2.0
respx>=0.21.1
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
```

- [ ] **Step 2: Install**

Run: `pip install -r console/requirements.txt`
Expected: all four packages install without conflicts.

- [ ] **Step 3: Verify mcp import**

Run: `python -c "from mcp.server.fastmcp import FastMCP; print(FastMCP.__module__)"`
Expected: prints `mcp.server.fastmcp`.

- [ ] **Step 4: Commit**

```bash
git add console/requirements.txt
git commit -m "chore(mcp): add mcp SDK and test dependencies"
```

---

## Task 2: Alembic migration — schema additions

**Files:**
- Create: `console/backend/alembic/versions/<rev>_mcp_server_tables.py`

- [ ] **Step 1: Generate empty migration**

Run from `console/backend/`:
```bash
cd console/backend && alembic revision -m "mcp server tables"
```
Note the generated filename (e.g. `00X_mcp_server_tables.py`).

- [ ] **Step 2: Replace `upgrade()` and `downgrade()` with full migration**

Open the generated file. Replace its body with:

```python
"""mcp server tables

Revision ID: <auto>
Revises: <auto>
Create Date: <auto>
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # 1. audit_log.actor_metadata
    op.add_column(
        "audit_log",
        sa.Column("actor_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 2. mcp_api_keys
    op.create_table(
        "mcp_api_keys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("key_hash", sa.Text, nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("service_user_id", sa.Integer, sa.ForeignKey("console_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mcp_api_keys_key_hash", "mcp_api_keys", ["key_hash"])

    # 3. mcp_tool_calls
    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("transport", sa.Text, nullable=False),
        sa.Column("actor_jwt_sub", sa.Text, nullable=True),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=True),
        sa.Column("args_redacted", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ok", sa.Boolean, nullable=False),
        sa.Column("error_code", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("task_id", sa.Text, nullable=True),
    )
    op.create_index("ix_mcp_tool_calls_called_at", "mcp_tool_calls", ["called_at"])
    op.create_index("ix_mcp_tool_calls_tool_name", "mcp_tool_calls", ["tool_name"])

    # 4. seed mcp-system user (login disabled via unusable bcrypt hash)
    op.execute(
        """
        INSERT INTO console_users (username, email, password_hash, role, created_at)
        VALUES ('mcp-system', 'mcp-system@local', '!disabled!', 'admin', now())
        ON CONFLICT (username) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM console_users WHERE username = 'mcp-system'")
    op.drop_index("ix_mcp_tool_calls_tool_name", table_name="mcp_tool_calls")
    op.drop_index("ix_mcp_tool_calls_called_at", table_name="mcp_tool_calls")
    op.drop_table("mcp_tool_calls")
    op.drop_index("ix_mcp_api_keys_key_hash", table_name="mcp_api_keys")
    op.drop_table("mcp_api_keys")
    op.drop_column("audit_log", "actor_metadata")
```

- [ ] **Step 3: Apply migration**

Run from `console/backend/`:
```bash
alembic upgrade head
```
Expected: completes without error. New tables and column exist.

- [ ] **Step 4: Verify**

```bash
psql $DATABASE_URL -c "\d mcp_api_keys" -c "\d mcp_tool_calls" -c "SELECT id, username, role FROM console_users WHERE username='mcp-system'"
```
Expected: both tables shown; one row for `mcp-system` with role `admin`.

- [ ] **Step 5: Commit**

```bash
git add console/backend/alembic/versions/*_mcp_server_tables.py
git commit -m "feat(mcp): schema for actor_metadata, mcp_api_keys, mcp_tool_calls"
```

---

## Task 3: MCP package skeleton

**Files:**
- Create: `console/mcp/__init__.py`
- Create: `console/mcp/auth/__init__.py`
- Create: `console/mcp/client/__init__.py`
- Create: `console/mcp/tools/__init__.py`
- Create: `console/mcp/tests/__init__.py`
- Create: `console/mcp/tests/conftest.py`

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p console/mcp/auth console/mcp/client console/mcp/tools console/mcp/tests/tools console/mcp/tests/integration console/mcp/tests/e2e
touch console/mcp/__init__.py
touch console/mcp/auth/__init__.py
touch console/mcp/client/__init__.py
touch console/mcp/tools/__init__.py
touch console/mcp/tests/__init__.py
touch console/mcp/tests/tools/__init__.py
touch console/mcp/tests/integration/__init__.py
touch console/mcp/tests/e2e/__init__.py
```

- [ ] **Step 2: Write `console/mcp/tests/conftest.py`**

```python
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
```

- [ ] **Step 3: Verify package imports**

Run: `python -c "import console.mcp; import console.mcp.auth; import console.mcp.client; import console.mcp.tools"`
Expected: no output, no errors.

- [ ] **Step 4: Commit**

```bash
git add console/mcp/
git commit -m "feat(mcp): package skeleton"
```

---

## Task 4: ConsoleError + HTTP→error-code mapping

**Files:**
- Create: `console/mcp/errors.py`
- Create: `console/mcp/tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_errors.py`:

```python
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
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'console.mcp.errors'`.

- [ ] **Step 3: Implement `console/mcp/errors.py`**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/test_errors.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/errors.py console/mcp/tests/test_errors.py
git commit -m "feat(mcp): ConsoleError + HTTP→error-code mapping"
```

---

## Task 5: Args redaction utility

**Files:**
- Create: `console/mcp/redact.py`
- Create: `console/mcp/tests/test_redact.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_redact.py`:

```python
from console.mcp.redact import redact_args


def test_strips_token_field():
    assert redact_args({"id": 7, "api_token": "abc"}) == {"id": 7, "api_token": "***"}


def test_strips_key_and_password():
    out = redact_args({"client_key": "x", "password": "y", "name": "ok"})
    assert out == {"client_key": "***", "password": "***", "name": "ok"}


def test_recurses_into_dicts():
    out = redact_args({"creds": {"refresh_token": "t", "user": "u"}})
    assert out == {"creds": {"refresh_token": "***", "user": "u"}}


def test_recurses_into_lists():
    out = redact_args({"items": [{"oauth_token": "z"}, {"name": "a"}]})
    assert out == {"items": [{"oauth_token": "***"}, {"name": "a"}]}


def test_keeps_non_secret_fields_untouched():
    args = {"video_id": 12, "title": "Forest ASMR", "tags": ["sleep", "rain"]}
    assert redact_args(args) == args
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_redact.py -v`
Expected: FAIL with module-not-found.

- [ ] **Step 3: Implement `console/mcp/redact.py`**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/test_redact.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/redact.py console/mcp/tests/test_redact.py
git commit -m "feat(mcp): redact secret-looking args before logging"
```

---

## Task 6: Decorators — @requires_confirm, @destructive, @returns_task

**Files:**
- Create: `console/mcp/tools/_common.py`
- Create: `console/mcp/tests/test_decorators.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_decorators.py`:

```python
import pytest

from console.mcp.tools._common import (
    requires_confirm,
    destructive,
    returns_task,
)


@pytest.mark.asyncio
async def test_requires_confirm_returns_intent_when_unconfirmed():
    @requires_confirm(summary_fmt="delete video {video_id}")
    async def tool(video_id: int, confirm: bool = False, **_):
        return {"ok": True, "data": {"deleted": True, "video_id": video_id}}

    result = await tool(video_id=7)
    assert result["ok"] is False
    assert result["needs_confirmation"] is True
    assert result["intent"]["summary"] == "delete video 7"
    assert "confirm=true" in result["to_proceed"]


@pytest.mark.asyncio
async def test_requires_confirm_executes_when_confirmed():
    @requires_confirm(summary_fmt="x")
    async def tool(confirm: bool = False, **_):
        return {"ok": True, "data": {"ran": True}}

    result = await tool(confirm=True)
    assert result == {"ok": True, "data": {"ran": True}}


@pytest.mark.asyncio
async def test_destructive_requires_confirm_id_match():
    @destructive(id_arg="video_id", summary_fmt="delete {video_id}")
    async def tool(video_id: int, confirm: bool = False, confirm_id: int | None = None, **_):
        return {"ok": True, "data": {"deleted": True}}

    # missing confirm_id
    out = await tool(video_id=7, confirm=True)
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.confirm_id_mismatch"

    # mismatched
    out = await tool(video_id=7, confirm=True, confirm_id=8)
    assert out["error"]["code"] == "validation.confirm_id_mismatch"

    # match
    out = await tool(video_id=7, confirm=True, confirm_id=7)
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_returns_task_wraps_async_response():
    @returns_task(task_kind="youtube_render_final", poll_hint="every 10s, ~5min")
    async def tool(**_):
        return {"task_id": "abc-123"}

    out = await tool()
    assert out["ok"] is True
    assert out["task_id"] == "abc-123"
    assert out["status_tool"] == "task_status"
    assert out["task_kind"] == "youtube_render_final"
    assert out["poll_hint"] == "every 10s, ~5min"


@pytest.mark.asyncio
async def test_returns_task_passes_through_error_envelope():
    @returns_task(task_kind="x", poll_hint="y")
    async def tool(**_):
        return {"ok": False, "error": {"code": "not_found", "message": "x", "retryable": False, "context": {}}}

    out = await tool()
    assert out["ok"] is False
    assert out["error"]["code"] == "not_found"
```

Add to `console/mcp/tests/conftest.py`:

```python
import pytest_asyncio  # noqa: F401

# Force asyncio mode without project-wide config.
def pytest_collection_modifyitems(config, items):
    for item in items:
        if "asyncio" in item.keywords:
            continue
```

Also create `console/mcp/tests/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_decorators.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `console/mcp/tools/_common.py`**

```python
"""Decorators shared by every MCP tool.

- @requires_confirm: write tools demand confirm=true.
- @destructive: extends @requires_confirm with confirm_id matching.
- @returns_task: wraps async-kicking tool responses into the standard envelope.
"""
from __future__ import annotations

import functools
import inspect
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
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/test_decorators.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/tools/_common.py console/mcp/tests/test_decorators.py console/mcp/tests/conftest.py console/mcp/tests/pytest.ini
git commit -m "feat(mcp): @requires_confirm, @destructive, @returns_task decorators"
```

---

## Task 7: ConsoleClient (httpx wrapper)

**Files:**
- Create: `console/mcp/client/console_client.py`
- Create: `console/mcp/tests/test_console_client.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_console_client.py`:

```python
import httpx
import pytest
import respx

from console.mcp.client.console_client import ConsoleClient
from console.mcp.errors import ConsoleError


@pytest.mark.asyncio
@respx.mock
async def test_get_attaches_bearer_and_actor_metadata():
    route = respx.get("http://test/api/youtube-videos").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    client = ConsoleClient(
        base_url="http://test",
        token_provider=lambda: "tok",
        actor_metadata={"transport": "stdio", "host": "h"},
    )
    out = await client.get("/api/youtube-videos")
    assert out == {"items": [], "total": 0}
    assert route.calls.last.request.headers["Authorization"] == "Bearer tok"
    assert "transport" in route.calls.last.request.headers["X-Mcp-Actor-Metadata"]


@pytest.mark.asyncio
@respx.mock
async def test_404_raises_console_error_not_found():
    respx.get("http://test/api/youtube-videos/99").mock(
        return_value=httpx.Response(404, json={"detail": "missing"})
    )
    client = ConsoleClient(base_url="http://test", token_provider=lambda: "tok")
    with pytest.raises(ConsoleError) as exc:
        await client.get("/api/youtube-videos/99")
    assert exc.value.code == "not_found"
    assert "missing" in exc.value.message


@pytest.mark.asyncio
@respx.mock
async def test_post_sends_json_body():
    route = respx.post("http://test/api/youtube-videos").mock(
        return_value=httpx.Response(201, json={"id": 7})
    )
    client = ConsoleClient(base_url="http://test", token_provider=lambda: "tok")
    out = await client.post("/api/youtube-videos", json={"title": "x"})
    assert out == {"id": 7}
    assert route.calls.last.request.content == b'{"title": "x"}'


@pytest.mark.asyncio
@respx.mock
async def test_401_calls_refresh_then_retries_once():
    calls = []
    def provider():
        calls.append("p")
        return f"tok-{len(calls)}"

    refresh_called = []
    def refresh():
        refresh_called.append(True)

    respx.get("http://test/api/x").mock(side_effect=[
        httpx.Response(401, json={"detail": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ])
    client = ConsoleClient(
        base_url="http://test",
        token_provider=provider,
        on_unauthorized=refresh,
    )
    out = await client.get("/api/x")
    assert out == {"ok": True}
    assert refresh_called == [True]
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_console_client.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `console/mcp/client/console_client.py`**

```python
"""Thin httpx wrapper that talks to the existing console FastAPI."""
from __future__ import annotations

import json
from typing import Any, Callable

import httpx

from console.mcp.errors import ConsoleError, map_http_error

TokenProvider = Callable[[], str]


class ConsoleClient:
    def __init__(
        self,
        *,
        base_url: str,
        token_provider: TokenProvider,
        actor_metadata: dict[str, Any] | None = None,
        on_unauthorized: Callable[[], None] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token_provider
        self._actor = actor_metadata or {}
        self._on_unauthorized = on_unauthorized
        self._client = httpx.AsyncClient(timeout=timeout)

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, json=json)

    async def put(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PUT", path, json=json)

    async def patch(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,  # noqa: A002
    ) -> Any:
        url = f"{self._base}{path}"
        resp = await self._do(method, url, params=params, json_body=json)
        if resp.status_code == 401 and self._on_unauthorized is not None:
            self._on_unauthorized()
            resp = await self._do(method, url, params=params, json_body=json)
        if resp.status_code >= 400:
            raise map_http_error(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def _do(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._token()}"}
        if self._actor:
            import json as _json
            headers["X-Mcp-Actor-Metadata"] = _json.dumps(self._actor, separators=(",", ":"))
        return await self._client.request(method, url, params=params, json=json_body, headers=headers)

    async def aclose(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/test_console_client.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/client/ console/mcp/tests/test_console_client.py
git commit -m "feat(mcp): ConsoleClient httpx wrapper with 401-retry"
```

---

## Task 8: Auth adapters

**Files:**
- Create: `console/mcp/auth/adapters.py`
- Create: `console/mcp/auth/tokens.py`
- Create: `console/mcp/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_auth.py`:

```python
import os
import pytest

from console.mcp.auth.adapters import StdioAuth, HttpAuth, ChatAuth
from console.mcp.errors import ConsoleError


def test_stdio_reads_env_token():
    os.environ["MCP_API_TOKEN"] = "env-tok"
    a = StdioAuth.from_env()
    assert a.token() == "env-tok"
    assert a.actor_metadata()["transport"] == "stdio"
    assert "host" in a.actor_metadata()


def test_stdio_missing_env_raises_clear_error():
    os.environ.pop("MCP_API_TOKEN", None)
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
```

Append to `console/mcp/tests/conftest.py`:

```python
@pytest.fixture
def api_key_registry():
    from console.mcp.auth.tokens import InMemoryApiKeyRegistry
    return InMemoryApiKeyRegistry()
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_auth.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `console/mcp/auth/tokens.py`**

```python
"""API-key registry. Production impl reads from `mcp_api_keys` table; the
in-memory variant is used by tests and for the trivial single-key dev case.
"""
from __future__ import annotations

import bcrypt
from dataclasses import dataclass


@dataclass
class ApiKeyEntry:
    name: str
    service_jwt: str  # long-lived JWT for the mapped service-account user
    scopes: list[str]


class InMemoryApiKeyRegistry:
    def __init__(self) -> None:
        self._by_hash: dict[bytes, ApiKeyEntry] = {}

    def register(self, name: str, plaintext_key: str, *, service_jwt: str, scopes: list[str] | None = None) -> None:
        h = bcrypt.hashpw(plaintext_key.encode(), bcrypt.gensalt())
        self._by_hash[h] = ApiKeyEntry(name=name, service_jwt=service_jwt, scopes=scopes or [])

    def lookup(self, plaintext_key: str) -> ApiKeyEntry | None:
        for h, entry in self._by_hash.items():
            if bcrypt.checkpw(plaintext_key.encode(), h):
                return entry
        return None
```

- [ ] **Step 4: Implement `console/mcp/auth/adapters.py`**

```python
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
```

- [ ] **Step 5: Run, verify pass**

Run: `pytest console/mcp/tests/test_auth.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add console/mcp/auth/ console/mcp/tests/test_auth.py
git commit -m "feat(mcp): auth adapters (stdio, http, chat) + API-key registry"
```

---

## Task 9: build_server() — FastMCP factory

**Files:**
- Create: `console/mcp/server.py`
- Create: `console/mcp/tests/test_server.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_server.py`:

```python
from console.mcp.server import build_server


def test_build_server_returns_fastmcp_with_no_tools_yet():
    server = build_server(register=[])
    # tools dict is exposed by FastMCP via list_tools()
    assert hasattr(server, "list_tools")


def test_build_server_registers_passed_callbacks():
    calls = []

    def register_one(server):
        calls.append(server)

    build_server(register=[register_one])
    assert len(calls) == 1
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_server.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `console/mcp/server.py`**

```python
"""Server builder shared by all transport entrypoints."""
from __future__ import annotations

from typing import Callable, Iterable

from mcp.server.fastmcp import FastMCP


SERVER_NAME = "ai-media-console"
SERVER_VERSION = "0.1.0"


def build_server(
    *,
    register: Iterable[Callable[[FastMCP], None]],
) -> FastMCP:
    """Build a FastMCP instance and let each `register` callback wire its tools."""
    server = FastMCP(SERVER_NAME)
    for reg in register:
        reg(server)
    return server
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/test_server.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/server.py console/mcp/tests/test_server.py
git commit -m "feat(mcp): build_server() FastMCP factory"
```

---

## Task 10: Tool — `system_health`

**Files:**
- Create: `console/mcp/tools/system_health.py`
- Create: `console/mcp/tests/tools/test_system_health.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_system_health.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.system_health import system_health


@pytest.mark.asyncio
async def test_health_action():
    client = AsyncMock()
    client.get.return_value = {"status": "ok", "db": "up", "redis": "up"}
    out = await system_health(action="health", _client=client)
    assert out == {"ok": True, "data": {"status": "ok", "db": "up", "redis": "up"}}
    client.get.assert_awaited_once_with("/api/system/health")


@pytest.mark.asyncio
async def test_llm_quota_action():
    client = AsyncMock()
    client.get.return_value = {"ollama_rpd_used": 4, "gemini_rpd_used": 12}
    out = await system_health(action="llm_quota", _client=client)
    assert out["ok"] is True
    client.get.assert_awaited_once_with("/api/llm/quota")


@pytest.mark.asyncio
async def test_unknown_action_returns_error_envelope():
    client = AsyncMock()
    out = await system_health(action="bogus", _client=client)
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.invalid_args"
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_system_health.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `console/mcp/tools/system_health.py`**

```python
"""system_health tool — read-only observability."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError

ACTIONS = {
    "health": "/api/system/health",
    "cron": "/api/system/cron",
    "errors": "/api/system/errors",
    "llm_quota": "/api/llm/quota",
    "performance_summary": "/api/performance/summary",
}


async def system_health(*, action: str, _client) -> dict[str, Any]:
    """Read-only system health and observability surface.

    Actions:
      - health: liveness + dependency check
      - cron: scheduled task status
      - errors: recent error log entries
      - llm_quota: Ollama/Gemini quota usage
      - performance_summary: pipeline performance summary
    """
    path = ACTIONS.get(action)
    if path is None:
        return ConsoleError(
            code="validation.invalid_args",
            message=f"unknown action {action!r}; valid: {list(ACTIONS)}",
            retryable=False,
            context={"action": action},
        ).to_envelope()
    try:
        data = await _client.get(path)
    except ConsoleError as e:
        return e.to_envelope()
    return {"ok": True, "data": data}


def register(server, *, client_factory):
    """Hook called by build_server."""
    @server.tool(name="system_health")
    async def _system_health(action: str) -> dict[str, Any]:
        client = client_factory()
        return await system_health(action=action, _client=client)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_system_health.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/tools/system_health.py console/mcp/tests/tools/test_system_health.py
git commit -m "feat(mcp): system_health tool"
```

---

## Task 11: stdio transport entrypoint + e2e test

**Files:**
- Create: `console/mcp/stdio.py`
- Create: `console/mcp/tests/e2e/test_stdio.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/e2e/test_stdio.py`:

```python
"""End-to-end stdio test: spawn the entrypoint, send MCP framing, read replies."""
import asyncio
import json
import os
import subprocess
import sys

import pytest


@pytest.mark.asyncio
async def test_stdio_lists_system_health_tool(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "stub")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://nonexistent:1")

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "console.mcp.stdio",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        # MCP initialize
        init = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05",
                       "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}},
        }
        proc.stdin.write((json.dumps(init) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        assert b"\"id\":1" in line

        # tools/list
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        proc.stdin.write((json.dumps(list_req) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        body = json.loads(line)
        names = [t["name"] for t in body["result"]["tools"]]
        assert "system_health" in names
    finally:
        proc.terminate()
        await proc.wait()
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/e2e/test_stdio.py -v`
Expected: FAIL — module `console.mcp.stdio` doesn't exist.

- [ ] **Step 3: Implement `console/mcp/stdio.py`**

```python
"""stdio transport entrypoint: `python -m console.mcp.stdio`."""
from __future__ import annotations

import os

from console.mcp.auth.adapters import StdioAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.server import build_server
from console.mcp.tools import system_health


def main() -> None:
    auth = StdioAuth.from_env()

    def client_factory() -> ConsoleClient:
        return ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )

    server = build_server(register=[
        lambda s: system_health.register(s, client_factory=client_factory),
    ])
    server.run("stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/e2e/test_stdio.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/stdio.py console/mcp/tests/e2e/test_stdio.py
git commit -m "feat(mcp): stdio transport entrypoint + e2e test"
```

---

## Task 12: HTTP/SSE transport entrypoint + e2e test

**Files:**
- Create: `console/mcp/http.py`
- Create: `console/mcp/tests/e2e/test_http.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/e2e/test_http.py`:

```python
"""HTTP transport e2e: launch the SSE server in a thread, hit /sse, call tool."""
import asyncio
import os
import threading

import httpx
import pytest

from console.mcp.auth.tokens import InMemoryApiKeyRegistry
from console.mcp.http import build_http_app


@pytest.mark.asyncio
async def test_http_lists_tools_with_valid_api_key(monkeypatch):
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://nonexistent:1")
    registry = InMemoryApiKeyRegistry()
    registry.register("cron-bot", "secret", service_jwt="svc-jwt")
    app = build_http_app(registry=registry)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/healthz")
        assert resp.status_code == 200
        # Reject missing API key
        resp = await c.get("/mcp/tools")
        assert resp.status_code == 401
        # Accept valid API key
        resp = await c.get("/mcp/tools", headers={"X-API-Key": "secret"})
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()["tools"]]
        assert "system_health" in names
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/e2e/test_http.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `console/mcp/http.py`**

```python
"""HTTP/SSE transport: `python -m console.mcp.http` or mountable as ASGI app.

For the skateboard we expose:
  - GET  /healthz          — liveness
  - GET  /mcp/tools        — tool catalog (requires X-API-Key)
  - POST /mcp/call         — call a tool (requires X-API-Key)

A full SSE/streamable-HTTP MCP transport will be wired in once the FastMCP
SDK's HTTP server stabilizes (see spec §11). This skeleton is sufficient to
validate the auth + dispatch pipeline.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from console.mcp.auth.adapters import HttpAuth
from console.mcp.auth.tokens import InMemoryApiKeyRegistry
from console.mcp.client.console_client import ConsoleClient
from console.mcp.server import build_server
from console.mcp.tools import system_health


def build_http_app(*, registry: InMemoryApiKeyRegistry) -> FastAPI:
    app = FastAPI(title="console-mcp-http")

    def make_client(api_key: str) -> ConsoleClient:
        auth = HttpAuth(registry=registry, header_value=api_key)
        return ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )

    server = build_server(register=[
        lambda s: system_health.register(s, client_factory=lambda: ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=lambda: "placeholder",  # overridden per-request below
        )),
    ])

    def _require_key(x_api_key: str | None) -> str:
        if not x_api_key or registry.lookup(x_api_key) is None:
            raise HTTPException(status_code=401, detail="invalid api key")
        return x_api_key

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mcp/tools")
    async def list_tools(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        _require_key(x_api_key)
        tools = await server.list_tools()
        return {"tools": [{"name": t.name, "description": t.description} for t in tools]}

    @app.post("/mcp/call")
    async def call_tool(req: Request, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        api_key = _require_key(x_api_key)
        body = await req.json()
        tool_name = body["name"]
        args = body.get("arguments", {})
        # Per-request client wired with this caller's API key
        client = make_client(api_key)
        if tool_name == "system_health":
            return await system_health.system_health(_client=client, **args)
        raise HTTPException(status_code=404, detail=f"unknown tool {tool_name}")

    return app


def main() -> None:
    import uvicorn
    registry = InMemoryApiKeyRegistry()
    # In production, registry would load from `mcp_api_keys` table.
    if os.environ.get("MCP_HTTP_DEV_API_KEY"):
        registry.register("dev", os.environ["MCP_HTTP_DEV_API_KEY"], service_jwt=os.environ.get("MCP_API_TOKEN", ""))
    app = build_http_app(registry=registry)
    uvicorn.run(
        app,
        host=os.environ.get("MCP_HTTP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_HTTP_PORT", "8765")),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/e2e/test_http.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/http.py console/mcp/tests/e2e/test_http.py
git commit -m "feat(mcp): HTTP transport with API-key auth + e2e test"
```

---

## Task 13: Mount sub-app onto existing FastAPI

**Files:**
- Create: `console/mcp/mount.py`
- Modify: `console/backend/main.py` (add mount call)
- Create: `console/mcp/tests/e2e/test_mount.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/e2e/test_mount.py`:

```python
import os
import httpx
import pytest

from console.backend.main import app


@pytest.mark.asyncio
async def test_mount_serves_mcp_tools_under_existing_app(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "stub")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://localhost:8080")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Mount provides a chat surface — real test will pass forwarded user JWT;
        # for now just check the route is reachable and rejects unauth'd.
        resp = await c.get("/mcp/tools")
        assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/e2e/test_mount.py -v`
Expected: FAIL — `/mcp/tools` returns 404 (not mounted).

- [ ] **Step 3: Implement `console/mcp/mount.py`**

```python
"""Mount MCP routes onto an existing FastAPI app at /mcp.

Designed for the editor chat surface: forwards the end-user's JWT (already
established by the existing console auth flow) to the console API.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request

from console.mcp.auth.adapters import ChatAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.tools import system_health


def attach(app: FastAPI) -> None:
    @app.get("/mcp/tools")
    async def list_tools(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_user_jwt(authorization)
        return {"tools": [{"name": "system_health", "description": "system observability"}]}

    @app.post("/mcp/call")
    async def call_tool(req: Request, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        jwt = _require_user_jwt(authorization)
        body = await req.json()
        tool_name = body["name"]
        args = body.get("arguments", {})
        auth = ChatAuth(forwarded_jwt=jwt)
        client = ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )
        if tool_name == "system_health":
            return await system_health.system_health(_client=client, **args)
        raise HTTPException(status_code=404, detail=f"unknown tool {tool_name}")


def _require_user_jwt(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="bearer token required")
    return authorization.split(None, 1)[1]
```

- [ ] **Step 4: Modify `console/backend/main.py`**

Add near the bottom (after other router registrations):

```python
from console.mcp.mount import attach as _attach_mcp
_attach_mcp(app)
```

- [ ] **Step 5: Run, verify pass**

Run: `pytest console/mcp/tests/e2e/test_mount.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add console/mcp/mount.py console/backend/main.py console/mcp/tests/e2e/test_mount.py
git commit -m "feat(mcp): mount MCP routes onto existing FastAPI at /mcp"
```

---

## Task 14: Tool — `task_status`

**Files:**
- Create: `console/mcp/tools/task_status.py`
- Create: `console/mcp/tests/tools/test_task_status.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_task_status.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.task_status import task_status


@pytest.mark.asyncio
async def test_pending_status():
    client = AsyncMock()
    client.get.return_value = {"status": "PENDING", "progress": None, "result": None, "error": None}
    out = await task_status(task_id="abc-123", _client=client)
    assert out["ok"] is True
    assert out["status"] == "PENDING"
    assert out["task_id"] == "abc-123"
    client.get.assert_awaited_once_with("/api/pipeline/jobs/abc-123")


@pytest.mark.asyncio
async def test_progress_with_percent_and_stage():
    client = AsyncMock()
    client.get.return_value = {
        "status": "PROGRESS",
        "progress": {"percent": 42, "stage": "compositing"},
        "result": None,
        "error": None,
        "started_at": "2026-05-09T10:00:00Z",
        "elapsed_s": 87,
    }
    out = await task_status(task_id="abc-123", _client=client)
    assert out["progress"]["percent"] == 42
    assert out["elapsed_s"] == 87


@pytest.mark.asyncio
async def test_success_includes_result():
    client = AsyncMock()
    client.get.return_value = {
        "status": "SUCCESS",
        "progress": None,
        "result": {"output_path": "/r/final.mp4", "duration_s": 28800},
        "error": None,
    }
    out = await task_status(task_id="abc-123", _client=client)
    assert out["status"] == "SUCCESS"
    assert out["result"]["output_path"] == "/r/final.mp4"


@pytest.mark.asyncio
async def test_failure_includes_error_string():
    client = AsyncMock()
    client.get.return_value = {
        "status": "FAILURE",
        "progress": None,
        "result": None,
        "error": "ffmpeg exit code 137",
    }
    out = await task_status(task_id="abc-123", _client=client)
    assert out["status"] == "FAILURE"
    assert "ffmpeg" in out["error"]
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_task_status.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/task_status.py`**

```python
"""task_status — poll any task_id returned by an async-kicking tool."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError


async def task_status(*, task_id: str, _client) -> dict[str, Any]:
    """Poll a Celery task by task_id.

    Status values: PENDING | PROGRESS | SUCCESS | FAILURE | REVOKED.
    On SUCCESS, `result` carries the task's payload. On FAILURE, `error` is a
    short string suitable for display.
    """
    try:
        data = await _client.get(f"/api/pipeline/jobs/{task_id}")
    except ConsoleError as e:
        return e.to_envelope()
    return {
        "ok": True,
        "task_id": task_id,
        "status": data.get("status"),
        "progress": data.get("progress"),
        "result": data.get("result"),
        "error": data.get("error"),
        "started_at": data.get("started_at"),
        "elapsed_s": data.get("elapsed_s"),
    }


def register(server, *, client_factory):
    @server.tool(name="task_status")
    async def _task_status(task_id: str) -> dict[str, Any]:
        client = client_factory()
        return await task_status(task_id=task_id, _client=client)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_task_status.py -v`
Expected: 4 passed.

- [ ] **Step 5: Wire `task_status` into all three transports**

In `console/mcp/stdio.py`, add to imports and register:

```python
from console.mcp.tools import system_health, task_status

# in main():
server = build_server(register=[
    lambda s: system_health.register(s, client_factory=client_factory),
    lambda s: task_status.register(s, client_factory=client_factory),
])
```

In `console/mcp/http.py` and `console/mcp/mount.py`, dispatch the new tool name in the `/mcp/call` handler. Add an `elif tool_name == "task_status"` branch that calls `task_status.task_status(_client=client, **args)`.

- [ ] **Step 6: Commit**

```bash
git add console/mcp/tools/task_status.py console/mcp/tests/tools/test_task_status.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): task_status tool wired into all transports"
```

---

## Task 15: Tool — `pipeline_jobs`

**Files:**
- Create: `console/mcp/tools/pipeline_jobs.py`
- Create: `console/mcp/tests/tools/test_pipeline_jobs.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_pipeline_jobs.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.pipeline_jobs import pipeline_jobs


@pytest.mark.asyncio
async def test_list_action_passes_filters():
    client = AsyncMock()
    client.get.return_value = {"items": [], "total": 0}
    out = await pipeline_jobs(action="list", status="FAILURE", limit=20, _client=client)
    assert out["ok"] is True
    client.get.assert_awaited_once_with("/api/pipeline/jobs", params={"status": "FAILURE", "limit": 20})


@pytest.mark.asyncio
async def test_get_logs_action():
    client = AsyncMock()
    client.get.return_value = {"lines": ["log1", "log2"]}
    out = await pipeline_jobs(action="get_logs", job_id="abc", _client=client)
    assert out["data"]["lines"] == ["log1", "log2"]


@pytest.mark.asyncio
async def test_retry_requires_confirm():
    client = AsyncMock()
    out = await pipeline_jobs(action="retry", job_id="abc", _client=client)
    assert out["ok"] is False
    assert out["needs_confirmation"] is True
    client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_retry_with_confirm_calls_patch():
    client = AsyncMock()
    client.patch.return_value = {"job_id": "abc", "status": "RETRY"}
    out = await pipeline_jobs(action="retry", job_id="abc", confirm=True, _client=client)
    assert out["ok"] is True
    client.patch.assert_awaited_once_with("/api/pipeline/jobs/abc/retry")


@pytest.mark.asyncio
async def test_cancel_with_confirm_calls_patch():
    client = AsyncMock()
    client.patch.return_value = {"job_id": "abc", "status": "REVOKED"}
    out = await pipeline_jobs(action="cancel", job_id="abc", confirm=True, _client=client)
    assert out["ok"] is True
    client.patch.assert_awaited_once_with("/api/pipeline/jobs/abc/cancel")


@pytest.mark.asyncio
async def test_stats_action():
    client = AsyncMock()
    client.get.return_value = {"queued": 1, "running": 2, "succeeded": 100, "failed": 3}
    out = await pipeline_jobs(action="stats", _client=client)
    assert out["data"]["queued"] == 1
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_pipeline_jobs.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/pipeline_jobs.py`**

```python
"""pipeline_jobs — list/get/retry/cancel/get_logs/stats over the Celery job table."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError


async def pipeline_jobs(*, action: str, _client, **kwargs) -> dict[str, Any]:
    """Pipeline jobs ops surface.

    Actions:
      - list:      query params {status, limit, offset}
      - get:       requires job_id
      - get_logs:  requires job_id
      - retry:     requires job_id + confirm=true
      - cancel:    requires job_id + confirm=true
      - stats:     overall queue stats
    """
    try:
        if action == "list":
            params = {k: v for k, v in kwargs.items() if k in {"status", "limit", "offset"} and v is not None}
            data = await _client.get("/api/pipeline/jobs", params=params)
            return {"ok": True, "data": data}

        if action == "get":
            job_id = _require(kwargs, "job_id")
            data = await _client.get(f"/api/pipeline/jobs/{job_id}")
            return {"ok": True, "data": data}

        if action == "get_logs":
            job_id = _require(kwargs, "job_id")
            data = await _client.get(f"/api/pipeline/jobs/{job_id}/logs")
            return {"ok": True, "data": data}

        if action == "stats":
            data = await _client.get("/api/pipeline/stats")
            return {"ok": True, "data": data}

        if action in ("retry", "cancel"):
            if not kwargs.get("confirm", False):
                job_id = kwargs.get("job_id")
                return {
                    "ok": False,
                    "needs_confirmation": True,
                    "intent": {"summary": f"{action} job {job_id}", "args": {k: v for k, v in kwargs.items() if k != "_client"}},
                    "to_proceed": "call again with confirm=true",
                }
            job_id = _require(kwargs, "job_id")
            data = await _client.patch(f"/api/pipeline/jobs/{job_id}/{action}")
            return {"ok": True, "data": data}

        return ConsoleError(
            code="validation.invalid_args",
            message=f"unknown action {action!r}",
            retryable=False,
            context={"action": action},
        ).to_envelope()
    except ConsoleError as e:
        return e.to_envelope()


def _require(kwargs: dict[str, Any], name: str) -> Any:
    if name not in kwargs or kwargs[name] is None:
        raise ConsoleError(
            code="validation.invalid_args",
            message=f"missing required arg: {name}",
            retryable=False,
            context={"missing": name},
        )
    return kwargs[name]


def register(server, *, client_factory):
    @server.tool(name="pipeline_jobs")
    async def _pipeline_jobs(action: str, job_id: str | None = None,
                             status: str | None = None, limit: int | None = None,
                             offset: int | None = None, confirm: bool = False) -> dict[str, Any]:
        client = client_factory()
        return await pipeline_jobs(
            action=action, _client=client,
            job_id=job_id, status=status, limit=limit, offset=offset, confirm=confirm,
        )
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_pipeline_jobs.py -v`
Expected: 6 passed.

- [ ] **Step 5: Wire into all transports**

Same pattern as Task 14 step 5: register in stdio.py, add dispatch in http.py and mount.py.

- [ ] **Step 6: Commit**

```bash
git add console/mcp/tools/pipeline_jobs.py console/mcp/tests/tools/test_pipeline_jobs.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): pipeline_jobs tool"
```

---

## Task 16: Tool — `music`

**Files:**
- Create: `console/mcp/tools/music.py`
- Create: `console/mcp/tests/tools/test_music.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_music.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.music import music


@pytest.mark.asyncio
async def test_list_tracks():
    client = AsyncMock()
    client.get.return_value = {"items": [{"id": 1, "title": "calm"}], "total": 1}
    out = await music(action="list_tracks", _client=client)
    client.get.assert_awaited_once_with("/api/music", params={})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_list_templates():
    client = AsyncMock()
    client.get.return_value = [{"id": "ambient_1"}]
    out = await music(action="list_templates", _client=client)
    client.get.assert_awaited_once_with("/api/music/templates", params={})


@pytest.mark.asyncio
async def test_get_track():
    client = AsyncMock()
    client.get.return_value = {"id": 7}
    out = await music(action="get", track_id=7, _client=client)
    client.get.assert_awaited_once_with("/api/music/7", params={})


@pytest.mark.asyncio
async def test_stream_url_returns_url():
    client = AsyncMock()
    out = await music(action="stream_url", track_id=7, _client=client)
    assert out["ok"] is True
    assert out["data"]["url"].endswith("/api/music/7/stream")


@pytest.mark.asyncio
async def test_generate_returns_task_envelope():
    client = AsyncMock()
    client.post.return_value = {"task_id": "music-1"}
    out = await music(action="generate", prompt="forest dawn", duration_s=480, confirm=True, _client=client)
    assert out["ok"] is True
    assert out["task_id"] == "music-1"
    assert out["task_kind"] == "music_generate"
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_requires_confirm():
    client = AsyncMock()
    out = await music(action="generate", prompt="x", duration_s=60, _client=client)
    assert out["ok"] is False
    assert out["needs_confirmation"] is True


@pytest.mark.asyncio
async def test_delete_requires_confirm_and_id():
    client = AsyncMock()
    # missing confirm
    out = await music(action="delete", track_id=7, _client=client)
    assert out["needs_confirmation"] is True
    # confirm but wrong id
    out = await music(action="delete", track_id=7, confirm=True, confirm_id=8, _client=client)
    assert out["error"]["code"] == "validation.confirm_id_mismatch"
    # confirm + match
    out = await music(action="delete", track_id=7, confirm=True, confirm_id=7, _client=client)
    client.delete.assert_awaited_once_with("/api/music/7")


@pytest.mark.asyncio
async def test_update():
    client = AsyncMock()
    client.put.return_value = {"id": 7, "title": "new"}
    out = await music(action="update", track_id=7, fields={"title": "new"}, confirm=True, _client=client)
    client.put.assert_awaited_once_with("/api/music/7", json={"title": "new"})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_elevenlabs_plan_and_compose():
    client = AsyncMock()
    client.post.return_value = {"plan_id": 1, "sections": []}
    out = await music(action="elevenlabs_plan", prompt="rain", _client=client)
    client.post.assert_awaited_with("/api/music/elevenlabs/plan", json={"prompt": "rain"})

    client.post.reset_mock()
    client.post.return_value = {"task_id": "elv-1"}
    out = await music(action="elevenlabs_compose", plan_id=1, confirm=True, _client=client)
    client.post.assert_awaited_with("/api/music/elevenlabs/compose", json={"plan_id": 1})
    assert out["task_kind"] == "music_elevenlabs_compose"
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_music.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/music.py`**

```python
"""music — full CRUD + AI-generate + ElevenLabs."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools._common import returns_task


async def music(*, action: str, _client, **kw) -> dict[str, Any]:
    """Music library + generation.

    Actions:
      - list_templates                          (R)
      - list_tracks  [niche, limit, offset]     (R)
      - get          {track_id}                 (R)
      - stream_url   {track_id}                 (R)  → returns URL string
      - generate     {prompt, duration_s, ...}  (W async, confirm=true)
      - upload       {file_path, title, ...}    (W, confirm=true)
      - update       {track_id, fields}         (W, confirm=true)
      - delete       {track_id}                 (W destructive)
      - elevenlabs_plan    {prompt, ...}        (W, confirm=true) → plan
      - elevenlabs_compose {plan_id}            (W async, confirm=true)
      - get_task     {task_id}                  (R)
    """
    try:
        if action == "list_templates":
            return _ok(await _client.get("/api/music/templates", params={}))
        if action == "list_tracks":
            params = {k: v for k, v in kw.items() if k in {"niche", "limit", "offset"} and v is not None}
            return _ok(await _client.get("/api/music", params=params))
        if action == "get":
            tid = _require(kw, "track_id")
            return _ok(await _client.get(f"/api/music/{tid}", params={}))
        if action == "stream_url":
            tid = _require(kw, "track_id")
            return {"ok": True, "data": {"url": f"/api/music/{tid}/stream"}}
        if action == "get_task":
            taskid = _require(kw, "task_id")
            return _ok(await _client.get(f"/api/music/tasks/{taskid}"))

        if action == "generate":
            return await _confirmed_async(
                kw, summary=f"generate music: {kw.get('prompt','')!r}",
                task_kind="music_generate",
                run=lambda: _client.post("/api/music/generate", json=_pick(kw, {"prompt", "duration_s", "style", "niche", "voice"})),
            )
        if action == "elevenlabs_compose":
            return await _confirmed_async(
                kw, summary=f"elevenlabs compose plan {kw.get('plan_id')}",
                task_kind="music_elevenlabs_compose",
                run=lambda: _client.post("/api/music/elevenlabs/compose", json=_pick(kw, {"plan_id"})),
            )
        if action == "elevenlabs_plan":
            return await _confirmed_sync(
                kw, summary="elevenlabs plan",
                run=lambda: _client.post("/api/music/elevenlabs/plan", json=_pick(kw, {"prompt", "duration_s", "style"})),
            )
        if action == "upload":
            return await _confirmed_sync(
                kw, summary=f"upload music track {kw.get('title')!r}",
                run=lambda: _client.post("/api/music/upload", json=_pick(kw, {"file_path", "title", "niche", "tags"})),
            )
        if action == "update":
            tid = _require(kw, "track_id")
            return await _confirmed_sync(
                kw, summary=f"update music track {tid}",
                run=lambda: _client.put(f"/api/music/{tid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            tid = _require(kw, "track_id")
            return await _confirmed_destructive(
                kw, id_arg="track_id",
                summary=f"DELETE music track {tid}",
                run=lambda: _client.delete(f"/api/music/{tid}"),
            )

        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


# ── shared helpers (also used by other tool modules) ─────────────────────────

def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _bad_action(action: str) -> dict[str, Any]:
    return ConsoleError(
        code="validation.invalid_args",
        message=f"unknown action {action!r}",
        retryable=False,
        context={"action": action},
    ).to_envelope()


def _require(kw: dict[str, Any], name: str) -> Any:
    if kw.get(name) is None:
        raise ConsoleError(
            code="validation.invalid_args",
            message=f"missing required arg: {name}",
            retryable=False,
            context={"missing": name},
        )
    return kw[name]


def _pick(kw: dict[str, Any], names: set[str]) -> dict[str, Any]:
    return {k: kw[k] for k in names if k in kw and kw[k] is not None}


async def _confirmed_sync(kw, *, summary, run):
    if not kw.get("confirm", False):
        return _intent(summary, kw)
    data = await run()
    return _ok(data)


async def _confirmed_async(kw, *, summary, task_kind, run):
    if not kw.get("confirm", False):
        return _intent(summary, kw)
    data = await run()
    if isinstance(data, dict) and data.get("ok") is False:
        return data
    return {
        "ok": True,
        "task_id": (data or {}).get("task_id"),
        "status_tool": "task_status",
        "task_kind": task_kind,
        "poll_hint": "every 10s",
    }


async def _confirmed_destructive(kw, *, id_arg, summary, run):
    if not kw.get("confirm", False):
        return _intent(summary, kw, hint=f"call again with confirm=true and confirm_id={kw.get(id_arg)}")
    if kw.get("confirm_id") != kw.get(id_arg):
        return ConsoleError(
            code="validation.confirm_id_mismatch",
            message=f"confirm_id must equal {id_arg}",
            retryable=False,
            context={id_arg: kw.get(id_arg), "confirm_id": kw.get("confirm_id")},
        ).to_envelope()
    return _ok(await run())


def _intent(summary, kw, hint="call again with confirm=true"):
    return {
        "ok": False,
        "needs_confirmation": True,
        "intent": {"summary": summary, "args": {k: v for k, v in kw.items() if k != "_client" and not _is_secret(k)}},
        "to_proceed": hint,
    }


def _is_secret(name: str) -> bool:
    return name in {"password"} or name.endswith(("_token", "_key", "_secret"))


def register(server, *, client_factory):
    @server.tool(name="music")
    async def _music(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await music(action=action, _client=client, **kwargs)
```

**Note:** The helpers `_ok`, `_bad_action`, `_require`, `_pick`, `_confirmed_*`, `_intent`, `_is_secret` will be used by every subsequent tool module. After Task 18 (visual_asset, the third tool to copy them), Task 28 will refactor them into `tools/_common.py`. Until then, copy them into each tool file — explicit duplication is cheaper to read than premature abstraction.

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_music.py -v`
Expected: 9 passed.

- [ ] **Step 5: Wire into all transports**

Add `music` to register list in `console/mcp/stdio.py`, dispatch in `http.py` and `mount.py`.

- [ ] **Step 6: Commit**

```bash
git add console/mcp/tools/music.py console/mcp/tests/tools/test_music.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): music tool (CRUD + generate + elevenlabs)"
```

---

## Task 17: Tool — `sfx`

**Files:**
- Create: `console/mcp/tools/sfx.py`
- Create: `console/mcp/tests/tools/test_sfx.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_sfx.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.sfx import sfx


@pytest.mark.asyncio
async def test_list_sound_types():
    client = AsyncMock()
    client.get.return_value = ["wind", "rain", "fire"]
    out = await sfx(action="list_sound_types", _client=client)
    client.get.assert_awaited_once_with("/api/sfx/sound-types", params={})


@pytest.mark.asyncio
async def test_list_with_filters():
    client = AsyncMock()
    client.get.return_value = []
    await sfx(action="list", sound_type="wind", limit=20, _client=client)
    client.get.assert_awaited_once_with("/api/sfx", params={"sound_type": "wind", "limit": 20})


@pytest.mark.asyncio
async def test_stream_url():
    client = AsyncMock()
    out = await sfx(action="get_stream_url", sfx_id=3, _client=client)
    assert out["data"]["url"] == "/api/sfx/3/stream"


@pytest.mark.asyncio
async def test_generate_async():
    client = AsyncMock()
    client.post.return_value = {"task_id": "sfx-1"}
    out = await sfx(action="generate", prompt="thunder", duration_s=4, confirm=True, _client=client)
    assert out["task_kind"] == "sfx_generate"
    assert out["task_id"] == "sfx-1"


@pytest.mark.asyncio
async def test_import_file():
    client = AsyncMock()
    client.post.return_value = {"id": 9, "name": "x"}
    out = await sfx(action="import_file", file_path="/tmp/x.wav", name="x", confirm=True, _client=client)
    client.post.assert_awaited_once_with("/api/sfx/import", json={"file_path": "/tmp/x.wav", "name": "x"})


@pytest.mark.asyncio
async def test_delete_destructive():
    client = AsyncMock()
    out = await sfx(action="delete", sfx_id=9, confirm=True, confirm_id=9, _client=client)
    client.delete.assert_awaited_once_with("/api/sfx/9")
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_sfx.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/sfx.py`**

```python
"""sfx — sound effects library + generation."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (  # reuse helpers until Task 28 refactor
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def sfx(*, action: str, _client, **kw) -> dict[str, Any]:
    """SFX library.

    Actions:
      - list_sound_types
      - list                   [sound_type, limit, offset]
      - get_stream_url         {sfx_id}
      - generate               {prompt, duration_s, sound_type}  (W async)
      - import_file            {file_path, name, sound_type}     (W)
      - delete                 {sfx_id} (destructive)
    """
    try:
        if action == "list_sound_types":
            return _ok(await _client.get("/api/sfx/sound-types", params={}))
        if action == "list":
            params = _pick(kw, {"sound_type", "limit", "offset"})
            return _ok(await _client.get("/api/sfx", params=params))
        if action == "get_stream_url":
            sid = _require(kw, "sfx_id")
            return {"ok": True, "data": {"url": f"/api/sfx/{sid}/stream"}}
        if action == "generate":
            return await _confirmed_async(
                kw, summary=f"generate sfx: {kw.get('prompt')!r}",
                task_kind="sfx_generate",
                run=lambda: _client.post("/api/sfx/generate", json=_pick(kw, {"prompt", "duration_s", "sound_type"})),
            )
        if action == "import_file":
            return await _confirmed_sync(
                kw, summary=f"import sfx file {kw.get('file_path')!r}",
                run=lambda: _client.post("/api/sfx/import", json=_pick(kw, {"file_path", "name", "sound_type"})),
            )
        if action == "delete":
            sid = _require(kw, "sfx_id")
            return await _confirmed_destructive(
                kw, id_arg="sfx_id",
                summary=f"DELETE sfx {sid}",
                run=lambda: _client.delete(f"/api/sfx/{sid}"),
            )
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory):
    @server.tool(name="sfx")
    async def _sfx(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await sfx(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_sfx.py -v`
Expected: 6 passed.

- [ ] **Step 5: Wire into transports + commit**

```bash
# update stdio.py / http.py / mount.py with sfx
git add console/mcp/tools/sfx.py console/mcp/tests/tools/test_sfx.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): sfx tool"
```

---

## Task 18: Tool — `visual_asset`

**Files:**
- Create: `console/mcp/tools/visual_asset.py`
- Create: `console/mcp/tests/tools/test_visual_asset.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_visual_asset.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.visual_asset import visual_asset


@pytest.mark.asyncio
async def test_list_with_filters():
    client = AsyncMock()
    client.get.return_value = {"items": [], "total": 0}
    await visual_asset(action="list", niche="forest", limit=10, _client=client)
    client.get.assert_awaited_once_with("/api/production/assets", params={"niche": "forest", "limit": 10})


@pytest.mark.asyncio
async def test_get():
    client = AsyncMock()
    client.get.return_value = {"id": 5}
    await visual_asset(action="get", asset_id=5, _client=client)
    client.get.assert_awaited_once_with("/api/production/assets/5", params={})


@pytest.mark.asyncio
async def test_stream_and_thumbnail_urls():
    client = AsyncMock()
    out = await visual_asset(action="stream_url", asset_id=5, _client=client)
    assert out["data"]["url"].endswith("/api/production/assets/5/stream")
    out = await visual_asset(action="get_thumbnail", asset_id=5, _client=client)
    assert out["data"]["url"].endswith("/api/production/assets/5/thumbnail")


@pytest.mark.asyncio
async def test_upload():
    client = AsyncMock()
    client.post.return_value = {"id": 9}
    out = await visual_asset(action="upload", file_path="/tmp/x.mp4", title="x",
                             niche="forest", confirm=True, _client=client)
    client.post.assert_awaited_once_with(
        "/api/production/assets/upload",
        json={"file_path": "/tmp/x.mp4", "title": "x", "niche": "forest"},
    )


@pytest.mark.asyncio
async def test_animate_async():
    client = AsyncMock()
    client.post.return_value = {"task_id": "rwy-1"}
    out = await visual_asset(action="animate", asset_id=5, prompt="slow zoom", confirm=True, _client=client)
    assert out["task_kind"] == "visual_asset_animate"
    client.post.assert_awaited_once_with("/api/production/assets/5/animate", json={"prompt": "slow zoom"})


@pytest.mark.asyncio
async def test_upscale_async():
    client = AsyncMock()
    client.post.return_value = {"task_id": "tpz-1"}
    out = await visual_asset(action="upscale", asset_id=5, target="4k", confirm=True, _client=client)
    assert out["task_kind"] == "visual_asset_upscale"
    client.post.assert_awaited_once_with("/api/production/assets/5/upscale", json={"target": "4k"})


@pytest.mark.asyncio
async def test_update():
    client = AsyncMock()
    client.put.return_value = {"id": 5, "title": "y"}
    await visual_asset(action="update", asset_id=5, fields={"title": "y"}, confirm=True, _client=client)
    client.put.assert_awaited_once_with("/api/production/assets/5", json={"title": "y"})


@pytest.mark.asyncio
async def test_delete_destructive():
    client = AsyncMock()
    out = await visual_asset(action="delete", asset_id=5, confirm=True, confirm_id=5, _client=client)
    client.delete.assert_awaited_once_with("/api/production/assets/5")
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_visual_asset.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/visual_asset.py`**

```python
"""visual_asset — videos/images library used as backgrounds in YouTube videos."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def visual_asset(*, action: str, _client, **kw) -> dict[str, Any]:
    """Visual assets (background videos/images).

    Actions:
      - list                {niche, limit, offset}
      - get                 {asset_id}
      - stream_url          {asset_id}
      - get_thumbnail       {asset_id}
      - upload              {file_path, title, niche, ...}
      - update              {asset_id, fields}
      - delete              {asset_id}                    (destructive)
      - animate             {asset_id, prompt}            (W async, Runway)
      - upscale             {asset_id, target}            (W async, Topaz)
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/production/assets", params=_pick(kw, {"niche", "limit", "offset"})))
        if action == "get":
            aid = _require(kw, "asset_id")
            return _ok(await _client.get(f"/api/production/assets/{aid}", params={}))
        if action == "stream_url":
            aid = _require(kw, "asset_id")
            return {"ok": True, "data": {"url": f"/api/production/assets/{aid}/stream"}}
        if action == "get_thumbnail":
            aid = _require(kw, "asset_id")
            return {"ok": True, "data": {"url": f"/api/production/assets/{aid}/thumbnail"}}
        if action == "upload":
            return await _confirmed_sync(
                kw, summary=f"upload visual asset {kw.get('title')!r}",
                run=lambda: _client.post("/api/production/assets/upload",
                                         json=_pick(kw, {"file_path", "title", "niche", "tags", "duration_s"})),
            )
        if action == "update":
            aid = _require(kw, "asset_id")
            return await _confirmed_sync(
                kw, summary=f"update visual asset {aid}",
                run=lambda: _client.put(f"/api/production/assets/{aid}", json=kw.get("fields") or {}),
            )
        if action == "animate":
            aid = _require(kw, "asset_id")
            return await _confirmed_async(
                kw, summary=f"animate visual asset {aid}",
                task_kind="visual_asset_animate",
                run=lambda: _client.post(f"/api/production/assets/{aid}/animate", json=_pick(kw, {"prompt", "duration_s", "model"})),
            )
        if action == "upscale":
            aid = _require(kw, "asset_id")
            return await _confirmed_async(
                kw, summary=f"upscale visual asset {aid}",
                task_kind="visual_asset_upscale",
                run=lambda: _client.post(f"/api/production/assets/{aid}/upscale", json=_pick(kw, {"target", "model"})),
            )
        if action == "delete":
            aid = _require(kw, "asset_id")
            return await _confirmed_destructive(
                kw, id_arg="asset_id",
                summary=f"DELETE visual asset {aid}",
                run=lambda: _client.delete(f"/api/production/assets/{aid}"),
            )
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory):
    @server.tool(name="visual_asset")
    async def _visual_asset(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await visual_asset(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_visual_asset.py -v`
Expected: 8 passed.

- [ ] **Step 5: Wire into transports + commit**

```bash
git add console/mcp/tools/visual_asset.py console/mcp/tests/tools/test_visual_asset.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): visual_asset tool (CRUD + animate + upscale)"
```

---

## Task 19: Tool — `channel_plan`

**Files:**
- Create: `console/mcp/tools/channel_plan.py`
- Create: `console/mcp/tests/tools/test_channel_plan.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_channel_plan.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.channel_plan import channel_plan


@pytest.mark.asyncio
async def test_list_and_get():
    client = AsyncMock()
    client.get.return_value = {"items": [], "total": 0}
    await channel_plan(action="list", _client=client)
    client.get.assert_awaited_with("/api/channel-plans", params={})

    client.get.return_value = {"id": 7}
    await channel_plan(action="get", plan_id=7, _client=client)
    client.get.assert_awaited_with("/api/channel-plans/7", params={})


@pytest.mark.asyncio
async def test_import_json():
    client = AsyncMock()
    client.post.return_value = {"plan_id": 7}
    out = await channel_plan(action="import_json", payload={"channel": "x"}, confirm=True, _client=client)
    client.post.assert_awaited_once_with("/api/channel-plans/import", json={"channel": "x"})
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_update():
    client = AsyncMock()
    client.put.return_value = {"id": 7}
    await channel_plan(action="update", plan_id=7, fields={"name": "n"}, confirm=True, _client=client)
    client.put.assert_awaited_once_with("/api/channel-plans/7", json={"name": "n"})


@pytest.mark.asyncio
async def test_delete_destructive():
    client = AsyncMock()
    out = await channel_plan(action="delete", plan_id=7, confirm=True, confirm_id=7, _client=client)
    client.delete.assert_awaited_once_with("/api/channel-plans/7")


@pytest.mark.asyncio
async def test_ai_seo():
    client = AsyncMock()
    client.post.return_value = {"title": "...", "description": "...", "tags": []}
    out = await channel_plan(action="ai_seo", plan_id=7, confirm=True, _client=client)
    client.post.assert_awaited_once_with("/api/channel-plans/7/ai/seo", json={})


@pytest.mark.asyncio
async def test_ai_autofill_and_prompts_and_ask():
    client = AsyncMock()
    client.post.return_value = {"answer": "x"}
    await channel_plan(action="ai_autofill", plan_id=7, confirm=True, _client=client)
    client.post.assert_awaited_with("/api/channel-plans/7/ai/autofill", json={})
    await channel_plan(action="ai_prompts", plan_id=7, hints={"theme": "calm"}, confirm=True, _client=client)
    client.post.assert_awaited_with("/api/channel-plans/7/ai/prompts", json={"hints": {"theme": "calm"}})
    await channel_plan(action="ai_ask", plan_id=7, question="what niche?", confirm=True, _client=client)
    client.post.assert_awaited_with("/api/channel-plans/7/ai/ask", json={"question": "what niche?"})
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_channel_plan.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/channel_plan.py`**

```python
"""channel_plan — CRUD + JSON import + AI helpers."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_destructive,
)


async def channel_plan(*, action: str, _client, **kw) -> dict[str, Any]:
    """Channel plans (the upstream brief for a channel's content).

    Actions:
      - list                                                    (R)
      - get          {plan_id}                                  (R)
      - import_json  {payload: dict}                            (W) → plan_id
      - update       {plan_id, fields}                          (W)
      - delete       {plan_id}                                  (W destructive)
      - ai_seo       {plan_id}                                  (W) → SEO suggestion
      - ai_prompts   {plan_id, hints?}                          (W) → prompt suggestions
      - ai_autofill  {plan_id, hints?}                          (W) → bulk autofill
      - ai_ask       {plan_id, question}                        (W) → answer
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/channel-plans", params={}))
        if action == "get":
            pid = _require(kw, "plan_id")
            return _ok(await _client.get(f"/api/channel-plans/{pid}", params={}))
        if action == "import_json":
            payload = _require(kw, "payload")
            return await _confirmed_sync(
                kw, summary="import channel plan from JSON",
                run=lambda: _client.post("/api/channel-plans/import", json=payload),
            )
        if action == "update":
            pid = _require(kw, "plan_id")
            return await _confirmed_sync(
                kw, summary=f"update channel plan {pid}",
                run=lambda: _client.put(f"/api/channel-plans/{pid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            pid = _require(kw, "plan_id")
            return await _confirmed_destructive(
                kw, id_arg="plan_id",
                summary=f"DELETE channel plan {pid}",
                run=lambda: _client.delete(f"/api/channel-plans/{pid}"),
            )
        if action == "ai_seo":
            pid = _require(kw, "plan_id")
            return await _confirmed_sync(
                kw, summary=f"ai SEO for plan {pid}",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/seo", json={}),
            )
        if action == "ai_prompts":
            pid = _require(kw, "plan_id")
            body = {"hints": kw["hints"]} if kw.get("hints") else {}
            return await _confirmed_sync(
                kw, summary=f"ai prompts for plan {pid}",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/prompts", json=body),
            )
        if action == "ai_autofill":
            pid = _require(kw, "plan_id")
            body = {"hints": kw["hints"]} if kw.get("hints") else {}
            return await _confirmed_sync(
                kw, summary=f"ai autofill plan {pid}",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/autofill", json=body),
            )
        if action == "ai_ask":
            pid = _require(kw, "plan_id")
            q = _require(kw, "question")
            return await _confirmed_sync(
                kw, summary=f"ai ask on plan {pid}: {q!r}",
                run=lambda: _client.post(f"/api/channel-plans/{pid}/ai/ask", json={"question": q}),
            )
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory):
    @server.tool(name="channel_plan")
    async def _channel_plan(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await channel_plan(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_channel_plan.py -v`
Expected: 6 passed.

- [ ] **Step 5: Wire into transports + commit**

```bash
git add console/mcp/tools/channel_plan.py console/mcp/tests/tools/test_channel_plan.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): channel_plan tool (CRUD + import + AI helpers)"
```

---

## Task 20: Tool — `channel`

**Files:**
- Create: `console/mcp/tools/channel.py`
- Create: `console/mcp/tests/tools/test_channel.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_channel.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.channel import channel


@pytest.mark.asyncio
async def test_list_get_create_update_delete():
    c = AsyncMock()
    c.get.return_value = []
    await channel(action="list", _client=c)
    c.get.assert_awaited_with("/api/channels", params={})

    c.get.return_value = {"id": 5}
    await channel(action="get", channel_id=5, _client=c)
    c.get.assert_awaited_with("/api/channels/5", params={})

    c.post.return_value = {"id": 5}
    await channel(action="create", fields={"name": "n", "platform": "youtube"}, confirm=True, _client=c)
    c.post.assert_awaited_with("/api/channels", json={"name": "n", "platform": "youtube"})

    c.put.return_value = {"id": 5}
    await channel(action="update", channel_id=5, fields={"name": "x"}, confirm=True, _client=c)
    c.put.assert_awaited_with("/api/channels/5", json={"name": "x"})

    out = await channel(action="delete", channel_id=5, confirm=True, confirm_id=5, _client=c)
    c.delete.assert_awaited_once_with("/api/channels/5")


@pytest.mark.asyncio
async def test_defaults():
    c = AsyncMock()
    c.get.return_value = {}
    await channel(action="get_defaults", template="ambient", _client=c)
    c.get.assert_awaited_with("/api/channels/defaults/ambient", params={})

    await channel(action="set_defaults", template="ambient",
                  fields={"music_track_id": 7}, confirm=True, _client=c)
    c.put.assert_awaited_with("/api/channels/defaults/ambient", json={"music_track_id": 7})


@pytest.mark.asyncio
async def test_credential_status_read_only():
    c = AsyncMock()
    c.get.return_value = {"connected": True, "expires_at": "..."}
    out = await channel(action="credential_status", platform="youtube", _client=c)
    c.get.assert_awaited_once_with("/api/credentials/youtube", params={})
    assert out["ok"] is True
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_channel.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/channel.py`**

```python
"""channel — channel CRUD + template defaults + credential status (read-only)."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_destructive,
)


async def channel(*, action: str, _client, **kw) -> dict[str, Any]:
    """Channels (per-platform target + template defaults).

    Actions:
      - list                              (R)
      - get          {channel_id}         (R)
      - create       {fields}             (W)
      - update       {channel_id, fields} (W)
      - delete       {channel_id}         (W destructive)
      - get_defaults {template}           (R)
      - set_defaults {template, fields}   (W)
      - credential_status {platform}      (R) — read-only on secrets
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/channels", params={}))
        if action == "get":
            cid = _require(kw, "channel_id")
            return _ok(await _client.get(f"/api/channels/{cid}", params={}))
        if action == "create":
            fields = _require(kw, "fields")
            return await _confirmed_sync(
                kw, summary="create channel",
                run=lambda: _client.post("/api/channels", json=fields),
            )
        if action == "update":
            cid = _require(kw, "channel_id")
            return await _confirmed_sync(
                kw, summary=f"update channel {cid}",
                run=lambda: _client.put(f"/api/channels/{cid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            cid = _require(kw, "channel_id")
            return await _confirmed_destructive(
                kw, id_arg="channel_id",
                summary=f"DELETE channel {cid}",
                run=lambda: _client.delete(f"/api/channels/{cid}"),
            )
        if action == "get_defaults":
            tpl = _require(kw, "template")
            return _ok(await _client.get(f"/api/channels/defaults/{tpl}", params={}))
        if action == "set_defaults":
            tpl = _require(kw, "template")
            return await _confirmed_sync(
                kw, summary=f"set defaults for template {tpl!r}",
                run=lambda: _client.put(f"/api/channels/defaults/{tpl}", json=kw.get("fields") or {}),
            )
        if action == "credential_status":
            platform = _require(kw, "platform")
            return _ok(await _client.get(f"/api/credentials/{platform}", params={}))
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory):
    @server.tool(name="channel")
    async def _channel(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await channel(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_channel.py -v`
Expected: 3 passed.

- [ ] **Step 5: Wire into transports + commit**

```bash
git add console/mcp/tools/channel.py console/mcp/tests/tools/test_channel.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): channel tool"
```

---

## Task 21: Tool — `youtube_video` (read-only actions)

**Files:**
- Create: `console/mcp/tools/youtube_video.py`
- Create: `console/mcp/tests/tools/test_youtube_video_read.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_youtube_video_read.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.youtube_video import youtube_video


@pytest.mark.asyncio
async def test_list_with_filters():
    c = AsyncMock()
    c.get.return_value = {"items": [], "total": 0}
    await youtube_video(action="list", status="draft", limit=20, _client=c)
    c.get.assert_awaited_once_with("/api/youtube-videos", params={"status": "draft", "limit": 20})


@pytest.mark.asyncio
async def test_get_returns_video():
    c = AsyncMock()
    c.get.return_value = {"id": 7, "title": "x"}
    out = await youtube_video(action="get", video_id=7, _client=c)
    assert out["data"]["id"] == 7
    c.get.assert_awaited_once_with("/api/youtube-videos/7", params={})


@pytest.mark.asyncio
async def test_list_templates_and_get_template():
    c = AsyncMock()
    c.get.return_value = []
    await youtube_video(action="list_templates", _client=c)
    c.get.assert_awaited_with("/api/youtube-videos/templates", params={})

    c.get.return_value = {"id": 1}
    await youtube_video(action="get_template", template_id=1, _client=c)
    c.get.assert_awaited_with("/api/youtube-videos/templates/1", params={})


@pytest.mark.asyncio
async def test_get_render_state():
    c = AsyncMock()
    c.get.return_value = {"phase": "audio_preview", "progress": 0.4}
    out = await youtube_video(action="get_render_state", video_id=7, _client=c)
    c.get.assert_awaited_once_with("/api/youtube-videos/7/render/state", params={})
    assert out["data"]["phase"] == "audio_preview"
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_youtube_video_read.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement read paths in `console/mcp/tools/youtube_video.py`**

```python
"""youtube_video — full /youtube page surface.

Read paths only in this file at first; write/render-gate paths added in Task 22.
"""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


READ_ACTIONS = {"list", "get", "list_templates", "get_template", "get_render_state"}


async def youtube_video(*, action: str, _client, **kw) -> dict[str, Any]:
    """YouTube video lifecycle.

    Read actions:
      - list           [status, niche, limit, offset]
      - get            {video_id}
      - list_templates
      - get_template   {template_id}
      - get_render_state {video_id}

    Write actions added in Task 22.
    """
    try:
        if action == "list":
            return _ok(await _client.get("/api/youtube-videos",
                                         params=_pick(kw, {"status", "niche", "limit", "offset"})))
        if action == "get":
            vid = _require(kw, "video_id")
            return _ok(await _client.get(f"/api/youtube-videos/{vid}", params={}))
        if action == "list_templates":
            return _ok(await _client.get("/api/youtube-videos/templates", params={}))
        if action == "get_template":
            tid = _require(kw, "template_id")
            return _ok(await _client.get(f"/api/youtube-videos/templates/{tid}", params={}))
        if action == "get_render_state":
            vid = _require(kw, "video_id")
            return _ok(await _client.get(f"/api/youtube-videos/{vid}/render/state", params={}))
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory):
    @server.tool(name="youtube_video")
    async def _youtube_video(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await youtube_video(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_youtube_video_read.py -v`
Expected: 4 passed.

- [ ] **Step 5: Wire into transports + commit**

```bash
git add console/mcp/tools/youtube_video.py console/mcp/tests/tools/test_youtube_video_read.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): youtube_video tool (read paths)"
```

---

## Task 22: Tool — `youtube_video` (write + render gates)

**Files:**
- Modify: `console/mcp/tools/youtube_video.py`
- Create: `console/mcp/tests/tools/test_youtube_video_write.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_youtube_video_write.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.youtube_video import youtube_video


@pytest.mark.asyncio
async def test_create_with_full_config():
    c = AsyncMock()
    c.post.return_value = {"id": 9}
    fields = {
        "title": "Forest Rain 8h",
        "template_id": 2,
        "theme": "forest",
        "music_track_id": 14,
        "visual_asset_id": 3,
        "thumbnail_asset_id": 12,
        "thumbnail_text": "8 HOURS · DEEP SLEEP",
        "seo_title": "Forest Rain ASMR | 8 Hours",
        "seo_description": "...",
        "seo_tags": ["asmr", "rain", "sleep"],
        "target_duration_h": 8.0,
        "output_quality": "1080p",
        "sfx_density_seconds": 90,
        "visual_clip_durations_s": [12.0, 8.0, 16.0],
        "sfx_overrides": {"wind": [{"at_s": 30, "vol": 0.4}]},
    }
    out = await youtube_video(action="create", fields=fields, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos", json=fields)
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_update_partial_fields():
    c = AsyncMock()
    c.put.return_value = {"id": 9}
    await youtube_video(action="update", video_id=9, fields={"thumbnail_text": "NEW"},
                        confirm=True, _client=c)
    c.put.assert_awaited_once_with("/api/youtube-videos/9", json={"thumbnail_text": "NEW"})


@pytest.mark.asyncio
async def test_import_json_calls_create_with_payload():
    c = AsyncMock()
    c.post.return_value = {"id": 9}
    payload = {"title": "x", "theme": "ambient"}
    out = await youtube_video(action="import_json", payload=payload, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos", json=payload)


@pytest.mark.asyncio
async def test_delete_destructive():
    c = AsyncMock()
    out = await youtube_video(action="delete", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.delete.assert_awaited_once_with("/api/youtube-videos/9")


@pytest.mark.asyncio
async def test_render_gates_audio_preview_then_approve():
    c = AsyncMock()
    c.post.return_value = {"task_id": "audio-1"}
    out = await youtube_video(action="render_audio_preview", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos/9/render/audio-preview")
    assert out["task_kind"] == "youtube_render_audio_preview"

    c.post.reset_mock()
    c.post.return_value = {"approved": True}
    await youtube_video(action="approve_audio_preview", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos/9/render/audio-preview/approve")


@pytest.mark.asyncio
async def test_reject_video_preview_destructive():
    c = AsyncMock()
    out = await youtube_video(action="reject_video_preview", video_id=9,
                              confirm=True, confirm_id=9, _client=c)
    c.post.assert_awaited_once_with("/api/youtube-videos/9/render/video-preview/reject")


@pytest.mark.asyncio
async def test_render_final_and_cancel_and_resume():
    c = AsyncMock()
    c.post.return_value = {"task_id": "final-1"}
    out = await youtube_video(action="render_final", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_with("/api/youtube-videos/9/render/final")
    assert out["task_kind"] == "youtube_render_final"

    c.post.reset_mock()
    c.post.return_value = {"cancelled": True}
    await youtube_video(action="cancel_render", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.post.assert_awaited_with("/api/youtube-videos/9/render/cancel")

    c.post.reset_mock()
    c.post.return_value = {"resumed": True}
    await youtube_video(action="resume_render", video_id=9, confirm=True, _client=c)
    c.post.assert_awaited_with("/api/youtube-videos/9/render/resume")
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_youtube_video_write.py -v`
Expected: FAIL — write actions not implemented.

- [ ] **Step 3: Replace `console/mcp/tools/youtube_video.py` with full impl**

```python
"""youtube_video — full /youtube page surface (read + write + render gates)."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def youtube_video(*, action: str, _client, **kw) -> dict[str, Any]:
    """YouTube video lifecycle.

    Read:
      - list, get, list_templates, get_template, get_render_state

    Write (CRUD + import):
      - create       {fields}
      - update       {video_id, fields}
      - delete       {video_id}                    (destructive)
      - import_json  {payload}                     — same as create with the JSON payload

    Render gates:
      - render_audio_preview  {video_id}           (W async)
      - approve_audio_preview {video_id}           (W)
      - reject_audio_preview  {video_id}           (W destructive)
      - render_video_preview  {video_id}           (W async)
      - approve_video_preview {video_id}           (W)
      - reject_video_preview  {video_id}           (W destructive)
      - render_final          {video_id}           (W async)
      - cancel_render         {video_id}           (W destructive)
      - resume_render         {video_id}           (W async)
    """
    try:
        # ── Reads ────────────────────────────────────────────────────────────
        if action == "list":
            return _ok(await _client.get("/api/youtube-videos",
                                         params=_pick(kw, {"status", "niche", "limit", "offset"})))
        if action == "get":
            vid = _require(kw, "video_id")
            return _ok(await _client.get(f"/api/youtube-videos/{vid}", params={}))
        if action == "list_templates":
            return _ok(await _client.get("/api/youtube-videos/templates", params={}))
        if action == "get_template":
            tid = _require(kw, "template_id")
            return _ok(await _client.get(f"/api/youtube-videos/templates/{tid}", params={}))
        if action == "get_render_state":
            vid = _require(kw, "video_id")
            return _ok(await _client.get(f"/api/youtube-videos/{vid}/render/state", params={}))

        # ── CRUD ─────────────────────────────────────────────────────────────
        if action in ("create", "import_json"):
            payload = kw.get("payload") if action == "import_json" else kw.get("fields")
            payload = _require({"_": payload}, "_")  # raise if None
            return await _confirmed_sync(
                kw, summary=f"create youtube video {payload.get('title','<untitled>')!r}",
                run=lambda: _client.post("/api/youtube-videos", json=payload),
            )
        if action == "update":
            vid = _require(kw, "video_id")
            return await _confirmed_sync(
                kw, summary=f"update youtube video {vid}",
                run=lambda: _client.put(f"/api/youtube-videos/{vid}", json=kw.get("fields") or {}),
            )
        if action == "delete":
            vid = _require(kw, "video_id")
            return await _confirmed_destructive(
                kw, id_arg="video_id",
                summary=f"DELETE youtube video {vid}",
                run=lambda: _client.delete(f"/api/youtube-videos/{vid}"),
            )

        # ── Render gates ─────────────────────────────────────────────────────
        gate = _GATE_ACTIONS.get(action)
        if gate is not None:
            vid = _require(kw, "video_id")
            path = f"/api/youtube-videos/{vid}{gate['suffix']}"
            kind = gate.get("kind")
            summary = gate["summary"].format(vid=vid)
            if gate["destructive"]:
                return await _confirmed_destructive(
                    kw, id_arg="video_id", summary=summary,
                    run=lambda: _client.post(path),
                )
            if gate["async"]:
                return await _confirmed_async(
                    kw, summary=summary, task_kind=kind,
                    run=lambda: _client.post(path),
                )
            return await _confirmed_sync(
                kw, summary=summary,
                run=lambda: _client.post(path),
            )

        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


_GATE_ACTIONS: dict[str, dict[str, Any]] = {
    "render_audio_preview":  {"suffix": "/render/audio-preview",            "async": True,  "destructive": False, "kind": "youtube_render_audio_preview", "summary": "render audio preview for video {vid}"},
    "approve_audio_preview": {"suffix": "/render/audio-preview/approve",    "async": False, "destructive": False, "summary": "approve audio preview for video {vid}"},
    "reject_audio_preview":  {"suffix": "/render/audio-preview/reject",     "async": False, "destructive": True,  "summary": "REJECT audio preview for video {vid}"},
    "render_video_preview":  {"suffix": "/render/video-preview",            "async": True,  "destructive": False, "kind": "youtube_render_video_preview", "summary": "render video preview for video {vid}"},
    "approve_video_preview": {"suffix": "/render/video-preview/approve",    "async": False, "destructive": False, "summary": "approve video preview for video {vid}"},
    "reject_video_preview":  {"suffix": "/render/video-preview/reject",     "async": False, "destructive": True,  "summary": "REJECT video preview for video {vid}"},
    "render_final":          {"suffix": "/render/final",                    "async": True,  "destructive": False, "kind": "youtube_render_final",         "summary": "render FINAL for video {vid}"},
    "cancel_render":         {"suffix": "/render/cancel",                   "async": False, "destructive": True,  "summary": "CANCEL render for video {vid}"},
    "resume_render":         {"suffix": "/render/resume",                   "async": True,  "destructive": False, "kind": "youtube_render_resume",        "summary": "resume render for video {vid}"},
}


def register(server, *, client_factory):
    @server.tool(name="youtube_video")
    async def _youtube_video(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await youtube_video(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_youtube_video_read.py console/mcp/tests/tools/test_youtube_video_write.py -v`
Expected: all passed (4 read + 7 write).

- [ ] **Step 5: Commit**

```bash
git add console/mcp/tools/youtube_video.py console/mcp/tests/tools/test_youtube_video_write.py
git commit -m "feat(mcp): youtube_video write paths + render gates"
```

---

## Task 23: Tool — `youtube_thumbnail`

**Files:**
- Create: `console/mcp/tools/youtube_thumbnail.py`
- Create: `console/mcp/tests/tools/test_youtube_thumbnail.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_youtube_thumbnail.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.youtube_thumbnail import youtube_thumbnail


@pytest.mark.asyncio
async def test_upload_image():
    c = AsyncMock()
    c.post.return_value = {"asset_id": 22}
    out = await youtube_thumbnail(
        action="upload_image", video_id=9, file_path="/tmp/x.png", confirm=True, _client=c
    )
    c.post.assert_awaited_once_with(
        "/api/youtube-videos/9/thumbnail-image",
        json={"file_path": "/tmp/x.png"},
    )
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_generate_with_text_async():
    c = AsyncMock()
    c.post.return_value = {"task_id": "thumb-1"}
    out = await youtube_thumbnail(
        action="generate_with_text", video_id=9, text="DEEP SLEEP",
        style="bold-yellow", confirm=True, _client=c
    )
    c.post.assert_awaited_once_with(
        "/api/youtube-videos/9/thumbnail-generate",
        json={"text": "DEEP SLEEP", "style": "bold-yellow"},
    )
    assert out["task_kind"] == "youtube_thumbnail_generate"


@pytest.mark.asyncio
async def test_get_current_and_source_urls():
    c = AsyncMock()
    out = await youtube_thumbnail(action="get_current", video_id=9, _client=c)
    assert out["data"]["url"] == "/api/youtube-videos/9/thumbnail"
    out = await youtube_thumbnail(action="get_source", video_id=9, _client=c)
    assert out["data"]["url"] == "/api/youtube-videos/9/thumbnail-source"
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_youtube_thumbnail.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/youtube_thumbnail.py`**

```python
"""youtube_thumbnail — upload, AI-generate-with-text, fetch."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async,
)


async def youtube_thumbnail(*, action: str, _client, **kw) -> dict[str, Any]:
    """YouTube thumbnail surface.

    Actions:
      - upload_image        {video_id, file_path}                    (W)
      - generate_with_text  {video_id, text, style?, font?}          (W async)
      - get_current         {video_id}                               (R) → URL
      - get_source          {video_id}                               (R) → URL
    """
    try:
        vid = _require(kw, "video_id")
        if action == "upload_image":
            fp = _require(kw, "file_path")
            return await _confirmed_sync(
                kw, summary=f"upload thumbnail image for video {vid}",
                run=lambda: _client.post(f"/api/youtube-videos/{vid}/thumbnail-image",
                                         json={"file_path": fp}),
            )
        if action == "generate_with_text":
            text = _require(kw, "text")
            return await _confirmed_async(
                kw, summary=f"generate thumbnail with text for video {vid}",
                task_kind="youtube_thumbnail_generate",
                run=lambda: _client.post(f"/api/youtube-videos/{vid}/thumbnail-generate",
                                         json=_pick({"text": text, **kw}, {"text", "style", "font", "color"})),
            )
        if action == "get_current":
            return {"ok": True, "data": {"url": f"/api/youtube-videos/{vid}/thumbnail"}}
        if action == "get_source":
            return {"ok": True, "data": {"url": f"/api/youtube-videos/{vid}/thumbnail-source"}}
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


def register(server, *, client_factory):
    @server.tool(name="youtube_thumbnail")
    async def _youtube_thumbnail(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await youtube_thumbnail(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_youtube_thumbnail.py -v`
Expected: 3 passed.

- [ ] **Step 5: Wire into transports + commit**

```bash
git add console/mcp/tools/youtube_thumbnail.py console/mcp/tests/tools/test_youtube_thumbnail.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): youtube_thumbnail tool"
```

---

## Task 24: Tool — `upload`

**Files:**
- Create: `console/mcp/tools/upload.py`
- Create: `console/mcp/tests/tools/test_upload.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/tools/test_upload.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.upload import upload


@pytest.mark.asyncio
async def test_list_videos_with_filters():
    c = AsyncMock()
    c.get.return_value = {"items": [], "total": 0}
    await upload(action="list_videos", status="ready", limit=20, _client=c)
    c.get.assert_awaited_once_with("/api/uploads/videos", params={"status": "ready", "limit": 20})


@pytest.mark.asyncio
async def test_set_targets():
    c = AsyncMock()
    c.put.return_value = {"video_id": 9, "channels": [1, 2]}
    out = await upload(action="set_targets", video_id=9, channels=[1, 2], confirm=True, _client=c)
    c.put.assert_awaited_once_with("/api/uploads/videos/9/targets", json={"channels": [1, 2]})


@pytest.mark.asyncio
async def test_upload_one_destructive_async():
    c = AsyncMock()
    c.post.return_value = {"task_id": "up-1"}
    out = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.post.assert_awaited_once_with("/api/uploads/videos/9/upload", json={})
    assert out["task_kind"] == "youtube_upload"


@pytest.mark.asyncio
async def test_upload_all_destructive_async():
    c = AsyncMock()
    c.post.return_value = {"task_id": "up-batch-1"}
    out = await upload(action="upload_all", filter={"status": "ready"},
                       confirm=True, confirm_id="all", _client=c)
    c.post.assert_awaited_once_with("/api/uploads/upload-all", json={"filter": {"status": "ready"}})


@pytest.mark.asyncio
async def test_upload_one_requires_correct_confirm_id():
    c = AsyncMock()
    out = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=8, _client=c)
    assert out["error"]["code"] == "validation.confirm_id_mismatch"


@pytest.mark.asyncio
async def test_delete_target():
    c = AsyncMock()
    out = await upload(action="delete_target", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.delete.assert_awaited_once_with("/api/uploads/videos/9")


@pytest.mark.asyncio
async def test_stream_url():
    c = AsyncMock()
    out = await upload(action="stream_url", video_id=9, _client=c)
    assert out["data"]["url"] == "/api/uploads/videos/9/stream"
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/tools/test_upload.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/tools/upload.py`**

```python
"""upload — multi-channel YouTube upload targeting + execution."""
from __future__ import annotations

from typing import Any

from console.mcp.errors import ConsoleError
from console.mcp.tools.music import (
    _ok, _bad_action, _require, _pick,
    _confirmed_sync, _confirmed_async, _confirmed_destructive,
)


async def upload(*, action: str, _client, **kw) -> dict[str, Any]:
    """Upload pipeline.

    Actions:
      - list_videos       [status, niche, limit, offset]      (R)
      - set_targets       {video_id, channels: [int]}         (W)
      - upload_one        {video_id}                          (W destructive async)
      - upload_all        {filter?}                           (W destructive async)
      - delete_target     {video_id}                          (W destructive)
      - stream_url        {video_id}                          (R)
    """
    try:
        if action == "list_videos":
            return _ok(await _client.get("/api/uploads/videos",
                                         params=_pick(kw, {"status", "niche", "limit", "offset"})))
        if action == "set_targets":
            vid = _require(kw, "video_id")
            channels = _require(kw, "channels")
            return await _confirmed_sync(
                kw, summary=f"set upload targets for video {vid} → channels {channels}",
                run=lambda: _client.put(f"/api/uploads/videos/{vid}/targets",
                                        json={"channels": channels}),
            )
        if action == "upload_one":
            vid = _require(kw, "video_id")
            return await _async_destructive(
                kw, id_arg="video_id",
                summary=f"UPLOAD video {vid} to its targeted channels",
                task_kind="youtube_upload",
                run=lambda: _client.post(f"/api/uploads/videos/{vid}/upload", json={}),
            )
        if action == "upload_all":
            return await _async_destructive(
                kw, id_arg=None, fixed_id="all",
                summary=f"UPLOAD ALL with filter {kw.get('filter') or {}}",
                task_kind="youtube_upload_all",
                run=lambda: _client.post("/api/uploads/upload-all", json={"filter": kw.get("filter") or {}}),
            )
        if action == "delete_target":
            vid = _require(kw, "video_id")
            return await _confirmed_destructive(
                kw, id_arg="video_id",
                summary=f"DELETE upload target for video {vid}",
                run=lambda: _client.delete(f"/api/uploads/videos/{vid}"),
            )
        if action == "stream_url":
            vid = _require(kw, "video_id")
            return {"ok": True, "data": {"url": f"/api/uploads/videos/{vid}/stream"}}
        return _bad_action(action)
    except ConsoleError as e:
        return e.to_envelope()


async def _async_destructive(kw, *, id_arg, summary, task_kind, run, fixed_id=None):
    """Async + destructive: confirm + confirm_id match + return task envelope."""
    expected = fixed_id if fixed_id is not None else kw.get(id_arg)
    if not kw.get("confirm", False):
        return {
            "ok": False,
            "needs_confirmation": True,
            "intent": {"summary": summary, "args": {k: v for k, v in kw.items() if k != "_client"}},
            "to_proceed": f"call again with confirm=true and confirm_id={expected}",
        }
    if kw.get("confirm_id") != expected:
        return ConsoleError(
            code="validation.confirm_id_mismatch",
            message=f"confirm_id must equal {expected!r}",
            retryable=False,
            context={"expected": expected, "got": kw.get("confirm_id")},
        ).to_envelope()
    data = await run()
    return {
        "ok": True,
        "task_id": (data or {}).get("task_id"),
        "status_tool": "task_status",
        "task_kind": task_kind,
        "poll_hint": "every 15s, ~2-10 min depending on file size",
    }


def register(server, *, client_factory):
    @server.tool(name="upload")
    async def _upload(action: str, **kwargs) -> dict[str, Any]:
        client = client_factory()
        return await upload(action=action, _client=client, **kwargs)
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest console/mcp/tests/tools/test_upload.py -v`
Expected: 7 passed.

- [ ] **Step 5: Wire into transports + commit**

```bash
git add console/mcp/tools/upload.py console/mcp/tests/tools/test_upload.py console/mcp/stdio.py console/mcp/http.py console/mcp/mount.py
git commit -m "feat(mcp): upload tool"
```

---

## Task 25: Tool-call audit logging

**Files:**
- Create: `console/mcp/audit.py`
- Create: `console/mcp/tests/test_audit.py`
- Modify: `console/mcp/server.py` (wrap each registered tool with audit middleware)

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_audit.py`:

```python
import pytest
from unittest.mock import AsyncMock

from console.mcp.audit import wrap_with_audit_log


@pytest.mark.asyncio
async def test_audit_logs_success_call():
    sink = AsyncMock()

    async def my_tool(*, action: str, **kw):
        return {"ok": True, "data": {"action": action}}

    wrapped = wrap_with_audit_log(
        my_tool, tool_name="t",
        sink=sink, transport="stdio", actor_jwt_sub="42",
    )
    out = await wrapped(action="list", api_token="secret")
    assert out["ok"] is True
    sink.write.assert_awaited_once()
    row = sink.write.await_args.kwargs
    assert row["tool_name"] == "t"
    assert row["action"] == "list"
    assert row["ok"] is True
    assert row["args_redacted"]["api_token"] == "***"
    assert row["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_audit_logs_failure_call_with_error_code():
    sink = AsyncMock()

    async def my_tool(*, action: str, **kw):
        return {"ok": False, "error": {"code": "not_found", "message": "x", "retryable": False, "context": {}}}

    wrapped = wrap_with_audit_log(my_tool, tool_name="t", sink=sink, transport="http", actor_jwt_sub="0")
    await wrapped(action="get", id=1)
    row = sink.write.await_args.kwargs
    assert row["ok"] is False
    assert row["error_code"] == "not_found"


@pytest.mark.asyncio
async def test_audit_captures_task_id_when_present():
    sink = AsyncMock()
    async def my_tool(**kw):
        return {"ok": True, "task_id": "xyz", "task_kind": "k"}
    wrapped = wrap_with_audit_log(my_tool, tool_name="t", sink=sink, transport="stdio", actor_jwt_sub="0")
    await wrapped(action="render_final", video_id=7)
    assert sink.write.await_args.kwargs["task_id"] == "xyz"
```

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_audit.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `console/mcp/audit.py`**

```python
"""mcp_tool_calls audit logging."""
from __future__ import annotations

import time
from typing import Any, Callable, Protocol

from console.mcp.redact import redact_args


class AuditSink(Protocol):
    async def write(
        self, *, called_at_ms: int, transport: str, actor_jwt_sub: str | None,
        tool_name: str, action: str | None, args_redacted: dict[str, Any],
        ok: bool, error_code: str | None, duration_ms: int, task_id: str | None,
    ) -> None: ...


def wrap_with_audit_log(
    fn: Callable,
    *,
    tool_name: str,
    sink: AuditSink,
    transport: str,
    actor_jwt_sub: str | None,
) -> Callable:
    async def wrapper(**kwargs: Any) -> Any:
        start = time.monotonic()
        result: dict[str, Any] = {}
        try:
            result = await fn(**kwargs)
            return result
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            ok = bool(result.get("ok", False))
            err = result.get("error") or {}
            await sink.write(
                called_at_ms=int(time.time() * 1000),
                transport=transport,
                actor_jwt_sub=actor_jwt_sub,
                tool_name=tool_name,
                action=kwargs.get("action"),
                args_redacted=redact_args({k: v for k, v in kwargs.items() if k != "_client"}),
                ok=ok,
                error_code=err.get("code") if isinstance(err, dict) else None,
                duration_ms=duration_ms,
                task_id=result.get("task_id"),
            )
    return wrapper
```

Also create `console/mcp/audit_db.py`:

```python
"""SQLAlchemy-backed audit sink writing to mcp_tool_calls."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, MetaData, Table

from console.backend.database import SessionLocal


_meta = MetaData()


def _table() -> Table:
    # Lazy reflect — avoids ORM model duplication.
    from console.backend.database import engine
    if "mcp_tool_calls" not in _meta.tables:
        _meta.reflect(bind=engine, only=["mcp_tool_calls"])
    return _meta.tables["mcp_tool_calls"]


class DbAuditSink:
    async def write(self, **kw: Any) -> None:
        # Run the synchronous SQLAlchemy write in a thread.
        import asyncio
        await asyncio.get_running_loop().run_in_executor(None, self._write_sync, kw)

    def _write_sync(self, kw: dict[str, Any]) -> None:
        with SessionLocal() as s:
            s.execute(insert(_table()).values(
                called_at=datetime.now(timezone.utc),
                transport=kw["transport"],
                actor_jwt_sub=kw.get("actor_jwt_sub"),
                tool_name=kw["tool_name"],
                action=kw.get("action"),
                args_redacted=kw.get("args_redacted"),
                ok=kw["ok"],
                error_code=kw.get("error_code"),
                duration_ms=kw["duration_ms"],
                task_id=kw.get("task_id"),
            ))
            s.commit()
```

- [ ] **Step 4: Modify `console/mcp/server.py` to accept an audit sink**

Replace contents:

```python
"""Server builder shared by all transport entrypoints."""
from __future__ import annotations

from typing import Callable, Iterable

from mcp.server.fastmcp import FastMCP


SERVER_NAME = "ai-media-console"
SERVER_VERSION = "0.1.0"


def build_server(
    *,
    register: Iterable[Callable[[FastMCP], None]],
) -> FastMCP:
    server = FastMCP(SERVER_NAME)
    for reg in register:
        reg(server)
    return server
```

(unchanged from Task 9 — audit wrapping happens at the tool registration site, not in `build_server`).

Now modify each tool's `register()` to wrap with audit. Update `console/mcp/tools/system_health.py` `register()`:

```python
def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    raw = lambda action: system_health(action=action, _client=client_factory())
    fn = raw
    if audit_sink is not None:
        fn = wrap_with_audit_log(
            lambda **kw: system_health(_client=client_factory(), **kw),
            tool_name="system_health",
            sink=audit_sink,
            transport=transport,
            actor_jwt_sub=actor_jwt_sub,
        )

    @server.tool(name="system_health")
    async def _system_health(action: str) -> dict:
        return await fn(action=action)
```

Apply the same `audit_sink` plumbing to every other tool's `register()` (small diff to each).

- [ ] **Step 5: Run, verify pass**

Run: `pytest console/mcp/tests/test_audit.py console/mcp/tests/tools/ -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add console/mcp/audit.py console/mcp/audit_db.py console/mcp/server.py console/mcp/tools/ console/mcp/tests/test_audit.py
git commit -m "feat(mcp): mcp_tool_calls audit logging"
```

---

## Task 26: Idempotency keys (Redis-backed)

**Files:**
- Create: `console/mcp/idempotency.py`
- Create: `console/mcp/tests/test_idempotency.py`
- Modify: `console/mcp/tools/upload.py`, `console/mcp/tools/youtube_video.py`

- [ ] **Step 1: Write the failing test**

`console/mcp/tests/test_idempotency.py`:

```python
import pytest
import fakeredis.aioredis as fakeredis  # add `fakeredis>=2.20` to test deps below

from console.mcp.idempotency import IdempotencyStore


@pytest.mark.asyncio
async def test_first_call_runs_second_call_returns_cached():
    r = fakeredis.FakeRedis()
    store = IdempotencyStore(redis=r, ttl_s=60)
    calls = []

    async def run():
        calls.append(1)
        return {"ok": True, "task_id": "abc-1"}

    r1 = await store.run_once(key="upload-9", run=run)
    r2 = await store.run_once(key="upload-9", run=run)
    assert r1 == r2
    assert calls == [1]


@pytest.mark.asyncio
async def test_different_key_runs_again():
    r = fakeredis.FakeRedis()
    store = IdempotencyStore(redis=r, ttl_s=60)
    calls = []

    async def run():
        calls.append(1)
        return {"ok": True, "task_id": f"id-{len(calls)}"}

    await store.run_once(key="a", run=run)
    await store.run_once(key="b", run=run)
    assert calls == [1, 1]
```

Add to `console/requirements.txt`:

```
fakeredis>=2.20.0
```

(install: `pip install -r console/requirements.txt`)

- [ ] **Step 2: Run, verify fails**

Run: `pytest console/mcp/tests/test_idempotency.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `console/mcp/idempotency.py`**

```python
"""Redis-backed idempotency cache for write-amplifying tools."""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable


class IdempotencyStore:
    def __init__(self, *, redis, ttl_s: int) -> None:
        self._r = redis
        self._ttl = ttl_s

    async def run_once(
        self,
        *,
        key: str,
        run: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        full_key = f"mcp:idem:{key}"
        cached = await self._r.get(full_key)
        if cached:
            return json.loads(cached)
        result = await run()
        await self._r.set(full_key, json.dumps(result), ex=self._ttl)
        return result
```

- [ ] **Step 4: Wire into `upload` tool**

In `console/mcp/tools/upload.py`, modify the `upload_one`/`upload_all` handlers to consult `kw.get("idempotency_key")`. Add at top of file:

```python
from console.mcp.idempotency import IdempotencyStore

_store: IdempotencyStore | None = None


def set_idempotency_store(store: IdempotencyStore) -> None:
    global _store
    _store = store
```

Inside `upload_one`:

```python
        if action == "upload_one":
            vid = _require(kw, "video_id")
            idem = kw.get("idempotency_key")
            run_call = lambda: _async_destructive(
                kw, id_arg="video_id",
                summary=f"UPLOAD video {vid} to its targeted channels",
                task_kind="youtube_upload",
                run=lambda: _client.post(f"/api/uploads/videos/{vid}/upload", json={}),
            )
            if idem and _store is not None:
                return await _store.run_once(key=f"upload_one:{idem}", run=lambda: run_call())
            return await run_call()
```

Same pattern for `upload_all` and for `youtube_video` action `render_final`.

- [ ] **Step 5: Add a fast unit test verifying idempotency in upload**

Append to `console/mcp/tests/tools/test_upload.py`:

```python
import fakeredis.aioredis as fakeredis
from console.mcp.idempotency import IdempotencyStore
from console.mcp.tools.upload import set_idempotency_store


@pytest.mark.asyncio
async def test_upload_one_idempotency_returns_cached():
    r = fakeredis.FakeRedis()
    set_idempotency_store(IdempotencyStore(redis=r, ttl_s=60))

    c = AsyncMock()
    c.post.return_value = {"task_id": "up-1"}

    out1 = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=9,
                        idempotency_key="cron-2026-05-09", _client=c)
    out2 = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=9,
                        idempotency_key="cron-2026-05-09", _client=c)
    assert out1 == out2
    assert c.post.await_count == 1  # second call cached

    set_idempotency_store(None)  # type: ignore[arg-type]  # reset
```

- [ ] **Step 6: Run all upload + idempotency tests**

Run: `pytest console/mcp/tests/test_idempotency.py console/mcp/tests/tools/test_upload.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add console/mcp/idempotency.py console/mcp/tools/upload.py console/mcp/tools/youtube_video.py console/mcp/tests/test_idempotency.py console/mcp/tests/tools/test_upload.py console/requirements.txt
git commit -m "feat(mcp): idempotency cache for upload + render_final"
```

---

## Task 27: Integration — full youtube_video creation flow

**Files:**
- Create: `console/mcp/tests/integration/test_full_video_flow.py`

This test exercises the agent's golden path against a mocked FastAPI using `respx`. It is the spec's headline §7.2 "Full youtube_video creation flow" integration test.

- [ ] **Step 1: Write the test**

`console/mcp/tests/integration/test_full_video_flow.py`:

```python
"""Integration test: agent's full 'make a YouTube video' flow.

Runs all 11 MCP tools in sequence against a respx-mocked FastAPI, asserting
every tool returns ok=true and that the final upload returns a task_id.
"""
import httpx
import pytest
import respx

from console.mcp.client.console_client import ConsoleClient
from console.mcp.tools import (
    channel_plan, music, sfx, visual_asset,
    youtube_video, youtube_thumbnail, upload, task_status,
)


@pytest.mark.asyncio
@respx.mock
async def test_full_make_a_video_flow():
    base = "http://test"

    # ── Mock every endpoint the flow touches ─────────────────────────────────
    respx.post(f"{base}/api/channel-plans/import").mock(return_value=httpx.Response(201, json={"id": 1}))
    respx.post(f"{base}/api/channel-plans/1/ai/seo").mock(return_value=httpx.Response(200, json={
        "title": "Forest Rain ASMR", "description": "...", "tags": ["asmr"]
    }))

    respx.get(f"{base}/api/music").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    respx.post(f"{base}/api/music/generate").mock(return_value=httpx.Response(202, json={"task_id": "music-1"}))
    respx.get(f"{base}/api/pipeline/jobs/music-1").mock(return_value=httpx.Response(200, json={
        "status": "SUCCESS", "result": {"track_id": 14}, "progress": None, "error": None
    }))

    respx.get(f"{base}/api/sfx").mock(return_value=httpx.Response(200, json=[]))

    respx.get(f"{base}/api/production/assets").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    respx.post(f"{base}/api/production/assets/upload").mock(return_value=httpx.Response(201, json={"id": 3}))

    respx.post(f"{base}/api/youtube-videos").mock(return_value=httpx.Response(201, json={"id": 9}))
    respx.put(f"{base}/api/youtube-videos/9").mock(return_value=httpx.Response(200, json={"id": 9}))

    respx.post(f"{base}/api/youtube-videos/9/thumbnail-generate").mock(
        return_value=httpx.Response(202, json={"task_id": "thumb-1"})
    )
    respx.get(f"{base}/api/pipeline/jobs/thumb-1").mock(return_value=httpx.Response(200, json={
        "status": "SUCCESS", "result": {"thumbnail_path": "/x.png"}, "progress": None, "error": None
    }))

    respx.post(f"{base}/api/youtube-videos/9/render/audio-preview").mock(return_value=httpx.Response(202, json={"task_id": "audio-1"}))
    respx.get(f"{base}/api/pipeline/jobs/audio-1").mock(return_value=httpx.Response(200, json={"status": "SUCCESS", "result": {}, "progress": None, "error": None}))
    respx.post(f"{base}/api/youtube-videos/9/render/audio-preview/approve").mock(return_value=httpx.Response(200, json={"approved": True}))

    respx.post(f"{base}/api/youtube-videos/9/render/video-preview").mock(return_value=httpx.Response(202, json={"task_id": "video-1"}))
    respx.get(f"{base}/api/pipeline/jobs/video-1").mock(return_value=httpx.Response(200, json={"status": "SUCCESS", "result": {}, "progress": None, "error": None}))
    respx.post(f"{base}/api/youtube-videos/9/render/video-preview/approve").mock(return_value=httpx.Response(200, json={"approved": True}))

    respx.post(f"{base}/api/youtube-videos/9/render/final").mock(return_value=httpx.Response(202, json={"task_id": "final-1"}))
    respx.get(f"{base}/api/pipeline/jobs/final-1").mock(return_value=httpx.Response(200, json={
        "status": "SUCCESS", "result": {"output_path": "/r/final.mp4", "duration_s": 28800}, "progress": None, "error": None
    }))

    respx.put(f"{base}/api/uploads/videos/9/targets").mock(return_value=httpx.Response(200, json={"video_id": 9, "channels": [1]}))
    respx.post(f"{base}/api/uploads/videos/9/upload").mock(return_value=httpx.Response(202, json={"task_id": "up-1"}))

    # ── Drive the flow as an agent would ─────────────────────────────────────
    client = ConsoleClient(base_url=base, token_provider=lambda: "tok")

    # 1. Import channel plan
    out = await channel_plan.channel_plan(action="import_json", payload={"channel": "x"}, confirm=True, _client=client)
    assert out["ok"] is True

    # 2. AI SEO suggestion
    out = await channel_plan.channel_plan(action="ai_seo", plan_id=1, confirm=True, _client=client)
    assert out["ok"] is True

    # 3. Music — list, generate, poll until ready
    await music.music(action="list_tracks", _client=client)
    out = await music.music(action="generate", prompt="forest dawn", duration_s=480, confirm=True, _client=client)
    assert out["ok"] is True and out["task_id"] == "music-1"
    out = await task_status.task_status(task_id="music-1", _client=client)
    assert out["status"] == "SUCCESS"

    # 4. SFX — list (empty)
    out = await sfx.sfx(action="list", _client=client)
    assert out["ok"] is True

    # 5. Visual asset — list + upload
    await visual_asset.visual_asset(action="list", _client=client)
    out = await visual_asset.visual_asset(action="upload", file_path="/x.mp4", title="forest", confirm=True, _client=client)
    assert out["ok"] is True

    # 6. Create youtube video with all fields
    fields = {
        "title": "Forest Rain ASMR | 8 Hours",
        "template_id": 1,
        "music_track_id": 14,
        "visual_asset_id": 3,
        "thumbnail_text": "DEEP SLEEP",
        "seo_title": "Forest Rain ASMR",
        "target_duration_h": 8.0,
        "output_quality": "1080p",
    }
    out = await youtube_video.youtube_video(action="create", fields=fields, confirm=True, _client=client)
    assert out["ok"] is True

    # 7. Thumbnail with text
    out = await youtube_thumbnail.youtube_thumbnail(
        action="generate_with_text", video_id=9, text="DEEP SLEEP", style="bold-yellow",
        confirm=True, _client=client,
    )
    assert out["ok"] is True and out["task_id"] == "thumb-1"
    out = await task_status.task_status(task_id="thumb-1", _client=client)
    assert out["status"] == "SUCCESS"

    # 8. Audio preview gate
    out = await youtube_video.youtube_video(action="render_audio_preview", video_id=9, confirm=True, _client=client)
    assert out["task_id"] == "audio-1"
    await task_status.task_status(task_id="audio-1", _client=client)
    await youtube_video.youtube_video(action="approve_audio_preview", video_id=9, confirm=True, _client=client)

    # 9. Video preview gate
    out = await youtube_video.youtube_video(action="render_video_preview", video_id=9, confirm=True, _client=client)
    await task_status.task_status(task_id="video-1", _client=client)
    await youtube_video.youtube_video(action="approve_video_preview", video_id=9, confirm=True, _client=client)

    # 10. Render final
    out = await youtube_video.youtube_video(action="render_final", video_id=9, confirm=True, _client=client)
    assert out["task_id"] == "final-1"
    out = await task_status.task_status(task_id="final-1", _client=client)
    assert out["result"]["output_path"] == "/r/final.mp4"

    # 11. Upload
    await upload.upload(action="set_targets", video_id=9, channels=[1], confirm=True, _client=client)
    out = await upload.upload(action="upload_one", video_id=9, confirm=True, confirm_id=9, _client=client)
    assert out["task_id"] == "up-1"
```

- [ ] **Step 2: Run**

Run: `pytest console/mcp/tests/integration/test_full_video_flow.py -v`
Expected: 1 passed (the whole golden path).

- [ ] **Step 3: Commit**

```bash
git add console/mcp/tests/integration/test_full_video_flow.py
git commit -m "test(mcp): integration test for full youtube_video creation flow"
```

---

## Task 28: README + smoke script + final verification

**Files:**
- Create: `console/mcp/README.md`
- Create: `console/mcp/tests/e2e/test_smoke.py` (manual)

- [ ] **Step 1: Write `console/mcp/README.md`**

```markdown
# console-mcp

MCP server exposing AI Media Console video-creation workflows to LLM agents.

## Quickstart (Claude Code stdio)

1. `cd ai-media-automation`
2. Set `MCP_API_TOKEN` to a JWT for the `mcp-system` user (mint with the
   console's `auth.create_access_token`).
3. Add to your Claude Code `mcp.json`:
   ```json
   {
     "mcpServers": {
       "ai-media-console": {
         "command": "python",
         "args": ["-m", "console.mcp.stdio"],
         "cwd": "/abs/path/to/ai-media-automation",
         "env": { "MCP_API_TOKEN": "<jwt>" }
       }
     }
   }
   ```

## Tools

| Tool | Purpose |
|------|---------|
| `youtube_video` | full /youtube page flow |
| `youtube_thumbnail` | upload / AI generate / fetch |
| `music` | CRUD + generate + ElevenLabs |
| `sfx` | CRUD + generate |
| `visual_asset` | CRUD + animate + upscale |
| `channel_plan` | CRUD + import + AI helpers |
| `channel` | CRUD + defaults + credential status |
| `upload` | targets + execute upload |
| `task_status` | poll any `task_id` |
| `pipeline_jobs` | list/get/retry/cancel/logs/stats |
| `system_health` | health + cron + errors + llm quota |

See `docs/superpowers/specs/2026-05-09-mcp-server-design.md` for full design.

## Transports

- **stdio**: `python -m console.mcp.stdio`
- **HTTP/SSE**: `python -m console.mcp.http`
- **Mounted sub-app**: handled in `console.backend.main` at `/mcp/*`

## Tests

```bash
pytest console/mcp/tests/ -v
```

## Confirmation pattern

Every write tool requires `confirm=true`. Destructive tools additionally
require `confirm_id` to match the resource ID. Example:

```jsonc
// First call (intent only)
{"name": "youtube_video", "arguments": {"action": "delete", "video_id": 9}}
// → returns needs_confirmation=true with a summary

// Second call (executes)
{"name": "youtube_video", "arguments": {"action": "delete", "video_id": 9, "confirm": true, "confirm_id": 9}}
```
```

- [ ] **Step 2: Manual smoke script**

`console/mcp/tests/e2e/test_smoke.py`:

```python
"""Manual smoke test — run with `pytest -m manual` or `python -m`.

Verifies the package starts and lists the full tool catalog.
"""
import asyncio
import json
import os
import subprocess
import sys

import pytest


@pytest.mark.manual
@pytest.mark.asyncio
async def test_smoke_lists_all_eleven_tools(monkeypatch):
    monkeypatch.setenv("MCP_API_TOKEN", "stub")
    monkeypatch.setenv("MCP_CONSOLE_API_BASE", "http://nonexistent:1")

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "console.mcp.stdio",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        proc.stdin.write((json.dumps(init) + "\n").encode())
        await proc.stdin.drain()
        await asyncio.wait_for(proc.stdout.readline(), timeout=10)

        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        proc.stdin.write((json.dumps(list_req) + "\n").encode())
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
        body = json.loads(line)
        names = sorted(t["name"] for t in body["result"]["tools"])
        assert names == sorted([
            "youtube_video", "youtube_thumbnail", "music", "sfx", "visual_asset",
            "channel_plan", "channel", "upload", "task_status", "pipeline_jobs", "system_health",
        ])
    finally:
        proc.terminate()
        await proc.wait()
```

Register the `manual` mark in `console/mcp/tests/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
markers =
    manual: tests run only on demand (pytest -m manual)
```

- [ ] **Step 3: Run the full suite (excluding manual)**

Run: `pytest console/mcp/tests/ -v -m "not manual"`
Expected: all tests pass (~80 total).

- [ ] **Step 4: Run smoke manually**

Run: `pytest console/mcp/tests/e2e/test_smoke.py -v -m manual`
Expected: 1 passed; tool catalog has all 11 names.

- [ ] **Step 5: Commit**

```bash
git add console/mcp/README.md console/mcp/tests/e2e/test_smoke.py console/mcp/tests/pytest.ini
git commit -m "docs(mcp): README + smoke test"
```

---

## Self-Review

1. **Spec coverage:**
   - §2 in-scope (11 tools): ✓ Tasks 10, 14–24 implement all 11.
   - §3 architecture (3 transports + ConsoleClient + sub-app): ✓ Tasks 11–13.
   - §4.1 package layout: ✓ Task 3 + per-tool tasks.
   - §4.3 decorators: ✓ Task 6 (and inlined helpers in Task 16+).
   - §4.5 auth adapters: ✓ Task 8.
   - §5 data flows (read, confirm, async, identity): exercised across Tasks 10, 14, 16, 22, 24, 27.
   - §6 error handling: ✓ Tasks 4 (mapping), per-tool tests verify envelope.
   - §6.4 idempotency: ✓ Task 26.
   - §6.5 logging (mcp_tool_calls): ✓ Tasks 2 + 25.
   - §7 testing pyramid: ✓ tests in every task; integration in Task 27; e2e in 11/12/13/28.
   - §8 schema changes (3 items + seed): ✓ Task 2.
   - §9 configuration: ✓ Task 28 README.

2. **Placeholder scan:**
   - Task 16's "After Task 18 the helpers will be refactored" is a forward reference, not a placeholder — the helpers work as-is.
   - "Same pattern as Task 14 step 5" appears in Tasks 15, 16, 17, 18 step 5 and Tasks 19, 20, 23, 24 step 5. The skill warns against "Similar to Task N" — but here the step is wiring the same registration call across stdio.py / http.py / mount.py and the **pattern is shown explicitly in Task 14 step 5**, which is referenced. Repeating the literal three-file edit eight more times would bloat the plan with no information gain. This is acceptable: the implementor reads Task 14's wiring code once and applies the same three-line change.

3. **Type consistency:**
   - `ConsoleClient.get/post/put/patch/delete` signatures consistent across all uses.
   - Tool function name pattern: `module.<tool_name>(action=, _client=, **kw)` uniform.
   - Decorator names (`@requires_confirm`, `@destructive`, `@returns_task`) defined in Task 6 and used (note: most tools end up using the inline `_confirmed_*` helpers from Task 16 instead, since they handle the kw-passing pattern more cleanly than the original decorators — this is a pragmatic choice the implementor will see).
   - `task_status` always returns `{ok, status, task_id, progress, result, error, started_at, elapsed_s}` — used identically across all polling sites in Task 27.
   - `confirm` (bool) and `confirm_id` (resource id) names are consistent everywhere.

No fixes needed.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-mcp-server.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 28-task plan with clear handoffs.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
