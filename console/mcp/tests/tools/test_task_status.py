import pytest
from unittest.mock import AsyncMock

from console.mcp.tools.task_status import task_status


@pytest.mark.asyncio
async def test_pending_status():
    client = AsyncMock()
    client.get.return_value = {"status": "PENDING", "progress": None, "result": None, "error": None}
    out = await task_status(task_id="abc-123", _client=client)
    assert out["ok"] is True
    assert out["status"] == "PENDING"
    assert out["task_id"] == "abc-123"
    client.get.assert_awaited_once_with("/api/pipeline/jobs/abc-123")


@pytest.mark.asyncio
async def test_progress_with_percent_and_stage():
    client = AsyncMock()
    client.get.return_value = {
        "status": "PROGRESS",
        "progress": {"percent": 42, "stage": "compositing"},
        "result": None,
        "error": None,
        "started_at": "2026-05-09T10:00:00Z",
        "elapsed_s": 87,
    }
    out = await task_status(task_id="abc-123", _client=client)
    assert out["progress"]["percent"] == 42
    assert out["elapsed_s"] == 87


@pytest.mark.asyncio
async def test_success_includes_result():
    client = AsyncMock()
    client.get.return_value = {
        "status": "SUCCESS",
        "progress": None,
        "result": {"output_path": "/r/final.mp4", "duration_s": 28800},
        "error": None,
    }
    out = await task_status(task_id="abc-123", _client=client)
    assert out["status"] == "SUCCESS"
    assert out["result"]["output_path"] == "/r/final.mp4"


@pytest.mark.asyncio
async def test_failure_includes_error_string():
    client = AsyncMock()
    client.get.return_value = {
        "status": "FAILURE",
        "progress": None,
        "result": None,
        "error": "ffmpeg exit code 137",
    }
    out = await task_status(task_id="abc-123", _client=client)
    assert out["status"] == "FAILURE"
    assert "ffmpeg" in out["error"]
