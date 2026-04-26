import pytest
from uploader.youtube_uploader import _build_tags, _build_description, _niche_to_category


def test_build_tags_always_has_shorts_first():
    tags = _build_tags({"hashtags": ["running", "fitness"], "niche": "running"})
    assert tags[0] == "Shorts"


def test_build_tags_no_duplicate_shorts():
    tags = _build_tags({"hashtags": ["Shorts", "running"], "niche": "running"})
    assert tags.count("Shorts") == 1


def test_build_tags_empty_metadata():
    tags = _build_tags({})
    assert tags[0] == "Shorts"


def test_build_description_appends_shorts_hashtag():
    desc = _build_description({"description": "Great run!", "hashtags": ["running"]})
    assert "#Shorts" in desc


def test_build_description_shorts_appended_when_no_hashtags():
    desc = _build_description({"description": "Great run!"})
    assert "#Shorts" in desc


def test_niche_to_category_running():
    assert _niche_to_category("running") == "17"


def test_niche_to_category_fitness():
    assert _niche_to_category("fitness") == "17"


def test_niche_to_category_unknown_defaults_to_people_blogs():
    assert _niche_to_category("unknown_niche") == "22"
