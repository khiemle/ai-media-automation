import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.youtube_thumbnail import youtube_thumbnail


@pytest.mark.asyncio
async def test_upload_image_not_implemented():
    c = AsyncMock()
    out = await youtube_thumbnail(
        action="upload_image", video_id=9, file_path="/tmp/x.png", confirm=True, _client=c
    )
    assert out["ok"] is False
    assert out["error"]["code"] == "not_implemented"
    c.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_with_text_sync():
    c = AsyncMock()
    c.post.return_value = {"thumbnail_url": "/thumbnails/9.png"}
    out = await youtube_thumbnail(
        action="generate_with_text", video_id=9, text="DEEP SLEEP",
        style="bold-yellow", confirm=True, _client=c
    )
    # Backend is synchronous — no task_id; returns data directly
    assert out["ok"] is True
    c.post.assert_awaited_once_with(
        "/api/youtube-videos/9/thumbnail-generate",
        json={"text": "DEEP SLEEP"},
    )


@pytest.mark.asyncio
async def test_get_current_and_source_urls():
    c = AsyncMock()
    out = await youtube_thumbnail(action="get_current", video_id=9, _client=c)
    assert out["data"]["url"] == "/api/youtube-videos/9/thumbnail"
    out = await youtube_thumbnail(action="get_source", video_id=9, _client=c)
    assert out["data"]["url"] == "/api/youtube-videos/9/thumbnail-source"
