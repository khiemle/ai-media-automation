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
