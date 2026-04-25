"""
Prompt builder — constructs LLM prompts for script generation.
Template-specific variants with structured instructions.
"""
import json

SCRIPT_JSON_SCHEMA = """
{
  "meta": {
    "topic": "string",
    "niche": "string (health|fitness|lifestyle|finance|food)",
    "template": "string (tiktok_viral|tiktok_30s|youtube_clean|shorts_hook)",
    "region": "vn"
  },
  "video": {
    "title": "string (YouTube title, <100 chars)",
    "description": "string (platform description)",
    "hashtags": ["string"],
    "voice": "af_heart",
    "voice_speed": 1.1,
    "mood": "string (uplifting|calm_focus|energetic|trust)",
    "total_duration": "number (seconds)"
  },
  "cta": {
    "type": "string (follow|subscribe|comment|share)",
    "text": "string",
    "affiliate_links": []
  },
  "scenes": [
    {
      "scene_number": 1,
      "type": "string (hook|body|transition|cta)",
      "narration": "string (Vietnamese, spoken text for TTS)",
      "visual_hint": "string (English, describe the video clip to find/generate)",
      "pexels_keywords": ["string", "string"],
      "text_overlay": "string (short text shown on screen, optional)",
      "overlay_style": "string (big_white_center|bottom_caption|top_title|highlight_box|minimal)",
      "duration": "number (seconds)",
      "transition": "string (cut|fade|crossfade)"
    }
  ]
}"""

TEMPLATE_SPECS = {
    "tiktok_viral": {
        "total_duration": "55–65s",
        "scene_count":    "6–8",
        "structure":      "hook(5s) → problem(8s) → solution×3(30s) → proof(8s) → cta(7s)",
        "style":          "Fast-paced, punchy sentences, direct address (bạn), surprise opener",
    },
    "tiktok_30s": {
        "total_duration": "25–35s",
        "scene_count":    "4–5",
        "structure":      "hook(5s) → solution×2(15s) → cta(5s)",
        "style":          "Ultra-concise, one key insight per scene, strong CTA",
    },
    "youtube_clean": {
        "total_duration": "55–65s",
        "scene_count":    "6–8",
        "structure":      "intro(10s) → content×4(35s) → recap(10s) → cta(8s)",
        "style":          "Informative, trust-building, slower pace, clear structure",
    },
    "shorts_hook": {
        "total_duration": "25–35s",
        "scene_count":    "4–5",
        "structure":      "shock_hook(5s) → reveal×3(20s) → cta(5s)",
        "style":          "Maximum engagement in first 3s, cliffhanger hook, satisfying reveal",
    },
}

NICHE_TONE = {
    "health":    "authoritative but warm, cite benefits not features, avoid medical claims",
    "fitness":   "motivational and energetic, use action verbs, relatable struggle → triumph",
    "lifestyle": "aspirational but authentic, storytelling approach, lifestyle benefits",
    "finance":   "credible and practical, use specific numbers, avoid get-rich-quick tone",
    "food":      "sensory and appealing, describe taste/texture, simple actionable steps",
}

LANGUAGE_CONFIG = {
    "vietnamese": {
        "persona":        "expert Vietnamese social media scriptwriter",
        "narration_note": "Vietnamese text optimized for TTS (natural spoken language, NOT written Vietnamese)",
        "visual_note":    "English description for stock footage search",
        "region":         "vn",
        "hashtag_note":   "10–15 relevant Vietnamese and English hashtags",
    },
    "english": {
        "persona":        "expert English social media scriptwriter",
        "narration_note": "English text optimized for TTS (natural spoken language, conversational tone)",
        "visual_note":    "English description for stock footage search",
        "region":         "us",
        "hashtag_note":   "10–15 relevant English hashtags",
    },
}


def build_prompt(
    topic: str,
    niche: str,
    template: str,
    language: str = "vietnamese",
    article_content: str | None = None,
    extra_hooks: list[str] | None = None,
) -> str:
    spec  = TEMPLATE_SPECS.get(template, TEMPLATE_SPECS["tiktok_viral"])
    tone  = NICHE_TONE.get(niche, "engaging and informative")
    lang  = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["vietnamese"])
    hooks = "\n".join(f"  - {h}" for h in (extra_hooks or [])[:5]) or "  (none available)"

    # Build a language-aware JSON schema snippet for the region field
    schema_with_region = SCRIPT_JSON_SCHEMA.replace('"region": "vn"', f'"region": "{lang["region"]}"')

    pexels_instruction = (
        'For each scene, generate "pexels_keywords": a list of 2-3 short English search terms\n'
        "suitable for Pexels stock footage. These must be in English even when narration is Vietnamese.\n"
        'Example: ["woman coffee morning", "cozy kitchen"] for a scene about morning routines.'
    )

    if article_content:
        content_excerpt = article_content[:3000].strip()
        if len(article_content) > 3000:
            content_excerpt += "\n[...content truncated...]"

        prompt = f"""You are an {lang["persona"]} specializing in viral {niche} content.

TASK: Rewrite the news article below into a complete {template} video script titled "{topic}".
Do NOT invent facts. All key information, numbers, and claims must come from the article.

SOURCE ARTICLE:
\"\"\"
{content_excerpt}
\"\"\"

TEMPLATE SPECIFICATION:
- Duration: {spec['total_duration']}
- Scenes: {spec['scene_count']}
- Structure: {spec['structure']}
- Style: {spec['style']}
- Tone: {tone}

TOP VIRAL HOOKS (apply these patterns to the hook scene):
{hooks}

REQUIREMENTS:
1. narration: {lang["narration_note"]}
2. visual_hint: {lang["visual_note"]} (e.g. "journalist reporting breaking news studio")
3. Each scene narration should be 1–3 short sentences max
4. Hook scene MUST lead with the most surprising or impactful fact from the article
5. CTA scene must have clear action (follow/comment/share)
6. Total narration duration when spoken at 1.1× speed must fit {spec['total_duration']}
7. text_overlay: short impactful text (max 5 words) or empty string
8. hashtags: {lang["hashtag_note"]}

{pexels_instruction}

OUTPUT: Return ONLY valid JSON matching this exact schema (no markdown, no explanation):
{schema_with_region}"""

    else:
        prompt = f"""You are an {lang["persona"]} specializing in viral {niche} content.

TASK: Write a complete {template} video script about: "{topic}"

TEMPLATE SPECIFICATION:
- Duration: {spec['total_duration']}
- Scenes: {spec['scene_count']}
- Structure: {spec['structure']}
- Style: {spec['style']}
- Tone: {tone}

TOP VIRAL HOOKS (study these patterns):
{hooks}

REQUIREMENTS:
1. narration: {lang["narration_note"]}
2. visual_hint: {lang["visual_note"]} (e.g. "woman exercising morning sunrise outdoor")
3. Each scene narration should be 1–3 short sentences max
4. Hook scene MUST grab attention in first 3 seconds
5. CTA scene must have clear action (follow/comment/share)
6. Total narration duration when spoken at 1.1× speed must fit {spec['total_duration']}
7. text_overlay: short impactful text (max 5 words) or empty string
8. hashtags: {lang["hashtag_note"]}

{pexels_instruction}

OUTPUT: Return ONLY valid JSON matching this exact schema (no markdown, no explanation):
{schema_with_region}"""

    return prompt


def build_scene_regen_prompt(scene: dict, script_meta: dict, language: str = "vietnamese") -> str:
    """Prompt for regenerating a single scene."""
    lang = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["vietnamese"])
    return f"""Rewrite this single scene for a {script_meta.get('template','tiktok_viral')} video.

Topic: {script_meta.get('topic', '')}
Niche: {script_meta.get('niche', '')}
Scene type: {scene.get('type', 'body')}
Duration: {scene.get('duration', 5)}s

Current scene:
{json.dumps(scene, ensure_ascii=False, indent=2)}

Return ONLY valid JSON with these keys: narration, visual_hint, text_overlay, overlay_style
The narration should be {lang["narration_note"]}, visual_hint should be {lang["visual_note"]}."""
