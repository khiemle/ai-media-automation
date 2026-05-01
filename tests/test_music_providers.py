import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _fake_suno_key():
    with patch.dict("os.environ", {"SUNO_API_KEY": "test-key"}):
        yield


def test_suno_provider_generate_returns_task_id():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 200, "data": {"taskId": "abc-123"}}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.music_providers.suno_provider.requests.post", return_value=mock_resp):
        from pipeline.music_providers.suno_provider import SunoProvider
        provider = SunoProvider()
        task_id = provider.submit(
            prompt="uplifting pop track",
            style="pop, electronic",
            title="Test Track",
            instrumental=True,
        )

    assert task_id == "abc-123"


def test_suno_provider_poll_returns_audio_url_on_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "code": 200,
        "data": {
            "status": "SUCCESS",
            "response": {"sunoData": [{"audioUrl": "https://cdn.suno.ai/track.mp3"}]},
        },
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.music_providers.suno_provider.requests.get", return_value=mock_resp):
        from pipeline.music_providers.suno_provider import SunoProvider
        provider = SunoProvider()
        url = provider.poll("abc-123")

    assert url == "https://cdn.suno.ai/track.mp3"


def test_suno_provider_poll_returns_none_when_pending():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 200, "data": {"status": "PENDING", "sunoData": []}}
    mock_resp.raise_for_status = MagicMock()

    with patch("pipeline.music_providers.suno_provider.requests.get", return_value=mock_resp):
        from pipeline.music_providers.suno_provider import SunoProvider
        provider = SunoProvider()
        url = provider.poll("abc-123")

    assert url is None


def test_lyria_provider_generate_returns_bytes():
    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.inline_data.data = b"FAKE_MP3_DATA"   # SDK returns raw bytes, no base64
    mock_part.inline_data.mime_type = "audio/mpeg"

    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    mock_candidate = MagicMock()
    mock_candidate.content = mock_content

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    with patch.dict("os.environ", {"GEMINI_MEDIA_API_KEY": "fake-key"}):
        with patch("pipeline.music_providers.lyria_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            from pipeline.music_providers.lyria_provider import LyriaProvider
            provider = LyriaProvider()
            audio_bytes, mime_type = provider.generate(
                prompt="calm ambient background",
                model="lyria-3-clip-preview",
                is_vocal=False,
            )

    assert audio_bytes == b"FAKE_MP3_DATA"
    assert mime_type == "audio/mpeg"
