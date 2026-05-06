import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.topaz_client import TopazClient, probe_video_metadata


@pytest.fixture
def client():
    return TopazClient(api_key="test-key-abc")


def test_create_job_returns_request_id(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"requestId": "req-123"}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.post", return_value=mock_resp) as mock_post:
        request_id = client.create_job(width=1080, height=1920, fps=30, duration=60.0, size=50_000_000)

    assert request_id == "req-123"
    # Verify output is 2x input
    call_data = json.loads(mock_post.call_args.kwargs["data"])
    assert call_data["filters"][0]["output_width"] == 2160
    assert call_data["filters"][0]["output_height"] == 3840


def test_accept_job_returns_upload_url(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"urls": ["https://upload.example.com/part1"]}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.patch", return_value=mock_resp):
        url = client.accept_job("req-123")

    assert url == "https://upload.example.com/part1"


def test_upload_file_returns_etag(client, tmp_path):
    test_file = tmp_path / "test.mp4"
    test_file.write_bytes(b"fake video data")

    mock_resp = MagicMock()
    mock_resp.headers = {"ETag": '"abc123"'}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.put", return_value=mock_resp):
        etag = client.upload_file("https://upload.example.com/part1", test_file)

    assert etag == '"abc123"'


def test_get_status_returns_dict(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "complete", "download": {"url": "https://dl.example.com/out.mp4"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.topaz_client.requests.get", return_value=mock_resp):
        result = client.get_status("req-123")

    assert result["status"] == "complete"
    assert result["download"]["url"] == "https://dl.example.com/out.mp4"
