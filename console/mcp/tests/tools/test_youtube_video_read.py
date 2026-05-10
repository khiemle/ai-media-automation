import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.youtube_video import youtube_video


@pytest.mark.asyncio
async def test_list_with_filters():
    c = AsyncMock()
    c.get.return_value = {"items": [], "total": 0}
    await youtube_video(action="list", status="draft", limit=20, _client=c)
    c.get.assert_awaited_once_with("/api/youtube-videos", params={"status": "draft", "limit": 20})


@pytest.mark.asyncio
async def test_get_returns_video():
    c = AsyncMock()
    c.get.return_value = {"id": 7, "title": "x"}
    out = await youtube_video(action="get", video_id=7, _client=c)
    assert out["data"]["id"] == 7
    c.get.assert_awaited_once_with("/api/youtube-videos/7", params={})


@pytest.mark.asyncio
async def test_list_templates_and_get_template():
    c = AsyncMock()
    c.get.return_value = []
    await youtube_video(action="list_templates", _client=c)
    c.get.assert_awaited_with("/api/youtube-videos/templates", params={})

    c.get.return_value = {"id": 1}
    await youtube_video(action="get_template", template_id=1, _client=c)
    c.get.assert_awaited_with("/api/youtube-videos/templates/1", params={})


@pytest.mark.asyncio
async def test_get_render_state():
    c = AsyncMock()
    c.get.return_value = {"phase": "audio_preview", "progress": 0.4}
    out = await youtube_video(action="get_render_state", video_id=7, _client=c)
    c.get.assert_awaited_once_with("/api/youtube-videos/7/render/state", params={})
    assert out["data"]["phase"] == "audio_preview"


@pytest.mark.asyncio
async def test_get_chapters_music_template():
    """get_chapters passes through the API response intact."""
    c = AsyncMock()
    c.get.return_value = {
        "video_id": 42,
        "chapters": [
            {"seconds": 0,   "title": "Track 1"},
            {"seconds": 60,  "title": "Track 2"},
            {"seconds": 120, "title": "Track 3"},
        ],
    }
    out = await youtube_video(action="get_chapters", video_id=42, _client=c)
    c.get.assert_awaited_once_with("/api/youtube-videos/42/chapters", params={})
    assert out["data"]["video_id"] == 42
    assert len(out["data"]["chapters"]) == 3
    assert out["data"]["chapters"][1]["seconds"] == 60


@pytest.mark.asyncio
async def test_get_chapters_non_music_returns_null():
    """For non-music templates the API returns chapters=null; tool passes it through."""
    c = AsyncMock()
    c.get.return_value = {"video_id": 5, "chapters": None}
    out = await youtube_video(action="get_chapters", video_id=5, _client=c)
    c.get.assert_awaited_once_with("/api/youtube-videos/5/chapters", params={})
    assert out["data"]["chapters"] is None


@pytest.mark.asyncio
async def test_get_chapters_requires_video_id():
    """get_chapters returns an error envelope when video_id is missing."""
    c = AsyncMock()
    out = await youtube_video(action="get_chapters", _client=c)
    assert out["ok"] is False
    assert "video_id" in out["error"]["message"]
    c.get.assert_not_awaited()
