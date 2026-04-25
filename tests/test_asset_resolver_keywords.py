import pytest
from pipeline.asset_resolver import _get_pexels_keywords


def test_uses_pexels_keywords_when_present():
    scene = {
        "type": "hook",
        "visual_hint": "người phụ nữ uống cà phê",
        "pexels_keywords": ["woman coffee morning", "cozy home"],
    }
    keywords = _get_pexels_keywords(scene, {"niche": "lifestyle"})
    assert keywords == ["woman coffee morning", "cozy home"]


def test_falls_back_to_niche_when_no_pexels_keywords():
    scene = {"type": "body", "visual_hint": "cảnh đẹp thiên nhiên"}
    keywords = _get_pexels_keywords(scene, {"niche": "lifestyle"})
    assert len(keywords) >= 1
    assert any(k in ["lifestyle", "people", "daily life"] for k in keywords)


def test_falls_back_to_niche_when_pexels_keywords_empty():
    scene = {"type": "cta", "pexels_keywords": [], "visual_hint": "vẫy tay"}
    keywords = _get_pexels_keywords(scene, {"niche": "fitness"})
    assert len(keywords) >= 1
    assert any(k in ["fitness", "workout", "exercise"] for k in keywords)


def test_scene_type_contributes_to_fallback():
    scene = {"type": "cta", "visual_hint": ""}
    keywords = _get_pexels_keywords(scene, {"niche": "unknown_niche"})
    assert "smiling" in keywords or "thumbs up" in keywords


def test_returns_at_most_three_keywords():
    scene = {
        "type": "body",
        "pexels_keywords": ["a", "b", "c", "d", "e"],
    }
    keywords = _get_pexels_keywords(scene, {"niche": "lifestyle"})
    assert len(keywords) <= 3


def test_falls_back_when_pexels_keywords_is_not_a_list():
    """Non-list pexels_keywords must fall back, not iterate characters."""
    scene = {"type": "body", "pexels_keywords": "woman coffee morning"}
    keywords = _get_pexels_keywords(scene, {"niche": "lifestyle"})
    assert keywords != ["w", "o", "m"]
    assert all(len(k) > 1 for k in keywords)
