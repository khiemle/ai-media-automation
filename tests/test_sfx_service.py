import pytest
from console.backend.services.sfx_service import SfxService


def test_list_sfx_empty(db):
    svc = SfxService(db)
    result = svc.list_sfx()
    assert result == []


def test_import_sfx(db, tmp_path):
    svc = SfxService(db)
    fake_wav = b"RIFF" + b"\x00" * 40
    track = svc.import_sfx(
        title="Heavy Rain",
        sound_type="rain_heavy",
        source="import",
        file_bytes=fake_wav,
        filename="rain.wav",
        sfx_dir=tmp_path,
    )
    assert track["id"] is not None
    assert track["title"] == "Heavy Rain"
    assert track["sound_type"] == "rain_heavy"
    assert (tmp_path / f"sfx_{track['id']}.wav").exists()


def test_list_sfx_filter_by_type(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    svc.import_sfx("Rain", "rain_heavy", "import", fake, "r.wav", sfx_dir=tmp_path)
    svc.import_sfx("Birds", "birds", "import", fake, "b.wav", sfx_dir=tmp_path)
    result = svc.list_sfx(sound_type="birds")
    assert len(result) == 1
    assert result[0]["sound_type"] == "birds"


def test_delete_sfx(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    track = svc.import_sfx("Rain", "rain_heavy", "import", fake, "r.wav", sfx_dir=tmp_path)
    file_path = tmp_path / f"sfx_{track['id']}.wav"
    svc.delete_sfx(track["id"])
    assert svc.list_sfx() == []
    assert not file_path.exists()


def test_list_distinct_sound_types(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    svc.import_sfx("Rain A", "rain_heavy", "import", fake, "a.wav", sfx_dir=tmp_path)
    svc.import_sfx("Rain B", "rain_heavy", "import", fake, "b.wav", sfx_dir=tmp_path)
    svc.import_sfx("Birds", "birds", "import", fake, "c.wav", sfx_dir=tmp_path)
    types = svc.list_sound_types()
    assert sorted(types) == ["birds", "rain_heavy"]


def test_import_sfx_is_loopable_true(db, tmp_path):
    svc = SfxService(db)
    fake = b"ID3" + b"\x00" * 40
    track = svc.import_sfx(
        title="Loop Campfire",
        sound_type=None,
        source="elevenlabs",
        file_bytes=fake,
        filename="sfx.mp3",
        is_loopable=True,
        sfx_dir=tmp_path,
    )
    assert track["is_loopable"] is True


def test_import_sfx_is_loopable_defaults_false(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    track = svc.import_sfx(
        title="Rain",
        sound_type="rain_heavy",
        source="import",
        file_bytes=fake,
        filename="r.wav",
        sfx_dir=tmp_path,
    )
    assert track["is_loopable"] is False
