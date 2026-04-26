import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _fake_gemini_key():
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
        yield


def test_gemini_router_returns_dict_on_success():
    mock_response = MagicMock()
    mock_response.text = '{"meta": {"topic": "test"}, "scenes": []}'

    with patch("rag.llm_router.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        from rag.llm_router import GeminiRouter
        router = GeminiRouter()
        result = router.generate("test prompt", expect_json=True)

    assert isinstance(result, dict)
    assert result["meta"]["topic"] == "test"


def test_gemini_router_raises_on_api_error():
    with patch("rag.llm_router.genai") as mock_genai, \
         patch("rag.llm_router.time.sleep"):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API error")

        from rag.llm_router import GeminiRouter
        router = GeminiRouter()

        with pytest.raises(RuntimeError, match="Gemini"):
            router.generate("test prompt")


def test_gemini_router_returns_string_when_not_json():
    mock_response = MagicMock()
    mock_response.text = "plain text response"

    with patch("rag.llm_router.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        from rag.llm_router import GeminiRouter
        router = GeminiRouter()
        result = router.generate("test prompt", expect_json=False)

    assert result == "plain text response"


def test_get_router_returns_singleton():
    from rag.llm_router import get_router
    r1 = get_router()
    r2 = get_router()
    assert r1 is r2
