# Cancel YouTube Video Celery Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revoke all Celery tasks (chunk renders + concat callback) when a YouTube video is cancelled or deleted, and transition the video to `"failed"` status.

**Architecture:** Pre-generate task UUIDs in the orchestrator and store them in `render_parts[*].task_id` (JSONB, no migration needed) before dispatching the chord. Repurpose `celery_task_id` to track the concat callback task ID (the orchestrator exits immediately, making its own ID useless). At cancel/delete time, revoke all stored IDs with `terminate=True`. Chunk and concat tasks check `video.status == "failed"` at start and return early if cancelled.

**Tech Stack:** Celery `control.revoke`, SQLAlchemy JSONB `flag_modified`, Python `uuid.uuid4`

---

## File Map

| File | Change |
|---|---|
| `console/backend/services/youtube_video_service.py` | Replace `_revoke_active_render_jobs` → `_revoke_all_render_jobs`; fix `cancel_chunked_render`; fix `delete_video`; update `resume_chunked_render` call site |
| `console/backend/tasks/youtube_render_task.py` | Orchestrator: pre-generate UUIDs; chunk task: add status guard; concat task: add status guard |
| `tests/test_youtube_cancel_tasks.py` | New test file (create) |

---

### Task 1: Add `_revoke_all_render_jobs` service method

**Files:**
- Modify: `console/backend/services/youtube_video_service.py:501-510`
- Test: `tests/test_youtube_cancel_tasks.py` (create)

- [ ] **Step 1: Write failing tests**

Create `tests/test_youtube_cancel_tasks.py`:

```python
"""Tests for cancel-all-tasks: revoke all chunk + concat Celery task IDs on cancel/delete."""
from unittest.mock import MagicMock, patch


def _make_video(parts=None, celery_task_id=None, status="rendering"):
    v = MagicMock()
    v.id = 42
    v.status = status
    v.celery_task_id = celery_task_id
    v.render_parts = parts or []
    return v


def test_revoke_all_render_jobs_revokes_each_chunk_task_id():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)

    video = _make_video(
        parts=[
            {"idx": 0, "task_id": "chunk-uuid-0", "status": "completed"},
            {"idx": 1, "task_id": "chunk-uuid-1", "status": "running"},
            {"idx": 2, "task_id": "chunk-uuid-2", "status": "pending"},
        ],
        celery_task_id="concat-uuid",
    )

    with patch("console.backend.celery_app.celery_app.control.revoke") as mock_revoke:
        svc._revoke_all_render_jobs(video)

    revoked = {c.args[0] for c in mock_revoke.call_args_list}
    assert "chunk-uuid-0" in revoked
    assert "chunk-uuid-1" in revoked
    assert "chunk-uuid-2" in revoked
    assert "concat-uuid" in revoked
    for c in mock_revoke.call_args_list:
        assert c.kwargs.get("terminate") is True


def test_revoke_all_render_jobs_skips_parts_without_task_id():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)

    video = _make_video(
        parts=[{"idx": 0, "status": "pending"}],  # no task_id key
        celery_task_id=None,
    )

    with patch("console.backend.celery_app.celery_app.control.revoke") as mock_revoke:
        svc._revoke_all_render_jobs(video)

    mock_revoke.assert_not_called()


def test_revoke_all_render_jobs_handles_empty_render_parts():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)

    video = _make_video(parts=None, celery_task_id="concat-uuid")

    with patch("console.backend.celery_app.celery_app.control.revoke") as mock_revoke:
        svc._revoke_all_render_jobs(video)

    mock_revoke.assert_called_once_with("concat-uuid", terminate=True, signal="SIGTERM")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python -m pytest tests/test_youtube_cancel_tasks.py -v
```

Expected: FAIL with `AttributeError: 'YoutubeVideoService' object has no attribute '_revoke_all_render_jobs'`

- [ ] **Step 3: Replace `_revoke_active_render_jobs` with `_revoke_all_render_jobs`**

In `console/backend/services/youtube_video_service.py`, replace lines 501–510 (the entire `_revoke_active_render_jobs` method):

```python
def _revoke_all_render_jobs(self, video: YoutubeVideo) -> None:
    """Revoke all chunk task IDs stored in render_parts, plus the concat callback."""
    from console.backend.celery_app import celery_app
    for part in (video.render_parts or []):
        task_id = part.get("task_id")
        if task_id:
            celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    if video.celery_task_id:
        celery_app.control.revoke(video.celery_task_id, terminate=True, signal="SIGTERM")
```

Also update the call site in `resume_chunked_render` at line 583. Change:

```python
self._revoke_active_render_jobs(video_id)
```

to:

```python
self._revoke_all_render_jobs(v)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_youtube_cancel_tasks.py console/backend/services/youtube_video_service.py
git commit -m "feat: add _revoke_all_render_jobs to revoke all chunk + concat task IDs"
```

---

### Task 2: Fix `cancel_chunked_render`

**Files:**
- Modify: `console/backend/services/youtube_video_service.py:596-602`
- Test: `tests/test_youtube_cancel_tasks.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_youtube_cancel_tasks.py`:

```python
def test_cancel_chunked_render_sets_status_to_failed():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(
        parts=[
            {"idx": 0, "task_id": "t0", "status": "completed"},
            {"idx": 1, "task_id": "t1", "status": "running"},
        ],
        celery_task_id="concat-uuid",
        status="rendering",
    )
    db.get.return_value = video

    result = svc.cancel_chunked_render(video_id=42)

    assert result["status"] == "failed"
    assert video.status == "failed"


def test_cancel_chunked_render_marks_non_completed_parts_cancelled():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(
        parts=[
            {"idx": 0, "status": "completed"},
            {"idx": 1, "status": "running"},
            {"idx": 2, "status": "pending"},
        ],
        celery_task_id="concat-uuid",
        status="rendering",
    )
    db.get.return_value = video

    svc.cancel_chunked_render(video_id=42)

    statuses = {p["idx"]: p["status"] for p in video.render_parts}
    assert statuses[0] == "completed"  # preserved
    assert statuses[1] == "cancelled"
    assert statuses[2] == "cancelled"


def test_cancel_chunked_render_clears_celery_task_id():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(celery_task_id="some-uuid", status="rendering")
    db.get.return_value = video

    svc.cancel_chunked_render(video_id=42)

    assert video.celery_task_id is None


def test_cancel_chunked_render_calls_revoke_all():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(status="rendering")
    db.get.return_value = video

    svc.cancel_chunked_render(video_id=42)

    svc._revoke_all_render_jobs.assert_called_once_with(video)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py::test_cancel_chunked_render_sets_status_to_failed -v
```

Expected: FAIL — current implementation returns `"video_preview_ready"` or `"queued"`, not `"failed"`

- [ ] **Step 3: Fix `cancel_chunked_render`**

In `console/backend/services/youtube_video_service.py`, replace lines 596–602:

```python
# REMOVE this entire method:
def cancel_chunked_render(self, video_id: int, user_id: int | None = None) -> dict:
    v = self._load_video_or_404(video_id)
    self._revoke_active_render_jobs(video_id)
    v.status = "video_preview_ready" if v.video_preview_path else "queued"
    _audit(self.db, user_id, "cancel_chunked_render", "youtube_video", str(video_id))
    self.db.commit()
    return {"status": v.status}
```

Replace with:

```python
def cancel_chunked_render(self, video_id: int, user_id: int | None = None) -> dict:
    from sqlalchemy.orm.attributes import flag_modified
    v = self._load_video_or_404(video_id)
    self._revoke_all_render_jobs(v)
    v.status = "failed"
    parts = list(v.render_parts or [])
    for p in parts:
        if p.get("status") != "completed":
            p["status"] = "cancelled"
    v.render_parts = parts
    flag_modified(v, "render_parts")
    v.celery_task_id = None
    _audit(self.db, user_id, "cancel_chunked_render", "youtube_video", str(video_id))
    self.db.commit()
    return {"status": v.status}
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py -v
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_youtube_cancel_tasks.py console/backend/services/youtube_video_service.py
git commit -m "fix(cancel): cancel_chunked_render transitions to failed and marks parts cancelled"
```

---

### Task 3: Fix `delete_video` to revoke all tasks

**Files:**
- Modify: `console/backend/services/youtube_video_service.py:391-406`
- Test: `tests/test_youtube_cancel_tasks.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_youtube_cancel_tasks.py`:

```python
def test_delete_video_revokes_all_render_jobs():
    from console.backend.services.youtube_video_service import YoutubeVideoService
    db = MagicMock()
    svc = YoutubeVideoService(db)
    svc._revoke_all_render_jobs = MagicMock()

    video = _make_video(
        parts=[{"idx": 0, "task_id": "t0", "status": "running"}],
        celery_task_id="concat-uuid",
        status="rendering",
    )
    db.get.return_value = video

    svc.delete_video(video_id=42)

    svc._revoke_all_render_jobs.assert_called_once_with(video)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py::test_delete_video_revokes_all_render_jobs -v
```

Expected: FAIL — current implementation calls `celery_app.control.revoke(v.celery_task_id)` only (and only when status in `{"queued", "rendering"}`)

- [ ] **Step 3: Fix `delete_video`**

In `console/backend/services/youtube_video_service.py`, replace lines 391–406:

```python
# REMOVE this entire method:
def delete_video(self, video_id: int, user_id: int | None = None) -> None:
    v = self.db.get(YoutubeVideo, video_id)
    if not v:
        raise KeyError(f"YoutubeVideo {video_id} not found")
    # Revoke active Celery task if video is queued or rendering
    if v.celery_task_id and v.status in {"queued", "rendering"}:
        from console.backend.celery_app import celery_app
        celery_app.control.revoke(v.celery_task_id, terminate=True)
    try:
        _audit(self.db, user_id, "delete_video", "youtube_video", str(video_id),
               {"title": v.title})
        self.db.delete(v)
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise
```

Replace with:

```python
def delete_video(self, video_id: int, user_id: int | None = None) -> None:
    v = self.db.get(YoutubeVideo, video_id)
    if not v:
        raise KeyError(f"YoutubeVideo {video_id} not found")
    self._revoke_all_render_jobs(v)
    try:
        _audit(self.db, user_id, "delete_video", "youtube_video", str(video_id),
               {"title": v.title})
        self.db.delete(v)
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_youtube_cancel_tasks.py console/backend/services/youtube_video_service.py
git commit -m "fix(delete): revoke all chunk + concat task IDs on video delete"
```

---

### Task 4: Orchestrator — pre-generate chunk and concat task UUIDs

**Files:**
- Modify: `console/backend/tasks/youtube_render_task.py:388-462`
- Test: `tests/test_youtube_cancel_tasks.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_youtube_cancel_tasks.py`:

```python
def test_orchestrator_writes_task_ids_before_chord_dispatch():
    """render_parts must have task_id populated and committed BEFORE chord dispatch."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.celery_task_id = "old-orch-id"
    video.sfx_seed = 1  # non-None → skips random.randint branch
    video.target_duration_h = 1 / 60  # 60s → 1 chunk
    video.render_parts = None
    video.status = "rendering"

    db = MagicMock()
    db.get.return_value = video

    write_order = []
    committed_state = {}

    def on_commit():
        if not committed_state:
            committed_state["parts"] = list(video.render_parts or [])
            committed_state["celery_task_id"] = video.celery_task_id
        write_order.append("commit")
    db.commit.side_effect = on_commit

    mock_chord_partial = MagicMock(side_effect=lambda _sig: write_order.append("dispatch"))
    mock_chord_cls = MagicMock(return_value=mock_chord_partial)

    # chord and group are imported inside the function body (`from celery import chord, group`),
    # so patch them at the celery module level, not at the task module level.
    with patch("console.backend.tasks.youtube_render_task.SessionLocal", return_value=db), \
         patch("console.backend.tasks.youtube_render_task._is_superseded", return_value=False), \
         patch("celery.chord", mock_chord_cls), \
         patch("celery.group", MagicMock()), \
         patch("sqlalchemy.orm.attributes.flag_modified"):
        from console.backend.tasks.youtube_render_task import render_youtube_chunked_orchestrator_task
        render_youtube_chunked_orchestrator_task.apply(args=[42])

    # commit must precede dispatch
    assert "commit" in write_order, "orchestrator must commit before dispatching"
    assert "dispatch" in write_order, "orchestrator must dispatch chord"
    assert write_order.index("commit") < write_order.index("dispatch"), \
        f"commit must precede dispatch; got order: {write_order}"

    # all pending parts must have task_id at commit time
    for p in committed_state["parts"]:
        assert p.get("task_id"), f"part {p.get('idx')} missing task_id at commit time"

    # celery_task_id must have changed from old orch ID to concat UUID
    assert committed_state["celery_task_id"] != "old-orch-id"
    assert committed_state["celery_task_id"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py::test_orchestrator_writes_task_ids_before_chord_dispatch -v
```

Expected: FAIL — committed_state["parts"] have no `task_id` key with current code

- [ ] **Step 3: Update orchestrator to pre-generate task UUIDs**

In `console/backend/tasks/youtube_render_task.py`, modify `render_youtube_chunked_orchestrator_task` (lines 393–462).

Add `from uuid import uuid4` to the imports inside the function (after the existing imports at the top of the function body).

Replace the section from the `pending` check down to the chord dispatch (lines 440–449):

```python
# REMOVE this block:
pending = [p for p in new_parts if p["status"] != "completed"]
if not pending:
    concat_youtube_chunks_task.delay([], youtube_video_id)
    return {"status": "all-completed", "n_chunks": n_chunks}

sigs = [
    render_youtube_chunk_task.s(youtube_video_id, p["idx"], p["start_s"], p["end_s"])
    for p in pending
]
chord(group(sigs))(concat_youtube_chunks_task.s(youtube_video_id))
return {"status": "dispatched", "n_chunks": n_chunks, "pending": len(pending)}
```

Replace with:

```python
from uuid import uuid4

pending = [p for p in new_parts if p["status"] != "completed"]
concat_task_id = str(uuid4())

if not pending:
    # All chunks already completed — still need to track the concat task ID
    video.celery_task_id = concat_task_id
    db.commit()
    concat_youtube_chunks_task.apply_async(args=[[], youtube_video_id], task_id=concat_task_id)
    return {"status": "all-completed", "n_chunks": n_chunks}

# Assign a UUID to each pending chunk and write to render_parts BEFORE dispatch
for p in new_parts:
    if p["status"] != "completed":
        p["task_id"] = str(uuid4())
# Update celery_task_id to the concat callback UUID (orchestrator's own ID is useless after exit)
video.celery_task_id = concat_task_id
flag_modified(video, "render_parts")
db.commit()  # MUST commit before chord dispatch so cancel can find these IDs immediately

sigs = [
    render_youtube_chunk_task.s(youtube_video_id, p["idx"], p["start_s"], p["end_s"])
    .set(task_id=p["task_id"])
    for p in pending
]
concat_sig = concat_youtube_chunks_task.s(youtube_video_id).set(task_id=concat_task_id)
chord(group(sigs))(concat_sig)
return {"status": "dispatched", "n_chunks": n_chunks, "pending": len(pending)}
```

Note: the `flag_modified(video, "render_parts")` call is already imported at the top of the function body from `from sqlalchemy.orm.attributes import flag_modified`. No new import needed.

- [ ] **Step 4: Run all tests to verify they pass**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py -v
```

Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_youtube_cancel_tasks.py console/backend/tasks/youtube_render_task.py
git commit -m "feat(orchestrator): pre-generate chunk + concat task UUIDs and commit before dispatch"
```

---

### Task 5: Add status guard to chunk task

**Files:**
- Modify: `console/backend/tasks/youtube_render_task.py:266-330`
- Test: `tests/test_youtube_cancel_tasks.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_youtube_cancel_tasks.py`:

```python
def test_chunk_task_returns_early_when_video_is_failed():
    """render_youtube_chunk_task must not call render_landscape if video.status == 'failed'."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.status = "failed"

    db = MagicMock()
    db.get.return_value = video

    # The status guard returns before _update_chunk_status is called, so no need to patch it.
    with patch("console.backend.tasks.youtube_render_task.SessionLocal", return_value=db), \
         patch("pipeline.youtube_ffmpeg.render_landscape") as mock_render:
        from console.backend.tasks.youtube_render_task import render_youtube_chunk_task
        result = render_youtube_chunk_task.apply(args=[42, 0, 0.0, 300.0]).get()

    mock_render.assert_not_called()
    assert result["status"] == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py::test_chunk_task_returns_early_when_video_is_failed -v
```

Expected: FAIL — current code doesn't check video.status

- [ ] **Step 3: Add status guard to `render_youtube_chunk_task`**

In `console/backend/tasks/youtube_render_task.py`, in `render_youtube_chunk_task` (starts at line 273), add the status check immediately after the `if not video:` guard (after line 291):

```python
video = db.get(YoutubeVideo, youtube_video_id)
if not video:
    return {"status": "failed", "reason": "video not found"}

# Guard: bail early if video was cancelled or failed while this task was queued
if video.status == "failed":
    logger.info(
        "YoutubeVideo %s chunk %s skipped — video is failed/cancelled",
        youtube_video_id, chunk_idx,
    )
    return {"status": "skipped", "reason": "video cancelled"}
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py -v
```

Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_youtube_cancel_tasks.py console/backend/tasks/youtube_render_task.py
git commit -m "feat(chunk-task): skip execution when video is failed/cancelled"
```

---

### Task 6: Add status guard to concat task

**Files:**
- Modify: `console/backend/tasks/youtube_render_task.py:333-385`
- Test: `tests/test_youtube_cancel_tasks.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_youtube_cancel_tasks.py`:

```python
def test_concat_task_returns_early_when_video_is_failed():
    """concat_youtube_chunks_task must not call concat_parts if video.status == 'failed'."""
    from unittest.mock import patch, MagicMock

    video = MagicMock()
    video.id = 42
    video.status = "failed"

    db = MagicMock()
    db.get.return_value = video

    with patch("console.backend.tasks.youtube_render_task.SessionLocal", return_value=db), \
         patch("pipeline.concat.concat_parts") as mock_concat:
        from console.backend.tasks.youtube_render_task import concat_youtube_chunks_task
        result = concat_youtube_chunks_task.apply(args=[[], 42]).get()

    mock_concat.assert_not_called()
    assert result["status"] == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py::test_concat_task_returns_early_when_video_is_failed -v
```

Expected: FAIL — current code doesn't check video.status

- [ ] **Step 3: Add status guard to `concat_youtube_chunks_task`**

In `console/backend/tasks/youtube_render_task.py`, in `concat_youtube_chunks_task` (starts at line 338), add the status check immediately after the `if not video:` guard (after line 353):

```python
video = db.get(YoutubeVideo, youtube_video_id)
if not video:
    return {"status": "failed", "reason": "video not found"}

# Guard: bail early if video was cancelled while chunks were in flight
if video.status == "failed":
    logger.info(
        "YoutubeVideo %s concat skipped — video is failed/cancelled",
        youtube_video_id,
    )
    return {"status": "skipped", "reason": "video cancelled"}
```

- [ ] **Step 4: Run full test suite to verify all tests pass**

```bash
python -m pytest tests/test_youtube_cancel_tasks.py tests/test_youtube_render_supersede.py -v
```

Expected: All 11 + 5 = 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_youtube_cancel_tasks.py console/backend/tasks/youtube_render_task.py
git commit -m "feat(concat-task): skip execution when video is failed/cancelled"
```

---

## Verify end-to-end manually (optional, requires running stack)

```bash
# Start a chunked render
curl -X POST http://localhost:8080/api/youtube-videos/42/render

# Immediately cancel it
curl -X POST http://localhost:8080/api/youtube-videos/42/cancel-render

# Verify status is "failed"
curl http://localhost:8080/api/youtube-videos/42 | python -m json.tool | grep status

# Verify no ffmpeg processes are still running
ps aux | grep ffmpeg
```
