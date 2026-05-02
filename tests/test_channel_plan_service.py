import pytest
from console.backend.services.channel_plan_service import ChannelPlanService, extract_metadata

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
