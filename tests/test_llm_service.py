import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


_FAKE_VOICES = {
    "kokoro": {
        "american_english": {
            "female": [{"id": "af_heart", "name": "Heart"}],
            "male":   [{"id": "am_adam",  "name": "Adam"}],
        },
        "british_english": {
            "female": [{"id": "bf_emma",   "name": "Emma"}],
            "male":   [{"id": "bm_george", "name": "George"}],
        },
    },
    "elevenlabs": {
        "en": {
            "male":   [{"id": "UgBBYS2sOqTuMpoF3BR0", "name": "James"}],
            "female": [{"id": "56AoDkrOh6qfVPDXZ7Pt", "name": "Sarah"}],
        },
        "vi": {
            "male":   [{"id": "3VnrjnYrskPMDsapTr8X", "name": "Minh"}],
            "female": [{"id": "A5w1fw5x0uXded1LDvZp", "name": "Lan"}],
        },
    },
}


@pytest.fixture
def voices_file(tmp_path):
    p = tmp_path / "tts_voices.json"
    p.write_text(json.dumps(_FAKE_VOICES))
    return p


def test_get_voices_returns_full_structure(voices_file):
    with patch("console.backend.services.llm_service._VOICES_PATH", voices_file):
        from console.backend.services.llm_service import LLMService
        result = LLMService().get_voices()
    assert "kokoro" in result
    assert "elevenlabs" in result
    assert result["kokoro"]["american_english"]["female"][0]["id"] == "af_heart"
    assert result["elevenlabs"]["vi"]["male"][0]["name"] == "Minh"


def test_get_voices_missing_file(tmp_path):
    with patch("console.backend.services.llm_service._VOICES_PATH", tmp_path / "missing.json"):
        from console.backend.services.llm_service import LLMService
        result = LLMService().get_voices()
    assert result == {}


def test_get_status_includes_kokoro():
    _cfg = {
        "gemini": {"script": {"api_key": "", "model": ""}, "media": {"api_key": "", "model": ""}, "music": {"api_key": "", "model": ""}},
        "elevenlabs": {"api_key": "", "voice_id_en": "", "voice_id_vi": "", "model": ""},
        "suno": {"api_key": "", "model": ""},
        "pexels": {"api_key": ""},
        "kokoro": {"default_voice_en": "af_heart"},
    }
    with patch("console.backend.services.llm_service.api_config.get_config", return_value=_cfg):
        from console.backend.services.llm_service import LLMService
        status = LLMService().get_status()
    assert "kokoro" in status
    assert status["kokoro"]["available"] is True
