from unittest.mock import patch, MagicMock


def test_submit_workflow_returns_invocation_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "inv-abc123"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.submit_workflow(
            workflow_id="wf-id",
            prompt_node_id="node-prompt",
            image_node_id="node-image",
            prompt="gentle rain",
            image_uri="https://example.com/img.jpg",
        )

    assert result == "inv-abc123"
    url = mock_post.call_args[0][0]
    assert "api.dev.runwayml.com" in url
    assert "workflows/wf-id" in url
    body = mock_post.call_args[1]["json"]
    assert "node-prompt" in body["nodeOutputs"]
    assert body["nodeOutputs"]["node-prompt"]["prompt"]["value"] == "gentle rain"
    assert body["nodeOutputs"]["node-image"]["image"]["uri"] == "https://example.com/img.jpg"


def test_submit_workflow_includes_version_header():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "inv-xyz"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        svc.submit_workflow("wf", "pn", "in", "prompt", "uri")

    headers = mock_post.call_args[1]["headers"]
    assert headers["X-Runway-Version"] == "2024-11-06"
    assert headers["Authorization"] == "Bearer test-key"


def test_poll_workflow_invocation_succeeded_with_outputs_list():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "SUCCEEDED",
        "outputs": [{"url": "https://cdn.runway.com/video.mp4"}],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "SUCCEEDED"
    assert result["output_url"] == "https://cdn.runway.com/video.mp4"


def test_poll_workflow_invocation_succeeded_with_output_string_list():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "SUCCEEDED",
        "output": ["https://cdn.runway.com/video.mp4"],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "SUCCEEDED"
    assert result["output_url"] == "https://cdn.runway.com/video.mp4"


def test_poll_workflow_invocation_running():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "RUNNING"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "RUNNING"
    assert result["output_url"] is None


def test_poll_workflow_invocation_failed():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "FAILED"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        result = svc.poll_workflow_invocation("inv-abc123")

    assert result["status"] == "FAILED"
    assert result["output_url"] is None


def test_poll_uses_workflow_invocations_endpoint():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "RUNNING"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        from console.backend.services.runway_service import RunwayService
        svc = RunwayService(api_key="test-key")
        svc.poll_workflow_invocation("inv-abc123")

    url = mock_get.call_args[0][0]
    assert "workflow_invocations/inv-abc123" in url
    assert "api.dev.runwayml.com" in url
