import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.pipeline_jobs import pipeline_jobs


@pytest.mark.asyncio
async def test_list_action_passes_filters():
    client = AsyncMock()
    client.get.return_value = {"items": [], "total": 0}
    out = await pipeline_jobs(action="list", status="FAILURE", limit=20, _client=client)
    assert out["ok"] is True
    client.get.assert_awaited_once_with("/api/pipeline/jobs", params={"status": "FAILURE", "limit": 20})


@pytest.mark.asyncio
async def test_get_logs_action():
    client = AsyncMock()
    client.get.return_value = {"lines": ["log1", "log2"]}
    out = await pipeline_jobs(action="get_logs", job_id="abc", _client=client)
    assert out["data"]["lines"] == ["log1", "log2"]


@pytest.mark.asyncio
async def test_retry_requires_confirm():
    client = AsyncMock()
    out = await pipeline_jobs(action="retry", job_id="abc", _client=client)
    assert out["ok"] is False
    assert out["needs_confirmation"] is True
    client.patch.assert_not_called()


@pytest.mark.asyncio
async def test_retry_with_confirm_calls_patch():
    client = AsyncMock()
    client.patch.return_value = {"job_id": "abc", "status": "RETRY"}
    out = await pipeline_jobs(action="retry", job_id="abc", confirm=True, _client=client)
    assert out["ok"] is True
    client.patch.assert_awaited_once_with("/api/pipeline/jobs/abc/retry")


@pytest.mark.asyncio
async def test_cancel_with_confirm_calls_patch():
    client = AsyncMock()
    client.patch.return_value = {"job_id": "abc", "status": "REVOKED"}
    out = await pipeline_jobs(action="cancel", job_id="abc", confirm=True, _client=client)
    assert out["ok"] is True
    client.patch.assert_awaited_once_with("/api/pipeline/jobs/abc/cancel")


@pytest.mark.asyncio
async def test_stats_action():
    client = AsyncMock()
    client.get.return_value = {"queued": 1, "running": 2, "succeeded": 100, "failed": 3}
    out = await pipeline_jobs(action="stats", _client=client)
    assert out["data"]["queued"] == 1
