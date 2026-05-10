# MCP Docker Image — Design

**Date:** 2026-05-10
**Status:** Approved (design); pending implementation plan
**Owner:** khiemlq

## 1. Problem

The `ai-media-console` MCP server currently runs on the host as
`python -m console.mcp.stdio`. This requires the operator's machine to have
a working Python 3.11 environment, the project's source tree on disk, and
the right venv activation in whatever process spawns it.

We want to package the MCP server as a Docker image so:

- Claude Code on any developer machine can run the MCP without provisioning
  a Python env or cloning the repo's full pipeline dependencies (MoviePy,
  Celery, Whisper, etc.).
- The MCP image stays small and single-purpose. It only makes HTTP calls to
  a FastAPI backend (local dev or production); it does not touch Postgres,
  Redis, or the render pipeline.
- Token provisioning reuses the existing **admin UI flow**
  (`POST /api/system/mcp/mint-token`, surfaced as the "MCP Service Token"
  card on the System tab) — no SSH, no `mint_token.py` invocation by hand.

## 2. Non-goals

- HTTP/SSE transport for this image. Stdio is the only mode.
- Pushing the image to a public registry. Local-only build.
- A `docker-compose` file for the MCP. The container is a one-shot
  per-Claude-session process; compose adds no value.
- Modifying the existing `mcp-dev.sh` (host-Python flow). It stays as a
  parallel option for contributors who don't want Docker.
- Frontend changes. The current "Copy command" output in the System tab is
  parseable as-is; we will not add a "docker variant" toggle.
- Automated SSH-based minting against production. The admin UI already
  removes the need for that.

## 3. Architecture

```
┌────────────────────┐       (one-time setup)
│  Web UI (System)   │  ──── click "Generate Token" ────► copy `claude mcp add …`
└────────────────────┘
            │ paste
            ▼
┌─────────────────────────────────────────────────────────┐
│  console/mcp/scripts/mcp-image.sh                       │
│  ─────────────────────────────────────────────────────  │
│  1. docker build -t ai-media-console-mcp:latest         │
│     -f Dockerfile.mcp .                                 │
│  2. parse MCP_API_TOKEN + MCP_CONSOLE_API_BASE          │
│     from pasted command                                 │
│  3. normalize host (localhost → host.docker.internal)   │
│  4. write ~/.mcp/ai-media-console.env (mode 600)        │
│  5. docker run --rm … --self-test (validates token +    │
│     backend reachability)                               │
│  6. print docker-flavored `claude mcp add …`            │
└─────────────────────────────────────────────────────────┘
            │ paste, then restart Claude Code
            ▼
┌─────────────────────────────────────────────────────────┐
│  Claude Code session                                    │
│  spawns: docker run -i --rm                             │
│            --env-file ~/.mcp/ai-media-console.env       │
│            --add-host=host.docker.internal:host-gateway │
│            ai-media-console-mcp:latest                  │
│                                                         │
│  container runs: python -m console.mcp.stdio            │
│                       │                                 │
│                       │ HTTP                            │
│                       ▼                                 │
│              FastAPI backend (MCP_CONSOLE_API_BASE)     │
└─────────────────────────────────────────────────────────┘
```

## 4. Components

### 4.1 `Dockerfile.mcp` (new — project root)

- Base: `python:3.11-slim`.
- Working dir: `/app`.
- Copy only the source the stdio entrypoint imports. The exact set is
  determined at implementation time by running, on the host:
  ```
  PYTHONPATH=. python -c "import console.mcp.stdio; \
    import sys; \
    print('\n'.join(sorted(m for m in sys.modules \
      if m.startswith('console.'))))"
  ```
  and copying the corresponding source files. Expected minimum:
  - `console/mcp/` (entire package)
  - `console/backend/config.py`
  - any `console/backend/*.py` files surfaced by the command above
    (e.g., `database.py` if a shared model is imported)
- Install from `requirements.mcp.txt`.
- ENTRYPOINT: `["python", "-m", "console.mcp.stdio"]`.
- No `CMD`. Args (e.g., `--self-test`) flow through `docker run … <args>`.

### 4.2 `requirements.mcp.txt` (new — project root)

A focused subset of `console/requirements.txt` containing only what
`console.mcp.stdio` and the registered tool modules import. Expected
contents (to be finalized when reading actual imports):

- `mcp` (FastMCP SDK)
- `httpx`
- `python-jose[cryptography]`
- `pydantic` and `pydantic-settings`
- `sqlalchemy` — only if a shared model module is imported by any
  `console.mcp.*` file at import time (otherwise drop)

Excluded: `fastapi`, `uvicorn`, `celery`, `redis`, `moviepy`,
`opencv-python`, `whisper`, etc.

### 4.3 `console/mcp/scripts/mcp-image.sh` (new)

Bash entry point. Exit codes: `0` success, `1` environment failure (Docker
missing, smoke-test failure), `2` user-input error.

Flags:

| Flag | Effect |
|---|---|
| (no flag) | full flow: build → ingest token → write env → smoke-test → print snippet |
| `--build-only` | build the image, skip token + env + smoke |
| `--token-only` | skip build, ingest token + write env + smoke + print snippet |
| `--no-smoke-test` | skip the `--self-test` step |
| `--from-clipboard` | read token source from `pbpaste`. Implicit default on macOS when neither `--from-clipboard` nor `--stdin` is passed and `pbpaste` is on PATH. |
| `--stdin` | read token source from stdin. Implicit default when stdin is not a TTY (i.e., piped input). |
| `--env-file <path>` | override default `~/.mcp/ai-media-console.env` |
| `--image-tag <tag>` | override default `ai-media-console-mcp:latest` |
| `-h` / `--help` | print usage |

Flags compose: `--token-only --no-smoke-test --stdin` is the canonical
combination for unit tests (skip build, skip docker entirely, parse from
stdin).

Behavior:

1. **Pre-flight**
   - Check `docker` is on PATH and the daemon is responding
     (`docker info >/dev/null`). If not: exit 1 with remediation.
2. **Build** (skipped if `--token-only`)
   - `docker build -t <image-tag> -f Dockerfile.mcp .`
3. **Token ingestion** (skipped if `--build-only`)
   - Read pasted text from clipboard or stdin.
   - Regex-extract `MCP_API_TOKEN="..."` and `MCP_CONSOLE_API_BASE=...`
     from the pasted `claude mcp add` command.
   - If extraction fails: exit 2 with the expected format.
4. **URL normalization**
   - If `MCP_CONSOLE_API_BASE` host is `localhost` or `127.0.0.1`, rewrite
     to `host.docker.internal` (preserve scheme, port, path) and warn the
     user that this is the in-container view.
   - Otherwise pass through unchanged.
5. **Env file write**
   - Ensure `~/.mcp/` exists with mode `0700`.
   - Write `~/.mcp/ai-media-console.env` with mode `0600`. Contents:
     ```
     MCP_API_TOKEN=<token>
     MCP_CONSOLE_API_BASE=<normalized-base>
     ```
6. **Smoke test** (skipped if `--no-smoke-test` or `--build-only`)
   - `docker run --rm --env-file <env> --add-host=host.docker.internal:host-gateway <image-tag> --self-test`
   - On non-zero exit: surface the container's stderr and exit 1.
7. **Print snippet**
   - Emit a docker-flavored `claude mcp add` command:
     ```
     claude mcp add ai-media-console \
       --transport stdio \
       -- docker run -i --rm \
            --env-file ~/.mcp/ai-media-console.env \
            --add-host=host.docker.internal:host-gateway \
            ai-media-console-mcp:latest
     ```
   - Note: env vars live in the env-file, not in `--env` flags, so the
     snippet does not echo the JWT to the screen.

### 4.4 `console/mcp/stdio.py` — modify

Add a `--self-test` argument. When present:

1. Build a `ConsoleClient` exactly as `main()` does (via `StdioAuth.from_env()`).
2. Call `GET /api/system/health` with the bearer token.
3. On HTTP 200: print `OK: <base> reachable, token accepted` and exit 0.
4. On HTTP 401: print `FAIL: token rejected by <base> (401). Re-mint in System tab.` and exit 1.
5. On any other HTTP / connection error: print
   `FAIL: cannot reach <base>: <error>. Check URL / network.` and exit 1.

The self-test path runs in-process — no JSON-RPC handshake — so it is
trivial to script from bash.

### 4.5 `console/mcp/tests/test_parse_claude_mcp_add.py` (new)

Pytest tests that invoke `mcp-image.sh --token-only --stdin
--no-smoke-test --env-file <tmp>` via `subprocess.run`, piping each
fixture as stdin, then assert the contents of the resulting temp env
file (or, on parse failure, that the script exits with code 2 and
stderr matches the expected message). Fixtures cover at least:

- The exact format emitted by `SystemPage.jsx` today (multi-line, `\\` line
  continuations, `--env MCP_API_TOKEN="..."`).
- A single-line variant.
- Trailing-slash and no-trailing-slash bases.
- Quoted vs unquoted token.
- Missing fields → expect parse error.

## 5. Data flow

### 5.1 One-time setup
1. Admin opens the System tab and clicks Generate Token. UI displays the
   token and a `claude mcp add …` command.
2. Admin clicks Copy command (token now on clipboard via the full
   command).
3. Admin runs `./console/mcp/scripts/mcp-image.sh` from the project root.
4. Script builds the image (cache-fast on rebuilds), parses the pasted
   command, normalizes the URL, writes the env file, smoke-tests, and
   prints the docker-flavored `claude mcp add` command.
5. Admin pastes that command and restarts Claude Code.

### 5.2 Each Claude session
1. Claude Code reads `~/.claude.json`, finds the `ai-media-console` entry,
   spawns `docker run -i --rm --env-file … ai-media-console-mcp:latest`.
2. Container starts `python -m console.mcp.stdio`. JSON-RPC over stdio
   begins.
3. Tool calls go through `ConsoleClient` → HTTP →
   `MCP_CONSOLE_API_BASE`. The container has no other dependencies.
4. When Claude Code exits or the user disconnects MCP, the container exits
   (because of `--rm`) and is cleaned up.

### 5.3 Token rotation
- Re-run `./mcp-image.sh --token-only` with a freshly minted command. Only
  the env file changes; image stays put.

## 6. Error handling

| Failure | Where caught | Script response |
|---|---|---|
| `docker` missing / daemon down | pre-flight | exit 1, "Install Docker Desktop / start the daemon" |
| Pasted text unparseable | token ingestion | exit 2, print expected format and what was missing |
| Self-test exits 401 | smoke step | exit 1, "Token expired or JWT_SECRET mismatch — re-mint in System tab" |
| Self-test connection error | smoke step | exit 1, "Backend unreachable at `<normalized-url>` — verify URL/LAN" |
| Image build fails | build step | bubble up Docker stderr; suggest `docker system prune` |
| Env file path not writable | env write | exit 1, point at `~/.mcp/` permissions |

The script never echoes the JWT to stdout/stderr after extraction. The
final `claude mcp add` snippet references the env file by path; the JWT
itself stays in `~/.mcp/ai-media-console.env` (mode 0600).

## 7. Testing

### 7.1 Unit
- Token+base regex: 5 fixtures (canonical multi-line, single-line,
  trailing-slash variants, missing-field, malformed).

### 7.2 Integration
- CI step: build the image (validates Dockerfile + requirements). Already
  doable with `docker build` in GitHub Actions.
- CI step: run `--self-test` against a stub backend that returns 200 on
  `/api/system/health`. Validates that container can resolve and reach
  `http://host:port`.

### 7.3 Manual
- Local backend (`http://localhost:8080`): script rewrites to
  `host.docker.internal`, smoke passes.
- LAN backend (`http://192.168.x.x:8080`): no rewrite, smoke passes.
- Expired token: smoke fails with 401 path, message guides user to System
  tab.
- Unreachable backend: smoke fails with connection-error path.
- Full end-to-end: admin UI → script → paste → restart Claude → call
  `system_health` tool → 200.

## 8. Files touched

| Path | New / Modified |
|---|---|
| `Dockerfile.mcp` | new |
| `requirements.mcp.txt` | new |
| `console/mcp/scripts/mcp-image.sh` | new |
| `console/mcp/stdio.py` | modified (add `--self-test`) |
| `console/mcp/tests/test_parse_claude_mcp_add.py` | new |
| `console/mcp/README.md` | modified (add Docker section pointing to the new flow) |

## 9. Security notes

- The JWT for `mcp-system` carries `role: admin`. Treat it as a password.
- Env file is written with mode `0600` and lives under `~/.mcp/` (mode
  `0700`). This matches existing dotfile conventions.
- The script does not log the token. The final printed snippet references
  the env file by path; the JWT never appears in shell history beyond what
  the user already pasted.
- The container has no inbound surface — no exposed ports, no listeners.
  Stdio only.
- The image does not bundle the JWT_SECRET, DATABASE_URL, or any other
  backend secret. It only holds Python source for the MCP layer.

## 10. Rollout

1. Land the spec.
2. Implement per the plan that follows.
3. Manually validate against local + LAN backends.
4. Update `console/mcp/README.md` with the Docker quickstart.
5. Announce to the (one-engineer) team. The legacy `mcp-dev.sh` flow
   remains supported for anyone who prefers host Python.
