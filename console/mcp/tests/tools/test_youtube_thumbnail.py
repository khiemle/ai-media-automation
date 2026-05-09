import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.youtube_thumbnail import youtube_thumbnail


@pytest.mark.asyncio
async def test_upload_image_multipart(tmp_path):
    f = tmp_path / "thumb.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n")

    c = AsyncMock()
    c.multipart_post.return_value = {"asset_id": 55, "source_url": "/api/youtube-videos/9/thumbnail-source"}

    out = await youtube_thumbnail(
        action="upload_image", video_id=9, file_path=str(f), confirm=True, _client=c
    )
    assert out["ok"] is True
    c.multipart_post.assert_awaited_once()
    call = c.multipart_post.await_args
    # Backend field name is "image", not "file"
    assert "image" in call.kwargs["files"]
    assert call.kwargs["files"]["image"][0] == "thumb.png"
    c.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_image_missing_file_returns_validation_error():
    c = AsyncMock()
    out = await youtube_thumbnail(
        action="upload_image", video_id=9, file_path="/nonexistent/thumb.png",
        confirm=True, _client=c
    )
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.invalid_args"
    c.multipart_post.assert_not_called()


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
