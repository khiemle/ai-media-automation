import pytest
import fakeredis.aioredis as fakeredis

from console.mcp.idempotency import IdempotencyStore


@pytest.mark.asyncio
async def test_first_call_runs_second_call_returns_cached():
    r = fakeredis.FakeRedis()
    store = IdempotencyStore(redis=r, ttl_s=60)
    calls = []

    async def run():
        calls.append(1)
        return {"ok": True, "task_id": "abc-1"}

    r1 = await store.run_once(key="upload-9", run=run)
    r2 = await store.run_once(key="upload-9", run=run)
    assert r1 == r2
    assert calls == [1]


@pytest.mark.asyncio
async def test_different_key_runs_again():
    r = fakeredis.FakeRedis()
    store = IdempotencyStore(redis=r, ttl_s=60)
    calls = []

    async def run():
        calls.append(1)
        return {"ok": True, "task_id": f"id-{len(calls)}"}

    await store.run_once(key="a", run=run)
    await store.run_once(key="b", run=run)
    assert calls == [1, 1]
