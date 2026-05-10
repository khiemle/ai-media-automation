# console-mcp Runbook

## Overview

`console/mcp` is an MCP server that exposes the AI Media Console's video-creation
workflows (YouTube videos, music, SFX, uploads, channel management, pipeline jobs) to
LLM agents. It runs in three transport modes: stdio (Claude Code / local dev), HTTP/SSE
(cron / remote agents), and a mounted sub-app on the existing console FastAPI process
(editor chat surface). The MCP layer is a thin proxy: it translates MCP tool calls into
authenticated HTTP requests against the console backend at `:8080`. It depends on
PostgreSQL (audit log), Redis (idempotency cache), and a running console FastAPI process.
All tool source lives under `console/mcp/`; the mounted sub-app is wired into
`console/backend/main.py`.

---

## Pre-flight checklist

For an automated check + setup, run `./console/mcp/scripts/mcp-dev.sh` from project root.

Otherwise, confirm all of the following manually:

- **PostgreSQL running.**
  ```bash
  psql "$DATABASE_URL" -c "SELECT 1"
  ```
  Expected: `1` row returned.

- **Redis running.**
  ```bash
  redis-cli -u "$REDIS_URL" ping
  ```
  Expected: `PONG`

- **Console FastAPI on :8080.**
  ```bash
  curl -sf http://localhost:8080/api/system/health | python3 -m json.tool
  ```
  Expected: JSON with `"status": "ok"`.

- **MCP migration applied** — `alembic_version` must include revision `d885cdd6570e`.
  ```bash
  cd console/backend && alembic current
  ```
  Expected: `d885cdd6570e (head)`. If not:
  ```bash
  cd console/backend && alembic upgrade head
  ```

- **`mcp-system` user seeded** — the migration seeds this automatically on upgrade.
  ```bash
  psql "$DATABASE_URL" -c "SELECT id, username, role FROM console_users WHERE username='mcp-system'"
  ```
  Expected: one row, `role = admin`.

---

## Mint the service-account JWT

The `mcp-system` user's password hash is set to `!disabled!` — login via the API is
blocked. Use the dedicated minting script:

```bash
# Locally (uses your local JWT_SECRET from console/.env)
python -m console.mcp.scripts.mint_token --days 90        # plaintext JWT
python -m console.mcp.scripts.mint_token --days 90 --json # JSON with expires_at + lifetime

# In a docker compose stack (uses the in-container JWT_SECRET)
docker compose exec -T api python -m console.mcp.scripts.mint_token --days 90
```

**Lifetime:** the script writes an explicit `exp` claim on the JWT and bypasses
`JWT_EXPIRE_MINUTES` entirely — service tokens have a different lifecycle from
short-lived user-login tokens. Default is 90 days; override with `--days N`.

There is no automatic service-token renewal. Re-mint and redeploy every ~60 days
(see "Token rotation policy" below). The `token_refresh` Celery beat task only
refreshes OAuth platform credentials.

Save the token:
```bash
export MCP_API_TOKEN="<output-from-above>"
# Or persist in console/.env alongside other env vars,
# or set as a GitHub repo secret for the deploy workflow to write to console/.env.
```

---

## Transport: stdio (Claude Code / dev)

### Start

```bash
cd /path/to/ai-media-automation
MCP_API_TOKEN="<jwt>" python -m console.mcp.stdio
```

Or via Claude Code `mcp.json`:
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

Optional env vars:
- `MCP_CONSOLE_API_BASE` — defaults to `http://localhost:8080`

### Verify

Send a `tools/list` request over stdin. The quickest check is the smoke test:
```bash
cd ai-media-automation
MCP_API_TOKEN=stub MCP_CONSOLE_API_BASE=http://nonexistent:1 \
  pytest console/mcp/tests/e2e/test_smoke.py -m manual -v
```
Expected: 11 tools listed (the test asserts the exact set).

For a live check against the real backend:
```bash
MCP_API_TOKEN="<jwt>" python -m console.mcp.stdio <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ops","version":"0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
EOF
```
Expected: JSON response with `result.tools` containing 11 entries.

### Common errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ConsoleError: auth.unauthorized — MCP_API_TOKEN not set` | `MCP_API_TOKEN` env var missing | Set it before starting |
| `auth.token_expired` in tool results | JWT has expired | Re-mint the token; extend `JWT_EXPIRE_MINUTES` if needed |
| `dependency.upstream_unavailable` | Console API on :8080 is down | Restart `./console/start.sh` |
| `not_found` on every tool call | Wrong `MCP_CONSOLE_API_BASE` | Check the env var points to the running console |

---

## Transport: HTTP/SSE (cron / remote agents)

### Start

```bash
cd ai-media-automation
MCP_HTTP_DEV_API_KEY="<random-secret>" \
MCP_API_TOKEN="<jwt>" \
MCP_CONSOLE_API_BASE="http://localhost:8080" \
MCP_HTTP_HOST="127.0.0.1" \
MCP_HTTP_PORT="8765" \
  python -m console.mcp.http
```

**Two registry modes**, controlled by `MCP_HTTP_USE_DB_KEYS`:

- `MCP_HTTP_USE_DB_KEYS=1` (default in prod compose) — `DbApiKeyRegistry` reads the
  `mcp_api_keys` table on every lookup, bcrypt-checks the inbound key against each
  unrevoked row's `key_hash`, updates `last_used_at` on success. Add keys with
  `manage_api_keys.py create`; revoke with `manage_api_keys.py revoke`. Effect is
  immediate (no service restart needed).
- `MCP_HTTP_USE_DB_KEYS=0` — `InMemoryApiKeyRegistry` is populated only from the
  `MCP_HTTP_DEV_API_KEY` env var. Used by `mcp-dev.sh --http` for local-only testing
  without touching the DB.

In either mode, **without at least one valid key**, every request returns
`401 invalid api key`.

Optional env vars:
- `MCP_HTTP_HOST` — defaults to `0.0.0.0` (compose port mapping uses
  `127.0.0.1:8765:8765` to keep it host-local; expose externally only via reverse
  proxy)
- `MCP_HTTP_PORT` — defaults to `8765`

### Configure the API key

The client must pass the key in `X-API-Key`. Set the same value on both sides:
```bash
# Server side (see above):
export MCP_HTTP_DEV_API_KEY="my-secret-key"

# Client side — every request:
curl -H "X-API-Key: my-secret-key" ...
```

> **FOLLOWUPS gap (see FOLLOWUPS.md — "http.py dead FastMCP wiring"):**
> `build_http_app` registers tools on a FastMCP instance, but `/mcp/call` dispatches
> through a manual if/elif ladder that bypasses that instance. The FastMCP registration
> is dead code; tool calls go through the ladder directly. This is cosmetic for now but
> means the FastMCP `server.list_tools()` response (used by `/mcp/tools`) and the actual
> dispatch are independently maintained.

### Verify

```bash
API_KEY="my-secret-key"
BASE="http://127.0.0.1:8765"

# Liveness (no auth required)
curl -sf "$BASE/healthz"
# Expected: {"status":"ok"}

# Tool catalog
curl -sf -H "X-API-Key: $API_KEY" "$BASE/mcp/tools" | python3 -m json.tool
# Expected: {"tools":[...]} with 11 entries

# Call a tool
curl -sf -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"name":"system_health","arguments":{"action":"health"}}' \
  "$BASE/mcp/call" | python3 -m json.tool
# Expected: {"ok":true,"data":{...}}
```

### Common errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 invalid api key` on all routes | `MCP_HTTP_DEV_API_KEY` not set | Set the env var before starting |
| `401 invalid api key` after restart | Key changed between runs | Restart with the same key value the client uses |
| `404 unknown tool <name>` | Tool name typo in `name` field | Check spelling against `/mcp/tools` catalog |
| `auth.unauthorized` in tool result | JWT in `MCP_API_TOKEN` is invalid or expired | Re-mint the token |
| `dependency.upstream_unavailable` | Console API unreachable | Restart console backend |
| bcrypt latency on every request | `InMemoryApiKeyRegistry.lookup` bcrypt-checks all stored hashes per call | Expected for single-key dev use; fix requires `DbApiKeyRegistry` |

---

## Transport: mounted sub-app (chat surface)

### How it activates

The mount is wired directly into `console/backend/main.py` at import time:
```python
# console/backend/main.py (last two lines)
from console.mcp.mount import attach as _attach_mcp
_attach_mcp(app)
```
This adds `GET /mcp/tools` and `POST /mcp/call` to the main FastAPI app. There is no
separate process. The routes go live whenever `uvicorn console.backend.main:app` starts.

Auth: the end-user's existing console JWT (from the browser session) is forwarded as-is.
No `MCP_API_TOKEN` is needed for this transport.

### Verify

```bash
# Get a user JWT by logging in
TOKEN=$(curl -sf -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_PASSWORD"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -sf -H "Authorization: Bearer $TOKEN" http://localhost:8080/mcp/tools | python3 -m json.tool
# Expected: {"tools":[...]} with 11 entries

curl -sf -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"system_health","arguments":{"action":"health"}}' \
  http://localhost:8080/mcp/call | python3 -m json.tool
# Expected: {"ok":true,"data":{...}}
```

### Common errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 bearer token required` | Missing or malformed `Authorization: Bearer ...` header | Pass the console JWT in the header |
| `401` / `auth.token_expired` | Console session JWT expired | Re-login via `/api/auth/login` |
| `auth.forbidden` | User role is insufficient for the tool's target endpoint | Check user role vs. endpoint permissions |
| Routes not found (404 on `/mcp/*`) | `_attach_mcp` import failed at startup (check uvicorn logs) | Investigate import error; ensure `console/mcp` package is importable |

---

## Audit logging

### What gets logged

When enabled, every tool call writes one row to `mcp_tool_calls`:

| Column | Contents |
|--------|----------|
| `called_at` | UTC timestamp |
| `transport` | `stdio`, `http`, or `chat` |
| `actor_jwt_sub` | JWT `sub` field (user ID string) |
| `tool_name` | e.g. `youtube_video` |
| `action` | e.g. `render_final` |
| `args_redacted` | JSONB — secrets replaced with `***` |
| `ok` | Whether the tool returned `ok: true` |
| `error_code` | Populated on failure |
| `duration_ms` | Wall time of the tool call |
| `task_id` | Celery task ID, if the tool kicked an async task |

### What's redacted

Keys whose name ends in `_token`, `_key`, `_secret`, or matches `password`, `passwd`,
`authorization` are replaced with `***` before the row is written (see `redact.py`).

### How to enable

Set `MCP_AUDIT_ENABLED=1` in the transport's environment. `console/mcp/activation.py`'s
`audit_kwargs()` helper reads this and returns a `DbAuditSink()` to each tool's
`register()` call. Default off (no rows written) — keeps tests and dev runs clean.

```bash
# Local stdio (rarely needed in dev):
MCP_AUDIT_ENABLED=1 python -m console.mcp.stdio

# Local HTTP:
MCP_AUDIT_ENABLED=1 python -m console.mcp.http
```

In production, the deploy workflow writes `MCP_AUDIT_ENABLED=1` into `console/.env`
automatically — no per-host action required.

**Backend audit chain:** when MCP makes a write call to FastAPI, `ConsoleClient` attaches
`X-Mcp-Actor-Metadata` (a JSON blob with transport + identity hints). The console's
audit middleware (`console/backend/middleware/audit.py`) parses the header and stores it
in `audit_log.actor_metadata`. So a single MCP-mediated tool call produces two rows: one
in `mcp_tool_calls` (the MCP-side log) and one in `audit_log` (the backend-side log
linking the change to a real `console_user`).

> **Known cosmetic issue (see FOLLOWUPS.md — "Audit middleware logs needs_confirmation
> calls as ok=false"):** First-call intent responses (`needs_confirmation: true`) are
> logged with `ok=false`. Inflates error-rate metrics; filter them out by also
> requiring `error_code IS NOT NULL` in dashboards.

> **Known gap (see FOLLOWUPS.md — "Mount transport audit gap"):** the `mount.py` chat
> sub-app dispatches via a hand-rolled if/elif ladder that bypasses
> `wrap_with_audit_log`. So `mcp_tool_calls` rows for chat-transport calls are not
> written. Backend `audit_log` rows still record the change (the chat user's JWT is
> forwarded), but the MCP-side log misses chat traffic until mount.py is refactored
> to use FastMCP-style registration.

### Querying

```sql
-- Recent calls by tool
SELECT tool_name, action, ok, error_code, duration_ms, called_at
FROM mcp_tool_calls
ORDER BY called_at DESC
LIMIT 50;

-- All failures in the last hour
SELECT tool_name, action, error_code, actor_jwt_sub, called_at
FROM mcp_tool_calls
WHERE ok = false AND called_at > now() - interval '1 hour'
ORDER BY called_at DESC;

-- Calls by actor
SELECT actor_jwt_sub, tool_name, action, ok, called_at
FROM mcp_tool_calls
WHERE actor_jwt_sub = '42'   -- replace with user.id
ORDER BY called_at DESC;

-- Async tasks kicked (those with a task_id)
SELECT tool_name, action, task_id, called_at
FROM mcp_tool_calls
WHERE task_id IS NOT NULL
ORDER BY called_at DESC;

-- Error rate by tool in the last 24h
SELECT tool_name,
       count(*) FILTER (WHERE ok = true) AS ok_count,
       count(*) FILTER (WHERE ok = false) AS err_count
FROM mcp_tool_calls
WHERE called_at > now() - interval '24 hours'
GROUP BY tool_name;
```

### Retention

No automatic retention. The `mcp_tool_calls` table grows unbounded. Add a cron job or
pg_partman policy if row count becomes a concern.

---

## Idempotency

### Which actions support it

Three actions accept an optional `idempotency_key` argument:
- `upload(action="upload_one", video_id=N, idempotency_key="<key>", confirm=true, confirm_id=N)`
- `upload(action="upload_all", idempotency_key="<key>", confirm=true, confirm_id="all")`
- `youtube_video(action="render_final", video_id=N, idempotency_key="<key>", confirm=true)`

**Activation:** set `MCP_IDEMPOTENCY_ENABLED=1` in the transport's environment.
`console/mcp/activation.py`'s `install_idempotency_store()` reads this at startup,
opens a `redis.asyncio` connection to `REDIS_URL`, and installs the store on both
`tools.upload._store` and `tools.youtube_video._store`. Default off (no key
deduplication) — keeps tests deterministic.

In production, the deploy workflow writes `MCP_IDEMPOTENCY_ENABLED=1` and the compose
file injects `REDIS_URL=redis://redis:6379/0` automatically.

> **Known gap (see FOLLOWUPS.md — "Module-level `_store` globals"):** the store is
> a module-level Python global. Fine for sequential test execution and the current
> single-process production layout, but parallel test runs (pytest-xdist) or multiple
> transports running in the same process would race. Convert to a `ContextVar` if
> either ever becomes a concern.

### How agents use it

Pass any stable string as `idempotency_key`. If the same key is reused within the TTL,
the cached result is returned without re-executing the upload or render.

```json
{
  "name": "upload",
  "arguments": {
    "action": "upload_one",
    "video_id": 42,
    "idempotency_key": "daily-batch-2026-05-10-vid42",
    "confirm": true,
    "confirm_id": 42
  }
}
```

### TTL

Controlled by `MCP_IDEMPOTENCY_TTL_S` (default `86400` = 24 hours). Set in the
transport process environment.

### Clearing the cache manually

```bash
# List all cached keys
redis-cli -u "$REDIS_URL" KEYS "mcp:idem:*"

# Delete a specific key
redis-cli -u "$REDIS_URL" DEL "mcp:idem:upload_one:daily-batch-2026-05-10-vid42"

# Delete all idempotency keys (use with care)
redis-cli -u "$REDIS_URL" EVAL "local k=redis.call('KEYS','mcp:idem:*') if #k>0 then return redis.call('DEL',unpack(k)) else return 0 end" 0
```

---

## Tasks (Celery)

### How tools surface them

Tools that kick async work return:
```json
{
  "ok": true,
  "task_id": "abc-123",
  "status_tool": "task_status",
  "task_kind": "youtube_render_final",
  "poll_hint": "every 30s, ~5-15 min for final render"
}
```

### Polling

```json
{"name": "task_status", "arguments": {"task_id": "abc-123"}}
```

Poll the console API via `GET /api/pipeline/jobs/{task_id}` (also accessible via the
`pipeline_jobs` tool with `action="get"`).

### Cancelling a stuck task

Via MCP:
```json
{"name": "pipeline_jobs", "arguments": {"action": "cancel", "job_id": "abc-123", "confirm": true}}
```

Or for a YouTube render specifically:
```json
{"name": "youtube_video", "arguments": {"action": "cancel_render", "video_id": 42, "confirm": true, "confirm_id": 42}}
```

### Forcing a stuck task to clear (last resort)

```bash
# Revoke the Celery task directly
redis-cli -u "$REDIS_URL" PUBLISH celery revoke-task-id-here

# Or restart the worker
./pipeline_start.sh
```

If the job row is stuck in `producing` state, reset it in PostgreSQL:
```sql
UPDATE pipeline_jobs SET status = 'failed', error = 'manually reset' WHERE task_id = 'abc-123';
```

---

## Health monitoring

### Quick liveness

```bash
# Console backend (the dependency of all MCP transports)
curl -sf http://localhost:8080/api/system/health | python3 -m json.tool

# HTTP transport liveness (if running)
curl -sf http://127.0.0.1:8765/healthz
```

### Tool-level health check via stdio

```bash
# Returns full dependency status including LLM quota, Redis, Celery
MCP_API_TOKEN="<jwt>" python -m console.mcp.stdio <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"ops","version":"0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"system_health","arguments":{"action":"health"}}}
EOF
```

---

## Production deployment

Production runs on a Windows host with NVIDIA GTX 1660S. Deployment is automated
via `.github/workflows/deploy.yml` — pushes a `v*` tag (or `gh workflow run
deploy.yml`) to:

1. Build api/render/frontend images on `ubuntu-latest`, push to GHCR
2. On the self-hosted Windows runner: write `console/.env`, `pipeline.env`,
   `config/api_keys.json`, root `.env` from GitHub secrets/vars
3. Pull images, start postgres + redis, wait for postgres ready
4. Run `alembic upgrade head` in a one-off container
5. `docker compose up -d --remove-orphans` (api, celery-*, frontend, mcp-http)

The `mcp-http` service in `docker-compose.yml` reuses the api image (same
`Dockerfile.api` build) with a different `command:`, so it gets the new MCP code
on every deploy without a separate image to build.

### Required GitHub repo secrets

Set under **Settings → Secrets and variables → Actions** before the first deploy:

| Secret | Value |
|--------|-------|
| `DB_PASSWORD` | postgres password chosen for the prod DB |
| `JWT_SECRET` | random 32+ byte string — signs all JWTs |
| `FERNET_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `MCP_API_TOKEN` | output of `mint_token.py` run on the prod host (after first deploy seeds the `mcp-system` user). Long-lived 90-day JWT used by `mcp-http` to call the FastAPI backend. |
| `RUNWAY_API_KEY` | Runway API key |
| `GEMINI_SCRIPT_API_KEY`, `GEMINI_MEDIA_API_KEY` | Google AI keys |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID_EN`, `ELEVENLABS_VOICE_ID_VI` | ElevenLabs |
| `SUNO_API_KEY` | Suno music gen |
| `PEXELS_API_KEY` | Pexels stock |

The deploy workflow also writes these MCP env vars to `console/.env`:
- `MCP_AUDIT_ENABLED=1` — activates `DbAuditSink` so `mcp_tool_calls` rows are written
- `MCP_IDEMPOTENCY_ENABLED=1` — installs the Redis-backed store on `upload` + `youtube_video`
- `MCP_HTTP_USE_DB_KEYS=1` — `mcp-http` reads `mcp_api_keys` table (not env-only)

### First deploy sequence

```bash
# 1. Push a release tag (or run workflow_dispatch from the GitHub UI)
git tag v0.1.0
git push origin v0.1.0
# → workflow runs, builds images, deploys, runs migrations.
#   First run takes ~10-15 min. Subsequent rebuilds are faster (Docker layer cache).
```

After the workflow completes, **before the prod `mcp-http` is usable, you must do
two things on the prod host (one-time):**

```bash
# A. Mint MCP_API_TOKEN and add to GitHub secrets — required because the migration
#    seeds the mcp-system user, but mint_token can only run after the first deploy.
docker compose exec -T api python -m console.mcp.scripts.mint_token --days 90
# Copy the printed JWT, add it to GitHub secrets as MCP_API_TOKEN.
# Then re-run the deploy workflow so the new value lands in console/.env.

# B. Create at least one API key for an MCP HTTP client
docker compose exec api python -m console.mcp.scripts.manage_api_keys create --name first-agent
# Save the printed api_key — it's bcrypt-hashed at rest, never retrievable.
```

### Verify

```bash
# On the prod host — liveness
curl -s http://127.0.0.1:8765/healthz   # → {"status":"ok"}

# With the API key from step B
KEY="<the-saved-api-key>"
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8765/mcp/tools | jq '.tools | length'
# → 11

# Make a real tool call
curl -s -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8765/mcp/call \
  -d '{"name":"system_health","arguments":{"action":"health"}}' | jq

# Confirm the audit row was written
docker compose exec postgres psql -U admin ai_media -c \
  "SELECT tool_name, action, ok, transport, called_at FROM mcp_tool_calls ORDER BY called_at DESC LIMIT 1;"

# Confirm X-Mcp-Actor-Metadata propagated to the backend audit log
docker compose exec postgres psql -U admin ai_media -c \
  "SELECT actor_metadata FROM audit_log WHERE actor_metadata IS NOT NULL ORDER BY id DESC LIMIT 1;"
```

If both SQL rows come back populated, audit + idempotency + actor-metadata
propagation are all working end to end.

### Token rotation policy

- **Service-account JWT (`MCP_API_TOKEN`)** — 90-day lifetime. Re-mint and
  redeploy every 60 days to leave 30 days of overlap. Both old and new tokens
  remain valid until the redeploy lands the new value (zero-downtime rotation).
  Procedure:
  ```bash
  # On the prod host
  docker compose exec -T api python -m console.mcp.scripts.mint_token --days 90 > /tmp/mcp-token

  # Update the GitHub secret (requires `gh auth login` against the repo)
  gh secret set MCP_API_TOKEN --repo khiemle/ai-media-automation < /tmp/mcp-token

  # Trigger the deploy workflow — pushes new console/.env, restarts mcp-http
  gh workflow run deploy.yml --repo khiemle/ai-media-automation

  rm -f /tmp/mcp-token
  ```
  Optional: same JWT can be reused in your local `claude mcp add` if you
  also use Mac → prod stdio. See README "Connecting to a remote backend".

- **API keys (`mcp_api_keys`)** — no automatic expiry. Rotate when:
  - a key is suspected of leakage
  - a holder agent is decommissioned
  - on a yearly cadence as defense-in-depth
- **Revocation**: `manage_api_keys.py revoke --id <N>`.
  Effect is immediate — `DbApiKeyRegistry.lookup()` reads each request and
  filters `revoked_at IS NOT NULL`. No restart needed.

### Operational gotchas

- **Empty `mcp_api_keys` table → all 401s.** Fresh deploy with no API key
  rows rejects every HTTP request. The `manage_api_keys create` one-time step
  is mandatory.
- **`MCP_API_TOKEN` GitHub secret missing/blank.** Deploy succeeds, but every
  backend call from `mcp-http` returns 401 (empty bearer token). Symptom in
  `mcp_tool_calls`: rows accumulate with `error_code = 'auth.unauthorized'`.
  Fix: `gh secret set MCP_API_TOKEN < <(mint_token output)` then rerun deploy.
- **Activation flags missing.** If `MCP_AUDIT_ENABLED` or
  `MCP_IDEMPOTENCY_ENABLED` aren't `=1` in the prod `console/.env`, those
  features stay inert. Verify with
  `docker compose exec mcp-http env | grep MCP_`.
- **Reverse proxy / TLS.** The compose port mapping is
  `127.0.0.1:8765:8765` — only host-local. Expose to the LAN by changing the
  port mapping prefix (and adding firewall rules), or front it with nginx /
  Caddy + TLS. Don't expose without TLS — the API key travels in the
  `X-API-Key` header on plain HTTP otherwise.

### Disabling MCP in production

To turn the HTTP transport off without redeploying:
```bash
docker compose stop mcp-http
```

To turn the mounted sub-app off (more invasive — comments out the attach call
in `console/backend/main.py` and rebuilds the api image): see "Turning it off"
section below.

---

## Common errors and recovery

| Error code | Meaning | Most likely cause | First check | Fix |
|-----------|---------|-------------------|-------------|-----|
| `auth.unauthorized` | No valid credentials | Missing `MCP_API_TOKEN` (stdio), missing `X-API-Key` (HTTP), missing `Authorization` header (mounted) | Check env var / header | Set the appropriate credential |
| `auth.forbidden` | Credentials valid but insufficient role | The `mcp-system` user was created with the wrong role, or the forwarded user JWT is for a restricted role | `SELECT role FROM console_users WHERE username='mcp-system'` | Ensure role is `admin`; for chat transport, check the end-user's role |
| `auth.token_expired` | JWT past expiry | Token age > `JWT_EXPIRE_MINUTES` | Decode the JWT and check `exp` claim | Re-mint the token or extend `JWT_EXPIRE_MINUTES` |
| `not_found` | Resource doesn't exist | Wrong ID, or wrong `MCP_CONSOLE_API_BASE` | Verify ID exists in the console UI; check `MCP_CONSOLE_API_BASE` | Correct the ID or base URL |
| `conflict.invalid_status` | State machine violation | e.g. approving an already-approved item | Check current status via a `get` action first | Follow the correct status sequence |
| `conflict.task_already_running` | Duplicate job attempted | Previous task still running | `pipeline_jobs(action="list", status="running")` | Wait for the running task or cancel it first |
| `dependency.upstream_unavailable` | Console API returned 502/503/504 | Console backend down or overloaded | `curl http://localhost:8080/api/system/health` | Restart console backend; check Celery workers |
| `dependency.rate_limited` | Console API returned 429 | Gemini / ElevenLabs / external API quota hit | Check `system_health(action="llm_quota")` | Back off; quota is time-limited |
| `task.failed` | Celery task completed with error | Render failure, TTS failure, asset not found | `pipeline_jobs(action="get_logs", job_id="...")` | Inspect logs; fix underlying asset/config issue |
| `task.timeout` | Task exceeded timeout | Large render job, slow GPU, stuck worker | Check worker process; `ps aux | grep celery` | Restart worker; retry task |
| `console.api_error` | Unexpected HTTP error from console | Bug in backend, DB error | Check uvicorn logs | Inspect backend exception |
| `internal` | Unhandled exception in MCP layer | Bug in tool code | Check stdio stderr or HTTP process logs | Report bug with tool name + action |
| `validation.missing_confirm` | Write tool called without `confirm=true` | Expected — this is the two-step confirmation flow | None — this is normal behavior | Resend with `confirm=true` (and `confirm_id` for destructive actions) |
| `validation.confirm_id_mismatch` | `confirm_id` doesn't match the resource ID | Agent passed wrong ID in second call | Compare `confirm_id` value to the resource ID | Correct `confirm_id` to match the resource being acted on |

---

## Turning it off

**stdio:** Just don't run it. It's a subprocess started on demand; no persistent process
to stop.

**HTTP transport:** Send SIGTERM to the uvicorn process:
```bash
pkill -f "console.mcp.http"
```

**Mounted sub-app:** The routes are compiled into the main FastAPI app at import time.
To disable surgically without restarting the full backend:
```python
# In console/backend/main.py, comment out:
# from console.mcp.mount import attach as _attach_mcp
# _attach_mcp(app)
```
Then restart uvicorn. There is no runtime toggle.

---

## Adding a new tool

Assumes a new endpoint has been added to the console backend and you want to expose it
via MCP.

**1. Decide where it fits.**
- New action on an existing tool? Add a branch to that tool's `async def <tool>()` function.
- Wholly new domain? Create a new tool file.

**2. Create the tool file.**

Use `system_health.py` as the template for read-only tools; use `sfx.py` as the template
for tools that mix reads and writes. Minimum structure:

```python
# console/mcp/tools/my_tool.py
from typing import Any
from console.mcp.errors import ConsoleError

async def my_tool(*, action: str, _client: Any, **kw: Any) -> dict:
    """One-line description."""
    try:
        if action == "list":
            return {"ok": True, "data": await _client.get("/api/my-resource", params={})}
        # ... other actions
        return ConsoleError(
            code="validation.invalid_args",
            message=f"unknown action {action!r}",
            retryable=False,
            context={"action": action},
        ).to_envelope()
    except ConsoleError as e:
        return e.to_envelope()

def register(server, *, client_factory, audit_sink=None, transport="stdio", actor_jwt_sub=None):
    from console.mcp.audit import wrap_with_audit_log

    async def _core(**kw):
        client = client_factory()
        action = kw.get("action")
        rest = {k: v for k, v in kw.items() if k != "action"}
        return await my_tool(action=action, _client=client, **rest)

    _audit_wrapped = None
    if audit_sink is not None:
        _audit_wrapped = wrap_with_audit_log(
            _core, tool_name="my_tool",
            sink=audit_sink, transport=transport, actor_jwt_sub=actor_jwt_sub,
        )

    @server.tool(name="my_tool")
    async def _my_tool(action: str, ...) -> dict:
        kw = {k: v for k, v in locals().items() if v is not None}
        if _audit_wrapped is not None:
            return await _audit_wrapped(**kw)
        act = kw.pop("action", action)
        return await my_tool(action=act, _client=client_factory(), **kw)
```

**3. Add a test file.**
```
console/mcp/tests/tools/test_my_tool.py
```
Mirror the structure of `test_sfx.py` or `test_system_health.py`.

**4. Wire into all three transport entrypoints.**

> **FOLLOWUPS gap (see FOLLOWUPS.md — "Tool dispatch duplicated"):** Until the if/elif
> ladders are extracted into a shared `TOOL_DISPATCH` table, you must update three files:

```python
# In console/mcp/stdio.py — add to both the import and the register list:
from console.mcp.tools import my_tool
lambda s: my_tool.register(s, client_factory=client_factory),

# In console/mcp/http.py — add to build_server register list AND the if/elif ladder:
elif tool_name == "my_tool":
    return await my_tool.my_tool(_client=client, **args)

# In console/mcp/mount.py — add to the /mcp/tools response list AND the if/elif ladder:
{"name": "my_tool", "description": "..."},
# and:
elif tool_name == "my_tool":
    return await my_tool.my_tool(_client=client, **args)
```

**5. Run tests.**
```bash
pytest console/mcp/tests/ -m "not manual" -v
```
All tests must stay green before merging.

**6. Update the README.**
- Add a row to the Tools table in `console/mcp/README.md`.
- Add the new tool name to the expected list in `console/mcp/tests/e2e/test_smoke.py`:
  ```python
  assert names == sorted([
      ...,
      "my_tool",
  ])
  ```

---

## Rollback

### Disable (no schema change)

1. Comment out the mount in `console/backend/main.py`:
   ```python
   # from console.mcp.mount import attach as _attach_mcp
   # _attach_mcp(app)
   ```
2. Stop the HTTP transport process if running: `pkill -f "console.mcp.http"`
3. Restart uvicorn: `./console/start.sh`

The stdio transport has no persistent process; no action needed.

### Schema rollback

To remove the MCP tables entirely:
```bash
cd console/backend
alembic downgrade -1
```

This drops `mcp_api_keys`, `mcp_tool_calls`, removes `audit_log.actor_metadata`, and
deletes the `mcp-system` console user.

**Before running:** confirm no other migration in the chain depends on revision
`d885cdd6570e`. Check with:
```bash
cd console/backend && alembic history | grep -A2 d885cdd6570e
```
The `down_revision` for any newer migration must not be `d885cdd6570e` for a clean
`downgrade -1`.

After downgrading, restart uvicorn so the MCP import in `main.py` fails gracefully (or
comment it out first to avoid an import error on startup).
