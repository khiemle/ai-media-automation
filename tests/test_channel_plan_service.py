import pytest
from unittest.mock import patch, MagicMock
from console.backend.services.channel_plan_service import ChannelPlanService, ChannelPlanAIService, extract_metadata

_ASMR_MD = """\
# Channel Launch Plan — ASMR Sleep & Relax

## 1. Tổng quan kênh

| Tiêu chí | Kênh ASMR Sleep & Relax |
|---|---|
| **Focus** | Sleep, deep relaxation, stress relief |
| **Audience** | Người mất ngủ, lo âu, cần thư giãn sâu |
| **Video length** | 8–10 giờ/video |
| **Upload frequency** | 3–4 video/tuần |
| **RPM ước tính** | $10–$11 |
"""

# ── metadata extraction ──────────────────────────────────────────────────────

def test_extract_name_from_h1():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["name"] == "ASMR Sleep & Relax"

def test_extract_slug_strips_prefix():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["slug"] == "asmr"

def test_extract_slug_fallback_no_prefix():
    result = extract_metadata(_ASMR_MD, "My_Custom.md")
    assert result["slug"] == "my_custom"

def test_extract_focus():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["focus"] == "Sleep, deep relaxation, stress relief"

def test_extract_upload_frequency():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["upload_frequency"] == "3–4 video/tuần"

def test_extract_rpm_estimate():
    result = extract_metadata(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert result["rpm_estimate"] == "$10–$11"

def test_extract_returns_none_for_missing_fields():
    minimal = "# Channel Launch Plan — Minimal\n"
    result = extract_metadata(minimal, "Channel_Launch_Plan_Minimal.md")
    assert result["name"] == "Minimal"
    assert result["focus"] is None
    assert result["upload_frequency"] is None
    assert result["rpm_estimate"] is None

def test_extract_name_fallback_strips_prefix_and_extension():
    no_h1 = "## Some other section\n"
    result = extract_metadata(no_h1, "Channel_Launch_Plan_Lofi.md")
    assert result["name"] == "Lofi"

# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_import_plan_stores_all_fields(db):
    svc = ChannelPlanService(db)
    plan = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    assert plan["id"] is not None
    assert plan["name"] == "ASMR Sleep & Relax"
    assert plan["slug"] == "asmr"
    assert plan["focus"] == "Sleep, deep relaxation, stress relief"
    assert plan["upload_frequency"] == "3–4 video/tuần"
    assert plan["rpm_estimate"] == "$10–$11"
    assert plan["md_filename"] == "Channel_Launch_Plan_ASMR.md"

def test_list_plans_excludes_md_content(db):
    svc = ChannelPlanService(db)
    svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    plans = svc.list_plans()
    assert len(plans) == 1
    assert "md_content" not in plans[0]
    assert plans[0]["name"] == "ASMR Sleep & Relax"

def test_get_plan_includes_md_content(db):
    svc = ChannelPlanService(db)
    created = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    retrieved = svc.get_plan(created["id"])
    assert retrieved["md_content"] == _ASMR_MD

def test_update_plan_re_parses_metadata(db):
    svc = ChannelPlanService(db)
    plan = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    new_md = "# Channel Launch Plan — Soundscapes\n\n## 1. Tổng quan kênh\n\n| **Focus** | Nature and focus |\n"
    updated = svc.update_plan(plan["id"], new_md)
    assert updated["name"] == "Soundscapes"
    assert updated["focus"] == "Nature and focus"
    assert updated["md_content"] == new_md

def test_delete_plan_removes_from_db(db):
    svc = ChannelPlanService(db)
    plan = svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    svc.delete_plan(plan["id"])
    assert svc.list_plans() == []

def test_get_plan_not_found_raises_key_error(db):
    svc = ChannelPlanService(db)
    with pytest.raises(KeyError):
        svc.get_plan(99999)

def test_duplicate_slug_raises(db):
    svc = ChannelPlanService(db)
    svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")
    with pytest.raises(Exception):
        svc.import_plan(_ASMR_MD, "Channel_Launch_Plan_ASMR.md")

# ── AI service ───────────────────────────────────────────────────────────────

_FAKE_CFG = {
    "gemini": {"script": {"api_key": "fake-key", "model": "gemini-2.0-flash"}}
}

def _gemini_response(text):
    m = MagicMock()
    m.text = text
    return m


def test_generate_seo_returns_parsed_dict():
    svc = ChannelPlanAIService()
    payload = '{"title": "Rain Sounds 8h", "description": "Relax with rain", "tags": "rain, sleep, asmr"}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response(payload)

    with patch("config.api_config.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.generate_seo("# Channel Plan\n", "Heavy Rain", "")

    assert result["title"] == "Rain Sounds 8h"
    assert result["description"] == "Relax with rain"
    assert result["tags"] == "rain, sleep, asmr"


def test_generate_prompts_returns_four_keys():
    svc = ChannelPlanAIService()
    payload = '{"suno": "s", "midjourney": "mj", "runway": "r", "thumbnail": "t"}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response(payload)

    with patch("config.api_config.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.generate_prompts("# Channel Plan\n", "Forest Stream", "")

    assert result["suno"] == "s"
    assert result["midjourney"] == "mj"
    assert result["runway"] == "r"
    assert result["thumbnail"] == "t"


def test_ask_question_wraps_plain_text():
    svc = ChannelPlanAIService()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response("Upload 3-4 videos per week.")

    with patch("config.api_config.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.ask_question("# Channel Plan\n", "What is the upload schedule?")

    assert result == {"answer": "Upload 3-4 videos per week."}


def test_autofill_returns_all_fields():
    svc = ChannelPlanAIService()
    payload = '{"title":"T","description":"D","tags":"t","suno_prompt":"s","runway_prompt":"r","target_duration_h":8}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response(payload)

    with patch("config.api_config.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.autofill("# Channel Plan\n", "Heavy Rain", "")

    for key in ("title", "description", "tags", "suno_prompt", "runway_prompt", "target_duration_h"):
        assert key in result
    assert result["target_duration_h"] == 8


def test_generate_seo_raises_on_missing_api_key():
    svc = ChannelPlanAIService()
    cfg_no_key = {"gemini": {"script": {"api_key": "", "model": ""}}}

    with patch("config.api_config.get_config", return_value=cfg_no_key):
        with pytest.raises(RuntimeError, match="API key"):
            svc.generate_seo("# Plan\n", "theme", "")


def test_generate_seo_handles_fenced_json_response():
    svc = ChannelPlanAIService()
    fenced = '```json\n{"title": "Rain 8h", "description": "Relax", "tags": "rain"}\n```'
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _gemini_response(fenced)
    with patch("config.api_config.get_config", return_value=_FAKE_CFG), \
         patch("console.backend.services.channel_plan_service.genai") as mock_genai:
        mock_genai.Client.return_value = mock_client
        mock_genai.types.GenerateContentConfig.return_value = MagicMock()
        result = svc.generate_seo("# Plan\n", "Rain", "")
    assert result["title"] == "Rain 8h"
