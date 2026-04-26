import pytest
from unittest.mock import MagicMock, patch


def _make_track(**kwargs):
    t = MagicMock()
    t.id = kwargs.get("id", 1)
    t.title = kwargs.get("title", "Test Track")
    t.file_path = kwargs.get("file_path", "assets/music/1.mp3")
    t.duration_s = kwargs.get("duration_s", 30.0)
    t.niches = kwargs.get("niches", ["fitness"])
    t.moods = kwargs.get("moods", ["energetic"])
    t.genres = kwargs.get("genres", ["pop"])
    t.is_vocal = kwargs.get("is_vocal", False)
    t.is_favorite = kwargs.get("is_favorite", False)
    t.volume = kwargs.get("volume", 0.15)
    t.usage_count = kwargs.get("usage_count", 0)
    t.quality_score = kwargs.get("quality_score", 80)
    t.provider = kwargs.get("provider", "import")
    t.provider_task_id = kwargs.get("provider_task_id", None)
    t.generation_status = kwargs.get("generation_status", "ready")
    t.generation_prompt = kwargs.get("generation_prompt", None)
    t.created_at = None
    return t


def test_list_tracks_returns_all_when_no_filters():
    db = MagicMock()
    track = _make_track()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [track]
    db.query.return_value.order_by.return_value.all.return_value = [track]

    from console.backend.services.music_service import MusicService
    svc = MusicService(db)
    result = svc.list_tracks()

    assert len(result) == 1
    assert result[0]["title"] == "Test Track"


def test_increment_usage_updates_count():
    db = MagicMock()
    track = _make_track(usage_count=3)
    db.query.return_value.filter.return_value.first.return_value = track

    from console.backend.services.music_service import MusicService
    svc = MusicService(db)
    svc.increment_usage(1)

    assert track.usage_count == 4
    db.commit.assert_called_once()


def test_expand_prompt_calls_gemini():
    db = MagicMock()

    mock_router = MagicMock()
    mock_router.generate.return_value = '{"expanded_prompt": "An energetic pop track...", "negative_tags": "slow, sad"}'

    with patch("rag.llm_router.GeminiRouter", return_value=mock_router):
        from console.backend.services.music_service import MusicService
        svc = MusicService(db)
        result = svc.expand_prompt_with_gemini(
            idea="upbeat workout music",
            niches=["fitness"],
            moods=["energetic"],
            genres=["pop"],
            is_vocal=False,
        )

    assert "expanded_prompt" in result
    assert "negative_tags" in result
