import uuid

import pytest
from pathlib import Path

from console.backend.models.video_template import VideoTemplate
from console.backend.models.youtube_video import YoutubeVideo
from console.backend.services.youtube_video_service import YoutubeVideoService


def _seed_template(db) -> VideoTemplate:
    slug = f"test-{uuid.uuid4().hex[:8]}"
    t = VideoTemplate(slug=slug, label="Test", output_format="landscape_long")
    db.add(t)
    db.flush()
    return t


def _seed_video(db, **overrides):
    template = _seed_template(db)
    v = YoutubeVideo(title="t", template_id=template.id, **overrides)
    db.add(v)
    db.flush()
    return v


def test_update_video_rejects_done_status(db):
    v = _seed_video(db, status="done")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="cannot be edited"):
        svc.update_video(v.id, {"title": "new"}, user_id=None)


def test_update_video_rejects_published_status(db):
    v = _seed_video(db, status="published")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="cannot be edited"):
        svc.update_video(v.id, {"title": "new"}, user_id=None)


def test_update_video_rejects_actively_running_statuses(db):
    svc = YoutubeVideoService(db)
    for status in ("queued", "rendering", "audio_preview_rendering", "video_preview_rendering"):
        v = _seed_video(db, status=status)
        with pytest.raises(ValueError, match="cannot be edited"):
            svc.update_video(v.id, {"title": "new"}, user_id=None)


def test_update_video_resets_to_draft_and_clears_celery_task(db):
    v = _seed_video(db, status="failed", celery_task_id="some-task-id")
    out = YoutubeVideoService(db).update_video(v.id, {"title": "new"}, user_id=None)
    assert out["status"] == "draft"
    assert out["celery_task_id"] is None
    assert out["title"] == "new"


def test_update_video_deletes_preview_files(tmp_path, db):
    audio = tmp_path / "audio.wav"
    video = tmp_path / "video.mp4"
    audio.write_bytes(b"fake")
    video.write_bytes(b"fake")
    v = _seed_video(
        db,
        status="video_preview_ready",
        audio_preview_path=str(audio),
        video_preview_path=str(video),
    )
    out = YoutubeVideoService(db).update_video(v.id, {"title": "new"}, user_id=None)
    assert not audio.exists()
    assert not video.exists()
    assert out["audio_preview_path"] is None
    assert out["video_preview_path"] is None


def test_update_video_validates_unknown_asset_ids(db):
    v = _seed_video(db, status="draft")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="unknown asset"):
        svc.update_video(v.id, {"visual_asset_ids": [99999]}, user_id=None)


def test_update_video_validates_per_clip_video_requires_positive_duration(db):
    from console.backend.models.video_asset import VideoAsset
    a = VideoAsset(file_path="/tmp/a.mp4", source="manual", asset_type="video_clip")
    db.add(a); db.flush()
    v = _seed_video(db, status="draft")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="per_clip mode requires duration > 0"):
        svc.update_video(v.id, {
            "visual_asset_ids": [a.id],
            "visual_clip_durations_s": [0.0],
            "visual_loop_mode": "per_clip",
        }, user_id=None)


def test_update_video_autofills_still_duration(db):
    from console.backend.models.video_asset import VideoAsset
    img = VideoAsset(file_path="/tmp/a.jpg", source="manual", asset_type="still_image")
    db.add(img); db.flush()
    v = _seed_video(db, status="draft")
    out = YoutubeVideoService(db).update_video(v.id, {
        "visual_asset_ids": [img.id],
        "visual_clip_durations_s": [0.0],
        "visual_loop_mode": "concat_loop",
    }, user_id=None)
    assert out["visual_clip_durations_s"] == [3.0]


def test_update_video_rejects_durations_length_mismatch(db):
    from console.backend.models.video_asset import VideoAsset
    a = VideoAsset(file_path="/tmp/a.mp4", source="manual", asset_type="video_clip")
    db.add(a); db.flush()
    v = _seed_video(db, status="draft")
    svc = YoutubeVideoService(db)
    with pytest.raises(ValueError, match="length .* must match"):
        svc.update_video(v.id, {
            "visual_asset_ids": [a.id],
            "visual_clip_durations_s": [1.0, 2.0],
        }, user_id=None)
