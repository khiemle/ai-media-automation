"""
Veo prompt builder — constructs cinematic prompts for Google Veo video generation.
"""

VEO_STYLE_DIRECTIVES = {
    "finance":      "professional setting, clean modern office, confident person, warm tones, 4K cinematic",
    "health":       "bright natural light, clean minimal space, wellness aesthetic, soft focus, calming",
    "lifestyle":    "golden hour, lifestyle vlog style, authentic candid feel, warm color grade",
    "fitness":      "dynamic movement, gym or outdoor, high contrast, energetic pacing, motivational",
    "food":         "overhead or 45-degree shot, soft natural light, appetizing close-up, warm tones, minimal",
    "productivity": "clean workspace, morning light, focused person, minimal clutter, calm aesthetic",
}

DEFAULT_STYLE = "cinematic, high quality, natural lighting, professional, engaging"


def build_veo_prompt(scene: dict, meta: dict) -> str:
    """
    Construct a Veo video generation prompt from a script scene and video metadata.

    Args:
        scene: A scene dict from script_json with keys: visual_hint, narration, type, duration
        meta:  The script meta dict with keys: topic, niche, template

    Returns:
        A Veo-optimized prompt string.
    """
    topic       = meta.get("topic", "")
    niche       = meta.get("niche", "lifestyle")
    narration   = scene.get("narration", "")[:120]
    visual_hint = scene.get("visual_hint", "")
    scene_type  = scene.get("type", "body")
    duration    = scene.get("duration", 8)

    style = VEO_STYLE_DIRECTIVES.get(niche, DEFAULT_STYLE)

    # Hook and CTA scenes get more creative direction
    if scene_type == "hook":
        energy = "Attention-grabbing opening shot. Dynamic, unexpected angle. Immediately captivating."
    elif scene_type == "cta":
        energy = "Warm, inviting closing shot. Friendly and encouraging. Leaves viewer wanting more."
    else:
        energy = "Clear, well-composed shot. Informative and engaging."

    prompt = (
        f"Cinematic vertical video, 9:16 portrait orientation, 1080x1920 resolution. "
        f"Topic: {topic}. "
        f"Scene: {visual_hint}. "
        f"Context: {narration}. "
        f"Style: {style}. "
        f"{energy} "
        f"Requirements: no text overlays, no subtitles, no watermarks, no logos, "
        f"smooth natural motion, suitable for {niche} social media content. "
        f"Duration: 8 seconds."
    )

    return prompt


def clips_needed(scene_duration: float) -> int:
    """Calculate number of 8s Veo clips needed to cover a scene duration."""
    import math
    return max(1, math.ceil(scene_duration / 8.0))
