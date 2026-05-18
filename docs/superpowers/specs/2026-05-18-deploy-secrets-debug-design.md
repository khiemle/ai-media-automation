# Deploy secrets diagnostic — design

**Date:** 2026-05-18
**Status:** Approved, ready for plan
**Author:** brainstorm session

## Problem

`config/api_keys.json` on the production Windows render host shows all
`api_key` fields as empty strings, even though:

- All seven expected secrets exist as repo-level GitHub Actions secrets
  (`gh secret list` confirms names + updated timestamps).
- The user is confident real values were pasted in.
- The most recent `Deploy` workflow run (v1.2.0, 2026-05-18 01:55 UTC)
  completed successfully and includes a step that writes
  `config/api_keys.json` from those secrets.
- `GET /api/llm/config/raw` on the live API at `192.168.68.119:8080`
  returns `{"elevenlabs": {"api_key": "", ...}, ...}` for every provider.
- `music(action="elevenlabs_plan")` via MCP returns `503 — ElevenLabs API
  key is not configured in config/api_keys.json`, confirming the running
  app reads the same empty values.

We have ruled out:

- **Empty secret values** — user confirms real values were set.
- **Image-baked stale file** — `.dockerignore` excludes
  `config/api_keys.json`, so the GHCR image has no embedded file.
- **`MCP_HTTP_USE_DB_KEYS=1` overriding service keys** — that flag only
  governs the `mcp_api_keys` registry (MCP auth), not provider keys.
- **`api_config.get_config()` reading from the wrong path** — the module
  resolves the file relative to its own `__file__`, which inside the
  container is `/app/config/api_keys.json`. That is exactly what the
  bind mount `./config:/app/config` in `docker-compose.yml` provides.

## Goal

Get a deploy run whose logs definitively answer **two** questions:

1. After the "Write config/api_keys.json" step completes, does the
   file on the runner workspace contain non-empty values?
2. After services start, does the running `api` container's
   `api_config.get_config()` return non-empty values?

Once we know the answer to both, the root cause is one of four
disjoint branches (see Decision Tree), each with a targeted fix.

## Non-goals

- We are **not** fixing the root cause as part of this change.
  This change adds diagnostics only. The fix is decided once we read
  the next deploy's logs.
- We are **not** refactoring `api_config` to read env vars. That was
  Approach C in brainstorming, deferred as more invasive than needed.
- We are **not** rotating any secret values.

## Design

### Where the diagnostics go

Two new steps are inserted into `.github/workflows/deploy.yml`:

1. **`Verify config/api_keys.json (file-side)`** — immediately after
   the existing "Write config/api_keys.json" step (currently lines
   122–144), before any docker-compose step touches the file.

2. **`Verify config/api_keys.json (container-side)`** — immediately
   after the existing "Start services" step (currently line 246).

Both run with `continue-on-error: true` on the first
post-merge run so we collect evidence even if values are empty. Once
the root cause is fixed, both should drop `continue-on-error` so they
become regression guards.

### Output format

Both steps emit the same JSON-shaped boolean map so the two outputs
can be eyeballed-diffed in the log:

```
=== file-side keys ===
{
  "gemini.script": true,
  "gemini.media":  true,
  "gemini.music":  true,
  "elevenlabs":    true,
  "suno":          true,
  "pexels":        true,
  "runway":        true
}
file_bytes: 412
file_sha256: a3f8...c41d
```

The booleans are `($value.Length -gt 0)`, never the value itself.
Byte length and SHA-256 are printed only by the file-side step. The
container-side step prints only the boolean map.

### File-side step (PowerShell)

Reads the file with `Get-Content -Raw | ConvertFrom-Json`. Walks the
known seven dotted paths (`gemini.script.api_key`, `gemini.media.api_key`,
`gemini.music.api_key`, `elevenlabs.api_key`, `suno.api_key`,
`pexels.api_key`, `runway.api_key`). For each, computes the bool with
`.Length -gt 0` and adds it to an ordered hashtable. Emits the hashtable
as JSON via `ConvertTo-Json`. Computes byte length via
`[System.IO.File]::ReadAllBytes($path).Length` and hash via
`(Get-FileHash $path -Algorithm SHA256).Hash`. Logs all three.

### Container-side step (PowerShell + docker exec)

Runs:

```
docker compose exec -T api python -c "
import json
from config.api_config import get_config
c = get_config()
out = {
  'gemini.script': bool(c.get('gemini',{}).get('script',{}).get('api_key')),
  'gemini.media':  bool(c.get('gemini',{}).get('media',{}).get('api_key')),
  'gemini.music':  bool(c.get('gemini',{}).get('music',{}).get('api_key')),
  'elevenlabs':    bool(c.get('elevenlabs',{}).get('api_key')),
  'suno':          bool(c.get('suno',{}).get('api_key')),
  'pexels':        bool(c.get('pexels',{}).get('api_key')),
  'runway':        bool(c.get('runway',{}).get('api_key')),
}
print(json.dumps(out, indent=2))
"
```

This uses the **same module path** the running FastAPI imports, so the
result is identical to what the live app sees, modulo the 30-second
internal cache. To force-flush the cache on first read, prepend the
inline script with `import config.api_config as ac; ac._cache = {}; ac._cache_time = 0`.

### Logging discipline

No secret value is ever expanded to stdout. Only booleans, byte length,
and SHA-256 (of the whole file — non-sensitive in aggregate). GitHub's
auto-masking of secrets is treated as defense-in-depth, not the primary
safeguard.

## Decision tree (what we do once we read the output)

Three disjoint outcomes drive the follow-up fix:

### Branch X — file: all `true`, container: all `false`

**Diagnosis:** the file is written correctly but the running container
isn't reading it. Two sub-causes:

- **X1 — bind mount staleness.** Docker Desktop on Windows occasionally
  caches the inode of a bind-mounted file when the file was created or
  truncated after container start. The existing
  `docker compose up -d --remove-orphans` at end of deploy is a no-op
  if image digests haven't changed, so no restart happens.
  **Fix:** add `docker compose restart api celery-worker celery-render
  celery-beat` between the file write and "Start services" (or as a
  trailing step). Run once manually to confirm; if it fixes it, commit.

- **X2 — wrong workspace mounted.** A previously-started `docker
  compose` project from a different host directory is still running
  alongside, with a stale bind mount.
  **Diagnose:** `docker compose ls` shows project name + working dir;
  `docker inspect <api-container> --format '{{json .Mounts}}'` shows
  the resolved source path. **Fix:** stop the rogue project
  (`docker compose -p <name> down`) and re-`up` from the canonical
  workspace.

### Branch Y — file: some/all `false`

**Diagnosis:** the write step is producing empties.

- **Y1 — all seven false.** The workflow context isn't seeing any
  secrets. Likely cause: secrets are environment-scoped (`environments:`
  in repo settings) and the `deploy` job is missing `environment: prod`,
  so `${{ secrets.X }}` expands to empty.
  **Diagnose:** check repo settings → Environments. **Fix:** either add
  `environment: prod` to the deploy job, or move the secrets to
  repository-level (they're already at repo level per `gh secret list`,
  but a duplicate environment-scoped one with empty value would shadow).

- **Y2 — some true, some false.** Specific secret values are blank
  despite names existing.
  **Fix:** `gh secret set NAME --body "<value>"` for each `false`
  entry, then re-run deploy.

### Branch Z — file and container both: all `true`

**Diagnosis:** keys are present, but our earlier MCP call hit a path
that bypasses them. Possible cause: a separate Celery worker process
(render queue) loaded the config at startup and cached `_DEFAULT`
before the file was written; the `_CACHE_TTL = 30.0` should have
expired by now, but cross-process caching shouldn't apply (each worker
has its own cache).

**Diagnose:** re-test `music(action="elevenlabs_plan")` immediately
after deploy completes. If it still 503s, add the same diagnostic to
the `celery-render` container (the music task runs in `render_q`).

### Defensive note

`continue-on-error: true` is set on both verify steps for the first
post-merge run so the existing deploy still completes if the
diagnostic itself has a bug. This means a broken PowerShell script
won't break production deploys — but it will be visible in the run
log. After the root cause is fixed and the diagnostic has been
through one clean run, drop `continue-on-error` (see Future
hardening).

## Future hardening (out of scope here)

Once root cause is known and fixed, two follow-ups become candidates:

1. **Drop `continue-on-error: true`** from both verify steps so future
   regressions fail the deploy.
2. **Move to env-var-first config** (Approach C from brainstorming).
   The existing `Write console/.env` step writes `RUNWAY_API_KEY` and
   a few other values from secrets via the same `${{ secrets.X }}`
   substitution mechanism, so it shares the JSON file's failure modes
   in principle — but env-file values reach the container via
   `env_file:` (no bind mount), removing one whole class of bug. The
   refactor would (a) extend the `Write console/.env` step to include
   `GEMINI_*`, `ELEVENLABS_*`, `SUNO_*`, `PEXELS_API_KEY`, and (b)
   change `api_config.get_config()` to read env vars first, falling
   back to the JSON file. Larger change; warrants its own design.

## Test plan

This change is itself a diagnostic, so the "test" is reading the next
deploy's logs. Acceptance criteria:

- Both new verify steps appear in the deploy run.
- File-side step prints the seven booleans + byte length + SHA-256.
- Container-side step prints the seven booleans.
- The output lands in exactly one branch of the decision tree, with
  enough signal to pick the targeted fix.

If acceptance fails (e.g. step errors out), iterate on the diagnostic
itself — do not attempt a speculative fix.

## Outcome

**Deploy run:** [26033769797](https://github.com/khiemle/ai-media-automation/actions/runs/26033769797) on `prod` (workflow_dispatch, 2026-05-18 12:34 UTC), completed `success`.

**File-side keys** (after the Write step, before any service start):

```
file_bytes: 1615
file_sha256: f5903d8537d84404d4d79abbaab64d69111fcb3447fc63cfb675476815068fd9

{
  "gemini.script": true,
  "gemini.media":  true,
  "gemini.music":  true,
  "elevenlabs":    true,
  "suno":          true,
  "pexels":        true,
  "runway":        true
}
```

**Container-side keys** (after `docker compose up -d --remove-orphans`):

```
{
  "gemini.script": true,
  "gemini.media":  true,
  "gemini.music":  true,
  "elevenlabs":    true,
  "suno":          true,
  "pexels":        true,
  "runway":        true
}
```

**Decision-tree branch:** **Z** — both sides report all `true`. The file is being written with real values AND the container is reading them. No empty-values bug surfaced by this diagnostic.

**Live re-verification of the original symptom:**

- `GET /api/llm/config/raw` on `http://192.168.68.119:8080` now returns non-empty `api_key` for every provider.
- `music(action="elevenlabs_plan")` via the MCP server now returns `ok: true` with a real composition plan (previously returned `503 — ElevenLabs API key is not configured`).

**Root cause inferred:**

The previous deploy (v1.2.0) DID write the api_keys.json correctly, but the running `api` container exhibited a state that bypassed the file — most plausibly a stuck Docker Desktop bind-mount inode (the file was created or truncated after the container started, and Docker on Windows held a reference to the empty state). The PowerShell `Verify` steps in this deploy could not have made the difference (they're read-only); what likely cured it is that `build-api` published a new image digest, which caused `docker compose up -d --remove-orphans` to recreate the `api` container. A fresh container has a fresh bind mount.

We did not get a Branch X observation that would have proved the mount-staleness theory directly, because the recreate happened as a side effect of the rebuild. The diagnostic remains in place as a regression guard.

**Next concrete action:**

The make-youtube-video workflow can resume immediately — the original blocker is gone. Two follow-ups remain candidates but are not yet open:

1. Drop `continue-on-error: true` on both verify steps now that the baseline output is known-good. Any future deploy that surfaces a `false` will fail loudly. Small follow-up commit.
2. Add an explicit `docker compose restart api celery-worker celery-render celery-beat` step before the container-side verify, so the mount-recreate cure is no longer an accident of image-digest changes. Larger follow-up because it adds ~10s to every deploy, and the diagnostic now lets us see if/when it's actually needed.

Neither follow-up needs its own spec — both are mechanical edits to `deploy.yml`. Open them only if a future deploy lands in Branch X.
