import json
import pytest
from unittest.mock import patch, MagicMock

_FAKE_CFG = {
    "suno": {"api_key": "test-suno-key", "model": "V4_5"},
    "gemini": {
        "script": {"api_key": "test-key", "model": "gemini-2.5-flash"},
        "media":  {"api_key": "test-key", "model": "gemini-2.0-flash-exp"},
        "music":  {"api_key": "test-gemini-music-key", "model": "lyria-3-clip-preview"},
    },
    "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": "eleven_flash_v2_5"},
    "pexels": {"api_key": ""},
    "kokoro": {"default_voice_en": "af_heart"},
}


@pytest.fixture(autouse=True)
def _fake_keys():
    with patch("pipeline.music_providers.suno_provider.get_config", return_value=_FAKE_CFG), \
         patch("pipeline.music_providers.lyria_provider.get_config", return_value=_FAKE_CFG):
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


# ── ElevenLabs provider tests ─────────────────────────────────────────────────

_ELEVENLABS_FAKE_CFG = {**_FAKE_CFG, "elevenlabs": {"api_key": "test-el-key"}}


@pytest.fixture
def _fake_el_keys():
    with patch("pipeline.music_providers.elevenlabs_provider.get_config", return_value=_ELEVENLABS_FAKE_CFG):
        yield


def test_elevenlabs_create_plan_returns_json_plan_as_is(_fake_el_keys):
    """If input is valid composition plan JSON, return it without calling the API."""
    plan = {
        "positive_global_styles": ["upbeat pop"],
        "negative_global_styles": ["dark"],
        "sections": [{"section_name": "Intro", "duration_ms": 8000, "lines": []}],
    }
    from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider
    with patch("pipeline.music_providers.elevenlabs_provider.ElevenLabs"):
        provider = ElevenLabsProvider()
        result = provider.create_plan(json.dumps(plan), 60000)
    assert result == plan


def test_elevenlabs_create_plan_calls_api_for_text_prompt(_fake_el_keys):
    """If input is a text prompt, call composition_plan.create and return the result."""
    expected_plan = {"positive_global_styles": ["calm"], "sections": []}

    mock_plan = MagicMock()
    mock_plan.model_dump.return_value = expected_plan

    with patch("pipeline.music_providers.elevenlabs_provider.ElevenLabs") as MockEL:
        mock_client = MockEL.return_value
        mock_client.music.composition_plan.create.return_value = mock_plan

        from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider
        provider = ElevenLabsProvider()
        result = provider.create_plan("calm ambient music", 60000)

    mock_client.music.composition_plan.create.assert_called_once_with(
        prompt="calm ambient music",
        music_length_ms=60000,
    )
    assert result == expected_plan


def test_elevenlabs_compose_returns_bytes(_fake_el_keys):
    """compose() returns the raw audio bytes from the SDK."""
    fake_audio = b"FAKE_AUDIO_DATA"

    with patch("pipeline.music_providers.elevenlabs_provider.ElevenLabs") as MockEL:
        mock_client = MockEL.return_value
        mock_client.music.compose.return_value = fake_audio

        from pipeline.music_providers.elevenlabs_provider import ElevenLabsProvider
        provider = ElevenLabsProvider()
        plan = {"sections": [], "positive_global_styles": ["pop"]}
        result = provider.compose(plan, output_format="mp3_44100_192")

    mock_client.music.compose.assert_called_once_with(
        composition_plan=plan,
        respect_sections_durations=True,
        output_format="mp3_44100_192",
    )
    assert result == fake_audio


def test_elevenlabs_ext_for_format():
    from pipeline.music_providers.elevenlabs_provider import _ext_for_format
    assert _ext_for_format("mp3_44100_192") == ".mp3"
    assert _ext_for_format("pcm_44100") == ".wav"
    assert _ext_for_format("opus_48000_192") == ".opus"
    assert _ext_for_format("ulaw_8000") == ".wav"
