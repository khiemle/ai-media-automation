# console-mcp follow-ups

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

- **`DbApiKeyRegistry` missing.** `http.py:main()` only reads a single
  `MCP_HTTP_DEV_API_KEY` env var. Production needs a registry that loads from
  `mcp_api_keys` (already migrated). README currently warns about this.

- **Backend doesn't read `X-Mcp-Actor-Metadata`.** `ConsoleClient` sends the
  header but `audit_log.actor_metadata` will stay NULL until the backend's
  audit middleware persists it. Wire `console/backend/middleware/audit.py` to
  parse the header and write to the column.

- **Module-level `_store` globals.** `tools/upload.py` and
  `tools/youtube_video.py` keep idempotency state in module globals. Convert
  to `ContextVar` or thread the store through `client_factory` to remove the
  test-isolation footgun.

## Cleanup

- **`_confirmed_*` helpers in `music.py`.** Move them to `tools/_common.py`
  alongside the existing decorators. Mechanical refactor; no behavior change.

- **`upload._async_destructive` could fold into `_common`.** The `fixed_id`
  variant (used for `upload_all`) is the only difference from
  `_confirmed_destructive`. A combined helper would serve both.

- **Decorator + `_confirmed_*` parallel patterns.** `tools/_common.py`'s
  decorators are defined but unused — every tool uses the helper functions
  instead. Pick one style.

- **Activate `DbAuditSink` in transport entrypoints.** All 11 tools accept
  `audit_sink=...` but no entrypoint passes one. Add an opt-in flag like
  `MCP_AUDIT_ENABLED=1` and wire `DbAuditSink()` when set.

- **`http.py` default host.** Currently `0.0.0.0`. Switch to `127.0.0.1` so
  developers don't accidentally LAN-expose an empty-registry server.

- **Audit middleware logs `needs_confirmation` calls as `ok=false`.** That
  distorts error-rate dashboards. Either branch on `needs_confirmation` and
  log them with a separate flag, or document the convention.
