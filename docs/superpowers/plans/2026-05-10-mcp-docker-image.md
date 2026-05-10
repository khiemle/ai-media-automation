# MCP Docker Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package `console.mcp.stdio` as a slim Docker image and provide a single bash script that builds the image, ingests a token from the admin UI's "Copy command" output, writes a 0600 env file, smoke-tests the container, and prints a docker-flavored `claude mcp add` snippet ready to paste.

**Architecture:** Single-purpose stdio container. `python -m console.mcp.stdio` runs as the entrypoint; a new `--self-test` mode in stdio.py validates token + backend reachability without a JSON-RPC handshake. The provisioning script (`console/mcp/scripts/mcp-image.sh`) is a bash orchestrator: pre-flight → build → parse pasted command → normalize URL → write env file → smoke-test → emit snippet. Token minting reuses the existing admin endpoint (`POST /api/system/mcp/mint-token`) — no SSH, no host-side `mint_token.py`.

**Tech Stack:** Python 3.11-slim base image, `mcp` SDK, `httpx`, `python-jose[cryptography]`, `sqlalchemy`, `bcrypt`, bash, pytest (subprocess-driven script tests).

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `Dockerfile.mcp` | new | Build a stdio-only MCP image |
| `requirements.mcp.txt` | new | Slim runtime deps for the image |
| `console/mcp/stdio.py` | modified | Add `--self-test` arg |
| `console/mcp/scripts/mcp-image.sh` | new | One-shot provisioner: build → token → env → smoke → snippet |
| `console/mcp/tests/test_mcp_image_script.py` | new | Subprocess-driven tests for the bash script |
| `console/mcp/tests/test_self_test.py` | new | Tests for the `--self-test` code path in stdio.py |
| `console/mcp/README.md` | modified | Add a Docker quickstart section |

Imports of `console.mcp.stdio` were verified at planning time — no `console.backend.*` modules are loaded transitively. Only `console/__init__.py` (already exists) plus `console/mcp/` is needed in the image.

---

## Task 1: Add `--self-test` mode to `console.mcp.stdio`

**Files:**
- Modify: `console/mcp/stdio.py`
- Test: `console/mcp/tests/test_self_test.py` (new)

The `--self-test` arg makes the module call `GET /api/system/health` with the bearer token from `MCP_API_TOKEN`, print a clear OK/FAIL message, and exit 0/1. Bash callers can use the exit code to gate further steps.

- [ ] **Step 1.1: Write the failing test**

Create `console/mcp/tests/test_self_test.py`:

```python
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
    err = ConsoleError(code="auth.unauthorized", message="invalid token", retryable=False, status=401)
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
```

- [ ] **Step 1.2: Run the test, expect failures**

Run: `pytest console/mcp/tests/test_self_test.py -v`
Expected: 4 failures (`_self_test`, `_run_self_test_sync` don't exist; `main` doesn't accept `--self-test`).

- [ ] **Step 1.3: Implement the self-test path**

Edit `console/mcp/stdio.py`. Replace the entire file with:

```python
"""stdio transport entrypoint: `python -m console.mcp.stdio`.

Usage:
    python -m console.mcp.stdio              # normal JSON-RPC stdio server
    python -m console.mcp.stdio --self-test  # validate token + backend; exit 0/1
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from console.mcp.activation import audit_kwargs, install_idempotency_store
from console.mcp.auth.adapters import StdioAuth
from console.mcp.client.console_client import ConsoleClient
from console.mcp.errors import ConsoleError
from console.mcp.server import build_server
from console.mcp.tools import (
    channel,
    channel_plan,
    music,
    pipeline_jobs,
    sfx,
    system_health,
    task_status,
    upload,
    visual_asset,
    youtube_thumbnail,
    youtube_video,
)


def _build_client() -> ConsoleClient:
    auth = StdioAuth.from_env()
    return ConsoleClient(
        base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
        token_provider=auth.token,
        actor_metadata=auth.actor_metadata(),
    )


async def _self_test() -> int:
    """Validate that the configured backend accepts our token. Returns exit code."""
    base = os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080")
    client = ConsoleClient(
        base_url=base,
        token_provider=StdioAuth.from_env().token,
    ) if False else _build_client()  # always use the real factory
    try:
        await client.get("/api/system/health")
    except ConsoleError as e:
        if getattr(e, "status", None) == 401 or e.code == "auth.unauthorized":
            print(
                f"FAIL: token rejected by {base} (401). "
                "Re-mint in the System tab of the console UI.",
                file=sys.stderr,
            )
            return 1
        print(f"FAIL: {base} returned error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # connection refused, DNS failure, timeout, ...
        print(
            f"FAIL: cannot reach {base}: {e}. "
            "Check the URL / network (use a LAN IP or host.docker.internal "
            "from inside Docker).",
            file=sys.stderr,
        )
        return 1
    finally:
        await client.aclose()

    print(f"OK: {base} reachable, token accepted.")
    return 0


def _run_self_test_sync() -> int:
    return asyncio.run(_self_test())


def main() -> None:
    parser = argparse.ArgumentParser(prog="console.mcp.stdio")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate token + backend reachability, then exit (no JSON-RPC).",
    )
    args = parser.parse_args()

    if args.self_test:
        sys.exit(_run_self_test_sync())

    auth = StdioAuth.from_env()
    install_idempotency_store()

    def client_factory() -> ConsoleClient:
        return ConsoleClient(
            base_url=os.environ.get("MCP_CONSOLE_API_BASE", "http://localhost:8080"),
            token_provider=auth.token,
            actor_metadata=auth.actor_metadata(),
        )

    activation = audit_kwargs(transport="stdio")

    server = build_server(register=[
        lambda s: system_health.register(s, client_factory=client_factory, **activation),
        lambda s: task_status.register(s, client_factory=client_factory, **activation),
        lambda s: pipeline_jobs.register(s, client_factory=client_factory, **activation),
        lambda s: music.register(s, client_factory=client_factory, **activation),
        lambda s: sfx.register(s, client_factory=client_factory, **activation),
        lambda s: visual_asset.register(s, client_factory=client_factory, **activation),
        lambda s: channel_plan.register(s, client_factory=client_factory, **activation),
        lambda s: channel.register(s, client_factory=client_factory, **activation),
        lambda s: youtube_video.register(s, client_factory=client_factory, **activation),
        lambda s: youtube_thumbnail.register(s, client_factory=client_factory, **activation),
        lambda s: upload.register(s, client_factory=client_factory, **activation),
    ])
    server.run("stdio")


if __name__ == "__main__":
    main()
```

Note: the previous file used a single import block for the tool modules; the rewrite uses one-per-line and `argparse`. The `_build_client()` helper is reused by `_self_test()` and `main()` to share construction logic.

- [ ] **Step 1.4: Run the test, expect pass**

Run: `pytest console/mcp/tests/test_self_test.py -v`
Expected: 4 passes.

- [ ] **Step 1.5: Verify the existing stdio path still imports cleanly**

Run: `PYTHONPATH=. python -c "import console.mcp.stdio; print('ok')"`
Expected: `ok`.

- [ ] **Step 1.6: Verify `--help` shows `--self-test`**

Run: `PYTHONPATH=. python -m console.mcp.stdio --help`
Expected: usage shows `--self-test` flag.

- [ ] **Step 1.7: Commit**

```bash
git add console/mcp/stdio.py console/mcp/tests/test_self_test.py
git commit -m "feat(mcp): add --self-test mode to stdio entrypoint

Validates that MCP_CONSOLE_API_BASE accepts MCP_API_TOKEN by hitting
/api/system/health, prints a clear OK/FAIL line, and exits 0/1. The
upcoming Dockerized MCP image uses this from a bash provisioner to
gate the install on a working token + reachable backend."
```

---

## Task 2: Create `requirements.mcp.txt`

**Files:**
- Create: `requirements.mcp.txt`

A focused subset. Verified by inspecting the imports of every `console/mcp/**.py` file. The container does not need FastAPI, Celery, Redis, or any media-pipeline dep.

- [ ] **Step 2.1: Create `requirements.mcp.txt`**

Create at the project root with exactly this content:

```text
# Slim runtime deps for the dockerized MCP image (console.mcp.stdio).
# Verified against every top-level import under console/mcp/.

# MCP SDK
mcp>=1.0.0

# HTTP client used by ConsoleClient
httpx>=0.27.0

# JWT decode/encode (used by auth.tokens for service tokens)
python-jose[cryptography]==3.3.0

# Models / settings (pydantic v2)
pydantic[email]>=2.0.0
pydantic-settings>=2.5.2,<3.0.0

# audit_db.py uses sqlalchemy.MetaData/Table/insert; auth/tokens uses bcrypt.
# These are required even though the container does not connect to Postgres
# (the imports run at module load time).
sqlalchemy>=2.0.31
bcrypt>=4.0.1
```

- [ ] **Step 2.2: Verify the list is complete by importing in a clean venv**

This is a manual sanity check — not committed as a test. Run from the project root:

```bash
python3 -m venv /tmp/mcp-image-check
/tmp/mcp-image-check/bin/pip install -q -r requirements.mcp.txt
PYTHONPATH=. /tmp/mcp-image-check/bin/python -c "import console.mcp.stdio; print('imports ok')"
rm -rf /tmp/mcp-image-check
```

Expected: `imports ok`. If it fails with `ModuleNotFoundError`, add the missing package to `requirements.mcp.txt` and re-run.

- [ ] **Step 2.3: Commit**

```bash
git add requirements.mcp.txt
git commit -m "build(mcp): add slim requirements file for docker image

Lists only the runtime deps needed by console.mcp.stdio import. The
upcoming Dockerfile.mcp installs from this file instead of the much
larger console/requirements.txt."
```

---

## Task 3: Create `Dockerfile.mcp` and verify build

**Files:**
- Create: `Dockerfile.mcp`
- (build artifact, not committed: image `ai-media-console-mcp:latest`)

- [ ] **Step 3.1: Create `Dockerfile.mcp`**

At the project root:

```dockerfile
# Slim, stdio-only image for the AI Media Console MCP server.
#
# The container makes outbound HTTP calls to a FastAPI backend specified
# by MCP_CONSOLE_API_BASE and authenticates with a bearer token from
# MCP_API_TOKEN. Both are supplied via `docker run --env-file`.
#
# Build:   docker build -t ai-media-console-mcp:latest -f Dockerfile.mcp .
# Run:     docker run -i --rm \
#            --env-file ~/.mcp/ai-media-console.env \
#            --add-host=host.docker.internal:host-gateway \
#            ai-media-console-mcp:latest
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.mcp.txt ./
RUN pip install -r requirements.mcp.txt

# Source — only what console.mcp.stdio actually imports. Verified via
# `PYTHONPATH=. python -c "import console.mcp.stdio; print(...)"` —
# nothing under console/backend/ is reached at import time.
COPY console/__init__.py ./console/__init__.py
COPY console/mcp ./console/mcp

ENTRYPOINT ["python", "-m", "console.mcp.stdio"]
```

- [ ] **Step 3.2: Build the image**

Run from the project root:

```bash
docker build -t ai-media-console-mcp:latest -f Dockerfile.mcp .
```

Expected: clean build, ends with `Successfully tagged ai-media-console-mcp:latest`. Final image should be under ~250MB.

- [ ] **Step 3.3: Verify the entrypoint runs and shows `--help`**

```bash
docker run --rm ai-media-console-mcp:latest --help
```

Expected: prints the `console.mcp.stdio` usage including `--self-test`.

- [ ] **Step 3.4: Verify `--self-test` fails predictably with no token**

```bash
docker run --rm \
  -e MCP_CONSOLE_API_BASE=http://does-not-exist.invalid:8080 \
  -e MCP_API_TOKEN=invalid \
  ai-media-console-mcp:latest --self-test
```

Expected: exit code 1, stderr contains `FAIL: cannot reach http://does-not-exist.invalid:8080:`.

- [ ] **Step 3.5: Commit**

```bash
git add Dockerfile.mcp
git commit -m "build(mcp): add Dockerfile.mcp for stdio-only image

Slim python:3.11-slim base. Copies only console/__init__.py and
console/mcp/ — confirmed via import sweep that nothing under
console/backend/ is reached. ENTRYPOINT runs python -m
console.mcp.stdio so --self-test flows through unchanged from
docker run --rm ... --self-test."
```

---

## Task 4: TDD — script token parsing and URL normalization

**Files:**
- Create: `console/mcp/scripts/mcp-image.sh`
- Create: `console/mcp/tests/test_mcp_image_script.py`

The script's parsing + normalization + env-write logic is the only part that's worth unit-testing. We drive it with `--token-only --stdin --no-smoke-test --env-file <tmp>` so tests skip Docker entirely.

- [ ] **Step 4.1: Write the failing tests**

Create `console/mcp/tests/test_mcp_image_script.py`:

```python
"""Tests for console/mcp/scripts/mcp-image.sh.

Drive the script with `--token-only --stdin --no-smoke-test --env-file`
so tests never invoke Docker or pbpaste.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "console" / "mcp" / "scripts" / "mcp-image.sh"


def run_script(stdin: str, env_file: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--token-only",
            "--stdin",
            "--no-smoke-test",
            "--env-file",
            str(env_file),
            *extra_args,
        ],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )


def read_env_file(p: Path) -> dict[str, str]:
    out = {}
    for line in p.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k] = v
    return out


CANONICAL_PASTED = '''claude mcp add ai-media-console-prod \\
  --transport stdio \\
  --env MCP_API_TOKEN="eyJhbGciOiJIUzI1NiJ9.aaa.bbb" \\
  --env MCP_CONSOLE_API_BASE=http://192.168.68.119:8080 \\
  -- python -m console.mcp.stdio
'''


def test_parses_canonical_admin_ui_output(tmp_path):
    env_file = tmp_path / "out.env"
    result = run_script(CANONICAL_PASTED, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_API_TOKEN"] == "eyJhbGciOiJIUzI1NiJ9.aaa.bbb"
    assert contents["MCP_CONSOLE_API_BASE"] == "http://192.168.68.119:8080"


def test_env_file_has_mode_0600(tmp_path):
    env_file = tmp_path / "out.env"
    run_script(CANONICAL_PASTED, env_file)
    mode = env_file.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"


def test_localhost_rewritten_to_host_docker_internal(tmp_path):
    pasted = CANONICAL_PASTED.replace(
        "http://192.168.68.119:8080", "http://localhost:8080"
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_CONSOLE_API_BASE"] == "http://host.docker.internal:8080"
    # User-visible warning on stderr
    assert "host.docker.internal" in result.stderr
    assert "warning" in result.stderr.lower() or "rewrote" in result.stderr.lower()


def test_127_0_0_1_rewritten(tmp_path):
    pasted = CANONICAL_PASTED.replace(
        "http://192.168.68.119:8080", "http://127.0.0.1:8080"
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_CONSOLE_API_BASE"] == "http://host.docker.internal:8080"


def test_lan_ip_passes_through(tmp_path):
    """LAN IPs should NOT be rewritten and should NOT emit a warning."""
    env_file = tmp_path / "out.env"
    result = run_script(CANONICAL_PASTED, env_file)

    contents = read_env_file(env_file)
    assert contents["MCP_CONSOLE_API_BASE"] == "http://192.168.68.119:8080"
    assert "host.docker.internal" not in result.stderr


def test_single_line_command_parsed(tmp_path):
    pasted = (
        'claude mcp add ai-media-console-prod --transport stdio '
        '--env MCP_API_TOKEN="abc.def.ghi" '
        '--env MCP_CONSOLE_API_BASE=http://example.com:8080 '
        '-- python -m console.mcp.stdio'
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 0, result.stderr
    contents = read_env_file(env_file)
    assert contents["MCP_API_TOKEN"] == "abc.def.ghi"
    assert contents["MCP_CONSOLE_API_BASE"] == "http://example.com:8080"


def test_missing_token_returns_exit_2(tmp_path):
    pasted = (
        'claude mcp add ai-media-console-prod --transport stdio '
        '--env MCP_CONSOLE_API_BASE=http://example.com:8080 '
        '-- python -m console.mcp.stdio'
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 2
    assert "MCP_API_TOKEN" in result.stderr
    assert not env_file.exists()


def test_missing_base_returns_exit_2(tmp_path):
    pasted = (
        'claude mcp add ai-media-console-prod --transport stdio '
        '--env MCP_API_TOKEN="abc.def.ghi" '
        '-- python -m console.mcp.stdio'
    )
    env_file = tmp_path / "out.env"
    result = run_script(pasted, env_file)

    assert result.returncode == 2
    assert "MCP_CONSOLE_API_BASE" in result.stderr
    assert not env_file.exists()


def test_garbage_input_returns_exit_2(tmp_path):
    env_file = tmp_path / "out.env"
    result = run_script("hello world\nthis is not the right command\n", env_file)

    assert result.returncode == 2
    assert "expected" in result.stderr.lower() or "format" in result.stderr.lower()
    assert not env_file.exists()


def test_help_flag(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0
    # Usage mentions every documented flag
    for flag in ["--build-only", "--token-only", "--no-smoke-test", "--from-clipboard", "--stdin", "--env-file", "--image-tag"]:
        assert flag in result.stdout
```

- [ ] **Step 4.2: Create the script skeleton (will fail tests until step 4.3)**

Create `console/mcp/scripts/mcp-image.sh` with mode `0755`:

```bash
#!/usr/bin/env bash
# Stub — full implementation in Task 4 step 4.3.
set -euo pipefail
echo "not yet implemented" >&2
exit 1
```

```bash
chmod +x console/mcp/scripts/mcp-image.sh
```

- [ ] **Step 4.3: Run the tests, expect failures**

Run: `pytest console/mcp/tests/test_mcp_image_script.py -v`
Expected: every test fails (script always exits 1).

- [ ] **Step 4.4: Implement parsing + normalization + env write + help**

Replace `console/mcp/scripts/mcp-image.sh` with the full implementation:

```bash
#!/usr/bin/env bash
# AI Media Console — MCP Docker image provisioner.
#
# Builds the ai-media-console-mcp image, ingests a token (pasted from the
# admin UI's "Copy command" output), normalizes the backend URL for
# in-container reachability, writes an env file, smoke-tests the
# container, and prints a docker-flavored `claude mcp add` snippet.
#
# Token source: paste the full `claude mcp add ...` command emitted by
# the System tab in the console UI (POST /api/system/mcp/mint-token).
#
# Usage:
#   ./console/mcp/scripts/mcp-image.sh                       # full flow (clipboard on macOS, stdin on Linux)
#   ./console/mcp/scripts/mcp-image.sh --build-only          # build image, skip token + smoke
#   ./console/mcp/scripts/mcp-image.sh --token-only          # skip build
#   ./console/mcp/scripts/mcp-image.sh --no-smoke-test       # skip docker run --self-test
#   ./console/mcp/scripts/mcp-image.sh --from-clipboard      # force pbpaste source (macOS)
#   ./console/mcp/scripts/mcp-image.sh --stdin               # read pasted command from stdin
#   ./console/mcp/scripts/mcp-image.sh --env-file PATH       # override default env-file path
#   ./console/mcp/scripts/mcp-image.sh --image-tag TAG       # override default image tag
#
# Exit codes: 0 success, 1 environment failure (Docker missing, smoke fail), 2 user-input error.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ─── defaults ──────────────────────────────────────────────────────────
DO_BUILD=1
DO_TOKEN=1
DO_SMOKE=1
INPUT_SOURCE=""   # "" = auto, "clipboard" = pbpaste, "stdin" = stdin
ENV_FILE="${HOME}/.mcp/ai-media-console.env"
IMAGE_TAG="ai-media-console-mcp:latest"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Builds the AI Media Console MCP Docker image, ingests a service token
from the admin UI's "Copy command" output, writes an env file, smoke-
tests the container, and prints a docker-flavored \`claude mcp add\`
snippet.

Options:
  --build-only          Build the image only; skip token ingestion + smoke.
  --token-only          Skip image build; only ingest token + write env + smoke.
  --no-smoke-test       Skip the post-write smoke test.
  --from-clipboard      Read the pasted command from \`pbpaste\` (macOS).
  --stdin               Read the pasted command from stdin.
  --env-file PATH       Override the default env file (default: \$HOME/.mcp/ai-media-console.env).
  --image-tag TAG       Override the default image tag (default: ai-media-console-mcp:latest).
  -h, --help            Show this help and exit.

Default input source: pbpaste on macOS if available, else stdin (or stdin
if input is piped in).

Exit codes:
  0  success
  1  environment failure (Docker missing, smoke-test failed)
  2  user-input error (unparseable token, unwritable env file)
USAGE
}

# ─── arg parse ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-only)      DO_BUILD=1; DO_TOKEN=0; DO_SMOKE=0 ;;
        --token-only)      DO_BUILD=0; DO_TOKEN=1; DO_SMOKE=1 ;;
        --no-smoke-test)   DO_SMOKE=0 ;;
        --from-clipboard)  INPUT_SOURCE="clipboard" ;;
        --stdin)           INPUT_SOURCE="stdin" ;;
        --env-file)        ENV_FILE="$2"; shift ;;
        --image-tag)       IMAGE_TAG="$2"; shift ;;
        -h|--help)         usage; exit 0 ;;
        *)                 echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

log()  { printf "  %s\n" "$1"; }
warn() { printf "  warning: %s\n" "$1" >&2; }
fail() { printf "  FAIL: %s\n" "$1" >&2; exit "${2:-1}"; }

# ─── helpers ───────────────────────────────────────────────────────────
read_input_source() {
    # Decide where to read the pasted command from. Prints to stdout.
    local src="$INPUT_SOURCE"
    if [[ -z "$src" ]]; then
        if [[ ! -t 0 ]]; then
            src="stdin"
        elif command -v pbpaste >/dev/null 2>&1; then
            src="clipboard"
        else
            src="stdin"
        fi
    fi
    case "$src" in
        clipboard) pbpaste ;;
        stdin)     cat ;;
        *)         fail "internal: unknown input source '$src'" 2 ;;
    esac
}

extract_token_and_base() {
    # Reads pasted text on stdin. Prints two lines: token, base.
    # Exits 2 with a remediation message if either is missing.
    local input token base
    input="$(cat)"

    token="$(printf '%s' "$input" | grep -oE 'MCP_API_TOKEN="[^"]+"' | head -1 | sed -E 's/^MCP_API_TOKEN="(.*)"$/\1/')"
    if [[ -z "$token" ]]; then
        # Allow unquoted variant too: MCP_API_TOKEN=foo
        token="$(printf '%s' "$input" | grep -oE 'MCP_API_TOKEN=[^[:space:]\\"]+' | head -1 | sed -E 's/^MCP_API_TOKEN=//')"
    fi

    base="$(printf '%s' "$input" | grep -oE 'MCP_CONSOLE_API_BASE=[^[:space:]\\"]+' | head -1 | sed -E 's/^MCP_CONSOLE_API_BASE=//')"

    if [[ -z "$token" ]]; then
        fail "could not find MCP_API_TOKEN in pasted text. Expected format: a 'claude mcp add' command from the System tab containing --env MCP_API_TOKEN=\"...\"." 2
    fi
    if [[ -z "$base" ]]; then
        fail "could not find MCP_CONSOLE_API_BASE in pasted text. Expected format: a 'claude mcp add' command from the System tab containing --env MCP_CONSOLE_API_BASE=..." 2
    fi

    printf '%s\n%s\n' "$token" "$base"
}

normalize_base() {
    # Rewrites localhost / 127.0.0.1 to host.docker.internal so the
    # container can reach the host's FastAPI. Other hosts pass through.
    local base="$1"
    case "$base" in
        http://localhost*|http://127.0.0.1*|https://localhost*|https://127.0.0.1*)
            local rewritten
            rewritten="$(printf '%s' "$base" | sed -E 's#^(https?://)(localhost|127\.0\.0\.1)#\1host.docker.internal#')"
            warn "rewrote $base → $rewritten so the container can reach the host's FastAPI."
            printf '%s\n' "$rewritten"
            ;;
        *)
            printf '%s\n' "$base"
            ;;
    esac
}

write_env_file() {
    local token="$1" base="$2" path="$3"
    local dir
    dir="$(dirname "$path")"
    mkdir -p "$dir"
    chmod 700 "$dir" 2>/dev/null || true
    # Write atomically via tmp file in the same dir.
    local tmp
    tmp="$(mktemp "${dir}/.mcp-env.XXXXXX")"
    {
        printf '# Written by mcp-image.sh — do not commit.\n'
        printf 'MCP_API_TOKEN=%s\n' "$token"
        printf 'MCP_CONSOLE_API_BASE=%s\n' "$base"
    } > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$path"
    log "wrote $path (mode 0600)"
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        fail "docker not on PATH. Install Docker Desktop or start the daemon."
    fi
    if ! docker info >/dev/null 2>&1; then
        fail "docker daemon not responding. Start Docker Desktop and retry."
    fi
}

build_image() {
    require_docker
    log "building $IMAGE_TAG ..."
    ( cd "$REPO_ROOT" && docker build -t "$IMAGE_TAG" -f Dockerfile.mcp . )
    log "built $IMAGE_TAG"
}

smoke_test() {
    require_docker
    log "smoke test: docker run --rm ... --self-test"
    if ! docker run --rm \
        --env-file "$ENV_FILE" \
        --add-host=host.docker.internal:host-gateway \
        "$IMAGE_TAG" --self-test; then
        fail "smoke test failed. See container output above. Common causes: token expired (re-mint in System tab), backend unreachable (check MCP_CONSOLE_API_BASE)."
    fi
    log "smoke test passed"
}

print_snippet() {
    cat <<SNIPPET

──── Run this to register the MCP with Claude Code ────

claude mcp add ai-media-console \\
  --transport stdio \\
  -- docker run -i --rm \\
       --env-file $ENV_FILE \\
       --add-host=host.docker.internal:host-gateway \\
       $IMAGE_TAG

Then restart Claude Code.

SNIPPET
}

# ─── main flow ─────────────────────────────────────────────────────────
if [[ "$DO_BUILD" -eq 1 ]]; then
    build_image
fi

if [[ "$DO_TOKEN" -eq 1 ]]; then
    log "reading pasted 'claude mcp add' command ..."
    pasted="$(read_input_source)"
    parsed="$(printf '%s' "$pasted" | extract_token_and_base)"
    token="$(printf '%s' "$parsed" | sed -n '1p')"
    base="$(printf '%s' "$parsed" | sed -n '2p')"
    base="$(normalize_base "$base")"
    write_env_file "$token" "$base" "$ENV_FILE"
fi

if [[ "$DO_SMOKE" -eq 1 ]]; then
    smoke_test
fi

if [[ "$DO_TOKEN" -eq 1 ]]; then
    print_snippet
fi
```

- [ ] **Step 4.5: Make the script executable**

```bash
chmod +x console/mcp/scripts/mcp-image.sh
```

- [ ] **Step 4.6: Run the tests, expect pass**

Run: `pytest console/mcp/tests/test_mcp_image_script.py -v`
Expected: 9 passes.

- [ ] **Step 4.7: Commit**

```bash
git add console/mcp/scripts/mcp-image.sh console/mcp/tests/test_mcp_image_script.py
git commit -m "feat(mcp): add mcp-image.sh provisioner with token-parse tests

Single bash entry point: builds the image, parses a pasted 'claude mcp
add' command (from the System tab admin UI), normalizes localhost →
host.docker.internal for in-container reachability, writes a 0600 env
file, smoke-tests the container via --self-test, and prints a docker-
flavored claude mcp add snippet.

Tests cover canonical multi-line + single-line pasted formats,
localhost / 127.0.0.1 rewrite, LAN IP pass-through, missing-token /
missing-base / garbage-input error paths, env-file mode 0600, and
--help output."
```

---

## Task 5: End-to-end manual validation

**Files:** none (validation only)

This task is non-automated by design — it touches Docker, Claude Code, and the live FastAPI backend. Each step is a manual check.

- [ ] **Step 5.1: Verify the FastAPI backend is up**

Run: `curl -fsS http://localhost:8080/api/system/health` (or whatever your backend URL is).
Expected: JSON response with status field.

- [ ] **Step 5.2: Mint a token via the admin UI**

1. Open the console UI in a browser, log in as admin.
2. Navigate to System tab.
3. Scroll to "MCP Service Token" card.
4. Click Generate Token, then Copy command.

The clipboard now contains a multi-line `claude mcp add ...` command.

- [ ] **Step 5.3: Run the provisioner**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
./console/mcp/scripts/mcp-image.sh
```

Expected output (in order):
- `building ai-media-console-mcp:latest ...`
- `built ai-media-console-mcp:latest`
- `reading pasted 'claude mcp add' command ...`
- (if backend was localhost) `warning: rewrote http://localhost:8080 → http://host.docker.internal:8080 ...`
- `wrote /Users/<you>/.mcp/ai-media-console.env (mode 0600)`
- `smoke test: docker run --rm ... --self-test`
- `OK: <base> reachable, token accepted.`
- `smoke test passed`
- The docker-flavored `claude mcp add` snippet.

- [ ] **Step 5.4: Verify env file permissions**

```bash
stat -f '%A %N' ~/.mcp/ai-media-console.env
```

Expected: `600 /Users/.../ai-media-console.env`.

- [ ] **Step 5.5: Register and verify in Claude Code**

1. Copy the printed `claude mcp add ai-media-console ...` snippet.
2. Run it in a fresh terminal.
3. Restart Claude Code.
4. In a Claude session, ask Claude to call the `system_health` tool with `action="health"`.

Expected: a JSON response from the backend (not a 401 or connection error).

- [ ] **Step 5.6: Validate token rotation flow**

```bash
# Re-mint a token in the UI, copy the new command, then:
./console/mcp/scripts/mcp-image.sh --token-only
```

Expected: image build skipped, env file rewritten, smoke passes, snippet reprinted.

- [ ] **Step 5.7: Validate the LAN-backend path**

If your backend is reachable via a LAN IP (e.g., `http://192.168.x.x:8080`), repeat steps 5.2–5.5 using a token minted with that base. Verify no `host.docker.internal` warning appears and the smoke test passes.

- [ ] **Step 5.8: No commit needed for this task**

Manual validation produces no artifacts.

---

## Task 6: Document the Docker flow in `console/mcp/README.md`

**Files:**
- Modify: `console/mcp/README.md`

- [ ] **Step 6.1: Add a Docker quickstart section**

Open `console/mcp/README.md` and add the following section. Place it **after** the existing "Quickstart" or "Running the server" section — whichever comes first — so the host-Python and Docker flows sit next to each other. (If neither section exists, add it near the top after the introduction.)

```markdown
## Docker quickstart

Run the MCP server in a slim Docker image instead of as host Python.
This is the recommended setup for clients (operators) — it keeps the
project's full Python pipeline off their machines.

### One-time setup

1. **Build the image and provision a token.** From the project root:

   ```bash
   ./console/mcp/scripts/mcp-image.sh
   ```

   Before running, mint a service token in the console UI:
   - Log in as admin → System tab → MCP Service Token card → Generate Token → Copy command.
   - The full `claude mcp add ...` command is now on your clipboard.

   The script:
   - Builds `ai-media-console-mcp:latest` from `Dockerfile.mcp`.
   - Reads the pasted command (clipboard on macOS, stdin elsewhere).
   - Rewrites `localhost` / `127.0.0.1` to `host.docker.internal` so the
     container can reach the host's FastAPI.
   - Writes `~/.mcp/ai-media-console.env` (mode 0600).
   - Smoke-tests the container via `docker run --rm ... --self-test`.
   - Prints a docker-flavored `claude mcp add` snippet.

2. **Register with Claude Code.** Paste the printed snippet, then
   restart Claude.

### Token rotation

```bash
# Mint a fresh token in the UI, copy command, then:
./console/mcp/scripts/mcp-image.sh --token-only
```

Image stays put; only `~/.mcp/ai-media-console.env` is rewritten.

### Other flags

| Flag | Effect |
|---|---|
| `--build-only` | Build image; skip token + smoke. |
| `--token-only` | Skip build; only ingest token + smoke. |
| `--no-smoke-test` | Skip the post-write smoke test. |
| `--from-clipboard` / `--stdin` | Force a specific input source. |
| `--env-file PATH` | Override the env-file path. |
| `--image-tag TAG` | Override the image tag. |

### Troubleshooting

- **"docker not on PATH" / "daemon not responding"** — install / start
  Docker Desktop and retry.
- **Smoke test fails with 401** — token expired or `JWT_SECRET` rotated;
  re-mint in the System tab.
- **Smoke test fails with connection error** — the container can't reach
  the backend. If your backend is on the host, the script rewrote the
  base URL; verify your FastAPI is actually listening. If your backend
  is on the LAN, verify the IP is reachable from inside Docker.
```

- [ ] **Step 6.2: Commit**

```bash
git add console/mcp/README.md
git commit -m "docs(mcp): add Docker quickstart to README

Documents the new mcp-image.sh provisioner flow alongside the existing
host-Python flow. Covers one-time setup, token rotation, all script
flags, and the three most common failure modes (no docker, 401, no
backend reachability)."
```

---

## Self-Review

**1. Spec coverage.** Each major spec section maps to a task:

| Spec section | Tasks |
|---|---|
| §3 Architecture diagram | 1, 3, 4 |
| §4.1 Dockerfile.mcp | 3 |
| §4.2 requirements.mcp.txt | 2 |
| §4.3 mcp-image.sh script (all 7 behaviors) | 4 |
| §4.4 stdio.py --self-test | 1 |
| §4.5 test_parse_claude_mcp_add.py | 4 |
| §5 Data flow (setup + per-session + rotation) | 4, 5 |
| §6 Error handling (all 6 rows) | 1 (401, conn-err), 4 (parse-fail, docker-missing, env-write), 5 (build-fail) |
| §7.1 Unit tests | 1, 4 |
| §7.2 Integration (docker build + self-test) | 3 |
| §7.3 Manual end-to-end | 5 |
| §8 Files touched | all (every row in the table is a task target) |
| §9 Security (0600 env, 0700 dir, no token logged, no exposed port) | 4 (mode tests + write_env_file impl) |
| §10 Rollout | 5 (manual validate), 6 (README) |

The spec's `console/mcp/tests/test_parse_claude_mcp_add.py` is delivered as `console/mcp/tests/test_mcp_image_script.py` (renamed because the file tests more than just parsing — also URL normalization, env-file mode, help output). Functionally equivalent.

**2. Placeholder scan.** No "TBD", "TODO", "implement later", or unresolved decisions. Every code block is complete and runnable.

**3. Type/name consistency.**
- `_self_test()` async, `_run_self_test_sync()` sync wrapper — both names referenced in tests and impl. Consistent.
- `MCP_API_TOKEN` / `MCP_CONSOLE_API_BASE` — consistent across stdio.py, Dockerfile, script, env-file, snippet, tests.
- `ai-media-console-mcp:latest` — consistent across Dockerfile build, script default, snippet, README.
- `~/.mcp/ai-media-console.env` — consistent everywhere.
- `host.docker.internal:host-gateway` — same `--add-host` arg in script smoke step + final printed snippet.

**4. Bash regex coverage.** The token regex handles both quoted and unquoted forms; tests in §4 cover canonical multi-line, single-line, missing-token, missing-base, and garbage. URL rewrite covers `http://` and `https://` for both `localhost` and `127.0.0.1`.

No issues found. Plan is complete.
