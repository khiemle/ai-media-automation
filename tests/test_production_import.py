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


def test_import_asset_filename_uses_id(db, tmp_path):
    svc = ProductionService(db)
    result = svc.import_asset(
        file_bytes=b'\xff\xd8\xff' + b'\x00' * 20,
        filename='test.png',
        source='manual',
        description=None,
        keywords=None,
        assets_dir=tmp_path,
    )
    expected_name = f"asset_{result['id']}.png"
    assert Path(result['file_path']).name == expected_name


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
