# CI Test Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up four GitHub Actions workflows (backend, frontend, render, mcp) that run the existing test suite on PRs and pushes to `main`, with all external services mocked.

**Architecture:** Four standalone workflow files under `.github/workflows/`, each with path-filtered triggers so a frontend PR doesn't spin up Postgres. Render-suite tests are gated out of the backend job via a project-root `pytest.ini` plus module-level `pytestmark = pytest.mark.render` on the affected files. A new `tests/fixtures/` package holds reusable mock factories for future tests.

**Tech Stack:** GitHub Actions (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`), pytest with custom markers, Vitest, Postgres 16 + Redis 7 service containers, `respx` for HTTP mocking (already in repo).

**Reference spec:** `docs/superpowers/specs/2026-05-16-ci-tests-workflow-design.md`

---

## File map

**Create:**
- `pytest.ini` — registers markers (unit, integration, render, slow, manual)
- `tests/fixtures/__init__.py`
- `tests/fixtures/llm.py`
- `tests/fixtures/youtube.py`
- `tests/fixtures/ffmpeg.py`
- `tests/fixtures/elevenlabs.py`
- `tests/fixtures/test_fixtures_smoke.py`
- `.github/workflows/backend.yml`
- `.github/workflows/frontend.yml`
- `.github/workflows/render.yml`
- `.github/workflows/mcp.yml`

**Modify (one-line `pytestmark = pytest.mark.render` near top of each):**
- `tests/test_composer_music.py`
- `tests/test_composer_subtitles.py`
- `tests/test_renderer_ass.py`
- `tests/test_youtube_ffmpeg.py`
- `tests/test_youtube_ffmpeg_visual_playlist.py`
- `tests/test_youtube_render_supersede.py`
- `tests/test_music_audio.py`
- `tests/test_music_duration.py`
- `tests/test_music_overlay.py`
- `tests/test_music_providers.py`
- `tests/test_music_render_smoke.py`
- `tests/test_music_service.py`
- `tests/test_chapter_builder.py`
- `tests/test_subtitle_builder.py`
- `tests/test_caption_word_timing.py`
- `tests/test_spectrum_bars.py`
- `tests/test_spectrum_filter.py`
- `tests/test_thumbnail_generation.py`
- `tests/test_tts_router_timing.py`
- `tests/pipeline/test_concat.py`
- `tests/pipeline/test_sfx_scheduler.py`

**Untouched:** `.github/workflows/deploy.yml`.

---

## Task 0: Create feature branch

**Files:** none

- [ ] **Step 1: Branch off main**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git checkout -b ci/test-workflows
git status   # should show clean tree on ci/test-workflows
```

---

## Task 1: Register pytest markers

**Files:**
- Create: `pytest.ini`

- [ ] **Step 1: Write `pytest.ini`**

Create `/Volumes/SSD/Workspace/ai-media-automation/pytest.ini`:

```ini
[pytest]
markers =
    unit: fast, no I/O, fully mocked (default in CI)
    integration: wires multiple components, mocks all external HTTP via respx
    render: requires ffmpeg installed; fully mocks heavy SDKs (excluded from backend job)
    slow: takes > 5 seconds; runnable on demand
    manual: opt-in only (use `pytest -m manual` to run)
```

- [ ] **Step 2: Verify markers registered**

Run: `pytest --markers | grep -E "unit:|integration:|render:|slow:|manual:"`

Expected output: five lines, one per marker, with the descriptions above. If pytest can't be imported: `pip install -r console/requirements.txt` first.

- [ ] **Step 3: Verify no marker warnings**

Run: `pytest --collect-only tests/test_api_config.py 2>&1 | grep -i "PytestUnknownMarkWarning" || echo "no warnings"`

Expected: `no warnings`. (If a marker warning appears, the marker is missing from the ini.)

- [ ] **Step 4: Commit**

```bash
git add pytest.ini
git commit -m "test: register pytest markers (unit, integration, render, slow, manual)"
```

---

## Task 2: Tag render-suite test files with `pytestmark = pytest.mark.render`

**Files:** modify 21 files listed in the file map above.

- [ ] **Step 1: Add the marker to each file via a one-shot sed**

The marker must appear *after* the existing `import` block but *before* any test function. The simplest safe rule: insert after the last top-level `import`/`from` line in the file. Easier still: insert as the **first non-comment, non-blank line** at module top, with `import pytest` if not already present.

Run this script (paste into terminal):

```bash
cd /Volumes/SSD/Workspace/ai-media-automation

FILES=(
  tests/test_composer_music.py
  tests/test_composer_subtitles.py
  tests/test_renderer_ass.py
  tests/test_youtube_ffmpeg.py
  tests/test_youtube_ffmpeg_visual_playlist.py
  tests/test_youtube_render_supersede.py
  tests/test_music_audio.py
  tests/test_music_duration.py
  tests/test_music_overlay.py
  tests/test_music_providers.py
  tests/test_music_render_smoke.py
  tests/test_music_service.py
  tests/test_chapter_builder.py
  tests/test_subtitle_builder.py
  tests/test_caption_word_timing.py
  tests/test_spectrum_bars.py
  tests/test_spectrum_filter.py
  tests/test_thumbnail_generation.py
  tests/test_tts_router_timing.py
  tests/pipeline/test_concat.py
  tests/pipeline/test_sfx_scheduler.py
)

for f in "${FILES[@]}"; do
  if grep -q "pytestmark = pytest.mark.render" "$f"; then
    echo "skip (already tagged): $f"
    continue
  fi
  # Use python for a precise insert: after last top-level import/from line.
  python3 - "$f" <<'PY'
import sys, re, pathlib
p = pathlib.Path(sys.argv[1])
src = p.read_text().splitlines(keepends=False)
last_import = -1
for i, line in enumerate(src):
    if re.match(r"^(import |from )\S", line):
        last_import = i
if last_import < 0:
    # No imports: put after module docstring/comments at top.
    insert_at = 0
else:
    insert_at = last_import + 1
# Ensure `import pytest` is present.
has_pytest_import = any(
    re.match(r"^(import pytest\b|from pytest\b)", line) for line in src
)
new_lines = []
if not has_pytest_import:
    new_lines.append("import pytest")
new_lines.append("")
new_lines.append("pytestmark = pytest.mark.render")
new_lines.append("")
out = src[:insert_at] + new_lines + src[insert_at:]
p.write_text("\n".join(out) + "\n")
print(f"tagged: {p}")
PY
done
```

- [ ] **Step 2: Verify each file has the marker exactly once**

Run:

```bash
for f in tests/test_composer_music.py tests/test_composer_subtitles.py tests/test_renderer_ass.py tests/test_youtube_ffmpeg.py tests/test_youtube_ffmpeg_visual_playlist.py tests/test_youtube_render_supersede.py tests/test_music_audio.py tests/test_music_duration.py tests/test_music_overlay.py tests/test_music_providers.py tests/test_music_render_smoke.py tests/test_music_service.py tests/test_chapter_builder.py tests/test_subtitle_builder.py tests/test_caption_word_timing.py tests/test_spectrum_bars.py tests/test_spectrum_filter.py tests/test_thumbnail_generation.py tests/test_tts_router_timing.py tests/pipeline/test_concat.py tests/pipeline/test_sfx_scheduler.py; do
  count=$(grep -c "pytestmark = pytest.mark.render" "$f")
  if [ "$count" != "1" ]; then echo "BAD ($count): $f"; fi
done
echo "done"
```

Expected: only `done` printed. Any `BAD` line means the file has 0 or >1 markers — fix manually.

- [ ] **Step 3: Verify render tests are now collected under the marker**

Run: `pytest --collect-only -q -m render tests/ 2>&1 | tail -20`

Expected: a summary line like `NN tests collected in M.MMs` where `NN` ≥ ~50 (the render files contain multiple tests each). Zero collected means the marker isn't being applied.

- [ ] **Step 4: Verify backend slice excludes them**

Run: `pytest --collect-only -q -m "not render" tests/ console/backend/tests/ 2>&1 | tail -20`

Expected: a much larger collection count, and **none** of the test IDs should start with the file paths from Step 1's list.

Spot check:

```bash
pytest --collect-only -q -m "not render" tests/ 2>&1 | grep "test_renderer_ass" || echo "correctly excluded"
```

Expected: `correctly excluded`.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: mark render-suite test files with pytest.mark.render"
```

---

## Task 3: Create `tests/fixtures/` package

**Files:**
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/llm.py`
- Create: `tests/fixtures/youtube.py`
- Create: `tests/fixtures/ffmpeg.py`
- Create: `tests/fixtures/elevenlabs.py`
- Create: `tests/fixtures/test_fixtures_smoke.py`

- [ ] **Step 1: Create the package init**

Create `/Volumes/SSD/Workspace/ai-media-automation/tests/fixtures/__init__.py`:

```python
"""Reusable mock factories for tests.

These produce canned responses that mimic the shape of real API responses
without making any network calls. Adopt them in new tests instead of
re-rolling MagicMock setups.
"""
```

- [ ] **Step 2: Create `tests/fixtures/llm.py`**

```python
"""Canned LLM responses (Gemini, Ollama)."""
from __future__ import annotations


def gemini_text_response(text: str = "ok") -> dict:
    """Shape returned by google-genai's `generate_content` (.text accessor)."""
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}], "role": "model"},
                "finish_reason": "STOP",
            }
        ],
        "usage_metadata": {
            "prompt_token_count": 10,
            "candidates_token_count": 5,
            "total_token_count": 15,
        },
    }


def ollama_chat_response(content: str = "ok", model: str = "qwen2.5") -> dict:
    """Shape returned by Ollama's /api/chat endpoint."""
    return {
        "model": model,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "total_duration": 1_000_000,
        "eval_count": 5,
    }
```

- [ ] **Step 3: Create `tests/fixtures/youtube.py`**

```python
"""Canned YouTube Data API v3 responses."""
from __future__ import annotations


def video_resource(video_id: str = "abc123", title: str = "Test Video") -> dict:
    """Shape returned by youtube.videos().insert() and .list()."""
    return {
        "kind": "youtube#video",
        "id": video_id,
        "snippet": {
            "title": title,
            "description": "test description",
            "tags": ["test"],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "private", "uploadStatus": "uploaded"},
        "statistics": {"viewCount": "0", "likeCount": "0"},
    }


def upload_progress(percent: int = 100) -> dict:
    """Shape used internally by the resumable uploader's status callback."""
    return {"progress": percent / 100.0, "resumable_progress": percent, "total_size": 100}
```

- [ ] **Step 4: Create `tests/fixtures/ffmpeg.py`**

```python
"""Canned ffmpeg/ffprobe stubs."""
from __future__ import annotations


def ffprobe_video(duration_s: float = 30.0, width: int = 1080, height: int = 1920) -> dict:
    """Shape returned by `ffprobe -v quiet -print_format json -show_streams -show_format`."""
    return {
        "streams": [
            {
                "index": 0,
                "codec_name": "h264",
                "codec_type": "video",
                "width": width,
                "height": height,
                "r_frame_rate": "30/1",
                "duration": str(duration_s),
            },
            {
                "index": 1,
                "codec_name": "aac",
                "codec_type": "audio",
                "sample_rate": "44100",
                "channels": 2,
                "duration": str(duration_s),
            },
        ],
        "format": {
            "filename": "test.mp4",
            "duration": str(duration_s),
            "size": str(int(duration_s * 100_000)),
            "bit_rate": "800000",
        },
    }


def silent_wav_bytes(duration_s: float = 1.0, sample_rate: int = 44100) -> bytes:
    """Minimal valid WAV header + silence. Use when a test only needs *some* WAV bytes."""
    import struct

    n_samples = int(duration_s * sample_rate)
    data_bytes = n_samples * 2  # 16-bit mono
    header = b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_bytes)
    return header + b"\x00" * data_bytes
```

- [ ] **Step 5: Create `tests/fixtures/elevenlabs.py`**

```python
"""Canned ElevenLabs music/SFX responses."""
from __future__ import annotations


def music_generation_response(track_id: str = "music-1") -> dict:
    """Shape returned by ElevenLabs music generation REST endpoint."""
    return {
        "id": track_id,
        "status": "completed",
        "audio_url": f"https://example.test/audio/{track_id}.mp3",
        "duration_s": 180.0,
    }


def sfx_generation_response(sfx_id: str = "sfx-1") -> dict:
    """Shape returned by ElevenLabs SFX generation endpoint."""
    return {
        "id": sfx_id,
        "status": "completed",
        "audio_url": f"https://example.test/sfx/{sfx_id}.mp3",
        "duration_s": 4.0,
    }
```

- [ ] **Step 6: Create the smoke test**

Create `/Volumes/SSD/Workspace/ai-media-automation/tests/fixtures/test_fixtures_smoke.py`:

```python
"""Smoke tests proving each fixture module imports and produces sensible output."""
from tests.fixtures import llm, youtube, ffmpeg, elevenlabs


def test_gemini_text_response_has_text():
    r = llm.gemini_text_response("hello")
    assert r["candidates"][0]["content"]["parts"][0]["text"] == "hello"


def test_ollama_chat_response_has_content():
    r = llm.ollama_chat_response("hi", model="m")
    assert r["message"]["content"] == "hi"
    assert r["model"] == "m"


def test_youtube_video_resource_has_id():
    r = youtube.video_resource("xyz", "T")
    assert r["id"] == "xyz"
    assert r["snippet"]["title"] == "T"


def test_youtube_upload_progress_pct():
    r = youtube.upload_progress(50)
    assert r["resumable_progress"] == 50
    assert r["progress"] == 0.5


def test_ffprobe_video_shape():
    r = ffmpeg.ffprobe_video(duration_s=10.0, width=1280, height=720)
    assert r["streams"][0]["width"] == 1280
    assert r["streams"][0]["height"] == 720
    assert float(r["format"]["duration"]) == 10.0


def test_silent_wav_bytes_starts_with_riff():
    b = ffmpeg.silent_wav_bytes(duration_s=0.1)
    assert b[:4] == b"RIFF"
    assert b[8:12] == b"WAVE"


def test_elevenlabs_music_response_has_url():
    r = elevenlabs.music_generation_response("m1")
    assert r["id"] == "m1"
    assert r["audio_url"].endswith("m1.mp3")


def test_elevenlabs_sfx_response_has_url():
    r = elevenlabs.sfx_generation_response("s1")
    assert r["id"] == "s1"
    assert r["audio_url"].endswith("s1.mp3")
```

- [ ] **Step 7: Run the smoke tests**

Run: `pytest tests/fixtures/test_fixtures_smoke.py -v`

Expected: 8 tests pass.

- [ ] **Step 8: Commit**

```bash
git add tests/fixtures/
git commit -m "test: add tests/fixtures/ package with reusable mock factories"
```

---

## Task 4: MCP workflow

**Files:**
- Create: `.github/workflows/mcp.yml`

- [ ] **Step 1: Write the workflow**

Create `/Volumes/SSD/Workspace/ai-media-automation/.github/workflows/mcp.yml`:

```yaml
name: MCP Tests

on:
  pull_request:
    paths:
      - 'console/mcp/**'
      - 'requirements.mcp.txt'
      - '.github/workflows/mcp.yml'
  push:
    branches: [main]
    paths:
      - 'console/mcp/**'
      - 'requirements.mcp.txt'
      - '.github/workflows/mcp.yml'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      MCP_API_TOKEN: test-token
      MCP_CONSOLE_API_BASE: http://test
      MCP_LOG_LEVEL: debug
      MCP_IDEMPOTENCY_TTL_S: '3600'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: requirements.mcp.txt

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.mcp.txt
          pip install pytest pytest-asyncio respx

      - name: Run MCP tests
        run: pytest console/mcp/tests/ -v
```

- [ ] **Step 2: Validate YAML syntax locally**

Run:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/mcp.yml')); print('ok')"
```

Expected: `ok`. Any traceback means a YAML syntax error — fix and re-run.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/mcp.yml
git commit -m "ci: add MCP test workflow"
```

---

## Task 5: Frontend workflow

**Files:**
- Create: `.github/workflows/frontend.yml`

- [ ] **Step 1: Write the workflow**

Create `/Volumes/SSD/Workspace/ai-media-automation/.github/workflows/frontend.yml`:

```yaml
name: Frontend Tests

on:
  pull_request:
    paths:
      - 'console/frontend/**'
      - '.github/workflows/frontend.yml'
  push:
    branches: [main]
    paths:
      - 'console/frontend/**'
      - '.github/workflows/frontend.yml'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: console/frontend
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: console/frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Run tests
        run: npm test
```

- [ ] **Step 2: Validate YAML syntax**

Run:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/frontend.yml')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Sanity-check `npm test` works locally**

Run:

```bash
cd console/frontend && npm ci && npm run build && npm test
```

Expected: build succeeds and at least the existing `seoJsonUtils.test.js` passes. If `npm ci` fails because no `package-lock.json` exists, run `npm install` first to generate one and commit it (`console/frontend/package-lock.json`).

- [ ] **Step 4: Commit**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
git add .github/workflows/frontend.yml
# Also add console/frontend/package-lock.json if it was just generated.
git status console/frontend/package-lock.json
git commit -m "ci: add frontend test workflow"
```

---

## Task 6: Backend workflow

**Files:**
- Create: `.github/workflows/backend.yml`

- [ ] **Step 1: Write the workflow**

Create `/Volumes/SSD/Workspace/ai-media-automation/.github/workflows/backend.yml`. The `FERNET_KEY` below was pre-generated for tests — it is a valid Fernet key but is not used to encrypt any real data.

```yaml
name: Backend Tests

on:
  pull_request:
    paths:
      - 'console/backend/**'
      - 'console/requirements.txt'
      - 'requirements.pipeline.txt'
      - 'tests/**'
      - 'database/**'
      - 'rag/**'
      - 'uploader/**'
      - 'feedback/**'
      - 'pytest.ini'
      - '.github/workflows/backend.yml'
  push:
    branches: [main]
    paths:
      - 'console/backend/**'
      - 'console/requirements.txt'
      - 'requirements.pipeline.txt'
      - 'tests/**'
      - 'database/**'
      - 'rag/**'
      - 'uploader/**'
      - 'feedback/**'
      - 'pytest.ini'
      - '.github/workflows/backend.yml'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest

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
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    env:
      TEST_DATABASE_URL: postgresql://admin:testpw@localhost:5432/ai_media_test
      DATABASE_URL: postgresql://admin:testpw@localhost:5432/ai_media_test
      REDIS_URL: redis://localhost:6379/0
      GEMINI_API_KEY: test
      GEMINI_MEDIA_API_KEY: test
      PEXELS_API_KEY: test
      ELEVENLABS_API_KEY: test
      RUNWAY_API_KEY: test
      YOUTUBE_API_KEY: test
      FERNET_KEY: 'xSDP9q3SS0jLfBLDhDDJZfaKH5WSoGUlJksXIdoaC_A='
      JWT_SECRET: test-jwt-secret

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: |
            console/requirements.txt
            requirements.pipeline.txt

      - name: System deps for Python wheels
        run: sudo apt-get update && sudo apt-get install -y libsndfile1 libgomp1 ffmpeg

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r console/requirements.txt

      - name: Run alembic migrations
        working-directory: console/backend
        run: alembic upgrade head

      - name: Run backend tests
        run: pytest -m "not render and not slow and not manual" tests/ console/backend/tests/ -v
```

- [ ] **Step 2: Validate YAML syntax**

Run:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/backend.yml')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Sanity-check the test command parses**

Run:

```bash
pytest --collect-only -q -m "not render and not slow and not manual" tests/ console/backend/tests/ 2>&1 | tail -3
```

Expected: a summary line showing collected tests (large number). Errors in collection point to import-time failures that the workflow will also hit — investigate before pushing.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/backend.yml
git commit -m "ci: add backend test workflow with postgres + redis services"
```

---

## Task 7: Render workflow

**Files:**
- Create: `.github/workflows/render.yml`

- [ ] **Step 1: Write the workflow**

Create `/Volumes/SSD/Workspace/ai-media-automation/.github/workflows/render.yml`:

```yaml
name: Render Tests

on:
  pull_request:
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
      - 'console/requirements.txt'
      - 'pytest.ini'
      - '.github/workflows/render.yml'
  push:
    branches: [main]
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
      - 'console/requirements.txt'
      - 'pytest.ini'
      - '.github/workflows/render.yml'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      GEMINI_API_KEY: test
      GEMINI_MEDIA_API_KEY: test
      PEXELS_API_KEY: test
      ELEVENLABS_API_KEY: test
      RUNWAY_API_KEY: test
      YOUTUBE_API_KEY: test
      FERNET_KEY: 'xSDP9q3SS0jLfBLDhDDJZfaKH5WSoGUlJksXIdoaC_A='
      JWT_SECRET: test-jwt-secret

    steps:
      - uses: actions/checkout@v4

      - name: System deps (ffmpeg + audio libs)
        run: sudo apt-get update && sudo apt-get install -y ffmpeg libsndfile1 libgomp1

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: |
            console/requirements.txt
            requirements.pipeline.txt

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r console/requirements.txt

      - name: Run render tests
        run: pytest -m render tests/ -v
```

- [ ] **Step 2: Validate YAML syntax**

Run:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/render.yml')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Sanity-check render collection locally**

Run:

```bash
pytest --collect-only -q -m render tests/ 2>&1 | tail -3
```

Expected: a summary line showing collected render tests (~50+).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/render.yml
git commit -m "ci: add render test workflow with ffmpeg and pytest -m render"
```

---

## Task 8: Push and verify on GitHub Actions

**Files:** none

- [ ] **Step 1: Push the branch**

```bash
git push -u origin ci/test-workflows
```

- [ ] **Step 2: Open a draft PR**

```bash
gh pr create --draft --title "ci: add test workflows for backend, frontend, render, mcp" --body "$(cat <<'EOF'
## Summary
- Adds four GitHub Actions workflows that run the existing test suite per component
- Registers pytest markers and tags the render-suite test files so the backend job excludes them
- Adds `tests/fixtures/` package with reusable mock factories for future tests

Spec: docs/superpowers/specs/2026-05-16-ci-tests-workflow-design.md
Plan: docs/superpowers/plans/2026-05-16-ci-tests-workflow.md

## Test plan
- [ ] Backend workflow runs and passes
- [ ] Frontend workflow runs and passes
- [ ] Render workflow runs and passes
- [ ] MCP workflow runs and passes
- [ ] Path filters work (touch a single file in one component, only that workflow runs)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Watch the four workflows**

```bash
gh run list --branch ci/test-workflows --limit 10
gh run watch
```

Expected: four workflow runs (Backend Tests, Frontend Tests, Render Tests, MCP Tests). All four should complete green.

- [ ] **Step 4: Investigate any failures**

For each red workflow:

```bash
gh run view --log-failed
```

Common failure modes and fixes:

- **Backend, alembic fails:** check `console/backend/alembic.ini` and the `script_location` path. The workflow `cd`s into `console/backend` before running `alembic upgrade head`.
- **Backend, import error in tests:** an env var the test reads at import time is missing. Add it to the `env:` block.
- **Render, missing system lib:** add to the `apt-get install` line.
- **MCP, fixture import error:** check the `MCP_*` env vars match those in `console/mcp/tests/conftest.py`.
- **Frontend, `npm ci` fails:** ensure `package-lock.json` is committed.

Fix the workflow file, push again, re-watch. Do not merge until all four are green.

- [ ] **Step 5: Verify path filters by touching a single file**

Make a no-op edit to `console/frontend/src/main.jsx` (e.g., add and remove a blank line), commit, push:

```bash
echo "" >> console/frontend/src/main.jsx
git add console/frontend/src/main.jsx
git commit -m "test: trigger frontend-only CI"
git push
gh run list --branch ci/test-workflows --limit 4
```

Expected: only `Frontend Tests` runs. If others fire too, the path filters need tightening.

Revert the no-op:

```bash
git revert --no-edit HEAD
git push
```

- [ ] **Step 6: Mark PR ready for review**

```bash
gh pr ready
```

---

## Self-review notes (already applied)

- **Spec coverage:** every numbered section in the spec maps to a task here. Spec section 1 (workflow structure) → Tasks 4-7. Section 2 (per-workflow steps) → embedded in each task. Section 3 (integration mocking) → Tasks 1, 3 (markers + fixtures). Section 4 (cross-cutting concurrency, caching, secrets) → embedded in each workflow YAML. Section 5 (out of scope) → respected (no coverage gates, no lint, no E2E added).
- **Placeholder scan:** no `TBD`/`TODO`/"add appropriate"; the `FERNET_KEY` placeholder from the spec was replaced with a pre-generated key in the plan.
- **Type consistency:** marker name `render` used identically in `pytest.ini`, in the per-file `pytestmark`, and in both `-m render` (render job) and `-m "not render"` (backend job). Workflow filename pattern (`backend.yml`, `frontend.yml`, `render.yml`, `mcp.yml`) used consistently in references.
