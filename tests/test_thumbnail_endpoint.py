import pytest
from pathlib import Path
from unittest.mock import patch
from console.backend.models.video_asset import VideoAsset


def _make_asset(db, tmp_path, asset_type="video_clip", with_thumb=False):
    video_file = tmp_path / "asset_99.mp4"
    video_file.write_bytes(b"\x00" * 16)
    thumb_file = tmp_path / "asset_99_thumb.jpg"
    if with_thumb:
        thumb_file.write_bytes(b"\xff\xd8\xff")

    asset = VideoAsset(
        file_path=str(video_file),
        thumbnail_path=str(thumb_file) if with_thumb else None,
        source="manual",
        asset_type=asset_type,
        keywords=[],
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _make_image_asset(db, tmp_path):
    img_file = tmp_path / "asset_88.jpg"
    img_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 20)
    asset = VideoAsset(
        file_path=str(img_file),
        thumbnail_path=None,
        source="midjourney",
        asset_type="still_image",
        keywords=[],
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def test_thumbnail_serves_existing_thumb(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_asset(db, tmp_path, with_thumb=True)
    svc = ProductionService(db)
    path, media_type = svc.get_thumbnail_path(asset.id, generate=True)
    assert path == asset.thumbnail_path
    assert "image" in media_type


def test_thumbnail_returns_none_when_no_thumb_and_generate_false(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_asset(db, tmp_path, with_thumb=False)
    svc = ProductionService(db)
    result = svc.get_thumbnail_path(asset.id, generate=False)
    assert result is None


def test_thumbnail_generates_lazily_for_video(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_asset(db, tmp_path, with_thumb=False)

    def fake_generate(video_path):
        thumb = tmp_path / "asset_99_thumb.jpg"
        thumb.write_bytes(b"\xff\xd8\xff")
        return str(thumb)

    with patch("console.backend.services.production_service.generate_video_thumbnail", side_effect=fake_generate):
        svc = ProductionService(db)
        result = svc.get_thumbnail_path(asset.id, generate=True)

    assert result is not None
    path, media_type = result
    assert path.endswith("_thumb.jpg")
    db.refresh(asset)
    assert asset.thumbnail_path == path  # persisted to DB


def test_thumbnail_lazy_for_still_image(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    asset = _make_image_asset(db, tmp_path)
    svc = ProductionService(db)
    result = svc.get_thumbnail_path(asset.id, generate=True)
    assert result is not None
    path, _ = result
    assert path == asset.file_path
    db.refresh(asset)
    assert asset.thumbnail_path == path  # persisted


def test_thumbnail_returns_none_for_missing_asset(db, tmp_path):
    from console.backend.services.production_service import ProductionService
    svc = ProductionService(db)
    result = svc.get_thumbnail_path(99999, generate=True)
    assert result is None


def test_thumbnail_generate_persists_bold_word_count(db, tmp_path, monkeypatch):
    """When bold_word_count is sent in the request, it's persisted on the video row."""
    import uuid
    from fastapi.testclient import TestClient
    from PIL import Image
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo

    # Seed: template, source-image asset, video pointing at it
    t = VideoTemplate(slug=f"thumb-bwc-{uuid.uuid4().hex[:6]}", label="x", output_format="landscape_long")
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
    """No bold_word_count in request -> use whatever the video already has."""
    import uuid
    from fastapi.testclient import TestClient
    from PIL import Image
    from console.backend.main import app
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.models.video_asset import VideoAsset
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.youtube_video import YoutubeVideo

    t = VideoTemplate(slug=f"thumb-bwc-stored-{uuid.uuid4().hex[:6]}", label="x", output_format="landscape_long")
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
