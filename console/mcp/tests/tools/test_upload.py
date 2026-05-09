import pytest
import fakeredis.aioredis as fakeredis
from unittest.mock import AsyncMock

from console.mcp.idempotency import IdempotencyStore
from console.mcp.tools.upload import upload, set_idempotency_store


@pytest.mark.asyncio
async def test_list_videos_with_filters():
    c = AsyncMock()
    c.get.return_value = {"items": [], "total": 0}
    await upload(action="list_videos", status="ready", limit=20, _client=c)
    c.get.assert_awaited_once_with("/api/uploads/videos", params={"status": "ready", "limit": 20})


@pytest.mark.asyncio
async def test_set_targets():
    c = AsyncMock()
    c.put.return_value = {"video_id": 9, "channels": [1, 2]}
    out = await upload(action="set_targets", video_id=9, channels=[1, 2], confirm=True, _client=c)
    c.put.assert_awaited_once_with("/api/uploads/videos/9/targets", json={"channels": [1, 2]})


@pytest.mark.asyncio
async def test_upload_one_destructive_async():
    c = AsyncMock()
    c.post.return_value = {"task_id": "up-1"}
    out = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.post.assert_awaited_once_with("/api/uploads/videos/9/upload", json={})
    assert out["task_kind"] == "youtube_upload"


@pytest.mark.asyncio
async def test_upload_all_destructive_async():
    c = AsyncMock()
    c.post.return_value = {"task_id": "up-batch-1"}
    out = await upload(action="upload_all", filter={"status": "ready"},
                       confirm=True, confirm_id="all", _client=c)
    c.post.assert_awaited_once_with("/api/uploads/upload-all", json={"filter": {"status": "ready"}})


@pytest.mark.asyncio
async def test_upload_one_requires_correct_confirm_id():
    c = AsyncMock()
    out = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=8, _client=c)
    assert out["error"]["code"] == "validation.confirm_id_mismatch"


@pytest.mark.asyncio
async def test_delete_target():
    c = AsyncMock()
    out = await upload(action="delete_target", video_id=9, confirm=True, confirm_id=9, _client=c)
    c.delete.assert_awaited_once_with("/api/uploads/videos/9")


@pytest.mark.asyncio
async def test_stream_url():
    c = AsyncMock()
    out = await upload(action="stream_url", video_id=9, _client=c)
    assert out["data"]["url"] == "/api/uploads/videos/9/stream"


# ─── Idempotency wiring tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_one_idempotency_returns_cached():
    r = fakeredis.FakeRedis()
    set_idempotency_store(IdempotencyStore(redis=r, ttl_s=60))
    try:
        c = AsyncMock()
        c.post.return_value = {"task_id": "up-1"}

        out1 = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=9,
                            idempotency_key="cron-2026-05-09", _client=c)
        out2 = await upload(action="upload_one", video_id=9, confirm=True, confirm_id=9,
                            idempotency_key="cron-2026-05-09", _client=c)
        assert out1 == out2
        assert c.post.await_count == 1  # second call cached
    finally:
        set_idempotency_store(None)  # reset for other tests
