# AI Media Console — MCP Server Design

**Date:** 2026-05-09
**Status:** Design (pre-implementation)
**Author:** Brainstorming session, khiemlq

---

## 1. Purpose

Expose the AI Media Console's video-creation capabilities to LLM agents over the
Model Context Protocol so that:

1. **Claude Code (local dev)** can drive the console end-to-end from the
   terminal during development.
2. **Scheduled / remote agents** (cron jobs, Claude Agent SDK routines) can run
   nightly automation: import → fill → render → publish.
3. **An end-user editor chat surface** can let the business user manage videos
   conversationally — using the same tool layer that the other transports use.

A single MCP server, three transports, one tool catalog.

---

## 2. Scope

### In scope (11 tools)

| # | Tool | Surface | R/W |
|---|------|---------|-----|
| 1 | `youtube_video` | full /youtube page flow + JSON import | R + W |
| 2 | `youtube_thumbnail` | upload image / AI generate / fetch | R + W |
| 3 | `music` | full CRUD + ElevenLabs generate | R + W |
| 4 | `sfx` | list / get / generate / import / delete | R + W |
| 5 | `visual_asset` | full CRUD + animate (Runway) + upscale (Topaz) | R + W |
| 6 | `channel_plan` | CRUD + import_json + AI helpers (seo/prompts/autofill/ask) | R + W |
| 7 | `channel` | CRUD + defaults + credential status (read-only on secrets) | R + W |
| 8 | `upload` | list / set targets / upload one / upload all | R + W |
| 9 | `task_status` | poll any `task_id` | R |
| 10 | `pipeline_jobs` | list / get / retry / cancel / get_logs / stats | R + W |
| 11 | `system_health` | health / cron / errors / llm_quota / performance summary | R |

### Explicitly out of scope (deferred)

- Scraper sources / scrape runs / scraped content browsing
- Legacy `scripts` workflow (list/generate/approve/regenerate)
- Legacy `production` workflow (assets-and-scenes editor for the script-driven
  pipeline)
- Niche CRUD
- Vector DB direct search

These can be added later; their endpoints exist on the API but are not part of
the MCP surface for this iteration.

---

## 3. Architecture

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  Claude Code (dev)  │  │  Cron / Routine     │  │  Editor chat UI     │
│  stdio transport    │  │  HTTP/SSE transport │  │  in-process sub-app │
└──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │  MCP protocol
                                    ▼
                       ┌────────────────────────────┐
                       │  console-mcp (Python)      │
                       │  • mcp.server.fastmcp      │
                       │  • Tool catalog (11)       │
                       │  • AuthAdapter per         │
                       │    transport               │
                       │  • ConsoleClient (httpx)   │
                       └────────────┬───────────────┘
                                    │  HTTP + Bearer JWT
                                    ▼
                       ┌────────────────────────────┐
                       │  Existing FastAPI :8080    │
                       │  /api/*  (unchanged)       │
                       └────────────────────────────┘
```

### Key decisions

- **One Python package: `console/mcp/`.** Tool functions defined once.
- **Three entrypoints, one server builder:** `python -m console.mcp.stdio`,
  `python -m console.mcp.http`, and `console.mcp.mount.attach(app)` for the
  sub-app variant.
- **No new business logic in the MCP layer.** Tools are dispatchers that call
  existing FastAPI endpoints via `httpx.AsyncClient`. Audit log, rate limiting,
  role checks all stay in FastAPI where they already work.
- **Service-account user:** seed a `mcp-system` ConsoleUser (role `admin`) used
  as fallback `edited_by` when no upstream user identity is available.
- **One additive schema change:** new `audit_log.actor_metadata` JSONB column
  to record `{transport, api_key_name, host}` alongside the existing
  `edited_by → console_users` FK. No churn of existing data.

---

## 4. Components

### 4.1 Package layout

```
console/mcp/
├── __init__.py
├── server.py              # build_server() returns FastMCP with all tools registered
├── stdio.py               # entrypoint for stdio transport
├── http.py                # entrypoint for standalone HTTP/SSE transport
├── mount.py               # helper to mount onto existing FastAPI at /mcp
│
├── auth/
│   ├── adapters.py        # StdioAuth · HttpAuth · ChatAuth
│   └── tokens.py          # service-account JWT mint/refresh, API-key registry
│
├── client/
│   └── console_client.py  # httpx wrapper, base http://localhost:8080,
│                          # attaches Bearer token, 401 refresh, raises ConsoleError
│
├── tools/
│   ├── __init__.py        # register_all(server)
│   ├── _common.py         # @requires_confirm, @destructive, @returns_task,
│   │                      # error mapping, args_redacted
│   ├── youtube_video.py
│   ├── youtube_thumbnail.py
│   ├── music.py
│   ├── sfx.py
│   ├── visual_asset.py
│   ├── channel_plan.py
│   ├── channel.py
│   ├── upload.py
│   ├── task_status.py
│   ├── pipeline_jobs.py
│   └── system_health.py
│
└── tests/
    ├── conftest.py
    ├── test_decorators.py
    ├── test_error_mapping.py
    ├── test_auth.py
    ├── tools/
    │   └── test_<tool>.py
    ├── integration/
    │   └── test_<flow>.py
    └── e2e/
        ├── test_stdio.py
        ├── test_http.py
        └── test_mount.py
```

### 4.2 Tool action enums

Each action-dispatched tool exposes a single MCP tool with an `action: str`
arg whose enum is documented in the tool description. Example for
`youtube_video`:

```
action ∈ {
  list, get, create, update, delete,
  import_json, list_templates, get_template,
  render_audio_preview, approve_audio_preview, reject_audio_preview,
  render_video_preview, approve_video_preview, reject_video_preview,
  render_final, cancel_render, resume_render, get_render_state
}
```

The full action enums for all 11 tools are listed in §2 above.

### 4.3 Decorators (the safety layer)

- **`@requires_confirm`** — write tools require `confirm: bool`. When
  `confirm=false` (default), the tool returns a `needs_confirmation` envelope
  with a human-readable summary; the agent must call again with `confirm=true`.
- **`@destructive`** — adds `confirm_id` requirement: caller must repeat the
  resource ID. Applied to `delete`, `upload_one`/`upload_all`, `disconnect`,
  `reject_*`. Mismatch → `validation.confirm_id_mismatch`.
- **`@returns_task`** — wraps async-kicking tool responses into the standard
  `{ok, task_id, status_tool, poll_hint, task_kind}` envelope.

### 4.4 ConsoleClient

`httpx.AsyncClient` wrapper. Responsibilities:

- Attach `Authorization: Bearer <jwt>` from the request-scoped AuthAdapter.
- Detect 401 → ask AuthAdapter to refresh, retry once.
- Forward `actor_metadata` to FastAPI via a custom header
  `X-Mcp-Actor-Metadata: <json>` so the audit hook can persist it.
- Map HTTP status → `ConsoleError(code, message, retryable, context)`.

### 4.5 Auth adapters

| Transport | Token source | Maps to | audit_log.actor_metadata |
|-----------|--------------|---------|--------------------------|
| stdio | env `MCP_API_TOKEN` | long-lived JWT for `mcp-system` user | `{transport: "stdio", host: <hostname>}` |
| HTTP/SSE | header `X-API-Key` | registry → service-account JWT (one of: `cron-bot`, `editor-chat`, etc.) | `{transport: "http", api_key_name: "<name>"}` |
| Chat sub-app | forwarded end-user JWT (Authorization: Bearer) | the user's own JWT | `{transport: "chat", via: "mcp"}` (real user in `edited_by`) |

API key registry lives in a new `mcp_api_keys` table:
`id, name, key_hash, scopes (text[]), service_user_id (FK), created_at, last_used_at, revoked_at`.

---

## 5. Data flow

### 5.1 Read tool (e.g. `music action=list_tracks`)

```
Agent → MCP transport → FastMCP dispatch → music_tool(action=list_tracks)
       → ConsoleClient.get("/api/music", headers={Authorization: Bearer ...})
       → FastAPI → MusicService → DB
       → tool returns {ok: true, data: [...], meta: {count: N, page: 1}}
```

### 5.2 Write tool with confirmation (e.g. `youtube_video action=delete`)

**Call 1** (no confirm):
```
youtube_video(action=delete, video_id=123)
→ {
    ok: false,
    needs_confirmation: true,
    intent: {
      tool: "youtube_video", action: "delete", video_id: 123,
      summary: "Permanently delete YouTube video #123 'Forest ASMR 8h'.
                Removes DB row + render artifacts + upload history."
    },
    to_proceed: "call again with confirm=true and confirm_id=123"
  }
```

**Call 2** (confirmed):
```
youtube_video(action=delete, video_id=123, confirm=true, confirm_id=123)
→ ConsoleClient.delete("/api/youtube-videos/123")
→ {ok: true, data: {deleted: true, video_id: 123}}
```

For non-destructive writes (create, update, approve), only `confirm=true` is
required; `confirm_id` applies only to destructive actions.

### 5.3 Async-kicking tool (e.g. `youtube_video action=render_final`)

```
youtube_video(action=render_final, video_id=123, confirm=true)
→ ConsoleClient.post("/api/youtube-videos/123/render/final")
→ FastAPI returns 202 with {task_id: "abc-123"}
→ tool returns:
  {
    ok: true,
    task_id: "abc-123",
    status_tool: "task_status",
    poll_hint: "poll every 10s, typical render = 4-8 min",
    task_kind: "youtube_render_final"
  }
```

Agent polls:
```
task_status(task_id="abc-123")
→ {
    ok: true,
    status: "PROGRESS",   // PENDING | PROGRESS | SUCCESS | FAILURE | REVOKED
    progress: {percent: 42, stage: "compositing scenes 6/12"},
    result: null,
    error: null,
    started_at: "...",
    elapsed_s: 87
  }
```

On SUCCESS:
```
{
  ok: true,
  status: "SUCCESS",
  result: {
    output_path: "/renders/.../final.mp4",
    duration_s: 28800,
    file_size_mb: 1240,
    stream_url: "/api/youtube-videos/123/stream"
  },
  elapsed_s: 312
}
```

`task_status` reads from Celery's `AsyncResult` plus per-domain task tables
(e.g. `pipeline_jobs`, `music.tasks`) to surface progress data the tool layer
recorded.

### 5.4 The full "make a video" agent flow

```
1. Import / pick template
   → channel_plan(action=import_json)         # channel-level plan
   → youtube_video(action=import_json)        # per-video JSON spec
   → youtube_video(action=list_templates)     # browse pre-built templates

2. Configure video
   → youtube_video(action=create | update)    # title, theme, target_duration_h,
                                              # output_quality, seo_*, sfx_overrides,
                                              # sfx_density_seconds, visual_clip_durations_s
   → channel_plan(action=ai_seo | ai_autofill) # AI-fill SEO / descriptions

3. Music
   → music(action=list_tracks)
   → music(action=generate | elevenlabs_compose)  # returns task_id
   → task_status(task_id) until SUCCESS
   → youtube_video(action=update, music_track_id=...)

4. SFX
   → sfx(action=list)
   → sfx(action=generate)                      # returns task_id
   → youtube_video(action=update, sfx_overrides={...})

5. Visual asset (background image/video)
   → visual_asset(action=list)
   → visual_asset(action=upload | animate | upscale)
   → youtube_video(action=update, visual_asset_id=...)

6. Thumbnail
   → youtube_thumbnail(action=upload_image)
   → youtube_thumbnail(action=generate_with_text, text="...", style="...")

7. Render gates
   → youtube_video(action=render_audio_preview)  → task_status → audio URL
   → youtube_video(action=approve_audio_preview)
   → youtube_video(action=render_video_preview)  → task_status → video URL
   → youtube_video(action=approve_video_preview)
   → youtube_video(action=render_final)          → task_status

8. Upload
   → upload(action=set_targets, channels=[...])
   → upload(action=upload_one | upload_all)      → task_status
```

### 5.5 Identity flow

```
                     stdio                       HTTP/SSE                       chat sub-app
                  ───────────────              ──────────────────              ──────────────────
Token source:     env MCP_API_TOKEN            request hdr X-API-Key           end-user JWT (cookie)
                                               → registry lookup               forwarded as-is
                                               → service-account JWT
Bearer used:      long-lived JWT for           mapped service-account JWT      end-user's own JWT
                  `mcp-system` user                                            (full attribution)
audit_log:        edited_by = mcp-system       edited_by = mcp-system          edited_by = real user
                  actor_metadata =             actor_metadata =                actor_metadata =
                  {transport, host}            {transport, api_key_name}       {transport, via}
```

---

## 6. Error handling

### 6.1 Uniform envelope

Every tool returns one of two shapes. No raised exceptions for business errors.

**Success:** `{ok: true, data: ..., meta?: ...}` (read) or `{ok: true, ...}`
(write) or `{ok: true, task_id, status_tool, ...}` (async).

**Failure:**
```json
{
  "ok": false,
  "error": {
    "code": "...",
    "message": "...",
    "retryable": true,
    "context": { "video_id": 123, "field": "target_duration_h" }
  }
}
```

### 6.2 Error codes

| Code | When | Retryable | Source |
|------|------|-----------|--------|
| `auth.unauthorized` | Missing/invalid token | no | MCP auth adapter |
| `auth.forbidden` | Token lacks role | no | FastAPI 403 |
| `auth.token_expired` | JWT expired, refresh failed | no | ConsoleClient |
| `validation.invalid_args` | Pydantic/MCP arg validation | no | FastMCP |
| `validation.missing_confirm` | Write tool without `confirm=true` | no | `@requires_confirm` |
| `validation.confirm_id_mismatch` | Destructive op with wrong `confirm_id` | no | `@destructive` |
| `not_found` | Resource doesn't exist | no | FastAPI 404 |
| `conflict.invalid_status` | e.g. approving an already-rendered video | no | service 409 |
| `conflict.task_already_running` | Render kicked off twice | no | service 409 |
| `dependency.upstream_unavailable` | Ollama/Gemini/Runway/Topaz down | yes | router 502/503 |
| `dependency.rate_limited` | LLM quota / YouTube quota hit | yes (backoff) | router 429 |
| `task.failed` | Polled task FAILURE | depends | task_status |
| `task.timeout` | Polled task exceeded max_wait | depends | task_status |
| `console.api_error` | FastAPI returned 5xx | yes | ConsoleClient |
| `internal` | Unhandled exception in MCP layer | no | catch-all |

### 6.3 Mapping rules

- HTTP `4xx` from FastAPI → tool returns `ok: false` with matching code; **not**
  raised as MCP-level error.
- HTTP `5xx` → `ok: false` with `retryable: true`.
- Only true MCP-protocol errors (transport-level failures, malformed args
  before tool body runs) propagate as exceptions.

### 6.4 Idempotency

`delete`, `upload_one`/`upload_all`, `render_final` accept an optional
`idempotency_key: str` arg. Same key reused within 24h → prior result
returned, no new operation. Backed by Redis: key → `{task_id, completed_at,
result}`. Lets cron jobs retry on network blips without double-uploading.

### 6.5 Logging

New `mcp_tool_calls` table:
```
id, called_at, transport, actor_jwt_sub, tool_name, action,
args_redacted, ok, error_code, duration_ms, task_id
```

`args_redacted` strips fields matching `*_token`, `*_key`, `password`. Read
tools log at debug; writes log at info.

---

## 7. Testing

### 7.1 Pyramid (~80 tests)

```
              E2E (3-5 tests) — stdio + HTTP + mount, real MCP client → server → FastAPI
              ────────────────────────────────────────────────────────────────────
              Tool integration (~25) — in-process FastMCP + httpx ASGITransport →
              real FastAPI test app + Postgres test DB
              ────────────────────────────────────────────────────────────────────
              Tool unit (~40) + Auth (~10) — mocked ConsoleClient → tool dispatch
              ────────────────────────────────────────────────────────────────────
              Decorator/utils (~10) — @requires_confirm, @destructive,
              @returns_task, error mapping, redaction
```

### 7.2 Layer details

**Decorator/utils tests:**
- `@requires_confirm` returns `needs_confirmation` envelope when `confirm=false`
- `@destructive` rejects `confirm=true` if `confirm_id` doesn't match
- `@returns_task` shape correct
- HTTP 4xx/5xx → correct error code + `retryable` flag
- `args_redacted` strips `*_token`, `*_key`, `password`

**Tool unit tests** (one file per tool, one test per action): assert correct
endpoint, method, payload, result envelope. Confirmation flow per write action.
Uses `FakeConsoleClient` returning canned responses.

**Auth tests:** StdioAuth (env), HttpAuth (registry), ChatAuth (forwarded).
Each writes correct `actor_metadata`.

**Integration tests** — golden flows:
- **Full youtube_video creation flow** end-to-end: import_json → update SEO
  → set music/sfx/visual → generate thumbnail → render_audio_preview →
  approve → render_video_preview → approve → render_final → upload.
  `task_always_eager=True` so Celery runs inline. Heavy work mocked at
  `pipeline.*` boundary.
- **Confirmation gate**: delete attempt without confirm → with wrong
  `confirm_id` → success.
- **Audit trail**: write tool runs, `audit_log` row exists with correct
  `actor_metadata`.
- **Idempotency**: `render_final` with same `idempotency_key` twice → same
  `task_id`.

**E2E tests:**
- **stdio**: spawn `python -m console.mcp.stdio` as subprocess, send MCP
  `initialize` + `tools/list` + a `tools/call` for `system_health`.
- **HTTP**: launch HTTP server on random port, hit `/sse` + call read tool
  with valid API key.
- **Mounted sub-app**: FastAPI with sub-app mounted, call MCP via `/mcp` with
  forwarded user JWT, verify `actor_metadata.transport == "chat"` lands in
  audit log.
- **Smoke** (manual, not in CI): `python -m console.mcp.stdio | jq` lists
  tools and calls `youtube_video action=list`.

### 7.3 Fixtures (`tests/conftest.py`)

- `console_users`: pre-seeded `mcp-system` (admin), `editor-test` (editor)
- `youtube_videos`: 3 fixtures — draft, audio-approved, fully-rendered
- `music_tracks`, `sfx_assets`, `video_assets`: a few of each
- `channel_plans`: one imported, one ready for AI autofill
- session scope for read-only, function scope for write-touched

### 7.4 External-service mocking

- LLM router: `unittest.mock.patch` on `LLMRouter.generate` → canned JSON
- ElevenLabs, Runway, Topaz, Pexels, Veo: `respx` at the `httpx` boundary
- YouTube Data API v3 upload: `respx` returns fake upload response
- Celery: `task_always_eager=True` + service-level mocks for heaviest ops

### 7.5 CI gates

- Decorator + tool unit + auth: every PR (~5s)
- Integration: every PR (~30–60s with eager Celery)
- E2E stdio + HTTP + mount: every PR (~20s)
- Smoke: tagged `@manual`, run before release

**Coverage target:** 90%+ for `console/mcp/`; 100% on decorators (they are the
safety mechanism for write ops).

---

## 8. Schema changes

Single Alembic migration:

1. **`audit_log.actor_metadata`** — new JSONB column, nullable. Records
   `{transport, api_key_name?, host?, via?}`.

2. **`mcp_api_keys`** — new table for HTTP transport API-key registry:
   ```
   id (pk)
   name (text, unique)
   key_hash (text)              -- bcrypt
   scopes (text[])              -- which tools/actions allowed; empty = all
   service_user_id (fk → console_users)
   created_at (timestamptz)
   last_used_at (timestamptz, nullable)
   revoked_at (timestamptz, nullable)
   ```

3. **`mcp_tool_calls`** — new table for MCP-side audit:
   ```
   id (pk)
   called_at (timestamptz)
   transport (text)             -- stdio | http | chat
   actor_jwt_sub (text)         -- subject claim of the JWT used
   tool_name (text)
   action (text)
   args_redacted (jsonb)
   ok (boolean)
   error_code (text, nullable)
   duration_ms (integer)
   task_id (text, nullable)
   ```

4. **Seed**: insert `mcp-system` row in `console_users` (role=`admin`, password
   hash randomly generated, login disabled).

---

## 9. Configuration

### 9.1 Environment variables

```bash
# stdio transport
MCP_API_TOKEN=<long-lived jwt for mcp-system user>

# HTTP transport
MCP_HTTP_HOST=0.0.0.0
MCP_HTTP_PORT=8765
MCP_HTTP_PUBLIC_BASE=https://mcp.example.com   # optional, for SSE clients

# Common
MCP_CONSOLE_API_BASE=http://localhost:8080     # FastAPI base URL
MCP_LOG_LEVEL=info
MCP_IDEMPOTENCY_TTL_S=86400
```

### 9.2 MCP client config snippets

**Claude Code (`~/.config/claude-code/mcp.json` or project-level):**
```json
{
  "mcpServers": {
    "ai-media-console": {
      "command": "python",
      "args": ["-m", "console.mcp.stdio"],
      "cwd": "/path/to/ai-media-automation",
      "env": { "MCP_API_TOKEN": "..." }
    }
  }
}
```

**Remote agent (Claude Agent SDK / cron):**
```python
client = MCPClient(url="https://mcp.example.com/sse",
                   headers={"X-API-Key": os.environ["MCP_API_KEY"]})
```

---

## 10. Risks and tradeoffs

| Risk | Mitigation |
|------|------------|
| Thin HTTP layer adds latency vs. in-process | Acceptable: tools are user-paced. If a hot path emerges, the sub-app variant is in-process anyway. |
| Action-dispatched tools have larger arg schemas | Action enums documented in description; per-action arg validation inside the dispatcher. |
| Long renders can outlive an HTTP/SSE connection | Fire-and-forget pattern: `task_id` is durable, agent reconnects and polls. |
| API drift between FastAPI and tool dispatchers | Integration tests run against real FastAPI; tool tests use fakes — drift surfaces in integration. |
| Cron job double-uploads on retry | `idempotency_key` arg backed by Redis. |
| Service-account JWT leaks | Token lives in env on dev machine; for prod, use a short-lived signed token issued by a side process. API keys hashed at rest in `mcp_api_keys`. |

---

## 11. Open questions deferred to plan

These are implementation-level and will be resolved during planning, not now:

- Whether to use `mcp` SDK's `FastMCP` directly or wrap it for testability.
- Exact wire format for SSE vs streamable HTTP (depends on which MCP clients
  the chat surface uses).
- Whether `task_status` should support a blocking `wait_until: "SUCCESS|FAILURE"`
  arg with a max-wait timeout (nice-to-have, not core).
- Where to host the standalone HTTP server in production (same Docker image
  as FastAPI, or separate?).

---

## 12. Out of scope for this spec

- Implementing tools beyond the 11 listed in §2.
- Frontend changes to the chat surface (separate spec).
- Long-term maintenance: how new console endpoints get added to MCP — assumed
  manual for now; revisit if catalog grows.
- Deployment/Docker changes (separate spec).
