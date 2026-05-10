# console-mcp follow-ups

## Streaming for large uploads

`open_for_upload()` in `tools/_multipart.py` reads the entire file into memory
before sending. For large visual assets (multi-GB `.mp4`), switch to httpx's
streaming multipart support (passing a file-like object instead of bytes) to
avoid blowing memory.

Deferred items from the final code review of the `feat/mcp-server` branch
(2026-05-09). Not blockers for merge; tracked here so they don't get lost.

## Important

- **`http.py` dead FastMCP wiring.** The `build_server(register=[...])` call
  inside `build_http_app` registers tools on a FastMCP instance that the
  `/mcp/call` route bypasses. Either remove the unused `server` build, or
  rewrite `/mcp/call` to dispatch through it (and stop hand-rolling the
  if/elif ladder).

- **Tool dispatch duplicated.** `http.py` and `mount.py` each have a 22-line
  if/elif ladder over `tool_name`. Extract a `TOOL_DISPATCH = {...}` table
  shared by both transports.

- ~~**`DbApiKeyRegistry` missing.**~~ DONE — `DbApiKeyRegistry` implemented in
  `console/mcp/auth/tokens.py`. `http.py:main()` now defaults to DB-backed
  registry (`MCP_HTTP_USE_DB_KEYS=1`). Dev mode uses `MCP_HTTP_USE_DB_KEYS=0`
  via `mcp-dev.sh`. Key management CLI at
  `console/mcp/scripts/manage_api_keys.py`.

- **`mcp_api_keys.service_user_id` is currently unused at lookup time.** All
  keys map to a single shared `MCP_API_TOKEN` from env. To allow per-key
  service tokens (so different agents have distinct audit trails),
  `DbApiKeyRegistry` should mint a per-user JWT on lookup or store an encrypted
  JWT alongside each key.

- ~~**Backend doesn't read `X-Mcp-Actor-Metadata`.**~~ DONE — `_parse_actor_metadata`
  helper added to `console/backend/middleware/audit.py`; `AuditLog.actor_metadata`
  (JSONB) is now populated for MCP traffic. `AuditLog` model also updated to
  declare the column.

- **Module-level `_store` globals.** `tools/upload.py` and
  `tools/youtube_video.py` keep idempotency state in module globals (now
  activated via `activation.install_idempotency_store()` at transport startup).
  Convert to `ContextVar` or thread the store through `client_factory` to
  remove the test-isolation footgun.

## Cleanup

- **`_confirmed_*` helpers in `music.py`.** Move them to `tools/_common.py`
  alongside the existing decorators. Mechanical refactor; no behavior change.

- **`upload._async_destructive` could fold into `_common`.** The `fixed_id`
  variant (used for `upload_all`) is the only difference from
  `_confirmed_destructive`. A combined helper would serve both.

- **Decorator + `_confirmed_*` parallel patterns.** `tools/_common.py`'s
  decorators are defined but unused — every tool uses the helper functions
  instead. Pick one style.

- ~~**Activate `DbAuditSink` in transport entrypoints.**~~ DONE — `activation.py`
  introduced with `audit_kwargs()` and `install_idempotency_store()`. All 11
  tools now receive `audit_sink=DbAuditSink()` when `MCP_AUDIT_ENABLED=1`.
  Idempotency store wired to `upload` + `youtube_video` when
  `MCP_IDEMPOTENCY_ENABLED=1` via `REDIS_URL`.

- **Mount-transport audit gap.** `mount.py`'s `/mcp/call` route dispatches
  via a hand-rolled if/elif ladder and calls tool functions directly, bypassing
  `wrap_with_audit_log`. MCP traffic through the chat surface is NOT covered
  by `DbAuditSink`. To fix, refactor `mount.py` to use FastMCP-style
  registration like `stdio.py` (and stop maintaining a parallel dispatch
  table).

- **`http.py` default host.** Currently `0.0.0.0`. Switch to `127.0.0.1` so
  developers don't accidentally LAN-expose an empty-registry server.

- **Audit middleware logs `needs_confirmation` calls as `ok=false`.** That
  distorts error-rate dashboards. Either branch on `needs_confirmation` and
  log them with a separate flag, or document the convention.
