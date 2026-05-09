import pytest
from pathlib import Path
from console.backend.services.production_service import ProductionService


def test_import_image_asset(db, tmp_path):
    svc = ProductionService(db)
    fake_jpg = b'\xff\xd8\xff\xe0' + b'\x00' * 40  # minimal JPEG header
    result = svc.import_asset(
        file_bytes=fake_jpg,
        filename='photo.jpg',
        source='midjourney',
        description='A dark rainy window',
        keywords=['rain', 'dark', 'window'],
        assets_dir=tmp_path,
    )
    assert result['id'] is not None
    assert result['asset_type'] == 'still_image'
    assert result['source'] == 'midjourney'
    assert result['description'] == 'A dark rainy window'
    assert result['keywords'] == ['rain', 'dark', 'window']
    assert Path(result['file_path']).exists()


def test_import_video_asset(db, tmp_path):
    svc = ProductionService(db)
    fake_mp4 = b'\x00\x00\x00\x18ftyp' + b'\x00' * 40
    result = svc.import_asset(
        file_bytes=fake_mp4,
        filename='loop.mp4',
        source='manual',
        description=None,
        keywords=None,
        assets_dir=tmp_path,
    )
    assert result['asset_type'] == 'video_clip'
    assert result['source'] == 'manual'
    assert result['keywords'] == []


def test_import_asset_filename_uses_slug(db, tmp_path):
    """Imported assets should use a readable slug filename, not asset_{id}.ext."""
    from datetime import date
    svc = ProductionService(db)
    result = svc.import_asset(
        file_bytes=b'\xff\xd8\xff' + b'\x00' * 20,
        filename='test.png',
        source='manual',
        description=None,
        keywords=None,
        assets_dir=tmp_path,
    )
    today = date.today().strftime('%Y%m%d')
    # Without title or description, label falls back to filename stem "test"
    assert Path(result['file_path']).name == f"{today}_test.png"

def test_import_asset_filename_uses_title(db, tmp_path):
    """When title is provided, the slug is derived from it."""
    from datetime import date
    svc = ProductionService(db)
    result = svc.import_asset(
        file_bytes=b'\xff\xd8\xff' + b'\x00' * 20,
        filename='upload.png',
        source='manual',
        description=None,
        keywords=None,
        title='Rainy Window Scene',
        assets_dir=tmp_path,
    )
    today = date.today().strftime('%Y%m%d')
    assert Path(result['file_path']).name == f"{today}_rainy-window-scene.png"

def test_import_asset_filename_uses_description_fallback(db, tmp_path):
    """When no title, description is used as the label fallback."""
    from datetime import date
    svc = ProductionService(db)
    result = svc.import_asset(
        file_bytes=b'\xff\xd8\xff' + b'\x00' * 20,
        filename='upload.png',
        source='manual',
        description='Dark forest path',
        keywords=None,
        assets_dir=tmp_path,
    )
    today = date.today().strftime('%Y%m%d')
    assert Path(result['file_path']).name == f"{today}_dark-forest-path.png"


def test_import_unsupported_extension_raises(db, tmp_path):
    svc = ProductionService(db)
    with pytest.raises(ValueError, match="Unsupported file type"):
        svc.import_asset(
            file_bytes=b'data',
            filename='file.txt',
            source='manual',
            description=None,
            keywords=None,
            assets_dir=tmp_path,
        )


def test_import_explicit_asset_type_override(db, tmp_path):
    svc = ProductionService(db)
    result = svc.import_asset(
        file_bytes=b'\xff\xd8\xff' + b'\x00' * 20,
        filename='photo.jpg',
        source='manual',
        description=None,
        keywords=None,
        asset_type='video_clip',  # override: jpg but caller says video_clip
        assets_dir=tmp_path,
    )
    assert result['asset_type'] == 'video_clip'
