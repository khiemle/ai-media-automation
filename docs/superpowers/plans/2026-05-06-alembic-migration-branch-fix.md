# Alembic Migration Branch Conflict Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicate revision-016 and revision-017 migration files from `feature/n8n-youtube-workflow` so `alembic upgrade head` runs cleanly in Docker.

**Architecture:** The feature branch accumulated two migration files at each of revision "016" and "017" — one set from `main` (merged in) and one set the branch authored itself. The fix deletes the feature-branch-authored "016" duplicate (functionally identical to main's), then renumbers the feature-branch "017" (`skip_chunking`) to "018" so it chains cleanly after main's "017" (`composition_plan`). Final chain: `...015 → 016 (thumbnail) → 017 (composition_plan) → 018 (skip_chunking)`.

**Tech Stack:** Git, Alembic, PostgreSQL (`ADD COLUMN IF NOT EXISTS`)

---

### Task 1: Switch to the feature branch

**Files:**
- No file changes — branch checkout only

- [ ] **Step 1: Check out the feature branch**

```bash
git checkout feature/n8n-youtube-workflow
```

Expected output:
```
Switched to branch 'feature/n8n-youtube-workflow'
```

- [ ] **Step 2: Confirm the conflicting files are present**

```bash
ls console/backend/alembic/versions/ | sort
```

Expected: you should see both `016_youtube_thumbnail.py` AND `016_youtube_video_thumbnail_fields.py`, and both `017_music_track_composition_plan.py` AND `017_skip_chunking.py`.

- [ ] **Step 3: Verify current revision chain is broken**

```bash
cd console/backend && alembic heads
```

Expected: two heads listed (confirms the problem before we fix it). Then `cd ../..` to return to project root.

---

### Task 2: Delete the duplicate 016 migration

**Files:**
- Delete: `console/backend/alembic/versions/016_youtube_video_thumbnail_fields.py`

- [ ] **Step 1: Delete the duplicate file**

```bash
rm console/backend/alembic/versions/016_youtube_video_thumbnail_fields.py
```

- [ ] **Step 2: Confirm only one 016 file remains**

```bash
ls console/backend/alembic/versions/016*
```

Expected: only `016_youtube_thumbnail.py`.

---

### Task 3: Replace 017_skip_chunking.py with 018_skip_chunking.py

**Files:**
- Delete: `console/backend/alembic/versions/017_skip_chunking.py`
- Create: `console/backend/alembic/versions/018_skip_chunking.py`

- [ ] **Step 1: Delete the old 017 skip_chunking file**

```bash
rm console/backend/alembic/versions/017_skip_chunking.py
```

- [ ] **Step 2: Create 018_skip_chunking.py**

Create `console/backend/alembic/versions/018_skip_chunking.py` with this exact content:

```python
"""skip_chunking flag on youtube_videos

Revision ID: 018
Revises: 017
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE youtube_videos
            ADD COLUMN IF NOT EXISTS skip_chunking BOOLEAN NOT NULL DEFAULT false
    """)


def downgrade() -> None:
    op.drop_column("youtube_videos", "skip_chunking")
```

> The `ADD COLUMN IF NOT EXISTS` form is used instead of `op.add_column` because some databases may already have the column from a prior deployment of the old `017_skip_chunking.py`. This makes the migration idempotent.

- [ ] **Step 3: Verify the revision chain is now linear**

```bash
cd console/backend && alembic heads
```

Expected: exactly **one** head (`018`). Then `cd ../..`.

- [ ] **Step 4: Verify no duplicate revision IDs remain**

```bash
grep -rn "^revision" console/backend/alembic/versions/*.py | sort
```

Expected: each revision string (`"001"` through `"018"`) appears exactly once.

---

### Task 4: Commit and push

- [ ] **Step 1: Stage the changes**

```bash
git add console/backend/alembic/versions/016_youtube_video_thumbnail_fields.py \
        console/backend/alembic/versions/017_skip_chunking.py \
        console/backend/alembic/versions/018_skip_chunking.py
```

- [ ] **Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
fix(migrations): resolve duplicate revision-016/017 conflict with main branch

- Delete 016_youtube_video_thumbnail_fields.py (duplicate of main's 016_youtube_thumbnail.py)
- Renumber 017_skip_chunking → 018_skip_chunking (down_revision="017")
- Use ADD COLUMN IF NOT EXISTS for idempotency

Fixes: alembic upgrade head failing with "Multiple head revisions" in Docker

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Push to remote**

```bash
git push origin feature/n8n-youtube-workflow
```

- [ ] **Step 4: Rebuild the Docker image**

Trigger a new Docker build from the `feature/n8n-youtube-workflow` branch in your CI/CD pipeline (GitHub Actions or manual). Once the new `:latest` image is available, re-run the migration command:

```powershell
docker run --rm `
  --env-file console\.env `
  --network ai-media-automation_default `
  ghcr.io/khiemle/ai-media-automation/api:latest `
  sh -c "cd /app/console/backend && alembic upgrade head"
```

Expected output: clean migration run ending with `INFO [alembic.runtime.migration] Running upgrade ... -> 018, skip_chunking flag on youtube_videos` (or a no-op if the DB is already current).
