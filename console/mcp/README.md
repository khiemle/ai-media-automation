# console-mcp

MCP server exposing AI Media Console video-creation workflows to LLM agents
(Claude Code, Claude Agent SDK, scheduled cron, in-product chat).

11 tools, 3 transports, schema-correct against the actual backend, multipart
uploads supported. Deploys via the same GitHub Actions workflow that ships
the api / render / frontend images.

---

## Tools

| Tool | Purpose |
|------|---------|
| `youtube_video` | full /youtube page flow — create, configure, render gates, upload |
| `youtube_thumbnail` | upload source image / AI generate with text overlay / fetch |
| `music` | list/get/CRUD tracks + ElevenLabs plan→compose |
| `sfx` | list / generate / import / delete |
| `visual_asset` | CRUD + Runway animate + Topaz upscale |
| `channel_plan` | CRUD + JSON/MD import + AI helpers (SEO / prompts / autofill / ask) |
| `channel` | CRUD + template defaults + credential status (read-only on secrets) |
| `upload` | list videos / set channel targets / upload one / upload all |
| `task_status` | poll any `task_id` returned by an async-kicking tool |
| `pipeline_jobs` | list / get / retry / cancel / get_logs / stats |
| `system_health` | health / cron / errors / llm quota / performance summary |

Spec: `docs/superpowers/specs/2026-05-09-mcp-server-design.md`.
Operational runbook: [`RUNBOOK.md`](RUNBOOK.md).
Known limitations + follow-ups: [`FOLLOWUPS.md`](FOLLOWUPS.md).

---

## Quickstart — local Claude Code (stdio)

Recommended path: use the launcher script.

```bash
cd /path/to/ai-media-automation
./console/mcp/scripts/mcp-dev.sh
```

It runs four pre-flight checks (Postgres / Redis / console FastAPI / migration),
mints a 90-day `mcp-system` JWT, and prints a ready-to-paste Claude Code
config. Restart Claude Code to pick up the change.

To use `claude` CLI directly instead of editing JSON:

```bash
claude mcp add ai-media-console \
  --transport stdio \
  --env MCP_API_TOKEN="<jwt-from-mint_token>" \
  --env MCP_CONSOLE_API_BASE=http://localhost:8080 \
  -- python -m console.mcp.stdio

claude mcp list   # confirm registration
```

The JWT comes from:

```bash
python -m console.mcp.scripts.mint_token --days 90
```

---

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

---

## Connecting to a remote backend

Run MCP locally on your Mac but route every tool call to a remote FastAPI
(e.g. the production host on the LAN). Add a second registration alongside
your local one:

```bash
# Mint a JWT signed with the REMOTE host's JWT_SECRET — must run there:
ssh user@192.168.68.119 \
  'cd /path/to/ai-media-automation && \
   docker compose exec -T api python -m console.mcp.scripts.mint_token --days 90'

# Then on your Mac:
claude mcp add ai-media-console-prod \
  --transport stdio \
  --env MCP_API_TOKEN="<paste-the-remote-jwt>" \
  --env MCP_CONSOLE_API_BASE=http://192.168.68.119:8080 \
  -- python -m console.mcp.stdio
```

You can keep `ai-media-console` (local backend) and `ai-media-console-prod`
(remote) registered side by side. Tell Claude which one to use by name.

> **Note:** the HTTP/SSE transport built into `console.mcp.http` is currently
> a placeholder REST API, **not** real MCP-over-SSE. Until it's rewritten to
> use FastMCP's SSE server, do remote MCP via the local-stdio + remote-backend
> pattern above. Tracked in [`FOLLOWUPS.md`](FOLLOWUPS.md).

---

## Transports

| Transport | Entrypoint | Use case |
|-----------|-----------|----------|
| **stdio** | `python -m console.mcp.stdio` | Claude Code, Claude Agent SDK, anything that spawns the server as a child process |
| **HTTP/SSE** | `python -m console.mcp.http` | Cron jobs, scheduled routines, remote chat surfaces. Currently exposes a stub REST API at `/healthz`, `/mcp/tools`, `/mcp/call` — proper MCP-over-SSE is a follow-up. |
| **Mounted sub-app** | auto-attached to `console.backend.main` at `/mcp/*` | The console's editor chat surface forwards the user's existing JWT |

---

## Production deployment

Production runs on a Windows host with NVIDIA GTX 1660S, GHCR-published
images, deployed via `.github/workflows/deploy.yml` on every `v*` tag (or
manual workflow dispatch).

```
git tag v0.2.0 && git push origin v0.2.0
# → workflow builds api/render/frontend images, pushes to GHCR,
#   then runs on the self-hosted Windows runner to:
#   1. write console/.env, pipeline.env, config/api_keys.json from secrets
#   2. docker compose pull
#   3. start postgres + redis, wait for postgres ready
#   4. run alembic migrations (one-off container)
#   5. docker compose up -d --remove-orphans (api, celery-*, frontend, mcp-http)
```

The `mcp-http` service in `docker-compose.yml` reuses the api image with a
different command (`python -m console.mcp.http`), so it gets the same code
the api gets — no separate image to build.

### One-time GitHub secrets

Before the first deploy, add these repo secrets (Settings → Secrets and
variables → Actions):

| Secret | Source |
|--------|--------|
| `DB_PASSWORD` | postgres password chosen for the prod DB |
| `JWT_SECRET` | random 32-byte string, used to sign all JWTs |
| `FERNET_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `MCP_API_TOKEN` | output of `mint_token.py` run on the prod host (after first deploy seeds the `mcp-system` user). Long-lived 90-day JWT used by `mcp-http` to call the FastAPI backend. Rotate every ~60 days. |
| `RUNWAY_API_KEY`, `GEMINI_*_API_KEY`, `ELEVENLABS_API_KEY`, `SUNO_API_KEY`, `PEXELS_API_KEY` | API keys for external services (see `deploy.yml` for the full list) |

Without `MCP_API_TOKEN` set: deploy succeeds but every backend call from
`mcp-http` returns 401 from FastAPI (empty bearer token).

### One-time prod setup (after first deploy completes)

```bash
# On the prod host, after the first successful deploy
docker compose exec api python -m console.mcp.scripts.manage_api_keys \
  create --name first-agent
# Save the printed api_key — it's bcrypt-hashed at rest, never retrievable
```

The `mcp_api_keys` table starts empty. Every request to the HTTP transport's
`/mcp/call` returns 401 until at least one key exists.

See [`RUNBOOK.md`](RUNBOOK.md) for the full ops guide (token rotation,
disabling, troubleshooting, schema rollback).

---

## Operational features

### Audit logging — `mcp_tool_calls`

Every tool call writes a row to `mcp_tool_calls` with `{tool_name, action,
args_redacted, ok, error_code, duration_ms, task_id, transport,
actor_jwt_sub, called_at}`. Args matching `*_token`, `*_key`, `password` are
replaced with `***` before persistence.

Activation: set `MCP_AUDIT_ENABLED=1` in the transport's env. Default off
(no rows written). The deploy workflow sets it for the prod `mcp-http`
service automatically.

Querying:
```sql
SELECT tool_name, action, ok, transport, error_code, duration_ms, called_at
FROM mcp_tool_calls
ORDER BY called_at DESC LIMIT 20;
```

### Idempotency — `MCP_IDEMPOTENCY_ENABLED`

Three actions accept an optional `idempotency_key` argument:

- `upload(action="upload_one", ...)` — same key + 24h TTL → no second YouTube upload
- `upload(action="upload_all", ...)` — same as above for batch upload
- `youtube_video(action="render_final", ...)` — same key → no duplicate render

Activation: set `MCP_IDEMPOTENCY_ENABLED=1`. Default off (key arg silently
ignored). The deploy workflow sets it for prod automatically. Backed by
Redis at `REDIS_URL`. TTL controlled by `MCP_IDEMPOTENCY_TTL_S` (default
86400 = 24h).

### Backend audit trail — `audit_log.actor_metadata`

The console's existing audit middleware writes a row to `audit_log` for
every write operation by an authenticated user. When the request originates
from the MCP server, `audit_log.actor_metadata` is populated from the
`X-Mcp-Actor-Metadata` header that `ConsoleClient` attaches automatically:

```jsonc
// Example actor_metadata for an stdio caller:
{ "transport": "stdio", "host": "developer-mac.local" }

// Example for an HTTP caller:
{ "transport": "http", "api_key_name": "cron-bot" }

// Example for a chat-surface caller:
{ "transport": "chat", "via": "mcp" }
```

This lets you distinguish MCP-mediated changes from direct console UI
changes, and (for HTTP traffic) which API key was used.

---

## Confirmation pattern

Every **write** tool requires `confirm=true`. **Destructive** tools
additionally require `confirm_id` to match the resource ID.

```jsonc
// First call — agent gets the intent, no side effect
{"name": "youtube_video", "arguments": {"action": "delete", "video_id": 9}}
// → {"ok": false, "needs_confirmation": true, "intent": {...}, "to_proceed": "..."}

// Second call — agent confirms with the matching id
{"name": "youtube_video", "arguments":
  {"action": "delete", "video_id": 9, "confirm": true, "confirm_id": 9}}
// → {"ok": true, "data": {...}}
```

This is the agent-side analog of "are you sure?" dialogs in the UI. It
costs an extra round-trip but prevents an LLM from issuing a destructive
call by accident.

For non-destructive writes (`create`, `update`, `approve`), only
`confirm=true` is needed; `confirm_id` is reserved for `delete`,
`upload_one` / `upload_all`, `disconnect`, `reject_*`, `cancel_render`.

Async-kicking tools return a task envelope that the agent polls:

```jsonc
{"ok": true, "task_id": "abc-1", "status_tool": "task_status",
 "task_kind": "youtube_render_final", "poll_hint": "every 10s, ~5min"}
```

Agent then calls `task_status(task_id="abc-1")` until `status` is
`SUCCESS` or `FAILURE`.

---

## API key management (HTTP transport)

```bash
# Create a key (run on the prod host where the DB is reachable)
docker compose exec api python -m console.mcp.scripts.manage_api_keys \
  create --name cron-uploader

# List existing keys
docker compose exec api python -m console.mcp.scripts.manage_api_keys list

# Revoke a key (immediate effect — DbApiKeyRegistry checks revoked_at on every lookup)
docker compose exec api python -m console.mcp.scripts.manage_api_keys revoke --id 3
```

Keys are bcrypt-hashed; the plaintext is only printed at create time and is
not retrievable later. If a key is lost, revoke it and create a new one.

---

## Skills (Claude Code)

Two project-level skills wrap MCP usage:

- **`make-youtube-video`** (`.claude/skills/make-youtube-video/SKILL.md`) —
  end-to-end "make a video from JSON templates" workflow. Reads
  `*music.json` / `*visual.json` / `*seo.json` from `working/<slug>/json/`,
  uploads visual + thumbnail, generates music + SFX, runs the render gates,
  uploads to YouTube. Use when you say "make a youtube video for working/foo".
- **`visual-video`** (`skills/visual-video/SKILL.md`) — generates the three
  JSON template files (no MCP calls). Stops after file save and asks whether
  to chain into `make-youtube-video`.

The two compose: `visual-video` → JSON files saved → user confirms →
`make-youtube-video` reads them and runs the pipeline.

---

## Tests

```bash
pytest console/mcp/tests/ -v -m "not manual"
```

Current count: **125 tests** (114 baseline + activation/audit/middleware).
Tests use respx to mock the FastAPI backend; no live DB required for the
unit and tool-level tests. The integration test (`test_full_video_flow.py`)
exercises all 11 tools in agent order against a respx-mocked backend.

The smoke test (`tests/e2e/test_smoke.py`) is `@pytest.mark.manual` — it
spawns the stdio server as a subprocess and asserts the full 11-tool
catalog. Run on demand:

```bash
pytest console/mcp/tests/e2e/test_smoke.py -v -m manual
```

---

## Source layout

```
console/mcp/
├── README.md                          ← you are here
├── RUNBOOK.md                         ← ops runbook (deploy, rotate, troubleshoot)
├── FOLLOWUPS.md                       ← deferred work
├── server.py                          ← FastMCP factory
├── stdio.py                           ← stdio entrypoint
├── http.py                            ← HTTP entrypoint (stub REST, not real MCP/SSE yet)
├── mount.py                           ← attach() → mounts /mcp/* on console.backend.main
├── activation.py                      ← env-gated audit + idempotency wiring
├── errors.py                          ← ConsoleError + HTTP→error-code map
├── redact.py                          ← strip *_token, *_key, password
├── audit.py                           ← wrap_with_audit_log middleware
├── audit_db.py                        ← DbAuditSink (writes to mcp_tool_calls)
├── idempotency.py                     ← Redis-backed IdempotencyStore
├── auth/
│   ├── adapters.py                    ← StdioAuth, HttpAuth, ChatAuth
│   └── tokens.py                      ← InMemoryApiKeyRegistry, DbApiKeyRegistry, ApiKeyEntry
├── client/
│   └── console_client.py              ← httpx wrapper, attaches X-Mcp-Actor-Metadata
├── tools/
│   ├── _common.py                     ← decorators (@requires_confirm, @destructive, @returns_task)
│   ├── _multipart.py                  ← open_for_upload helper
│   ├── system_health.py
│   ├── task_status.py
│   ├── pipeline_jobs.py
│   ├── music.py                       ← also hosts shared _confirmed_* helpers (see FOLLOWUPS)
│   ├── sfx.py
│   ├── visual_asset.py
│   ├── channel_plan.py
│   ├── channel.py
│   ├── youtube_video.py
│   ├── youtube_thumbnail.py
│   └── upload.py
├── scripts/
│   ├── mcp-dev.sh                     ← local-dev launcher (prereq checks + JWT mint)
│   ├── mint_token.py                  ← mint a long-lived JWT for mcp-system
│   └── manage_api_keys.py             ← CLI for mcp_api_keys table (create/list/revoke)
├── prompts/
│   └── MAKE_YOUTUBE_VIDEO.md          ← end-to-end agent prompt (used by make-youtube-video skill)
└── tests/                             ← unit / integration / e2e tests
```
