import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.visual_asset import visual_asset


@pytest.mark.asyncio
async def test_list_with_filters():
    client = AsyncMock()
    client.get.return_value = {"items": [], "total": 0}
    await visual_asset(action="list", niche="forest", limit=10, _client=client)
    client.get.assert_awaited_once_with("/api/production/assets", params={"niche": "forest", "limit": 10})


@pytest.mark.asyncio
async def test_get():
    client = AsyncMock()
    client.get.return_value = {"id": 5}
    await visual_asset(action="get", asset_id=5, _client=client)
    client.get.assert_awaited_once_with("/api/production/assets/5", params={})


@pytest.mark.asyncio
async def test_stream_and_thumbnail_urls():
    client = AsyncMock()
    out = await visual_asset(action="stream_url", asset_id=5, _client=client)
    assert out["data"]["url"].endswith("/api/production/assets/5/stream")
    out = await visual_asset(action="get_thumbnail", asset_id=5, _client=client)
    assert out["data"]["url"].endswith("/api/production/assets/5/thumbnail")


@pytest.mark.asyncio
async def test_upload_multipart(tmp_path):
    f = tmp_path / "forest.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypisom")

    client = AsyncMock()
    client.multipart_post.return_value = {"id": 77, "source": "manual"}

    out = await visual_asset(
        action="upload",
        file_path=str(f),
        title="forest clip",
        source="manual",
        description="rainy forest",
        keywords="forest,rain",
        asset_type="video_clip",
        confirm=True,
        _client=client,
    )
    assert out["ok"] is True
    client.multipart_post.assert_awaited_once()
    call = client.multipart_post.await_args
    assert call.kwargs["files"]["file"][0] == "forest.mp4"
    assert call.kwargs["data"]["title"] == "forest clip"
    assert call.kwargs["data"]["source"] == "manual"
    assert call.kwargs["data"]["keywords"] == "forest,rain"
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_missing_file_returns_validation_error():
    client = AsyncMock()
    out = await visual_asset(
        action="upload",
        file_path="/nonexistent/clip.mp4",
        confirm=True,
        _client=client,
    )
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.invalid_args"
    client.multipart_post.assert_not_called()


@pytest.mark.asyncio
async def test_animate_async():
    client = AsyncMock()
    client.post.return_value = {"task_id": "rwy-1"}
    out = await visual_asset(action="animate", asset_id=5, prompt="slow zoom", confirm=True, _client=client)
    assert out["task_kind"] == "visual_asset_animate"
    client.post.assert_awaited_once_with("/api/production/assets/5/animate", json={"prompt": "slow zoom"})


@pytest.mark.asyncio
async def test_upscale_async():
    client = AsyncMock()
    client.post.return_value = {"task_id": "tpz-1"}
    out = await visual_asset(action="upscale", asset_id=5, target="4k", confirm=True, _client=client)
    assert out["task_kind"] == "visual_asset_upscale"
    client.post.assert_awaited_once_with("/api/production/assets/5/upscale", json={"target": "4k"})


@pytest.mark.asyncio
async def test_update():
    client = AsyncMock()
    client.put.return_value = {"id": 5, "title": "y"}
    await visual_asset(action="update", asset_id=5, fields={"title": "y"}, confirm=True, _client=client)
    client.put.assert_awaited_once_with("/api/production/assets/5", json={"title": "y"})


@pytest.mark.asyncio
async def test_delete_destructive():
    client = AsyncMock()
    out = await visual_asset(action="delete", asset_id=5, confirm=True, confirm_id=5, _client=client)
    client.delete.assert_awaited_once_with("/api/production/assets/5")
