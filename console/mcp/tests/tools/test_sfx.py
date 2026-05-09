import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.sfx import sfx


@pytest.mark.asyncio
async def test_list_sound_types():
    client = AsyncMock()
    client.get.return_value = ["wind", "rain", "fire"]
    out = await sfx(action="list_sound_types", _client=client)
    client.get.assert_awaited_once_with("/api/sfx/sound-types", params={})


@pytest.mark.asyncio
async def test_list_with_filters():
    client = AsyncMock()
    client.get.return_value = []
    await sfx(action="list", sound_type="wind", limit=20, _client=client)
    client.get.assert_awaited_once_with("/api/sfx", params={"sound_type": "wind", "limit": 20})


@pytest.mark.asyncio
async def test_stream_url():
    client = AsyncMock()
    out = await sfx(action="get_stream_url", sfx_id=3, _client=client)
    assert out["data"]["url"] == "/api/sfx/3/stream"


@pytest.mark.asyncio
async def test_generate_sync():
    client = AsyncMock()
    client.post.return_value = {"id": 7, "title": "thunder crack", "file_path": "/sfx/7.mp3"}
    out = await sfx(action="generate", text="thunder", duration_seconds=4.0, confirm=True, _client=client)
    assert out["ok"] is True
    client.post.assert_awaited_once_with(
        "/api/sfx/generate",
        json={"text": "thunder", "duration_seconds": 4.0},
    )


@pytest.mark.asyncio
async def test_import_file_uploads_multipart(tmp_path):
    f = tmp_path / "rain.wav"
    f.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

    client = AsyncMock()
    client.multipart_post.return_value = {"id": 9, "title": "rain", "file_path": "/sfx/9.wav"}

    out = await sfx(
        action="import_file",
        file_path=str(f),
        title="rain",
        sound_type="nature",
        confirm=True,
        _client=client,
    )
    assert out["ok"] is True
    client.multipart_post.assert_awaited_once()
    call = client.multipart_post.await_args
    assert call.kwargs["files"]["file"][0] == "rain.wav"
    assert call.kwargs["data"] == {"title": "rain", "sound_type": "nature"}
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_file_with_source(tmp_path):
    f = tmp_path / "wind.mp3"
    f.write_bytes(b"\xff\xfb\x90\x00")

    client = AsyncMock()
    client.multipart_post.return_value = {"id": 10, "title": "wind", "file_path": "/sfx/10.mp3"}

    await sfx(
        action="import_file",
        file_path=str(f),
        title="wind",
        sound_type="nature",
        source="import",
        confirm=True,
        _client=client,
    )
    call = client.multipart_post.await_args
    assert call.kwargs["data"]["source"] == "import"


@pytest.mark.asyncio
async def test_import_file_missing_returns_validation_error():
    client = AsyncMock()
    out = await sfx(
        action="import_file",
        file_path="/nonexistent/rain.wav",
        title="rain",
        sound_type="nature",
        confirm=True,
        _client=client,
    )
    assert out["ok"] is False
    assert out["error"]["code"] == "validation.invalid_args"
    client.multipart_post.assert_not_called()


@pytest.mark.asyncio
async def test_delete_destructive():
    client = AsyncMock()
    out = await sfx(action="delete", sfx_id=9, confirm=True, confirm_id=9, _client=client)
    client.delete.assert_awaited_once_with("/api/sfx/9")
