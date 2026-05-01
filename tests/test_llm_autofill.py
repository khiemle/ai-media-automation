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
