import pytest
from console.backend.services.llm_service import (
    AutofillPromptBuilder,
    AutofillResponseParser,
)


# ── AutofillPromptBuilder ─────────────────────────────────────────────────────

def test_build_music_includes_filename_and_duration():
    prompt = AutofillPromptBuilder().build(
        "music",
        {"filename": "chill-lofi.mp3", "file_size_bytes": 1_000_000, "mime_type": "audio/mpeg", "duration_s": 142.3},
        {},
    )
    assert "chill-lofi.mp3" in prompt
    assert "142.3" in prompt


def test_build_music_with_form_values_includes_hints():
    prompt = AutofillPromptBuilder().build(
        "music",
        {"filename": "track.mp3", "file_size_bytes": 500_000, "mime_type": "audio/mpeg", "duration_s": None},
        {"title": "My Draft Title"},
    )
    assert "My Draft Title" in prompt


def test_build_sfx_includes_filename():
    prompt = AutofillPromptBuilder().build(
        "sfx",
        {"filename": "rain_heavy.wav", "file_size_bytes": 500_000, "mime_type": "audio/wav", "duration_s": None},
        {},
    )
    assert "rain_heavy.wav" in prompt


def test_build_asset_image_includes_image_type():
    prompt = AutofillPromptBuilder().build(
        "asset",
        {"filename": "forest_sunset.jpg", "file_size_bytes": 200_000, "mime_type": "image/jpeg", "duration_s": None},
        {},
    )
    assert "forest_sunset.jpg" in prompt
    assert "image" in prompt.lower()


def test_build_asset_video_includes_video_type():
    prompt = AutofillPromptBuilder().build(
        "asset",
        {"filename": "aerial_city.mp4", "file_size_bytes": 5_000_000, "mime_type": "video/mp4", "duration_s": None},
        {},
    )
    assert "video" in prompt.lower()


def test_build_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown modal_type"):
        AutofillPromptBuilder().build(
            "unknown",
            {"filename": "x", "file_size_bytes": 0, "mime_type": "x", "duration_s": None},
            {},
        )


# ── AutofillResponseParser ────────────────────────────────────────────────────

def test_parse_music_full_response():
    result = AutofillResponseParser().parse("music", {
        "title": "Chill Lo-Fi",
        "niches": ["study", "sleep"],
        "moods": ["calm_focus"],
        "genres": ["ambient", "hip-hop"],
        "volume": 0.15,
        "quality_score": 80,
        "is_vocal": False,
    })
    assert result["title"] == "Chill Lo-Fi"
    assert result["moods"] == ["calm_focus"]
    assert result["is_vocal"] is False


def test_parse_music_partial_response_nulls_missing_fields():
    result = AutofillResponseParser().parse("music", {"title": "Track Only"})
    assert result["title"] == "Track Only"
    assert result["moods"] is None
    assert result["niches"] is None


def test_parse_sfx_valid():
    result = AutofillResponseParser().parse("sfx", {"title": "Heavy Rain", "sound_type": "rain_heavy"})
    assert result["title"] == "Heavy Rain"
    assert result["sound_type"] == "rain_heavy"


def test_parse_asset_valid():
    result = AutofillResponseParser().parse("asset", {
        "description": "Aerial forest shot",
        "keywords": ["forest", "aerial", "nature"],
        "source": "manual",
    })
    assert result["description"] == "Aerial forest shot"
    assert result["keywords"] == ["forest", "aerial", "nature"]


def test_parse_malformed_json_string_returns_empty():
    result = AutofillResponseParser().parse("music", "not json at all {{}")
    assert result == {}


def test_parse_unknown_modal_type_returns_empty():
    result = AutofillResponseParser().parse("unknown", {"title": "x"})
    assert result == {}


def test_parse_music_quality_score_float_is_preserved():
    result = AutofillResponseParser().parse("music", {"title": "X", "quality_score": 80.5})
    assert result["quality_score"] == 80.5


def test_build_music_form_values_false_boolean_included():
    prompt = AutofillPromptBuilder().build(
        "music",
        {"filename": "track.mp3", "file_size_bytes": 500_000, "mime_type": "audio/mpeg", "duration_s": None},
        {"is_vocal": False},
    )
    assert "is_vocal" in prompt


# ── Endpoint ──────────────────────────────────────────────────────────────────

from unittest.mock import patch
from fastapi.testclient import TestClient


def _make_client():
    from console.backend.main import app
    from console.backend.auth import require_editor_or_admin
    app.dependency_overrides[require_editor_or_admin] = lambda: {"id": 1, "role": "admin"}
    return TestClient(app)


def test_autofill_endpoint_music_happy_path():
    mock_response = {
        "title": "Lo-Fi Chill",
        "niches": ["study"],
        "moods": ["calm_focus"],
        "genres": ["ambient"],
        "volume": 0.15,
        "quality_score": 80,
        "is_vocal": False,
    }
    with patch("rag.llm_router.get_router") as mock_get_router:
        mock_get_router.return_value.generate.return_value = mock_response
        resp = _make_client().post("/api/llm/autofill", json={
            "modal_type": "music",
            "metadata": {
                "filename": "lofi-chill.mp3",
                "file_size_bytes": 1_024_000,
                "mime_type": "audio/mpeg",
                "duration_s": 120.0,
            },
            "form_values": {"title": "My Track"},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Lo-Fi Chill"
    assert data["moods"] == ["calm_focus"]


def test_autofill_endpoint_rate_limited_returns_429():
    with patch("rag.llm_router.get_router") as mock_get_router:
        mock_get_router.return_value.generate.side_effect = RuntimeError("429 rate limit exceeded")
        resp = _make_client().post("/api/llm/autofill", json={
            "modal_type": "sfx",
            "metadata": {"filename": "rain.wav", "file_size_bytes": 500, "mime_type": "audio/wav"},
            "form_values": {},
        })
    assert resp.status_code == 429


def test_autofill_endpoint_gemini_failure_returns_422():
    with patch("rag.llm_router.get_router") as mock_get_router:
        mock_get_router.return_value.generate.side_effect = RuntimeError("Gemini failed after 3 attempts")
        resp = _make_client().post("/api/llm/autofill", json={
            "modal_type": "asset",
            "metadata": {"filename": "photo.jpg", "file_size_bytes": 200_000, "mime_type": "image/jpeg"},
            "form_values": {},
        })
    assert resp.status_code == 422
