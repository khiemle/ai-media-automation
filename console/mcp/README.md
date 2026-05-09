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

For an automated local-dev setup (prerequisite checks + JWT minting + ready-to-paste mcp.json), run:

```bash
./console/mcp/scripts/mcp-dev.sh           # stdio setup
./console/mcp/scripts/mcp-dev.sh --http    # also launch HTTP transport
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

### HTTP transport setup

`python -m console.mcp.http` reads its API-key registry from
`InMemoryApiKeyRegistry`, which is populated only from the `MCP_HTTP_DEV_API_KEY`
environment variable for now. **Without that variable set, every request
returns 401.** Production deployment will need a `DbApiKeyRegistry` reading
from the `mcp_api_keys` table — this is a known follow-up.

Required env for HTTP transport:
- `MCP_HTTP_DEV_API_KEY` — plaintext API key clients pass in `X-API-Key`
- `MCP_API_TOKEN` — JWT for the `mcp-system` user the registry maps to
- `MCP_CONSOLE_API_BASE` — defaults to `http://localhost:8080`
- `MCP_HTTP_HOST` / `MCP_HTTP_PORT` — defaults to `0.0.0.0:8765`

## Operational features

### Audit logging (`mcp_tool_calls`)

Every tool call can be logged to `mcp_tool_calls` (PostgreSQL) with
`{tool_name, action, args_redacted, ok, error_code, duration_ms, task_id,
transport, actor_jwt_sub, called_at}`. Args matching `*_token`, `*_key`,
`password` are replaced with `***` before persistence.

Audit is **opt-in per transport entrypoint** — set `audit_sink=DbAuditSink()`
when calling `<tool>.register()`. The default `None` sink means no rows are
written. Activation in `stdio.py`/`http.py`/`mount.py` is a follow-up.

### Idempotency (`MCP_IDEMPOTENCY_TTL_S`)

Write-amplifying tools accept an optional `idempotency_key` argument:
- `upload(action="upload_one", ...)`
- `upload(action="upload_all", ...)`
- `youtube_video(action="render_final", ...)`

Same key reused within the TTL returns the cached result (no second side
effect). Backed by Redis. TTL controlled by `MCP_IDEMPOTENCY_TTL_S` (default
86400 = 24h). Useful for cron jobs that retry on network blips without
double-uploading.

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
