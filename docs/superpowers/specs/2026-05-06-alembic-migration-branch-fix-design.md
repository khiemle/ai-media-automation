# Alembic Migration Branch Conflict Fix

**Date:** 2026-05-06  
**Branch:** `feature/n8n-youtube-workflow`

## Problem

The Docker image `ghcr.io/khiemle/ai-media-automation/api:latest` contains four migration files where two share revision IDs, creating a branched DAG that Alembic refuses to run:

| File | Branch origin | Revision | Action |
|---|---|---|---|
| `016_youtube_thumbnail.py` | main | 016 | adds 3 thumbnail columns |
| `016_youtube_video_thumbnail_fields.py` | feature | 016 | adds the same 3 thumbnail columns |
| `017_music_track_composition_plan.py` | main | 017 | adds `composition_plan` to `music_tracks` |
| `017_skip_chunking.py` | feature | 017 | adds `skip_chunking` to `youtube_videos` |

Both "016" files add `thumbnail_asset_id`, `thumbnail_text`, `thumbnail_path` — functionally identical. The feature branch independently created them before main's version was merged in.

## Fix

On the `feature/n8n-youtube-workflow` branch:

1. **Delete** `016_youtube_video_thumbnail_fields.py` — it is a functional duplicate of main's `016_youtube_thumbnail.py`.

2. **Delete** `017_skip_chunking.py` and **replace** with `018_skip_chunking.py`:
   - `revision = "018"`
   - `down_revision = "017"`
   - Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (idempotent, safe if column already exists)

3. Commit both changes and push to the feature branch.

4. Rebuild the Docker image from the feature branch to produce a new `:latest`.

## Resulting migration chain

```
001 → 002 → ... → 015 → 016 (thumbnail) → 017 (composition_plan) → 018 (skip_chunking)
```

## Safety considerations

- Databases already at revision "017" (composition_plan from main) will only need to run "018".
- Databases that previously ran `017_skip_chunking.py` already have `skip_chunking` column; the `ADD COLUMN IF NOT EXISTS` form makes "018" a no-op for those rows.
- The `016_youtube_video_thumbnail_fields.py` deletion causes no data loss — `016_youtube_thumbnail.py` provides identical columns.

## Files changed

- Delete: `console/backend/alembic/versions/016_youtube_video_thumbnail_fields.py`
- Delete: `console/backend/alembic/versions/017_skip_chunking.py`
- Add: `console/backend/alembic/versions/018_skip_chunking.py`
