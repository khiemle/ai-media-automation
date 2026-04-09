"""
Script writer — orchestrates the full RAG → LLM → validate → store pipeline.

Public API:
  generate_script(topic, niche, template, context_videos=None) → dict
  regenerate_scene(script_dict, scene_index) → dict
"""
import logging
import os

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.environ.get("SCRIPT_MAX_RETRIES", 3))


def generate_script(
    topic: str,
    niche: str = "lifestyle",
    template: str = "tiktok_viral",
    context_videos=None,          # list[ViralVideo] ORM objects, optional
    video_ids: list[int] | None = None,
) -> dict:
    """
    Full RAG + LLM script generation pipeline.
    1. Retrieve similar scripts, top hooks, and viral patterns from ChromaDB
    2. Build a RAG-enriched prompt
    3. Route to LLM (Gemini or Ollama based on LLM_MODE)
    4. Validate JSON output; retry up to MAX_RETRIES times on failure
    5. Normalize + return the final script dict
    """
    from rag.llm_router import get_router
    from rag.prompt_builder import build_prompt
    from rag.script_validator import validate, fix_and_normalize
    from vector_db.retriever import retrieve_similar_scripts, retrieve_top_hooks, retrieve_patterns

    # 1. Retrieve RAG context
    similar_scripts = retrieve_similar_scripts(topic, niche, k=3)
    top_hooks       = retrieve_top_hooks(niche, k=8)
    patterns        = retrieve_patterns(niche)

    # 2. Optionally enrich with passed-in context videos (from editor selection)
    extra_hooks: list[str] = []
    if context_videos:
        extra_hooks = [v.hook_text for v in context_videos if getattr(v, "hook_text", None)]
        top_hooks = (extra_hooks + top_hooks)[:10]

    # 3. Build prompt
    prompt = build_prompt(
        topic=topic,
        niche=niche,
        template=template,
        viral_scripts=similar_scripts,
        top_hooks=top_hooks,
        patterns=patterns,
    )

    # 4. Generate with retries
    router = get_router()
    script: dict | None = None
    last_errors: list[str] = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = router.generate(prompt, template=template, expect_json=True)

            if not isinstance(result, dict):
                logger.warning(f"[ScriptWriter] Attempt {attempt}: LLM returned non-dict ({type(result).__name__})")
                last_errors = [f"LLM returned {type(result).__name__}, expected dict"]
                continue

            # Inject meta in case LLM omitted it
            result.setdefault("meta", {})
            result["meta"].setdefault("topic", topic)
            result["meta"].setdefault("niche", niche)
            result["meta"].setdefault("template", template)

            valid, errors = validate(result)
            if valid:
                script = fix_and_normalize(result, topic, niche, template)
                logger.info(f"[ScriptWriter] Generated valid script on attempt {attempt}")
                break
            else:
                last_errors = errors
                logger.warning(
                    f"[ScriptWriter] Attempt {attempt} validation failed: {errors[:3]}"
                )
                # Add error feedback to prompt for next retry
                prompt += f"\n\nPREVIOUS ATTEMPT ERRORS (fix these):\n" + "\n".join(f"- {e}" for e in errors[:5])

        except Exception as e:
            last_errors = [str(e)]
            logger.error(f"[ScriptWriter] Attempt {attempt} exception: {e}")

    if script is None:
        logger.error(f"[ScriptWriter] All {MAX_RETRIES} attempts failed. Last errors: {last_errors}")
        # Return a minimal fallback script so the pipeline doesn't crash
        script = _fallback_script(topic, niche, template)

    return script


def regenerate_scene(script_dict: dict, scene_index: int) -> dict:
    """
    Regenerate a single scene using the LLM, preserving all other scenes.
    Returns the updated script dict.
    """
    from rag.llm_router import get_router
    from rag.prompt_builder import build_scene_regen_prompt

    if not isinstance(script_dict, dict):
        raise TypeError(f"script_dict must be a dict, got {type(script_dict).__name__}")

    scenes = script_dict.get("scenes", [])
    if scene_index >= len(scenes):
        raise ValueError(f"Scene index {scene_index} out of range ({len(scenes)} scenes)")

    scene = scenes[scene_index]
    meta  = script_dict.get("meta", {})

    prompt = build_scene_regen_prompt(scene, meta)
    router = get_router()

    try:
        result = router.generate(prompt, template=meta.get("template"), expect_json=True)
        if isinstance(result, dict):
            scene["narration"]    = result.get("narration",    scene.get("narration", ""))
            scene["visual_hint"]  = result.get("visual_hint",  scene.get("visual_hint", ""))
            scene["text_overlay"] = result.get("text_overlay", scene.get("text_overlay", ""))
            if result.get("overlay_style"):
                scene["overlay_style"] = result["overlay_style"]
    except Exception as e:
        logger.error(f"[ScriptWriter] Scene regeneration failed: {e}")

    scenes[scene_index] = scene
    script_dict["scenes"] = scenes
    return script_dict


def _fallback_script(topic: str, niche: str, template: str) -> dict:
    """Minimal valid script when all LLM attempts fail."""
    return {
        "meta":   {"topic": topic, "niche": niche, "template": template, "region": "vn"},
        "video":  {
            "title": topic, "description": "", "hashtags": [],
            "voice": "af_heart", "voice_speed": 1.1, "mood": "uplifting", "total_duration": 30,
        },
        "cta":    {"type": "follow", "text": "Theo dõi để xem thêm!", "affiliate_links": []},
        "scenes": [
            {
                "scene_number": 1, "type": "hook",
                "narration": f"Hôm nay chúng ta sẽ nói về chủ đề {topic}.",
                "visual_hint": f"{niche} lifestyle person talking",
                "text_overlay": topic[:30], "overlay_style": "big_white_center",
                "duration": 5, "transition": "cut",
            },
            {
                "scene_number": 2, "type": "body",
                "narration": "Đây là những thông tin quan trọng bạn cần biết.",
                "visual_hint": f"{niche} informative content",
                "text_overlay": "", "overlay_style": "minimal",
                "duration": 15, "transition": "fade",
            },
            {
                "scene_number": 3, "type": "cta",
                "narration": "Theo dõi kênh để không bỏ lỡ những nội dung hữu ích tiếp theo nhé!",
                "visual_hint": "person waving goodbye smiling camera",
                "text_overlay": "Theo dõi ngay!", "overlay_style": "big_white_center",
                "duration": 7, "transition": "fade",
            },
        ],
    }
