# Deploy Secrets Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two diagnostic steps to `.github/workflows/deploy.yml` that, after the next deploy, definitively answer (a) whether `config/api_keys.json` on the runner contains non-empty values and (b) whether the running `api` container reads non-empty values — so the root cause of "all keys empty" can be located in one disjoint branch of the decision tree in the spec.

**Architecture:** Two new PowerShell steps inserted into the `deploy` job — one after the file is written, one after services start. Both emit only booleans (`api_key.Length -gt 0`), a byte length, and a SHA-256 hash. Neither expands a secret value. Both run with `continue-on-error: true` on this first iteration so an unrelated PowerShell bug doesn't break the existing deploy.

**Tech Stack:** GitHub Actions workflow YAML, PowerShell (Windows self-hosted runner), `docker compose exec` to query the running container's Python config loader.

**Spec:** `docs/superpowers/specs/2026-05-18-deploy-secrets-debug-design.md`

---

## File Structure

- **Modify:** `.github/workflows/deploy.yml`
  - Insert one step after the existing `Write config/api_keys.json` step (currently ends line 144).
  - Insert one step after the existing `Start services` step (currently ends line 246).
  - No other lines in the file change.

- **No new files.** PowerShell logic is inline in YAML because it runs once on the Windows self-hosted runner and is not reused elsewhere.

- **No test files.** The "test" for this change is reading the next deploy's logs (see Task 4). PowerShell logic gets a local dry-run via the test-fixture JSON in Task 1 before being committed.

---

### Task 1: Locally dry-run the file-side verification logic

We cannot test the workflow in GitHub Actions before merging, but we *can* validate the file-parsing PowerShell logic against a fixture JSON locally. Since `pwsh` is not installed on macOS by default, this task uses Python to validate the *equivalent* logic — the same `bool(value)` semantics — against a fixture file with a mix of empty and non-empty values.

This guards against the most likely source of plan failure: a PowerShell typo that doesn't catch all seven keys, or a wrong dotted-path traversal (e.g. checking `gemini.api_key` instead of `gemini.script.api_key`).

**Files:**
- Create: `/tmp/api_keys_fixture.json`
- Reference: `config/api_config.py` (canonical shape of `api_keys.json`)

- [ ] **Step 1: Write the fixture file**

```bash
cat > /tmp/api_keys_fixture.json <<'EOF'
{
  "gemini": {
    "script": { "api_key": "AIza-script-real", "model": "gemini-2.5-flash" },
    "media":  { "api_key": "", "model": "veo-3.1-lite-generate-preview" },
    "music":  { "api_key": "AIza-music-real", "model": "lyria-3-clip-preview" }
  },
  "elevenlabs": { "api_key": "11labs-real", "voice_id_en": "x", "voice_id_vi": "y", "model": "eleven_flash_v2_5" },
  "suno":    { "api_key": "", "model": "V4_5" },
  "sunoapi": { "api_key": "" },
  "pexels":  { "api_key": "pexels-real" },
  "runway":  { "api_key": "" }
}
EOF
```

- [ ] **Step 2: Run the Python equivalent of the planned PowerShell logic**

```bash
python3 - <<'EOF'
import json, hashlib, pathlib
path = pathlib.Path('/tmp/api_keys_fixture.json')
data = json.loads(path.read_text())
keys = {
    'gemini.script': bool(data.get('gemini',{}).get('script',{}).get('api_key')),
    'gemini.media':  bool(data.get('gemini',{}).get('media',{}).get('api_key')),
    'gemini.music':  bool(data.get('gemini',{}).get('music',{}).get('api_key')),
    'elevenlabs':    bool(data.get('elevenlabs',{}).get('api_key')),
    'suno':          bool(data.get('suno',{}).get('api_key')),
    'pexels':        bool(data.get('pexels',{}).get('api_key')),
    'runway':        bool(data.get('runway',{}).get('api_key')),
}
print('=== file-side keys ===')
print(json.dumps(keys, indent=2))
print(f'file_bytes: {len(path.read_bytes())}')
print(f'file_sha256: {hashlib.sha256(path.read_bytes()).hexdigest()}')
EOF
```

- [ ] **Step 3: Verify the expected output**

Expected stdout:
```
=== file-side keys ===
{
  "gemini.script": true,
  "gemini.media": false,
  "gemini.music": true,
  "elevenlabs": true,
  "suno": false,
  "pexels": true,
  "runway": false
}
file_bytes: <some integer>
file_sha256: <64-hex-char string>
```

If any boolean disagrees with the fixture (e.g. `suno` is `true` despite the fixture having `""`), the dotted-path lookup is wrong — fix the path traversal in the PowerShell version of Task 2 before writing it.

- [ ] **Step 4: Clean up fixture**

```bash
rm /tmp/api_keys_fixture.json
```

- [ ] **Step 5: No commit**

This task produces no files in the repo. Move on.

---

### Task 2: Add the file-side verify step to deploy.yml

Insert a new step **after** the existing `Write config/api_keys.json` step (currently ends at line 144) and **before** the `Write pipeline.env` step (currently starts at line 146).

**Files:**
- Modify: `.github/workflows/deploy.yml` between line 144 and line 146

- [ ] **Step 1: Confirm exact insertion point**

Run: `awk 'NR==144 || NR==145 || NR==146' .github/workflows/deploy.yml`

Expected output (line 144 is the closing line of the WriteAllText call; line 145 is blank; line 146 is the next step header):
```
          [System.IO.File]::WriteAllText("$PWD\config\api_keys.json", $text, (New-Object System.Text.UTF8Encoding $false))

      # Write pipeline.env from variables (non-sensitive) + secrets
```

If line numbers have drifted (because the file changed since this plan was written), find the correct insertion point by locating the line containing `WriteAllText("$PWD\config\api_keys.json"` and inserting the new step after the blank line that follows it.

- [ ] **Step 2: Insert the file-side verify step**

Use the Edit tool to insert the following block. The `old_string` is the empty line immediately following the WriteAllText line; the `new_string` is the empty line plus the new step. This preserves YAML indentation.

Insert this block (note: 6-space indentation matches the surrounding `steps:` items):

```yaml

      # Diagnostic: verify config/api_keys.json was written with non-empty values.
      # Booleans only — no secret value ever leaves this step.
      - name: Verify config/api_keys.json (file-side)
        shell: powershell
        continue-on-error: true
        run: |
          $path = "$PWD\config\api_keys.json"
          if (-not (Test-Path $path)) {
            Write-Host "FATAL: $path does not exist"
            exit 1
          }
          $bytes = [System.IO.File]::ReadAllBytes($path)
          $hash  = (Get-FileHash $path -Algorithm SHA256).Hash
          $json  = Get-Content -Raw $path | ConvertFrom-Json
          function NonEmpty($v) {
            if ($null -eq $v) { return $false }
            return ($v.ToString().Length -gt 0)
          }
          $keys = [ordered]@{
            'gemini.script' = NonEmpty $json.gemini.script.api_key
            'gemini.media'  = NonEmpty $json.gemini.media.api_key
            'gemini.music'  = NonEmpty $json.gemini.music.api_key
            'elevenlabs'    = NonEmpty $json.elevenlabs.api_key
            'suno'          = NonEmpty $json.suno.api_key
            'pexels'        = NonEmpty $json.pexels.api_key
            'runway'        = NonEmpty $json.runway.api_key
          }
          Write-Host "=== file-side keys ==="
          $keys | ConvertTo-Json
          Write-Host "file_bytes: $($bytes.Length)"
          Write-Host "file_sha256: $hash"

```

- [ ] **Step 3: Verify YAML parses**

Run from the repo root:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"
```

Expected: no output, exit code 0. If `yaml.scanner.ScannerError` or similar: indentation is off. Fix the indentation (must be exactly 6 spaces for `- name:` and 8 for child keys) and re-run.

- [ ] **Step 4: Verify the step landed in the right place**

Run:
```bash
grep -n "Verify config/api_keys.json (file-side)\|Write config/api_keys.json\|Write pipeline.env" .github/workflows/deploy.yml
```

Expected output (line numbers will have shifted due to insertion):
```
122:      - name: Write config/api_keys.json
<X>:      - name: Verify config/api_keys.json (file-side)
<Y>:      - name: Write pipeline.env
```

`X` must be greater than 122 and less than `Y`. If the order is wrong, undo the edit and re-apply at the correct location.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci(deploy): add file-side verify step for api_keys.json"
```

---

### Task 3: Add the container-side verify step to deploy.yml

Insert a new step **after** the existing `Start services` step (currently ends at line 246).

**Files:**
- Modify: `.github/workflows/deploy.yml` after the `Start services` step (line 246, before insertion in Task 2; after Task 2 the line number will have shifted).

- [ ] **Step 1: Confirm exact insertion point**

Run:
```bash
grep -n "Start services\|docker compose up -d --remove-orphans" .github/workflows/deploy.yml
```

Expected: one line with `- name: Start services` and a following line with `docker compose up -d --remove-orphans`. Insertion goes at the end of file (after the `Start services` step — which is currently the final step of the deploy job).

- [ ] **Step 2: Insert the container-side verify step**

Use the Edit tool. The `old_string` is the `docker compose up -d --remove-orphans` line plus its trailing newline; the `new_string` is the same content plus the new step appended after it.

Insert this block at the very end of the deploy job (same 6-space indentation as other steps):

```yaml

      # Diagnostic: verify the running api container reads non-empty values
      # from api_config.get_config(). Compare against file-side booleans
      # above to localize the bug (file wrong, mount stale, or cache).
      - name: Verify config/api_keys.json (container-side)
        shell: powershell
        continue-on-error: true
        run: |
          # Force-flush the api_config 30s cache before reading, so we
          # see the file content the FastAPI process would see on a
          # fresh request right now (not what it cached at boot).
          $py = @"
          import json
          import config.api_config as ac
          ac._cache = {}
          ac._cache_time = 0
          c = ac.get_config()
          out = {
            'gemini.script': bool(c.get('gemini',{}).get('script',{}).get('api_key')),
            'gemini.media':  bool(c.get('gemini',{}).get('media',{}).get('api_key')),
            'gemini.music':  bool(c.get('gemini',{}).get('music',{}).get('api_key')),
            'elevenlabs':    bool(c.get('elevenlabs',{}).get('api_key')),
            'suno':          bool(c.get('suno',{}).get('api_key')),
            'pexels':        bool(c.get('pexels',{}).get('api_key')),
            'runway':        bool(c.get('runway',{}).get('api_key')),
          }
          print('=== container-side keys ===')
          print(json.dumps(out, indent=2))
          "@
          docker compose exec -T api python -c $py

```

- [ ] **Step 3: Verify YAML parses**

Run from the repo root:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"
```

Expected: no output, exit code 0.

- [ ] **Step 4: Verify the step landed at the end of the deploy job**

Run:
```bash
tail -40 .github/workflows/deploy.yml
```

Expected: the last step is `Verify config/api_keys.json (container-side)`. The previous step is `Start services`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci(deploy): add container-side verify step for api_keys.json"
```

---

### Task 4: Tag, deploy, and read the verification output

The deploy workflow triggers on `push: tags: ['v*']` and on `workflow_dispatch`. The cheapest path is `workflow_dispatch` so we don't burn a version number on a diagnostic-only change. Use `gh workflow run` from the repo root.

The user's deploy branch is `prod` (recent `v1.2.0` was cut from `prod`, not `main`). Push and dispatch against `prod`.

**Files:** none (this task only triggers and reads).

- [ ] **Step 1: Push the two commits to prod**

```bash
git push origin prod
```

Expected: push succeeds. CI tests (other workflows) may run but they're orthogonal.

- [ ] **Step 2: Trigger the Deploy workflow manually**

```bash
gh workflow run deploy.yml --ref prod
```

Expected: `✓ Created workflow_dispatch event for deploy.yml at prod`.

- [ ] **Step 3: Wait for the run to start, then watch it**

```bash
sleep 5
gh run list --workflow=deploy.yml --limit 1
```

Capture the run ID (first column). Then:

```bash
gh run watch <RUN_ID>
```

This blocks until the run finishes (success or failure). Expected duration: ~30 minutes (matches recent v* deploys).

- [ ] **Step 4: Read the file-side verify output**

```bash
gh run view <RUN_ID> --log --job <DEPLOY_JOB_ID> 2>&1 | grep -A 12 "=== file-side keys ==="
```

If `gh run view --log` is denied by the auto mode classifier (secrets-adjacent content), open the run in a browser instead:

```bash
gh run view <RUN_ID> --web
```

…and read the "Verify config/api_keys.json (file-side)" step output by eye.

- [ ] **Step 5: Read the container-side verify output**

Same as Step 4 but grep/scroll to `=== container-side keys ===`.

- [ ] **Step 6: Locate the outcome in the decision tree**

Compare the two boolean maps:

- **All `true` in both** → Branch Z. Re-test `music(action="elevenlabs_plan")` via MCP. If it still 503s, add the same diagnostic to the `celery-render` container (a follow-up plan).
- **File: all `true`, container: any `false`** → Branch X. Mount staleness or wrong workspace. Follow-up plan: add a `docker compose restart api celery-worker celery-render celery-beat` step, and/or run `docker compose ls` + `docker inspect` on the runner to find the wrong workspace.
- **File: any `false`** → Branch Y. Write step is producing empties.
  - All seven false → check repo Environments settings; re-paste secrets via UI.
  - Some true, some false → `gh secret set NAME --body "<value>"` for each `false`.

This task ends by recording the outcome — not by fixing it. The fix is a separate plan written against the spec's Decision Tree section.

- [ ] **Step 7: Write the outcome to the spec doc**

Append a `## Outcome` section to `docs/superpowers/specs/2026-05-18-deploy-secrets-debug-design.md` with:
- The deploy run ID
- The file-side boolean map (copy-paste)
- The container-side boolean map (copy-paste)
- Which branch (X / Y / Z) the evidence points to
- Next concrete action (e.g. "Branch X1 — open follow-up plan to add a restart step")

```bash
git add docs/superpowers/specs/2026-05-18-deploy-secrets-debug-design.md
git commit -m "docs(deploy-debug): record outcome of diagnostic deploy run"
```

---

## Out of scope (do not implement here)

The spec lists two "Future hardening" items that are explicitly deferred:

1. Drop `continue-on-error: true` from both verify steps once root cause is fixed.
2. Refactor `api_config.py` to read env vars first.

Both become candidate follow-ups *after* Task 4 reveals the root cause. Each warrants its own spec → plan cycle.

The targeted fix for whichever decision-tree branch Task 4 surfaces is also out of scope here. The fix is a separate plan because:

- Branch X fix touches `deploy.yml` differently than Branch Y or Z would.
- We don't know which branch we're in until Task 4 completes.
- Mixing the diagnostic and the speculative fix in one PR would couple two unrelated changes.

---

## Self-review notes

**Spec coverage check:**

- Goal section ↔ Task 4 captures both questions (file-side and container-side).
- "Where the diagnostics go" ↔ Task 2 (after Write step) + Task 3 (after Start services).
- "Output format" ↔ Tasks 2 and 3 use the exact JSON shape, byte length, and SHA-256 specified.
- "File-side step (PowerShell)" ↔ Task 2's PowerShell block.
- "Container-side step (PowerShell + docker exec)" ↔ Task 3's `docker compose exec -T api python` block, including the `_cache_time = 0` flush.
- "Logging discipline" ↔ both steps emit only booleans + length + hash.
- "Decision tree" ↔ Task 4 Step 6 maps output to branches X/Y/Z verbatim.
- "Defensive note" ↔ both new steps use `continue-on-error: true`.
- "Test plan" acceptance criteria ↔ Task 4 Steps 4, 5, 6 verify them.

**Placeholder scan:** no `TBD`/`TODO`/"appropriate"/"as needed"/"similar to" — every step shows the exact code or command.

**Type/name consistency:** the seven dotted-key names appear identically in every emit block (`gemini.script`, `gemini.media`, `gemini.music`, `elevenlabs`, `suno`, `pexels`, `runway`).
