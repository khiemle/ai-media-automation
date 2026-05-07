import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

_FAKE_CFG = {"elevenlabs": {"api_key": "test-el-key"}}
_FAKE_AUDIO = b"ID3" + b"\x00" * 100


def _make_client(db_session):
    from console.backend.database import get_db
    from console.backend.auth import require_editor_or_admin
    from console.backend.routers.sfx import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_editor_or_admin] = lambda: {"id": 1, "role": "admin"}
    return TestClient(app)


def test_generate_sfx_success(db, tmp_path):
    mock_instance = MagicMock()
    mock_instance.text_to_sound_effects.convert.return_value = iter([_FAKE_AUDIO])
    mock_class = MagicMock(return_value=mock_instance)

    with patch("console.backend.routers.sfx.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.routers.sfx.ElevenLabs", mock_class), \
         patch("console.backend.services.sfx_service.SFX_DIR", tmp_path):
        client = _make_client(db)
        resp = client.post("/api/sfx/generate", json={
            "text": "Crackling campfire with gentle wind",
            "loop": True,
            "duration_seconds": 10.0,
            "title": "Campfire Loop",
        })

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Campfire Loop"
    assert data["source"] == "elevenlabs"
    assert data["is_loopable"] is True
    mock_instance.text_to_sound_effects.convert.assert_called_once_with(
        text="Crackling campfire with gentle wind",
        loop=True,
        duration_seconds=10.0,
    )


def test_generate_sfx_auto_title_from_prompt(db, tmp_path):
    mock_instance = MagicMock()
    mock_instance.text_to_sound_effects.convert.return_value = iter([_FAKE_AUDIO])
    mock_class = MagicMock(return_value=mock_instance)

    with patch("console.backend.routers.sfx.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.routers.sfx.ElevenLabs", mock_class), \
         patch("console.backend.services.sfx_service.SFX_DIR", tmp_path):
        client = _make_client(db)
        resp = client.post("/api/sfx/generate", json={
            "text": "A very long prompt that exceeds sixty characters and should be truncated properly",
            "loop": False,
        })

    assert resp.status_code == 201
    assert len(resp.json()["title"]) <= 60


def test_generate_sfx_missing_api_key_returns_503(db):
    with patch("console.backend.routers.sfx.get_config", return_value={"elevenlabs": {"api_key": ""}}):
        client = _make_client(db)
        resp = client.post("/api/sfx/generate", json={"text": "rain"})
    assert resp.status_code == 503


def test_generate_sfx_elevenlabs_error_returns_502(db, tmp_path):
    mock_instance = MagicMock()
    mock_instance.text_to_sound_effects.convert.side_effect = RuntimeError("quota exceeded")
    mock_class = MagicMock(return_value=mock_instance)

    with patch("console.backend.routers.sfx.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.routers.sfx.ElevenLabs", mock_class):
        client = _make_client(db)
        resp = client.post("/api/sfx/generate", json={"text": "thunder"})

    assert resp.status_code == 502
    assert "quota exceeded" in resp.json()["detail"]


def test_generate_sfx_loop_false_persisted(db, tmp_path):
    mock_instance = MagicMock()
    mock_instance.text_to_sound_effects.convert.return_value = iter([_FAKE_AUDIO])
    mock_class = MagicMock(return_value=mock_instance)

    with patch("console.backend.routers.sfx.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.routers.sfx.ElevenLabs", mock_class), \
         patch("console.backend.services.sfx_service.SFX_DIR", tmp_path):
        client = _make_client(db)
        resp = client.post("/api/sfx/generate", json={"text": "gentle rain"})

    assert resp.status_code == 201
    assert resp.json()["is_loopable"] is False
