# /youtube Page Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four issues on the `/youtube` console page: thumbnail bold styling, black/silent shorts, missing synthetic-media disclosure, and the ability to recreate a finished video as a fresh draft.

**Architecture:** Each of the four fixes is independent and ships as its own short sequence of TDD tasks. Order is smallest-first to bank quick wins before the largest fix. The thumbnail fix swaps the rendering function from "lines of text" to "wrap plan of word segments tagged bold/regular" and uses real distinct font files (Roboto-Black for bold, Roboto-Regular for regular) already present in `assets/fonts/`. The recreate fix adds a service method, endpoint, and UI button. The shorts fix patches the asset resolvers and the MakeShortModal payload to consult plural-array fields. The synthetic-media fix corrects a single API field name in the uploader body.

**Tech Stack:** FastAPI · SQLAlchemy + Alembic · Pillow (PIL) · React 18 · ffmpeg · pytest · YouTube Data API v3

**Spec:** `docs/superpowers/specs/2026-05-12-youtube-page-bugfixes-design.md`

**Test conventions:**
- All tests live in `tests/` (repo root). Pytest discovers them automatically.
- `tests/conftest.py` provides a `db` fixture backed by a transactional SQLAlchemy session against `TEST_DATABASE_URL` (default `postgresql://localhost/ai_media_test`).
- Run a single test: `cd /Volumes/SSD/Workspace/ai-media-automation && pytest tests/test_<file>.py::<test_name> -v`
- Run a file: `pytest tests/test_<file>.py -v`

---

## File Structure (overview)

| File | Responsibility | Touched in |
|---|---|---|
| `uploader/youtube_uploader.py` | Build YouTube `videos.insert` body; switch field path for synthetic-media flag. | Fix 3 |
| `pipeline/youtube_ffmpeg.py` | `resolve_visual` / `resolve_audio` fall back to plural-array fields. | Fix 2 |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | `MakeShortModal` smart copy; "Recreate" button; thumbnail modal updates. | Fix 2, Fix 4, Fix 1 |
| `console/backend/services/youtube_video_service.py` | `recreate()` service method. | Fix 4 |
| `console/backend/routers/youtube_videos.py` | `POST /{id}/recreate` endpoint; extend `ThumbnailGenerateRequest`. | Fix 4, Fix 1 |
| `console/frontend/src/api/client.js` | Add `youtubeVideosApi.recreate()` method. | Fix 4 |
| `pipeline/youtube_thumbnail.py` | Replace `split_text` with `wrap_plan`; bold-N-words rendering; use Roboto fonts. | Fix 1 |
| `console/backend/models/youtube_video.py` | Add `thumbnail_bold_word_count` column. | Fix 1 |
| `console/backend/alembic/versions/026_thumbnail_bold_word_count.py` | Migration for new column. | Fix 1 |
| `Dockerfile.api`, `Dockerfile.render` | Install `fonts-liberation` so the thumbnail renderer has a real bold/regular pair. | Fix 1 |

---

# FIX 3 — Synthetic-media disclosure (1 task)

The current body uses `status.selfDeclaration.hasSyntheticOrAltered` which the YouTube Data API v3 does not recognize — the field is silently dropped. The correct field is `status.containsSyntheticMedia`. Hardcode `True`; no UI; no DB.

### Task 1: Switch to `containsSyntheticMedia` and log the response value

**Files:**
- Modify: `uploader/youtube_uploader.py:92-107` and the response-handling block further down
- Test: `tests/test_youtube_uploader.py` (extend existing file)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_youtube_uploader.py`:

```python
def test_upload_body_uses_contains_synthetic_media():
    """Verify the upload body sets status.containsSyntheticMedia=True at the top level
    (not nested under selfDeclaration, which YouTube v3 does not recognize)."""
    from unittest.mock import MagicMock, patch
    from uploader.youtube_uploader import upload

    captured_body = {}

    def _fake_insert(part, body, media_body):
        captured_body.update(body)
        req = MagicMock()
        req.next_chunk.return_value = (None, {"id": "vid123", "status": {"containsSyntheticMedia": True}})
        return req

    mock_youtube = MagicMock()
    mock_youtube.videos().insert.side_effect = _fake_insert
    mock_creds = MagicMock()
    mock_creds.expired = False

    with patch("uploader.youtube_uploader.Credentials", return_value=mock_creds), \
         patch("uploader.youtube_uploader.build", return_value=mock_youtube), \
         patch("uploader.youtube_uploader.MediaFileUpload"), \
         patch("pathlib.Path.exists", return_value=True):
        upload(
            "/tmp/v.mp4",
            {"title": "T", "description": "D", "niche": "lifestyle", "privacy_status": "unlisted"},
            {"access_token": "tok", "refresh_token": "ref", "client_id": "cid", "client_secret": "sec"},
        )

    assert captured_body["status"]["containsSyntheticMedia"] is True
    assert "selfDeclaration" not in captured_body["status"], \
        "selfDeclaration.hasSyntheticOrAltered is silently ignored by YouTube v3 — must not be used"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
pytest tests/test_youtube_uploader.py::test_upload_body_uses_contains_synthetic_media -v
```

Expected: FAIL — assertion error on `containsSyntheticMedia` missing, or `selfDeclaration` present.

- [ ] **Step 3: Edit `uploader/youtube_uploader.py`**

Replace lines 100-107 (the `"status": {…}` block) with:

```python
        "status": {
            "privacyStatus":           privacy_status,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia":  True,
        },
```

(Remove `"selfDeclaration"` entirely.)

- [ ] **Step 4: Add response logging after upload completes**

Find the block that processes `response = None; while response is None: status, response = request.next_chunk()` etc. Just after the loop exits with a successful response, add:

```python
    logger.info(
        "[YouTube] insert response: video_id=%s containsSyntheticMedia=%s",
        response.get("id"),
        response.get("status", {}).get("containsSyntheticMedia"),
    )
```

(If the existing code already logs the response in a similar way, append the `containsSyntheticMedia` value to that log line instead of duplicating.)

- [ ] **Step 5: Run the test, verify it passes**

```bash
pytest tests/test_youtube_uploader.py::test_upload_body_uses_contains_synthetic_media -v
```

Expected: PASS.

- [ ] **Step 6: Run the full uploader test file to confirm no regressions**

```bash
pytest tests/test_youtube_uploader.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add uploader/youtube_uploader.py tests/test_youtube_uploader.py
git commit -m "fix(uploader): use containsSyntheticMedia (YouTube v3 recognized field)

YouTube Data API v3 silently drops status.selfDeclaration.hasSyntheticOrAltered.
The recognized field is status.containsSyntheticMedia. Log the value returned
by the insert response so we can verify YouTube accepted it."
```

---

# FIX 2 — Short renders black with no audio (3 tasks)

When a parent video stores its assets in the plural arrays (`visual_asset_ids`, `music_track_ids`) — common for ASMR/soundscape templates — `MakeShortModal` copies `null` into the child's singular fields, and the short pipeline's `resolve_visual` / `resolve_audio` only check singular IDs. Result: black canvas + silent track.

Two-layer fix: defensive backend fallback to plural arrays, plus a smart-copy in the modal.

### Task 2: Defensive fallback in `resolve_visual` / `resolve_audio`

**Files:**
- Modify: `pipeline/youtube_ffmpeg.py:56-67` (`resolve_visual`) and `:163-174` (`resolve_audio`)
- Test: `tests/test_youtube_ffmpeg.py` (extend) — or new file if the existing one is unrelated

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_youtube_ffmpeg.py`:

```python
def test_resolve_visual_falls_back_to_first_plural_id(db):
    """When visual_asset_id is None but visual_asset_ids has entries, resolve to the first."""
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import resolve_visual

    template = VideoTemplate(slug="t-fb-vis", label="x", output_format="landscape_long")
    db.add(template); db.flush()

    a1 = VideoAsset(file_path="/tmp/plural1.mp4", source="manual", asset_type="video_clip")
    a2 = VideoAsset(file_path="/tmp/plural2.mp4", source="manual", asset_type="video_clip")
    db.add_all([a1, a2]); db.flush()

    video = YoutubeVideo(
        title="x", template_id=template.id,
        visual_asset_id=None,
        visual_asset_ids=[a1.id, a2.id],
    )
    db.add(video); db.flush()

    assert resolve_visual(video, db) == "/tmp/plural1.mp4"


def test_resolve_visual_singular_takes_precedence_over_plural(db):
    """When singular is present, it wins (preserve legacy behavior)."""
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import resolve_visual

    template = VideoTemplate(slug="t-prec-vis", label="x", output_format="landscape_long")
    db.add(template); db.flush()

    a_single = VideoAsset(file_path="/tmp/single.mp4", source="manual", asset_type="video_clip")
    a_plural = VideoAsset(file_path="/tmp/plural.mp4", source="manual", asset_type="video_clip")
    db.add_all([a_single, a_plural]); db.flush()

    video = YoutubeVideo(
        title="x", template_id=template.id,
        visual_asset_id=a_single.id,
        visual_asset_ids=[a_plural.id],
    )
    db.add(video); db.flush()

    assert resolve_visual(video, db) == "/tmp/single.mp4"


def test_resolve_visual_returns_none_when_no_assets(db):
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import resolve_visual

    template = VideoTemplate(slug="t-none-vis", label="x", output_format="landscape_long")
    db.add(template); db.flush()
    video = YoutubeVideo(title="x", template_id=template.id)
    db.add(video); db.flush()
    assert resolve_visual(video, db) is None


def test_resolve_audio_falls_back_to_first_plural_id(db):
    from database.models import MusicTrack
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import resolve_audio

    template = VideoTemplate(slug="t-fb-aud", label="x", output_format="landscape_long")
    db.add(template); db.flush()

    m1 = MusicTrack(file_path="/tmp/m1.mp3", title="m1")
    m2 = MusicTrack(file_path="/tmp/m2.mp3", title="m2")
    db.add_all([m1, m2]); db.flush()

    video = YoutubeVideo(
        title="x", template_id=template.id,
        music_track_id=None,
        music_track_ids=[m1.id, m2.id],
    )
    db.add(video); db.flush()

    assert resolve_audio(video, db) == "/tmp/m1.mp3"


def test_resolve_audio_singular_takes_precedence(db):
    from database.models import MusicTrack
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo
    from pipeline.youtube_ffmpeg import resolve_audio

    template = VideoTemplate(slug="t-prec-aud", label="x", output_format="landscape_long")
    db.add(template); db.flush()
    ms = MusicTrack(file_path="/tmp/single.mp3", title="s")
    mp = MusicTrack(file_path="/tmp/plural.mp3", title="p")
    db.add_all([ms, mp]); db.flush()

    video = YoutubeVideo(
        title="x", template_id=template.id,
        music_track_id=ms.id,
        music_track_ids=[mp.id],
    )
    db.add(video); db.flush()

    assert resolve_audio(video, db) == "/tmp/single.mp3"
```

If `tests/test_youtube_ffmpeg.py` does not exist, create it with the standard pytest header (no imports at module level for SQLA models — keep imports inside tests per the existing pattern in the repo).

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_youtube_ffmpeg.py -v -k "falls_back or singular_takes_precedence or no_assets"
```

Expected: 4 fall-back / precedence tests FAIL (returns None instead of plural path); `no_assets` may already pass.

- [ ] **Step 3: Update `resolve_visual` in `pipeline/youtube_ffmpeg.py`**

Replace the function body (lines 56-67) with:

```python
def resolve_visual(video, db) -> str | None:
    """Return the file path of the linked visual asset, or None.

    Prefers the singular `visual_asset_id`; falls back to the first entry in
    `visual_asset_ids` so videos built from playlist-only templates still work.
    """
    try:
        from console.backend.models.video_asset import VideoAsset
    except Exception:  # pragma: no cover
        return None

    asset_id = video.visual_asset_id
    if not asset_id:
        plural = list(getattr(video, "visual_asset_ids", None) or [])
        if plural:
            asset_id = plural[0]
    if not asset_id:
        return None
    try:
        asset = db.get(VideoAsset, asset_id)
        if asset and asset.file_path:
            return asset.file_path
    except Exception as exc:
        logger.warning("Could not load visual asset %s: %s", asset_id, exc)
    return None
```

- [ ] **Step 4: Update `resolve_audio` in `pipeline/youtube_ffmpeg.py`**

Replace the function body (lines 163-174) with:

```python
def resolve_audio(video, db) -> str | None:
    """Return the file path of the linked music track, or None.

    Prefers the singular `music_track_id`; falls back to the first entry in
    `music_track_ids` so videos built from playlist-only templates still work.
    """
    try:
        from database.models import MusicTrack
    except Exception:  # pragma: no cover
        return None

    track_id = video.music_track_id
    if not track_id:
        plural = list(getattr(video, "music_track_ids", None) or [])
        if plural:
            track_id = plural[0]
    if not track_id:
        return None
    try:
        track = db.get(MusicTrack, track_id)
        if track and track.file_path:
            return track.file_path
    except Exception as exc:
        logger.warning("Could not load music track %s: %s", track_id, exc)
    return None
```

- [ ] **Step 5: Run the resolver tests, verify they pass**

```bash
pytest tests/test_youtube_ffmpeg.py -v -k "resolve_visual or resolve_audio"
```

Expected: all PASS.

- [ ] **Step 6: Run the full `youtube_ffmpeg` test file**

```bash
pytest tests/test_youtube_ffmpeg.py tests/test_youtube_ffmpeg_visual_playlist.py -v
```

Expected: all PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add pipeline/youtube_ffmpeg.py tests/test_youtube_ffmpeg.py
git commit -m "fix(ffmpeg): resolve_visual/audio fall back to plural arrays

When a video is built from a playlist-only template, the singular *_id columns
are NULL and the short renderer used to produce a black/silent output.
Falling back to the first plural-array entry preserves the singular-as-default
contract while making playlist-only videos work as shorts."
```

### Task 3: `MakeShortModal` smart copy

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx:1856-1875` (the `handleSubmit` payload of `MakeShortModal`)

- [ ] **Step 1: Read the current modal**

```bash
sed -n '1856,1875p' console/frontend/src/pages/YouTubeVideosPage.jsx
```

Confirm the current payload still passes `music_track_id: form.sameMusic ? video.music_track_id : null` and `visual_asset_id: form.sameVisual ? video.visual_asset_id : null` at lines 1866-1867.

- [ ] **Step 2: Replace those two lines**

Find:

```jsx
        music_track_id: form.sameMusic ? video.music_track_id : null,
        visual_asset_id: form.sameVisual ? video.visual_asset_id : null,
```

Replace with:

```jsx
        music_track_id: form.sameMusic
          ? (video.music_track_id ?? video.music_track_ids?.[0] ?? null)
          : null,
        visual_asset_id: form.sameVisual
          ? (video.visual_asset_id ?? video.visual_asset_ids?.[0] ?? null)
          : null,
```

- [ ] **Step 3: Smoke-test in the dev console** (manual, no automated FE test exists for the modal)

```bash
# Start the backend if not running
./console/start.sh   # OR confirm uvicorn is up on :8080

# Frontend in a separate terminal
cd console/frontend && npm run dev
```

In the browser:
1. Open `/youtube`, find a soundscape/ASMR video that has populated `visual_asset_ids` and `music_track_ids` but null singular IDs.
2. Click "Make Short". Submit with "Same as parent" for both.
3. Check the network tab: the POST body should now contain integer values for both `music_track_id` and `visual_asset_id`.
4. After render completes, play the short — must have visible content and audible music.

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "fix(frontend): MakeShortModal picks first playlist entry when singular is null

Soundscape/ASMR videos store their assets in *_asset_ids / *_track_ids arrays
with the singular columns empty. MakeShortModal copies these into the child's
singular slots (a short is single-asset by design); falling back to the first
plural entry makes shorts of playlist-only parents render correctly."
```

### Task 4: Tie-up — full check on Fix 2

- [ ] **Step 1: Run all youtube-related tests**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
pytest tests/test_youtube_ffmpeg.py tests/test_youtube_ffmpeg_visual_playlist.py -v
```

Expected: all PASS.

(No commit — verification step.)

---

# FIX 4 — Recreate a render-done video (5 tasks)

Add `YoutubeVideoService.recreate(source_id)` that clones configuration into a new draft, a `POST /api/youtube-videos/{id}/recreate` endpoint, a frontend API method, and a "Recreate" button in the YouTube page action bar for `status="done"` rows.

### Task 5: `YoutubeVideoService.recreate` service method

**Files:**
- Modify: `console/backend/services/youtube_video_service.py`
- Test: `tests/test_youtube_video_service_recreate.py` (new file)

- [ ] **Step 1: Read the existing service to find a method to insert near**

```bash
grep -n "def " console/backend/services/youtube_video_service.py | head -30
```

Note the location of `create_video`. The new `recreate` method goes near `create_video` for proximity, and may reuse `create_video`'s internals where natural (or duplicate the persistence logic if `create_video` does more validation than recreate needs).

- [ ] **Step 2: Write the failing test**

Create `tests/test_youtube_video_service_recreate.py`:

```python
import uuid
import pytest

from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo


def _seed_template(db, output_format: str = "landscape_long") -> VideoTemplate:
    slug = f"recreate-{uuid.uuid4().hex[:8]}"
    t = VideoTemplate(slug=slug, label="Test", output_format=output_format)
    db.add(t); db.flush()
    return t


def _seed_full_video(db, template) -> YoutubeVideo:
    """A done video with every recreate-able field populated."""
    v = YoutubeVideo(
        title="Source Video",
        template_id=template.id,
        theme="cozy",
        music_track_id=11,
        visual_asset_id=22,
        music_track_ids=[11, 12, 13],
        visual_asset_ids=[22, 23],
        visual_clip_durations_s=[5.0, 7.5],
        visual_loop_mode="per_clip",
        sfx_overrides={"foreground": {"asset_id": 99, "volume": 0.7}},
        sfx_pool=[{"asset_id": 50, "weight": 1.0}],
        sfx_density_seconds=30,
        sfx_seed=42,
        seo_title="SEO title",
        seo_description="SEO description",
        seo_tags=["one", "two"],
        target_duration_h=2.0,
        output_quality="1080p",
        sound_layers={"background": {"asset_id": 1}},
        track_transition="crossfade",
        track_transition_seconds=3.5,
        playlist_overlay_style="banner",
        spectrum_enabled=True,
        spectrum_height_pct=0.18,
        spectrum_color="#abcdef",
        spectrum_opacity=0.5,
        spectrum_style="bars",
        spectrum_bar_width_px=12.0,
        spectrum_bar_count=64,
        spectrum_align_horizontal="left",
        spectrum_align_vertical="top",
        thumbnail_asset_id=33,
        thumbnail_text="DEEP FOCUS",
        black_from_seconds=120,
        skip_previews=False,
        # runtime fields (must be reset on recreate)
        status="done",
        output_path="/tmp/source_output.mp4",
        audio_preview_path="/tmp/aud.mp3",
        video_preview_path="/tmp/vid.mp4",
        celery_task_id="task-abc",
        thumbnail_path="/tmp/thumb.png",
        render_parts=[{"part": "1"}],
        parent_youtube_video_id=None,
    )
    db.add(v); db.flush()
    return v


def test_recreate_clones_configuration_fields(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)

    svc = YoutubeVideoService(db)
    new = svc.recreate(source.id)
    db.flush()

    cloned = [
        "template_id", "theme",
        "music_track_id", "visual_asset_id",
        "music_track_ids", "visual_asset_ids",
        "visual_clip_durations_s", "visual_loop_mode",
        "sfx_overrides", "sfx_pool", "sfx_density_seconds", "sfx_seed",
        "seo_title", "seo_description", "seo_tags",
        "target_duration_h", "output_quality",
        "sound_layers",
        "track_transition", "track_transition_seconds", "playlist_overlay_style",
        "spectrum_enabled", "spectrum_height_pct", "spectrum_color",
        "spectrum_opacity", "spectrum_style", "spectrum_bar_width_px",
        "spectrum_bar_count", "spectrum_align_horizontal", "spectrum_align_vertical",
        "thumbnail_asset_id", "thumbnail_text",
        "black_from_seconds", "skip_previews",
    ]
    for field in cloned:
        assert getattr(new, field) == getattr(source, field), \
            f"field {field!r} not cloned correctly: {getattr(new, field)!r} != {getattr(source, field)!r}"


def test_recreate_resets_runtime_fields(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)

    svc = YoutubeVideoService(db)
    new = svc.recreate(source.id)
    db.flush()

    assert new.status == "draft"
    assert new.output_path is None
    assert new.audio_preview_path is None
    assert new.video_preview_path is None
    assert new.celery_task_id is None
    assert new.thumbnail_path is None
    assert new.render_parts == []
    assert new.parent_youtube_video_id is None


def test_recreate_title_appended_with_recreate(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)
    new = YoutubeVideoService(db).recreate(source.id)
    db.flush()
    assert new.title == "Source Video (recreate)"


def test_recreate_assigns_new_id(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    template = _seed_template(db)
    source = _seed_full_video(db, template)
    new = YoutubeVideoService(db).recreate(source.id)
    db.flush()
    assert new.id is not None
    assert new.id != source.id


def test_recreate_missing_source_raises(db):
    from console.backend.services.youtube_video_service import YoutubeVideoService
    with pytest.raises(ValueError, match="not found"):
        YoutubeVideoService(db).recreate(999999)
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
pytest tests/test_youtube_video_service_recreate.py -v
```

Expected: FAIL with `AttributeError: 'YoutubeVideoService' object has no attribute 'recreate'`.

- [ ] **Step 4: Implement `recreate` in `console/backend/services/youtube_video_service.py`**

Add this method to the `YoutubeVideoService` class:

```python
    # Fields cloned from source to new draft. Keep this list explicit so each
    # field's inclusion is reviewable in isolation — see
    # docs/superpowers/specs/2026-05-12-youtube-page-bugfixes-design.md (Fix 4).
    _RECREATE_CLONED_FIELDS = (
        "template_id", "theme",
        "music_track_id", "visual_asset_id",
        "music_track_ids", "visual_asset_ids",
        "visual_clip_durations_s", "visual_loop_mode",
        "sfx_overrides", "sfx_pool", "sfx_density_seconds", "sfx_seed",
        "seo_title", "seo_description", "seo_tags",
        "target_duration_h", "output_quality",
        "sound_layers",
        "track_transition", "track_transition_seconds", "playlist_overlay_style",
        "spectrum_enabled", "spectrum_height_pct", "spectrum_color",
        "spectrum_opacity", "spectrum_style", "spectrum_bar_width_px",
        "spectrum_bar_count", "spectrum_align_horizontal", "spectrum_align_vertical",
        "thumbnail_asset_id", "thumbnail_text",
        "black_from_seconds", "skip_previews",
    )

    def recreate(self, source_id: int):
        """Clone a YoutubeVideo's configuration into a new draft.

        Runtime/output fields (status, paths, celery_task_id, render_parts,
        parent_youtube_video_id) are reset. Returns the persisted new YoutubeVideo.
        """
        from console.backend.models.youtube_video import YoutubeVideo

        source = self.db.get(YoutubeVideo, source_id)
        if source is None:
            raise ValueError(f"YoutubeVideo {source_id} not found")

        kwargs = {f: getattr(source, f) for f in self._RECREATE_CLONED_FIELDS}
        kwargs["title"] = f"{source.title} (recreate)"
        kwargs["status"] = "draft"
        # Runtime fields default to None / []; we don't have to set them, but be
        # explicit for documentation:
        kwargs["output_path"] = None
        kwargs["audio_preview_path"] = None
        kwargs["video_preview_path"] = None
        kwargs["celery_task_id"] = None
        kwargs["thumbnail_path"] = None
        kwargs["render_parts"] = []
        kwargs["parent_youtube_video_id"] = None

        new_video = YoutubeVideo(**kwargs)
        self.db.add(new_video)
        self.db.flush()
        return new_video
```

If `YoutubeVideoService` does not currently have a class-level attribute pattern, add `_RECREATE_CLONED_FIELDS` as a module-level constant at the top of the file instead. Either is acceptable — pick the style that matches surrounding code.

If the constructor stores the session as `self.db`, the above is correct. If it stores as `self.session`, substitute everywhere.

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_youtube_video_service_recreate.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add console/backend/services/youtube_video_service.py tests/test_youtube_video_service_recreate.py
git commit -m "feat(youtube): YoutubeVideoService.recreate clones config into draft

Adds a service method that takes a source video id and returns a new draft
with every configuration field (template, assets, SFX, SEO, thumbnail,
spectrum, etc.) cloned and every runtime field (status, paths, celery_task_id,
render_parts, parent_id) reset. Title is suffixed with ' (recreate)'."
```

### Task 6: `POST /youtube-videos/{id}/recreate` endpoint

**Files:**
- Modify: `console/backend/routers/youtube_videos.py`
- Test: `tests/test_youtube_video_service_recreate.py` (extend with endpoint tests, OR new `tests/test_youtube_videos_recreate_endpoint.py`)

- [ ] **Step 1: Look at an existing simple POST endpoint for the audit-log + response-shape pattern**

```bash
grep -n "AuditLog\|@router.post" console/backend/routers/youtube_videos.py | head -30
```

Pick a small existing endpoint (e.g. one of the thumbnail endpoints around line 526) as the structural template.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_youtube_video_service_recreate.py`:

```python
def test_recreate_endpoint_returns_new_id(db, monkeypatch):
    """The POST endpoint returns {id: <new_id>} and persists the draft."""
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.models.youtube_video import YoutubeVideo

    template = _seed_template(db)
    source = _seed_full_video(db, template)
    db.commit()  # endpoint will open its own session

    # Override get_db to share the test session
    def _get_db_override():
        yield db

    class _FakeUser:
        id = 1
        role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with TestClient(app) as client:
            resp = client.post(f"/api/youtube-videos/{source.id}/recreate")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "id" in body
        new_id = body["id"]
        assert new_id != source.id

        new_video = db.get(YoutubeVideo, new_id)
        assert new_video is not None
        assert new_video.status == "draft"
        assert new_video.title == "Source Video (recreate)"
    finally:
        app.dependency_overrides.clear()


def test_recreate_endpoint_404_when_missing(db):
    from fastapi.testclient import TestClient
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin

    def _get_db_override():
        yield db

    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with TestClient(app) as client:
            resp = client.post("/api/youtube-videos/999999/recreate")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
pytest tests/test_youtube_video_service_recreate.py -v -k "endpoint"
```

Expected: FAIL with 404 / 405 / 422 (the route doesn't exist).

- [ ] **Step 4: Implement the endpoint in `console/backend/routers/youtube_videos.py`**

Add this endpoint (place it near the other POST endpoints for the same resource, e.g. just after the upload endpoint or near `thumbnail-generate`):

```python
@router.post("/{video_id}/recreate")
def recreate_youtube_video(
    video_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_editor_or_admin),
):
    """Clone a YoutubeVideo's configuration into a new draft and return its id."""
    from console.backend.models.audit_log import AuditLog
    from console.backend.services.youtube_video_service import YoutubeVideoService

    svc = YoutubeVideoService(db)
    try:
        new_video = svc.recreate(video_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    db.add(AuditLog(
        user_id=user.id,
        action="recreate_youtube_video",
        target_type="youtube_video",
        target_id=str(new_video.id),
        details={"source_id": video_id},
    ))
    db.commit()

    return {"id": new_video.id}
```

If the existing endpoints use a different audit-log helper (e.g. `_audit(user, ...)`), use that helper instead — keep the action name `recreate_youtube_video` and the `details` payload.

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_youtube_video_service_recreate.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add console/backend/routers/youtube_videos.py tests/test_youtube_video_service_recreate.py
git commit -m "feat(youtube): POST /youtube-videos/{id}/recreate endpoint

Wraps YoutubeVideoService.recreate with a router endpoint, audit-logs the
action with source_id, returns 404 when the source video is missing."
```

### Task 7: Frontend API method + Recreate button

**Files:**
- Modify: `console/frontend/src/api/client.js` (add `recreate` method)
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (add button + handler in the done-row action group)

- [ ] **Step 1: Find the existing `youtubeVideosApi` shape**

```bash
grep -n "youtubeVideosApi" console/frontend/src/api/client.js
```

Locate the object and the existing method patterns (e.g. `create`, `upload`).

- [ ] **Step 2: Add `recreate` method**

Inside the `youtubeVideosApi` object, add:

```js
  recreate: (id) => request(`/api/youtube-videos/${id}/recreate`, { method: 'POST' }),
```

(Use whatever helper name the file already uses — `request`, `apiPost`, `client.post`, etc. Match the surrounding style.)

- [ ] **Step 3: Find the done-row action group in `YouTubeVideosPage.jsx`**

```bash
grep -n "preview\|Recreate\|status === 'done'\|Upload" console/frontend/src/pages/YouTubeVideosPage.jsx | head -20
```

The Explore report identified the actions block around lines 2326-2338. Confirm before editing.

- [ ] **Step 4: Add the Recreate button**

Inside the action group rendered for `status === "done"` rows, add a `<Button>` next to the existing actions:

```jsx
<Button
  size="xs"
  variant="ghost"
  onClick={async () => {
    try {
      const res = await youtubeVideosApi.recreate(video.id)
      showToast(`New draft created (id ${res.id})`, "success")
      onRefresh?.()   // or whatever the page's refresh trigger is named
    } catch (e) {
      showToast(e.message, "error")
    }
  }}
  title="Create a new draft with this video's configuration"
>
  Recreate
</Button>
```

If `showToast` / `onRefresh` are named differently in the surrounding component, use the surrounding names. The behavior must be: POST → toast on success → refresh the list so the new draft appears.

- [ ] **Step 5: Smoke-test manually**

In the browser:
1. Find a done video. Click "Recreate".
2. Toast appears. List refreshes — a new draft titled `<original> (recreate)` appears at the top.
3. Open the new draft → confirm fields (assets, SFX, SEO, thumbnail-text) match the source.
4. Render the new draft end-to-end → confirm it produces a valid output.

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/api/client.js console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(frontend): Recreate button for done YouTube videos

Adds youtubeVideosApi.recreate(id) and a per-row Recreate button (visible
when status='done') that creates a new draft from the source video's
configuration, then refreshes the list."
```

---

# FIX 1 — Thumbnail: bold first N words (default 1) + real fonts (6 tasks)

`pipeline/youtube_thumbnail.py` currently bolds the first **line** of split text using a hack that relies on `font.set_variation_by_name("Bold")`. Both regular and bold paths default to the same font file, so the variation call silently no-ops and bold ≈ regular visually. Replace with:

1. Distinct bold/regular font files. **Production source of truth:** the `fonts-liberation` apt package installed inside the Docker image (`LiberationSans-Bold.ttf` + `LiberationSans-Regular.ttf` — distinct files, distinct weights, ubiquitous on Debian/Ubuntu, ~2 MB).
2. A `wrap_plan(text, bold_word_count)` function that returns lines as lists of `(word, is_bold)` tuples.
3. A renderer that draws each word at its measured x-offset, picking the bold or regular font per word.
4. A new `thumbnail_bold_word_count INT NOT NULL DEFAULT 1` column.
5. UI + router wiring.

**Font persistence notes (read first):**
- `assets/` is excluded from git (`.gitignore: /assets`) AND from the Docker build context (`.dockerignore: /assets/`). The local files at `assets/fonts/Roboto-*.ttf` are **dev-only convenience** — they will NOT exist in a container.
- The `python:3.11-slim` base image (used by `Dockerfile.api`) and the `nvidia/cuda:*ubuntu22.04` base (used by `Dockerfile.render`) ship with **no system fonts at all**.
- The fix is therefore: install `fonts-liberation` via apt in both Dockerfiles (Task 8a), then resolve fonts via a chain that prefers env-var override → system Liberation paths → bundled Roboto (dev convenience) → other system fallbacks. The container path becomes the canonical, persistent source.

### Task 8a: Bake `fonts-liberation` into both Dockerfiles

This task ensures bold/regular fonts are present in every container, surviving rebuilds and restarts. Required before Task 8 (the font-resolution logic depends on having a known-good system font pair).

**Files:**
- Modify: `Dockerfile.api`
- Modify: `Dockerfile.render`

- [ ] **Step 1: Update `Dockerfile.api`**

Find the existing apt-get line (around line 6-7):

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client redis-tools ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*
```

Replace with:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client redis-tools ffmpeg curl \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Update `Dockerfile.render`**

Find the equivalent apt-get install block (it starts around line 8 of `Dockerfile.render` — confirm the exact location). Add `fonts-liberation` to the package list using the same pattern as Step 1.

If `Dockerfile.render` already lists multiple packages on continuation lines, append `fonts-liberation` to the list. Keep `--no-install-recommends` so we don't pull in the full fontconfig recommends tree.

- [ ] **Step 3: Verify locally** (only if Docker is available)

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
docker build -f Dockerfile.api -t aim-api-fontcheck . --target=builder 2>&1 | tail -5 || \
docker build -f Dockerfile.api -t aim-api-fontcheck .
docker run --rm aim-api-fontcheck ls /usr/share/fonts/truetype/liberation/ | grep -E "Liberation(Sans|Mono)-(Regular|Bold)\.ttf"
```

Expected: `LiberationSans-Regular.ttf` and `LiberationSans-Bold.ttf` listed.

If Docker is not available locally, skip this step — Task 8 has its own font-resolution tests that will catch a missing font.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.api Dockerfile.render
git commit -m "build(docker): install fonts-liberation in api and render images

assets/fonts/ is dockerignored, so dev-bundled Roboto files never reach the
image. The python:3.11-slim and nvidia/cuda base images ship with no fonts
at all, which makes the thumbnail renderer fail in production. fonts-liberation
is ~2 MB and provides distinct Regular and Bold files at standard paths
(/usr/share/fonts/truetype/liberation/), which the next commit will consume."
```

### Task 8: Fonts + `wrap_plan` (pure logic, no rendering yet)

**Files:**
- Modify: `pipeline/youtube_thumbnail.py`
- Test: `tests/test_youtube_thumbnail.py` (update existing tests + add new ones)

- [ ] **Step 1: Confirm a usable font pair is available on this host**

The plan uses a resolution chain (env override → system Liberation → bundled Roboto → other system fallbacks). At least ONE pair must be present:

```bash
ls /usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf 2>/dev/null || \
ls assets/fonts/Roboto-Regular.ttf assets/fonts/Roboto-Black.ttf 2>/dev/null
```

If neither is present, on macOS install Roboto via:

```bash
mkdir -p assets/fonts
curl -L -o /tmp/roboto.zip https://fonts.google.com/download?family=Roboto
unzip -o /tmp/roboto.zip -d /tmp/roboto/
cp /tmp/roboto/static/Roboto-Regular.ttf assets/fonts/
cp /tmp/roboto/static/Roboto-Black.ttf assets/fonts/
```

(`assets/fonts/` is gitignored and dockerignored — these files live on your dev machine only.)

- [ ] **Step 2: Write failing tests for `wrap_plan`**

In `tests/test_youtube_thumbnail.py`, **remove** the three `split_text` tests (lines 51-63):

```python
def test_split_text_single_word(): ...
def test_split_text_three_words(): ...
def test_split_text_four_words_third_line_joins_remainder(): ...
```

And **add** in their place:

```python
def test_wrap_plan_single_word_default_bold_1():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("FOCUS", bold_word_count=1) == [
        [("FOCUS", True)],
    ]


def test_wrap_plan_three_words_default_bold_1():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP SLEEP MUSIC", bold_word_count=1) == [
        [("DEEP", True)],
        [("SLEEP", False)],
        [("MUSIC", False)],
    ]


def test_wrap_plan_four_words_remainder_on_third_line():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP FOCUS STUDY MUSIC", bold_word_count=1) == [
        [("DEEP", True)],
        [("FOCUS", False)],
        [("STUDY", False), ("MUSIC", False)],
    ]


def test_wrap_plan_bold_count_two_spans_two_lines():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP SLEEP MUSIC", bold_word_count=2) == [
        [("DEEP", True)],
        [("SLEEP", True)],
        [("MUSIC", False)],
    ]


def test_wrap_plan_bold_count_three_on_five_words_mixes_third_line():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP FOCUS STUDY MUSIC LOOP", bold_word_count=3) == [
        [("DEEP", True)],
        [("FOCUS", True)],
        [("STUDY", True), ("MUSIC", False), ("LOOP", False)],
    ]


def test_wrap_plan_bold_count_zero_all_regular():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP FOCUS", bold_word_count=0) == [
        [("DEEP", False)],
        [("FOCUS", False)],
    ]


def test_wrap_plan_bold_count_exceeds_word_count_caps():
    from pipeline.youtube_thumbnail import wrap_plan
    assert wrap_plan("DEEP", bold_word_count=10) == [
        [("DEEP", True)],
    ]


def test_wrap_plan_empty_text_raises():
    from pipeline.youtube_thumbnail import wrap_plan
    import pytest
    with pytest.raises(ValueError):
        wrap_plan("", bold_word_count=1)
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
pytest tests/test_youtube_thumbnail.py -v -k "wrap_plan"
```

Expected: FAIL — `ImportError: cannot import name 'wrap_plan'`.

- [ ] **Step 4: Replace `split_text` with `wrap_plan` in `pipeline/youtube_thumbnail.py`**

Replace the `split_text` function (lines 44-50) with:

```python
def wrap_plan(text: str, bold_word_count: int) -> list[list[tuple[str, bool]]]:
    """Wrap thumbnail text into lines, tagging each word as bold or regular.

    Layout (preserved from previous split_text):
      - 1-3 words → one word per line
      - 4+ words  → line1=word1, line2=word2, line3=remaining-words

    `bold_word_count` words from the start (in reading order, left-to-right,
    top-to-bottom) are tagged is_bold=True; the rest are False. Counts beyond
    the total number of words are clamped.
    """
    words = text.strip().split()
    if not words:
        raise ValueError("Text cannot be empty.")

    if len(words) <= 3:
        line_words: list[list[str]] = [[w] for w in words]
    else:
        line_words = [[words[0]], [words[1]], words[2:]]

    n = max(0, bold_word_count)
    plan: list[list[tuple[str, bool]]] = []
    seen = 0
    for line in line_words:
        segs: list[tuple[str, bool]] = []
        for w in line:
            segs.append((w, seen < n))
            seen += 1
        plan.append(segs)
    return plan
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_youtube_thumbnail.py -v -k "wrap_plan"
```

Expected: all PASS.

- [ ] **Step 6: Update the font resolution to be Docker-safe**

Replace lines 17-41 (`_find_system_font`, `_resolve_font`, `DEFAULT_REGULAR_FONT`, `DEFAULT_BOLD_FONT`) with:

```python
_REPO_ROOT = Path(__file__).resolve().parents[1]

# Production path: fonts-liberation installed via apt in Dockerfile.api / Dockerfile.render.
# Dev convenience: bundled Roboto in assets/fonts/ (gitignored + dockerignored — local only).
# Resolution chain (first existing file wins):
#   1. THUMBNAIL_FONT_PATH / THUMBNAIL_BOLD_FONT_PATH env overrides
#   2. System Liberation Sans (container default)
#   3. Bundled Roboto (dev mac default)
#   4. Other system fonts (last-resort, may not provide a distinct bold)
_REGULAR_CANDIDATES = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    _REPO_ROOT / "assets" / "fonts" / "Roboto-Regular.ttf",
    Path("/System/Library/Fonts/SFNS.ttf"),                                    # macOS fallback
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),                   # common Linux
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),                               # Arch
    Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),                 # Fedora/RHEL
]
_BOLD_CANDIDATES = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    _REPO_ROOT / "assets" / "fonts" / "Roboto-Black.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"),
]


def _first_existing(candidates: list[Path]) -> Path | None:
    for p in candidates:
        if p.exists():
            return p
    return None


def _resolve_regular_font() -> Path:
    override = os.environ.get("THUMBNAIL_FONT_PATH")
    if override:
        return Path(override)
    found = _first_existing(_REGULAR_CANDIDATES)
    if found:
        return found
    raise FileNotFoundError(
        "No regular font found. Install fonts-liberation (apt) or set THUMBNAIL_FONT_PATH."
    )


def _resolve_bold_font(regular: Path) -> Path:
    override = os.environ.get("THUMBNAIL_BOLD_FONT_PATH")
    if override:
        return Path(override)
    found = _first_existing(_BOLD_CANDIDATES)
    if found:
        return found
    # Last-resort: fall back to regular. Bold will visually equal regular —
    # this is the silent-failure mode this fix was meant to prevent, so log loudly.
    import logging
    logging.getLogger(__name__).warning(
        "No bold font found; bold spans will render identically to regular. "
        "Install fonts-liberation (apt) or set THUMBNAIL_BOLD_FONT_PATH."
    )
    return regular


def _find_system_font() -> Path:
    """Backwards-compatible export used by existing tests / scripts."""
    return _resolve_regular_font()


DEFAULT_REGULAR_FONT = _resolve_regular_font()
DEFAULT_BOLD_FONT    = _resolve_bold_font(DEFAULT_REGULAR_FONT)

import logging as _thumb_log
_thumb_log.getLogger(__name__).info(
    "Thumbnail fonts resolved: regular=%s bold=%s",
    DEFAULT_REGULAR_FONT, DEFAULT_BOLD_FONT,
)
```

(Keep the module-level `DEFAULT_REGULAR_FONT` / `DEFAULT_BOLD_FONT` / `_find_system_font` symbols so existing tests importing them still work.)

- [ ] **Step 7: Run thumbnail tests, verify no regressions**

```bash
pytest tests/test_youtube_thumbnail.py -v
```

Expected: the size/parent-dir tests still pass; the wrap_plan tests still pass.

- [ ] **Step 8: Commit**

```bash
git add pipeline/youtube_thumbnail.py tests/test_youtube_thumbnail.py
git commit -m "refactor(thumbnail): wrap_plan(text, bold_word_count) + Roboto fonts

Replaces split_text with wrap_plan, which returns lines of (word, is_bold)
segments. Counts bold words in reading order; clamps to total word count.
Uses bundled Roboto-Regular/Black so bold visually differs from regular
(set_variation_by_name was a no-op on most systems)."
```

### Task 9: Rewrite `measure_lines` / draw loop to render per-word segments

**Files:**
- Modify: `pipeline/youtube_thumbnail.py:77-177` (`measure_lines`, `fit_text`, `generate_thumbnail`)
- Test: `tests/test_youtube_thumbnail.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_youtube_thumbnail.py`:

```python
def test_generate_thumbnail_bold_pixels_differ_from_regular_pixels(tmp_path):
    """Smoke-test that the bold span renders with visibly different stroke than the regular span.

    We render the same thumbnail twice — once with bold_word_count=0 (all regular)
    and once with bold_word_count=1 — and assert the resulting PNGs differ.
    This catches the regression where bold and regular fonts collapsed to the
    same file."""
    from pipeline.youtube_thumbnail import generate_thumbnail, DEFAULT_BOLD_FONT, DEFAULT_REGULAR_FONT
    import pytest
    if DEFAULT_BOLD_FONT == DEFAULT_REGULAR_FONT:
        pytest.skip("Bold font equals regular font on this system — visual diff not meaningful")

    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1280, 720), color=(50, 60, 70)).save(src)

    out_regular = tmp_path / "out_regular.png"
    out_bold    = tmp_path / "out_bold.png"

    generate_thumbnail(src, out_regular, text="DEEP FOCUS MUSIC", bold_word_count=0)
    generate_thumbnail(src, out_bold,    text="DEEP FOCUS MUSIC", bold_word_count=1)

    assert out_regular.read_bytes() != out_bold.read_bytes(), \
        "Bold and regular thumbnails are byte-identical — bold rendering isn't actually bolding."


def test_generate_thumbnail_accepts_bold_word_count_kwarg(tmp_path):
    """Public API: generate_thumbnail accepts bold_word_count and runs without error."""
    from pipeline.youtube_thumbnail import generate_thumbnail
    from PIL import Image
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1280, 720), color=(50, 60, 70)).save(src)
    out = tmp_path / "out.png"
    generate_thumbnail(src, out, text="DEEP FOCUS", bold_word_count=2)
    assert out.exists()
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest tests/test_youtube_thumbnail.py -v -k "bold_pixels or bold_word_count_kwarg"
```

Expected: FAIL — `bold_word_count` kwarg not accepted or pixel difference assertion.

- [ ] **Step 3: Rewrite `measure_lines`, `fit_text`, and the draw loop**

Replace the entire block from `measure_lines` (line 77) through the end of `generate_thumbnail` (line 177) with:

```python
def _measure_word(
    draw: ImageDraw.ImageDraw,
    word: str,
    font: ImageFont.FreeTypeFont,
    stroke_width: int,
) -> tuple[int, int, tuple[int, int, int, int]]:
    bbox = draw.textbbox((0, 0), word, font=font, stroke_width=stroke_width)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox


def measure_plan(
    draw: ImageDraw.ImageDraw,
    plan: list[list[tuple[str, bool]]],
    font_size: int,
    regular_font_path: Path,
    bold_font_path: Path,
) -> tuple[int, int, list[list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]]]:
    """Measure a wrap plan; return (max_line_width, total_block_height, per_word_metadata).

    per_word_metadata is one inner list per line. Each item is
    (word, font, stroke_width, bbox) — ready for the draw loop.
    """
    stroke_width = max(2, round(font_size * 0.045))
    spacing = max(8, round(font_size * 0.17))

    regular_font = load_font(regular_font_path, font_size)
    bold_font    = load_font(bold_font_path,    font_size)
    space_w, _, _ = _measure_word(draw, " ", regular_font, stroke_width)

    measured_plan: list[list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int, int, int, int]]]] = []
    line_widths:   list[int] = []
    line_heights:  list[int] = []

    for line in plan:
        words_meta = []
        line_w = 0
        line_h = 0
        for i, (word, is_bold) in enumerate(line):
            font = bold_font if is_bold else regular_font
            w, h, bbox = _measure_word(draw, word, font, stroke_width)
            if i > 0:
                line_w += space_w
            line_w += w
            line_h = max(line_h, h)
            words_meta.append((word, font, stroke_width, bbox))
        measured_plan.append(words_meta)
        line_widths.append(line_w)
        line_heights.append(line_h)

    total_height = sum(line_heights) + spacing * max(0, len(line_heights) - 1)
    return max(line_widths), total_height, measured_plan


def load_font(path: Path, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    if not path.exists():
        raise FileNotFoundError(f"Font file not found: {path}")
    return ImageFont.truetype(str(path), size=size)


def fit_text_plan(
    draw: ImageDraw.ImageDraw,
    plan: list[list[tuple[str, bool]]],
    regular_font_path: Path,
    bold_font_path: Path,
    max_width: int,
    max_height: int,
    preferred_size: int,
    min_size: int,
) -> tuple[int, int, list]:
    for font_size in range(preferred_size, min_size - 1, -2):
        width, height, measured = measure_plan(
            draw, plan, font_size, regular_font_path, bold_font_path
        )
        if width <= max_width and height <= max_height:
            return font_size, height, measured
    raise ValueError(
        f"Text is too large to fit. Try shorter text or lower min_font_size below {min_size}."
    )


def generate_thumbnail(
    source_path: Path | str,
    output_path: Path | str,
    text: str | None = None,
    font: Path = DEFAULT_REGULAR_FONT,
    bold_font: Path = DEFAULT_BOLD_FONT,
    bold_word_count: int = 1,
    preferred_font_size: int = 162,
    min_font_size: int = 48,
    margin_x: int = 58,
    margin_bottom: int = 48,
    fill: str = "#F7F2E8",
    stroke_fill: str = "#06100C",
) -> Path:
    """Generate a 1280x720 YouTube thumbnail PNG.

    text=None or empty: cover-resize only, no overlay.
    text provided: resize then draw text bottom-left with stroke; the first
        `bold_word_count` words (default 1) are drawn in the bold font.
    Returns output_path as a Path.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)

    image = Image.open(source_path).convert("RGB")
    canvas = cover_resize(image, THUMBNAIL_SIZE)

    if text and text.strip():
        draw = ImageDraw.Draw(canvas)
        plan = wrap_plan(text.upper(), bold_word_count)
        max_width = THUMBNAIL_SIZE[0] - margin_x * 2
        max_height = THUMBNAIL_SIZE[1] - margin_bottom * 2
        font_size, block_height, measured = fit_text_plan(
            draw, plan, font, bold_font,
            max_width, max_height, preferred_font_size, min_font_size,
        )
        spacing = max(8, round(font_size * 0.17))
        regular_for_space = load_font(font, font_size)
        space_w, _, _ = _measure_word(draw, " ", regular_for_space,
                                       max(2, round(font_size * 0.045)))

        y = THUMBNAIL_SIZE[1] - margin_bottom - block_height
        for line in measured:
            x = margin_x
            line_h = max((bbox[3] - bbox[1]) for (_, _, _, bbox) in line)
            for i, (word, word_font, stroke_width, bbox) in enumerate(line):
                if i > 0:
                    x += space_w
                draw.text(
                    (x - bbox[0], y - bbox[1]),
                    word,
                    font=word_font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=stroke_fill,
                )
                x += (bbox[2] - bbox[0])
            y += line_h + spacing

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path
```

Notes for the engineer reading this:
- The `load_font` helper now ignores the `variation` argument — distinct font files do the work. The kwarg is kept for source-compat.
- `measure_lines`, `fit_text`, and the old `split_text` are gone. If any other module in the repo imported them, update those imports (`grep -r "split_text\|measure_lines\|fit_text" --include="*.py"`).

- [ ] **Step 4: Search for and update any other imports of the removed symbols**

```bash
grep -rn "from pipeline.youtube_thumbnail import" --include="*.py"
grep -rn "youtube_thumbnail.split_text\|youtube_thumbnail.measure_lines\|youtube_thumbnail.fit_text" --include="*.py"
```

If `split_text`, `measure_lines`, or `fit_text` are imported elsewhere, switch them to `wrap_plan`, `measure_plan`, `fit_text_plan` respectively (the call sites will need adapting).

- [ ] **Step 5: Run tests, verify they pass**

```bash
pytest tests/test_youtube_thumbnail.py -v
```

Expected: all PASS (including `bold_pixels_differ_from_regular_pixels` and `bold_word_count_kwarg`).

- [ ] **Step 6: Visual eyeball check (optional but recommended)**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "
from pathlib import Path
from PIL import Image
from pipeline.youtube_thumbnail import generate_thumbnail
src = Path('/tmp/src_thumb.jpg')
Image.new('RGB', (1280, 720), color=(20, 40, 80)).save(src)
generate_thumbnail(src, Path('/tmp/thumb_bold1.png'), text='DEEP FOCUS MUSIC', bold_word_count=1)
generate_thumbnail(src, Path('/tmp/thumb_bold2.png'), text='DEEP FOCUS MUSIC', bold_word_count=2)
generate_thumbnail(src, Path('/tmp/thumb_bold0.png'), text='DEEP FOCUS MUSIC', bold_word_count=0)
print('wrote /tmp/thumb_bold[0,1,2].png — open them and confirm the bold span grows.')
"
open /tmp/thumb_bold0.png /tmp/thumb_bold1.png /tmp/thumb_bold2.png
```

- [ ] **Step 7: Commit**

```bash
git add pipeline/youtube_thumbnail.py tests/test_youtube_thumbnail.py
git commit -m "feat(thumbnail): render wrap_plan as per-word bold/regular spans

Rewrites measure_lines / fit_text / draw loop to handle multi-style lines.
Each line is drawn word-by-word with the per-word font; word spacing comes
from the regular font's space width. Removes the variation-name hack; bold
now visibly differs from regular because the font files differ.

Adds a pixel-diff smoke test that catches the previous regression (bold
font silently collapsing to regular)."
```

### Task 10: Add `thumbnail_bold_word_count` column

**Files:**
- Create: `console/backend/alembic/versions/026_thumbnail_bold_word_count.py`
- Modify: `console/backend/models/youtube_video.py`

- [ ] **Step 1: Find the current Alembic head**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic heads
```

Note the head revision id (likely `025_spectrum_bar_count_and_align` based on file listing, but verify — there's also a divergent `d885cdd6570e_mcp_server_tables` chain to check).

If both `025_spectrum_bar_count_and_align` and `d885cdd6570e_mcp_server_tables` show as heads, the new migration must `depends_on` only the `025_*` head (the one touching `youtube_videos`) OR be a merge. Use a single down_revision pointing at `025_spectrum_bar_count_and_align`; if alembic complains about multiple heads, the engineer will need to create a merge migration first (`alembic merge heads`) — but only if both heads conflict on `youtube_videos`. Default plan: chain off `025_spectrum_bar_count_and_align`.

- [ ] **Step 2: Create the migration file**

`console/backend/alembic/versions/026_thumbnail_bold_word_count.py`:

```python
"""thumbnail_bold_word_count column

Revision ID: 026_thumbnail_bold_word_count
Revises: 025_spectrum_bar_count_and_align
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = "026_thumbnail_bold_word_count"
down_revision = "025_spectrum_bar_count_and_align"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "youtube_videos",
        sa.Column(
            "thumbnail_bold_word_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("youtube_videos", "thumbnail_bold_word_count")
```

- [ ] **Step 3: Update the model**

In `console/backend/models/youtube_video.py`, add (next to the other thumbnail fields around line 64-69):

```python
    thumbnail_bold_word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
```

- [ ] **Step 4: Run migration locally**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation/console/backend
alembic upgrade head
```

Expected: migration runs cleanly; new column exists. Confirm via:

```bash
psql -d $POSTGRES_DB -c "\d youtube_videos" | grep thumbnail_bold_word_count
```

(Substitute your actual db name; default is the value of `DATABASE_URL` in `console/.env`.)

- [ ] **Step 5: Quick model test**

Append to `tests/test_youtube_video_service_thumbnail.py` (or create `tests/test_youtube_video_bold_word_count.py` if cleaner):

```python
def test_youtube_video_has_thumbnail_bold_word_count_default_1(db):
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_template import VideoTemplate
    t = VideoTemplate(slug="t-bwc", label="x", output_format="landscape_long")
    db.add(t); db.flush()
    v = YoutubeVideo(title="x", template_id=t.id)
    db.add(v); db.flush()
    assert v.thumbnail_bold_word_count == 1
```

Run:

```bash
pytest tests/test_youtube_video_service_thumbnail.py -v -k "thumbnail_bold_word_count"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add console/backend/alembic/versions/026_thumbnail_bold_word_count.py console/backend/models/youtube_video.py tests/test_youtube_video_service_thumbnail.py
git commit -m "feat(thumbnail): add youtube_videos.thumbnail_bold_word_count column

INTEGER NOT NULL DEFAULT 1. Used by the thumbnail-generate endpoint to
control how many leading words render in the bold font."
```

### Task 11: Wire the column through router + frontend

**Files:**
- Modify: `console/backend/routers/youtube_videos.py` (`ThumbnailGenerateRequest`, `generate_thumbnail_endpoint`)
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx` (`RegenerateThumbnailModal`)
- Modify: `console/frontend/src/api/client.js` (extend `generateThumbnail` signature)
- Test: `tests/test_thumbnail_endpoint.py`

- [ ] **Step 1: Read the current `ThumbnailGenerateRequest` and endpoint**

```bash
grep -n "ThumbnailGenerateRequest\|generate_thumbnail_endpoint\|thumbnail-generate" console/backend/routers/youtube_videos.py
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_thumbnail_endpoint.py`:

```python
def test_thumbnail_generate_persists_bold_word_count(db, tmp_path, monkeypatch):
    """When bold_word_count is sent in the request, it's persisted on the video row."""
    from fastapi.testclient import TestClient
    from PIL import Image
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo

    # Seed: template, source-image asset, video pointing at it
    t = VideoTemplate(slug=f"thumb-bwc", label="x", output_format="landscape_long")
    db.add(t); db.flush()
    src_path = tmp_path / "src.jpg"
    Image.new("RGB", (100, 100), color=(100, 100, 100)).save(src_path)
    asset = VideoAsset(file_path=str(src_path), source="manual", asset_type="still_image")
    db.add(asset); db.flush()
    video = YoutubeVideo(title="x", template_id=t.id, thumbnail_asset_id=asset.id)
    db.add(video); db.flush()
    db.commit()

    def _get_db_override():
        yield db

    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/api/youtube-videos/{video.id}/thumbnail-generate",
                json={"text": "DEEP FOCUS MUSIC", "bold_word_count": 2},
            )
        assert resp.status_code == 200, resp.text
        db.refresh(video)
        assert video.thumbnail_bold_word_count == 2
        assert video.thumbnail_text == "DEEP FOCUS MUSIC"
    finally:
        app.dependency_overrides.clear()


def test_thumbnail_generate_uses_video_stored_bold_word_count_when_not_in_request(db, tmp_path):
    """No bold_word_count in request → use whatever the video already has."""
    from fastapi.testclient import TestClient
    from PIL import Image
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo

    t = VideoTemplate(slug=f"thumb-bwc-stored", label="x", output_format="landscape_long")
    db.add(t); db.flush()
    src_path = tmp_path / "src.jpg"
    Image.new("RGB", (100, 100), color=(50, 50, 50)).save(src_path)
    asset = VideoAsset(file_path=str(src_path), source="manual", asset_type="still_image")
    db.add(asset); db.flush()
    video = YoutubeVideo(
        title="x", template_id=t.id, thumbnail_asset_id=asset.id,
        thumbnail_bold_word_count=3,
    )
    db.add(video); db.flush()
    db.commit()

    def _get_db_override():
        yield db

    class _FakeUser:
        id = 1; role = "admin"

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[require_editor_or_admin] = lambda: _FakeUser()
    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/api/youtube-videos/{video.id}/thumbnail-generate",
                json={"text": "DEEP FOCUS MUSIC LOOP"},
            )
        assert resp.status_code == 200, resp.text
        db.refresh(video)
        assert video.thumbnail_bold_word_count == 3  # unchanged
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
pytest tests/test_thumbnail_endpoint.py -v -k "bold_word_count"
```

Expected: FAIL — the field doesn't exist on the request body or isn't being persisted.

- [ ] **Step 4: Update `ThumbnailGenerateRequest`**

Find the `ThumbnailGenerateRequest` class in `console/backend/routers/youtube_videos.py` (it's near the imports / schemas section). Add:

```python
class ThumbnailGenerateRequest(BaseModel):
    text: str | None = None
    bold_word_count: int | None = None
```

- [ ] **Step 5: Update `generate_thumbnail_endpoint`**

In the endpoint body (around line 545-575), after the `text` validation and before calling `generate_thumbnail`, persist the bold count if provided:

```python
    text = body.text
    if text and len(text.strip().split()) > 5:
        raise HTTPException(status_code=400, detail="Thumbnail text must be 5 words or fewer")

    if body.bold_word_count is not None:
        if body.bold_word_count < 0 or body.bold_word_count > 20:
            raise HTTPException(status_code=400, detail="bold_word_count must be between 0 and 20")
        video.thumbnail_bold_word_count = body.bold_word_count
```

Then update the `generate_thumbnail` call from:

```python
    generate_thumbnail(source_path=asset.file_path, output_path=output_path, text=text or None)
```

to:

```python
    generate_thumbnail(
        source_path=asset.file_path,
        output_path=output_path,
        text=text or None,
        bold_word_count=video.thumbnail_bold_word_count,
    )
```

Also extend the AuditLog `details` to include `bold_word_count`:

```python
    db.add(AuditLog(
        user_id=user.id,
        action="generate_thumbnail",
        target_type="youtube_video",
        target_id=str(video_id),
        details={"text": text or None, "bold_word_count": video.thumbnail_bold_word_count},
    ))
```

- [ ] **Step 6: Run tests, verify they pass**

```bash
pytest tests/test_thumbnail_endpoint.py -v
```

Expected: all PASS.

- [ ] **Step 7: Update the frontend API client**

In `console/frontend/src/api/client.js`, find `generateThumbnail` inside `youtubeVideosApi`. Change it to accept and pass an optional `boldWordCount`:

```js
  generateThumbnail: (id, text, boldWordCount) =>
    request(`/api/youtube-videos/${id}/thumbnail-generate`, {
      method: "POST",
      body: JSON.stringify({
        text,
        ...(boldWordCount != null ? { bold_word_count: boldWordCount } : {}),
      }),
    }),
```

(Adapt to the file's actual style — `request` may be named `apiFetch` etc.)

- [ ] **Step 8: Update `RegenerateThumbnailModal` in `YouTubeVideosPage.jsx`**

In the component, add a `boldCount` state alongside `text` (around line 1933):

```jsx
const [boldCount, setBoldCount] = useState(video?.thumbnail_bold_word_count ?? 1)
```

In the `handleGenerate` API call (line 1956), update to pass it:

```jsx
await youtubeVideosApi.generateThumbnail(video.id, text.trim() || null, boldCount)
```

In the modal body, just after the text Input (around line 1999), add a small number input:

```jsx
<div className="flex flex-col gap-1">
  <label className="text-xs text-[#9090a8] font-medium">
    Bold first __ words
  </label>
  <Input
    type="number"
    min={0}
    max={Math.max(wordCount, 1)}
    value={boldCount}
    onChange={e => setBoldCount(Math.max(0, parseInt(e.target.value || "0", 10)))}
  />
  <p className="text-xs text-[#5a5a70]">
    {boldCount === 0 ? "All words regular" :
     boldCount >= wordCount && wordCount > 0 ? "All words bold" :
     `First ${boldCount} of ${wordCount} word${wordCount === 1 ? "" : "s"} bold`}
  </p>
</div>
```

The "5 words max" guard remains on `text`; `boldCount` is allowed up to that, clamped server-side at 20.

- [ ] **Step 9: Smoke-test manually**

```bash
# Backend
cd /Volumes/SSD/Workspace/ai-media-automation
./console/start.sh

# Frontend
cd console/frontend && npm run dev
```

Open `/youtube`, find a video, click thumbnail regenerate:
1. Default boldCount = 1. Generate → first word visibly bolder than the rest.
2. Change to 2 → first two words bold.
3. Change to 0 → all regular.

- [ ] **Step 10: Commit**

```bash
git add console/backend/routers/youtube_videos.py tests/test_thumbnail_endpoint.py console/frontend/src/api/client.js console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat(thumbnail): bold_word_count wired through router + UI

Adds bold_word_count to ThumbnailGenerateRequest, persists it on the video
row, passes it to generate_thumbnail. Frontend modal exposes a number
input (default = video's current value or 1)."
```

### Task 12: Final integration check on Fix 1

- [ ] **Step 1: Run the whole thumbnail test surface**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
pytest tests/test_youtube_thumbnail.py tests/test_thumbnail_endpoint.py tests/test_youtube_video_service_thumbnail.py -v
```

Expected: all PASS.

- [ ] **Step 2: Smoke-test the recreate flow with thumbnail settings**

(Verifies Fix 1 ↔ Fix 4 interaction.)

1. Configure a video with a custom `thumbnail_bold_word_count` (e.g. 2).
2. Render it.
3. Click "Recreate".
4. Open the new draft → thumbnail modal shows boldCount=2 (cloned correctly via the `_RECREATE_CLONED_FIELDS` list).

(No commit — verification step.)

---

## Final cross-cutting verification (no commits)

- [ ] **Step 1: Run the entire YouTube test surface**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
pytest tests/ -v -k "youtube or thumbnail or uploader" 2>&1 | tail -40
```

Expected: all PASS.

- [ ] **Step 2: Browse the changelog**

```bash
git log --oneline main..HEAD
```

Expected: ~10 commits, each scoped to one fix or one sub-step.

- [ ] **Step 3: Manual end-to-end smoke**

In the browser, exercise each of the four fixes:

1. **Fix 3:** Upload a video; in YouTube Studio, confirm "Altered or synthetic content" is ticked.
2. **Fix 2:** Make a short from a soundscape parent; confirm the short has visible/audible content.
3. **Fix 4:** Recreate a done video; confirm the new draft has all settings cloned.
4. **Fix 1:** Regenerate a thumbnail with `boldCount=0,1,2`; confirm the bold span grows.

- [ ] **Step 4: Verify container-side fonts survive a fresh build**

```bash
docker compose build api render
docker compose run --rm api ls /usr/share/fonts/truetype/liberation/ | grep -E "Liberation(Sans|Mono)-(Regular|Bold)\.ttf"
docker compose run --rm api python -c "from pipeline.youtube_thumbnail import DEFAULT_REGULAR_FONT, DEFAULT_BOLD_FONT; print(DEFAULT_REGULAR_FONT, DEFAULT_BOLD_FONT); assert DEFAULT_REGULAR_FONT != DEFAULT_BOLD_FONT, 'bold collapsed to regular in container'"
```

Expected: Liberation Regular and Bold files listed; the python assert passes (paths differ).

---

## Self-Review

**Spec coverage:**
- Fix 1: bundled fonts (Task 8), wrap_plan + bold tagging (Task 8), measure/draw rewrite (Task 9), DB column (Task 10), router persistence (Task 11), UI input (Task 11), default = 1 across the board ✓.
- Fix 2: frontend smart copy (Task 3), backend defensive fallback (Task 2) ✓.
- Fix 3: field rename + logging (Task 1); no DB, no UI per the simplified spec ✓.
- Fix 4: service.recreate (Task 5), endpoint + AuditLog (Task 6), UI + API method (Task 7) ✓.

**Placeholder scan:** Every code step shows full code blocks. Migration revision id is concrete (`026_thumbnail_bold_word_count`). The only intentional flexibility is "use whatever helper name the file already uses" for the frontend API client (Task 7 Step 2) and "AuditLog helper if one exists" (Task 6 Step 4) — both gated on what the engineer finds in the file.

**Type consistency:** `wrap_plan` returns `list[list[tuple[str, bool]]]`; `measure_plan` returns `list[list[tuple[str, ImageFont.FreeTypeFont, int, tuple[int,int,int,int]]]]`; `generate_thumbnail` accepts `bold_word_count: int`. Service method name is `recreate` everywhere. Column name is `thumbnail_bold_word_count` in model, migration, request, and service-clone list. Request field is `bold_word_count`. ✓

**Naming alignment:** Field at API level uses snake_case (`bold_word_count`), JS variable uses camelCase (`boldWordCount`) — this matches the existing pattern in `client.js` (translation at the request boundary).
