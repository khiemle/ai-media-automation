"""
Script validator — checks LLM output against the required script JSON schema.
"""
from typing import Any

REQUIRED_SCENE_KEYS = {"narration", "visual_hint", "duration", "type"}
VALID_SCENE_TYPES   = {"hook", "body", "transition", "cta", "proof", "outro", "intro"}
VALID_OVERLAY_STYLES = {
    "big_white_center", "bottom_caption", "top_title", "highlight_box", "minimal", ""
}
VALID_TRANSITIONS   = {"cut", "fade", "crossfade"}
VALID_NICHES        = {"health", "fitness", "lifestyle", "finance", "food"}
VALID_TEMPLATES     = {"tiktok_viral", "tiktok_30s", "youtube_clean", "shorts_hook"}

MIN_TOTAL_DURATION  = 20    # seconds
MAX_TOTAL_DURATION  = 120   # seconds (3B models tend to generate longer scripts)
MIN_SCENES          = 3
MAX_SCENES          = 12


def validate(script: Any) -> tuple[bool, list[str]]:
    """
    Validate a script dict against the required schema.
    Returns (valid: bool, errors: list[str]).
    """
    errors: list[str] = []

    if not isinstance(script, dict):
        return False, [f"Expected dict, got {type(script).__name__}"]

    # Top-level required keys
    for key in ("meta", "video", "scenes"):
        if key not in script:
            errors.append(f"Missing required key: '{key}'")

    if errors:
        return False, errors

    # meta validation
    meta = script.get("meta", {})
    if not meta.get("topic"):
        errors.append("meta.topic is empty")
    if meta.get("niche") and meta["niche"] not in VALID_NICHES:
        errors.append(f"meta.niche '{meta['niche']}' not in {VALID_NICHES}")
    if meta.get("template") and meta["template"] not in VALID_TEMPLATES:
        errors.append(f"meta.template '{meta['template']}' not in {VALID_TEMPLATES}")

    # scenes validation
    scenes = script.get("scenes", [])
    if not isinstance(scenes, list):
        errors.append("scenes must be a list")
        return False, errors

    if len(scenes) < MIN_SCENES:
        errors.append(f"Too few scenes: {len(scenes)} (min {MIN_SCENES})")
    if len(scenes) > MAX_SCENES:
        errors.append(f"Too many scenes: {len(scenes)} (max {MAX_SCENES})")

    total_duration = 0.0
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            errors.append(f"scenes[{i}] is not a dict")
            continue

        missing = REQUIRED_SCENE_KEYS - set(scene.keys())
        if missing:
            errors.append(f"scenes[{i}] missing keys: {missing}")

        if not scene.get("narration"):
            errors.append(f"scenes[{i}].narration is empty")
        if not scene.get("visual_hint"):
            errors.append(f"scenes[{i}].visual_hint is empty")

        stype = scene.get("type", "")
        if stype and stype not in VALID_SCENE_TYPES:
            errors.append(f"scenes[{i}].type '{stype}' not in {VALID_SCENE_TYPES}")

        duration = scene.get("duration", 0)
        try:
            duration = float(duration)
            if duration <= 0:
                errors.append(f"scenes[{i}].duration must be > 0")
            total_duration += duration
        except (TypeError, ValueError):
            errors.append(f"scenes[{i}].duration must be a number")

        style = scene.get("overlay_style", "")
        if style and style not in VALID_OVERLAY_STYLES:
            errors.append(f"scenes[{i}].overlay_style '{style}' not in valid styles")

        pexels_kw = scene.get("pexels_keywords")
        if pexels_kw is not None and not isinstance(pexels_kw, list):
            errors.append(f"scenes[{i}].pexels_keywords must be a list, got {type(pexels_kw).__name__}")

    # Total duration check
    if total_duration < MIN_TOTAL_DURATION:
        errors.append(f"Total duration {total_duration}s too short (min {MIN_TOTAL_DURATION}s)")
    if total_duration > MAX_TOTAL_DURATION:
        errors.append(f"Total duration {total_duration}s too long (max {MAX_TOTAL_DURATION}s)")

    return len(errors) == 0, errors


def fix_and_normalize(script: dict, topic: str, niche: str, template: str) -> dict:
    """
    Best-effort normalization of a partially valid script.
    Fills in defaults for missing optional fields.
    """
    script.setdefault("meta", {})
    script["meta"].setdefault("topic",    topic)
    script["meta"].setdefault("niche",    niche)
    script["meta"].setdefault("template", template)
    script["meta"].setdefault("region",   "vn")
    script["meta"].setdefault("language", "vietnamese")

    script.setdefault("video", {})
    script["video"].setdefault("title",       topic)
    script["video"].setdefault("description", "")
    script["video"].setdefault("hashtags",    [])
    script["video"].setdefault("voice",       "af_heart")
    script["video"].setdefault("voice_speed", 1.1)
    script["video"].setdefault("mood",        "uplifting")

    script.setdefault("cta", {"type": "follow", "text": "Theo dõi để xem thêm!", "affiliate_links": []})

    scenes = script.get("scenes", [])
    for i, scene in enumerate(scenes):
        scene.setdefault("scene_number", i + 1)
        scene.setdefault("type",         "body")
        scene.setdefault("narration",    "")
        scene.setdefault("visual_hint",  "person talking camera lifestyle")
        scene.setdefault("pexels_keywords", [])
        scene.setdefault("text_overlay", "")
        scene.setdefault("overlay_style", "minimal")
        scene.setdefault("duration",     5)
        scene.setdefault("transition",   "cut")

    # Recalculate total_duration
    total = sum(float(s.get("duration", 0)) for s in scenes)
    script["video"]["total_duration"] = total

    return script
