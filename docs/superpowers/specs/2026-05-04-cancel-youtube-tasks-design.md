# Design: Cancel All Celery Tasks for YouTube Video

**Date:** 2026-05-04  
**Status:** Approved  
**Files changed:** `console/backend/tasks/youtube_render_task.py`, `console/backend/services/youtube_video_service.py` only

---

## Problem

When a YouTube video is deleted or its rendering is cancelled from the frontend, only the orchestrator Celery task ID (`celery_task_id`) is revoked. The orchestrator dispatches a `chord(group(N chunk tasks), concat_callback)` and exits immediately — so revoking the orchestrator ID has no effect on the chunks already in the broker or running in workers.

Two additional bugs in `cancel_chunked_render`:
- Status is set to `"video_preview_ready"` or `"queued"` instead of `"failed"`
- Non-completed render_parts are not marked cancelled

**Result:** After cancel or delete, ffmpeg processes keep running for every in-flight chunk, burning CPU/GPU until they finish or time out.

---

## Approach

Approach A: pre-generate chunk task UUIDs in the orchestrator, store them in `render_parts[*].task_id` before dispatching the chord. At cancel/delete time, revoke all stored IDs. No DB migration (JSONB is schema-flexible).

---

## Design

### 1. Data model (no migration)

`render_parts` is a JSONB array. Each element gains a new `task_id` string field written by the orchestrator before dispatch:

```json
{
  "idx": 3,
  "start_s": 900,
  "end_s": 1200,
  "status": "pending",
  "task_id": "a1b2c3d4-..."
}
```

`video.celery_task_id` is repurposed from "orchestrator task ID" to "concat callback task ID". The orchestrator exits immediately after dispatch, making its own ID useless for revocation. The concat callback is the long-lived terminal task and is now the meaningful ID to track at the video level.

At cancel time, chunk task IDs come from `render_parts[*].task_id` and the concat ID comes from `video.celery_task_id`.

---

### 2. Orchestrator changes (`youtube_render_task.py`)

In `render_youtube_chunked_orchestrator_task`, before `chord().delay()`:

```python
from uuid import uuid4

# Pre-generate task IDs
chunk_task_ids = [str(uuid4()) for _ in chunks]
concat_task_id = str(uuid4())

# Write task IDs into render_parts before dispatch
for part, task_id in zip(video.render_parts, chunk_task_ids):
    part['task_id'] = task_id
video.celery_task_id = concat_task_id
flag_modified(video, 'render_parts')
db.commit()  # MUST commit before chord().delay()

# Build signatures with pre-assigned IDs
sigs = [
    render_youtube_chunk.s(video_id, part['idx'], part['start_s'], part['end_s'])
    .set(task_id=task_id)
    for part, task_id in zip(video.render_parts, chunk_task_ids)
]
concat_sig = concat_youtube_chunks_task.s(video_id).set(task_id=concat_task_id)
chord(group(sigs), concat_sig).delay()
```

**Why commit before dispatch:** A fast worker could pick up a chunk before the DB write, making it unrevocable. Writing first guarantees the IDs are queryable the instant chunks enter the broker.

---

### 3. Revocation helper + cancel/delete (`youtube_video_service.py`)

Replace `_revoke_active_render_jobs` with `_revoke_all_render_jobs`:

```python
def _revoke_all_render_jobs(self, video: YoutubeVideo) -> None:
    for part in (video.render_parts or []):
        task_id = part.get('task_id')
        if task_id:
            celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
    if video.celery_task_id:
        celery_app.control.revoke(video.celery_task_id, terminate=True, signal='SIGTERM')
```

`cancel_chunked_render` updated to:
1. Call `_revoke_all_render_jobs(video)`
2. Transition status to `"failed"` via `_transition_status`
3. Mark all non-completed render_parts as cancelled:
   ```python
   for part in (video.render_parts or []):
       if part.get('status') != 'completed':
           part['status'] = 'cancelled'
   flag_modified(video, 'render_parts')
   ```
4. Set `video.celery_task_id = None`
5. Commit

`delete_video` updated to call `_revoke_all_render_jobs(video)` before the existing deletion logic. No other changes to the delete flow.

---

### 4. Supersede guard in chunk and concat tasks

`_is_superseded` currently compares `task.request.id == video.celery_task_id`. After the change, `celery_task_id` holds the concat UUID, so this comparison is always false for chunk tasks.

Replace with a status check at task start in both `render_youtube_chunk` and `concat_youtube_chunks_task`:

```python
# At task start, after loading video from DB
if video.status == "failed":
    logger.info(f"Chunk {chunk_idx} skipped — video {video_id} is cancelled/failed")
    return
```

This is simpler and more robust: tasks already mid-ffmpeg are terminated by `revoke(terminate=True)` via SIGTERM; tasks that haven't started their work yet bail cleanly on the status check.

The orchestrator-level `_is_superseded` check (comparing orchestrator ID) can be removed — the orchestrator runs exactly once and exits, so there is nothing to supersede at that level.

---

## Change Summary

| What | Location | Change |
|---|---|---|
| Add `task_id` to render_parts entries | `render_youtube_chunked_orchestrator_task` | Pre-generate UUIDs, write before dispatch |
| Store concat task ID | `render_youtube_chunked_orchestrator_task` | Set `video.celery_task_id = concat_task_id` |
| Replace revoke helper | `youtube_video_service.py` | `_revoke_all_render_jobs` iterates render_parts + concat ID |
| Fix cancel status | `cancel_chunked_render` | Transition to `"failed"`, mark parts `"cancelled"` |
| Fix delete revocation | `delete_video` | Call `_revoke_all_render_jobs` before deletion |
| Update supersede guard | `render_youtube_chunk`, `concat_youtube_chunks_task` | Status check replaces task ID comparison |

**Two files. Six focused edits. No schema migration.**

---

## What is NOT changed

- `render_portrait_short` — no chunking; untouched
- Frontend cancel/delete endpoints — status change is transparent; they already handle `"failed"`
- Celery chord dispatch pattern — same `chord(group(sigs), concat_sig)`, only UUIDs are pre-assigned
- `render_parts` schema for completed parts — `task_id` is additive; existing fields unchanged
