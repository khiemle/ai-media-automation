# CI Test Workflows Design

**Date:** 2026-05-16
**Status:** Approved (awaiting implementation plan)
**Owner:** khiemlq@gmail.com

## Goal

Add GitHub Actions workflows that run the existing test suite on every pull request and push to `main`, split into four independent components — **backend**, **frontend**, **render**, **mcp** — so each appears as its own check, runs only when its code changes, and can be debugged or disabled in isolation. Integration tests stay in CI but mock all external services (HTTP APIs, LLM providers, ffmpeg-heavy SDKs) so runs are deterministic and free.

The existing `.github/workflows/deploy.yml` (Docker build + push on `v*` tags) is untouched.

## Non-goals

- E2E browser tests (Playwright UI) — none exist today.
- GPU-accelerated render path — stays on the self-hosted Windows runner via `deploy.yml`.
- Coverage reporting / Codecov — follow-up.
- Lint and type-check workflows — follow-up.
- Adding new test cases — this spec only wires up what already exists.

## Approach

Four standalone workflow files under `.github/workflows/`. Chosen over a single `ci.yml` because:

1. The user explicitly asked for separate workflows.
2. Path filters give per-PR signal: a frontend-only PR won't spin up Postgres for nothing.
3. Each workflow is independently togglable and re-runnable.
4. The four components share little setup, so DRY-ing via reusable workflows is overkill.

Acceptable tradeoff: a few duplicated `actions/setup-python@v5` steps across files.

## Component partitioning

### Backend — `.github/workflows/backend.yml`

**What it tests.** FastAPI routers and services in `console/backend/`, plus the slice of root-level `tests/` that exercises service/router code without ffmpeg:
- `tests/test_api_*.py`
- `tests/test_*_service.py` (excluding the render-heavy ones listed under Render below)
- `tests/test_llm_*.py`
- `tests/test_channel_*.py`
- `tests/test_dispatch_render.py`
- `tests/test_file_naming.py`
- `tests/test_script_language.py`
- `tests/test_runway_service.py`
- `tests/test_topaz_client.py`
- `tests/test_youtube_video_service_*.py`
- `tests/test_youtube_upload_*.py`
- `tests/test_youtube_uploader*.py`
- `tests/test_youtube_cancel_tasks.py`
- `tests/test_upload_*.py`
- `tests/test_thumbnail_endpoint.py`
- `tests/test_sfx_generate_endpoint.py`
- `tests/test_sfx_service.py`
- `tests/test_production_import.py`
- `tests/test_elevenlabs_tts.py`
- `tests/test_tts_router.py`
- `tests/test_llm_autofill.py`
- `console/backend/tests/`

**Triggers.** `pull_request`, `push` to `main`, `workflow_dispatch`. Path filter:
```yaml
paths:
  - 'console/backend/**'
  - 'console/requirements.txt'
  - 'requirements.pipeline.txt'
  - 'tests/**'
  - 'database/**'
  - 'rag/**'
  - 'uploader/**'
  - 'feedback/**'
  - '.github/workflows/backend.yml'
```
(Note: `tests/**` is broad on purpose — backend job runs the broadest test slice; if a render-only test file changes, the render job also fires via its own filter.)

**Runner:** `ubuntu-latest`.

**Service containers:**
```yaml
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: testpw
      POSTGRES_DB: ai_media_test
    ports: ['5432:5432']
    options: >-
      --health-cmd "pg_isready -U admin"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
  redis:
    image: redis:7-alpine
    ports: ['6379:6379']
```

**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` with `python-version: '3.11'` and `cache: pip` keyed on `console/requirements.txt`, `requirements.pipeline.txt`
3. `pip install -r console/requirements.txt` (transitively pulls `requirements.pipeline.txt`)
4. `cd console/backend && alembic upgrade head` with `TEST_DATABASE_URL=postgresql://admin:testpw@localhost:5432/ai_media_test`
5. `pytest -m "not render and not slow" tests/ console/backend/tests/ --ignore=tests/pipeline --ignore=tests/test_composer_subtitles.py ...` (full ignore list derived from the Render section below)

**Env (step-level, dummy values):**
```yaml
env:
  TEST_DATABASE_URL: postgresql://admin:testpw@localhost:5432/ai_media_test
  REDIS_URL: redis://localhost:6379/0
  GEMINI_API_KEY: test
  GEMINI_MEDIA_API_KEY: test
  PEXELS_API_KEY: test
  ELEVENLABS_API_KEY: test
  RUNWAY_API_KEY: test
  YOUTUBE_API_KEY: test
  # FERNET_KEY: any valid 44-char urlsafe-base64 key (Fernet.generate_key().decode()).
  # Generate once and hard-code in the workflow YAML — value is irrelevant for tests.
  FERNET_KEY: 'PLACEHOLDER_GENERATE_DURING_IMPLEMENTATION='
  JWT_SECRET: test-jwt-secret
```

---

### Frontend — `.github/workflows/frontend.yml`

**What it tests.** `console/frontend/src/__tests__/*.test.js` and any future Vitest files. Today: `seoJsonUtils.test.js`.

**Triggers.** `pull_request`, `push` to `main`, `workflow_dispatch`. Path filter:
```yaml
paths:
  - 'console/frontend/**'
  - '.github/workflows/frontend.yml'
```

**Runner:** `ubuntu-latest`. **No services.**

**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-node@v4` with `node-version: '20'` and `cache: npm`, `cache-dependency-path: console/frontend/package-lock.json`
3. `cd console/frontend && npm ci`
4. `npm run build` (catches Vite/JSX errors that tests miss)
5. `npm test` (runs `vitest run`)

---

### Render — `.github/workflows/render.yml`

**What it tests.** ffmpeg-touching pipeline tests that have already been written to mock the heavy deps with `MagicMock`:
- `tests/test_composer_*.py`
- `tests/test_renderer_ass.py`
- `tests/test_youtube_ffmpeg*.py`
- `tests/test_youtube_render_supersede.py`
- `tests/test_music_*.py`
- `tests/test_chapter_builder.py`
- `tests/test_subtitle_builder.py`
- `tests/test_caption_word_timing.py`
- `tests/test_spectrum_*.py`
- `tests/test_thumbnail_generation.py`
- `tests/test_tts_router_timing.py`
- `tests/pipeline/` (test_concat.py, test_sfx_scheduler.py)

**Triggers.** `pull_request`, `push` to `main`, `workflow_dispatch`. Path filter:
```yaml
paths:
  - 'pipeline/**'
  - 'tests/pipeline/**'
  - 'tests/test_composer_*.py'
  - 'tests/test_renderer_*.py'
  - 'tests/test_youtube_ffmpeg*.py'
  - 'tests/test_youtube_render_supersede.py'
  - 'tests/test_music_*.py'
  - 'tests/test_chapter_*.py'
  - 'tests/test_subtitle_*.py'
  - 'tests/test_caption_*.py'
  - 'tests/test_spectrum_*.py'
  - 'tests/test_thumbnail_generation.py'
  - 'tests/test_tts_router_timing.py'
  - 'requirements.pipeline.txt'
  - '.github/workflows/render.yml'
```

**Runner:** `ubuntu-latest`. **No services** — render tests use `MagicMock` and don't touch a database.

**Steps:**
1. `actions/checkout@v4`
2. `apt-get install -y ffmpeg libsndfile1 libgomp1` (system deps for any tests that shell out to ffmpeg or load audio libs)
3. `actions/setup-python@v5` (3.11) with `cache: pip`
4. `pip install -r requirements.pipeline.txt`. Also install the minimum console deps that pipeline tests transitively import (sqlalchemy, pydantic, etc.). The simplest path is to install `console/requirements.txt` too — slower but bullet-proof. Decision deferred to plan; default to the simpler path unless cold-start time is painful.
5. `pytest tests/test_composer_*.py tests/test_renderer_*.py tests/test_youtube_ffmpeg*.py tests/pipeline/ ...` (explicit list above)

**Env:** same dummy keys as backend (most heavy SDKs are mocked, but their constructors may probe env vars).

---

### MCP — `.github/workflows/mcp.yml`

**What it tests.** `console/mcp/tests/` — three subgroups:
- Unit: `console/mcp/tests/test_*.py` (root-level test files in `tests/`)
- Integration: `console/mcp/tests/integration/` (e.g., `test_full_video_flow.py` — full 11-tool agent flow against `respx`-mocked FastAPI)
- E2E: `console/mcp/tests/e2e/` (HTTP, stdio, mount, smoke)

All three already use `respx` for HTTP mocking and in-process FastAPI test clients. No real DB or network.

**Triggers.** `pull_request`, `push` to `main`, `workflow_dispatch`. Path filter:
```yaml
paths:
  - 'console/mcp/**'
  - 'requirements.mcp.txt'
  - '.github/workflows/mcp.yml'
```

**Runner:** `ubuntu-latest`. **No services.**

**Steps:**
1. `actions/checkout@v4`
2. `actions/setup-python@v5` (3.11) with `cache: pip` keyed on `requirements.mcp.txt`
3. `pip install -r requirements.mcp.txt pytest pytest-asyncio respx`
4. `pytest console/mcp/tests/` (the existing `console/mcp/tests/pytest.ini` provides `asyncio_mode = auto`)

**Env:** `MCP_API_TOKEN=test-token`, `MCP_CONSOLE_API_BASE=http://test`, `MCP_LOG_LEVEL=debug` (mirrors `console/mcp/tests/conftest.py`).

---

## Integration tests with mocking — strategy

### Pytest markers

Add a project-root `pytest.ini` (or extend `console/mcp/tests/pytest.ini`'s pattern in a top-level config) with:

```ini
[pytest]
markers =
    unit: fast, no I/O, fully mocked (default in CI)
    integration: wires multiple components, mocks all external HTTP via respx
    render: requires ffmpeg installed; fully mocks heavy SDKs
    slow: takes > 5 seconds; runnable on demand
    manual: opt-in only (already used by MCP)
```

Existing tests inherit `unit` implicitly (no marker = runs by default). New integration tests get `@pytest.mark.integration`. Render-suite files get a module-level `pytestmark = pytest.mark.render` so the backend job's `-m "not render"` filter cleanly excludes them without per-file `--ignore` flags.

**Migration plan within this spec's scope:** add module-level `pytestmark = pytest.mark.render` to each render-suite file enumerated above. No new tests. No reorganization of existing tests beyond the marker.

### Mocking conventions

Reusable mock factories go in a new `tests/fixtures/` package:
- `tests/fixtures/llm.py` — canned Gemini / Ollama responses
- `tests/fixtures/youtube.py` — canned YouTube Data API JSON
- `tests/fixtures/ffmpeg.py` — canned `ffprobe` output dicts and silent WAV/MP4 byte stubs
- `tests/fixtures/elevenlabs.py` — canned music/SFX generation responses

These wrap patterns already present (search the suite for `MagicMock(` to find the duplicated ones). Adoption in existing tests is **not** in scope for this spec — fixtures are added so future tests can reuse them; existing tests keep their inline mocks.

`respx` is the chosen HTTP mock library — already in `console/requirements.txt`, already proven by `test_full_video_flow.py`. No new HTTP mocking framework is introduced.

DB integration tests reuse the existing `engine` / `db` fixtures in `tests/conftest.py` (rolled-back transactions per test) against the Postgres service container in `backend.yml`.

---

## Cross-cutting

**Concurrency.** Each workflow:
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```
New PR pushes cancel stale runs of the same workflow on the same ref.

**Caching.** Pip cache keyed on the relevant `requirements*.txt` hash; npm cache keyed on `package-lock.json` (handled by `setup-python` and `setup-node` actions).

**Secrets.** No real secrets are referenced. Each workflow exports dummy values via step-level `env:`. `FERNET_KEY` uses a hard-coded, test-only Fernet key checked into the workflow file (it only needs to be a valid 44-char base64 key — value is irrelevant for tests).

**Failure budget.** No coverage gates yet. Goal of this milestone: every workflow green on `main`. Coverage and stricter gates land in a follow-up spec.

**Permissions.** Each workflow uses `permissions: contents: read` (minimum needed for `actions/checkout`).

---

## Files to create / modify

**Create:**
- `.github/workflows/backend.yml`
- `.github/workflows/frontend.yml`
- `.github/workflows/render.yml`
- `.github/workflows/mcp.yml`
- `pytest.ini` (project root) — registers markers
- `tests/fixtures/__init__.py`
- `tests/fixtures/llm.py`
- `tests/fixtures/youtube.py`
- `tests/fixtures/ffmpeg.py`
- `tests/fixtures/elevenlabs.py`

**Modify:**
- Each render-suite test file gets a one-line `pytestmark = pytest.mark.render` added at module top (list enumerated above).

**Untouched:** `.github/workflows/deploy.yml`.

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Heavy pip installs (kokoro-onnx, faster-whisper, moviepy) blow CI runtime | pip cache, run tests in parallel via separate workflows; if still slow, follow-up spec to slim render deps to only what's importable in mocked tests |
| A render-suite test secretly needs GPU | Run the full render workflow once locally before merging; any failure is investigated rather than masked. None of the listed render tests have a GPU dependency today (all use `MagicMock`). |
| Path filter mis-routes a test | Backend filter is intentionally broad on `tests/**`; the explicit `--ignore` / `-m "not render"` keeps render files out. Worst case a render-only change runs both backend and render jobs — acceptable. |
| `alembic upgrade head` fails on a fresh DB due to multiple migration heads | Existing repo behavior is single-head; if heads diverge, `alembic merge` is run as part of normal dev — not a CI concern. |
| Postgres service container schema differs from prod | `Base.metadata.create_all` plus `alembic upgrade head` covers both paths; existing `tests/conftest.py` already uses this pattern successfully. |

---

## Open questions

None blocking. Two minor items to decide during implementation:

1. **Render job dep install:** pin to `requirements.pipeline.txt` only (faster, may break) vs. install both console+pipeline (slower, safer). Default to safer.
2. **Backend `-m` filter exact form:** `-m "not render and not slow"` requires the marker rollout above; if rollout slips, fall back to explicit `--ignore` lists per file (already enumerated).

---

## Out of scope (for follow-up specs)

- Coverage reporting and thresholds (Codecov / `pytest --cov`).
- Lint workflows (`ruff`, `eslint`).
- Type-check workflows (`mypy`, `tsc`).
- E2E Playwright UI tests.
- Self-hosted GPU render-path tests in CI.
- Migrating existing inline mocks to the new `tests/fixtures/` factories.
