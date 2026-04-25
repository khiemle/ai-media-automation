"""
Script writer — orchestrates the LLM → validate pipeline for script generation.

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
    language: str = "vietnamese",
    article_content: str | None = None,
    context_videos=None,
    video_ids: list[int] | None = None,
) -> dict:
    """
    Generate a script via Gemini. Raises RuntimeError if Gemini fails.
    """
    from rag.llm_router import get_router
    from rag.prompt_builder import build_prompt
    from rag.script_validator import validate, fix_and_normalize

    extra_hooks: list[str] = []
    if context_videos:
        extra_hooks = [v.hook_text for v in context_videos if getattr(v, "hook_text", None)]

    prompt = build_prompt(
        topic=topic,
        niche=niche,
        template=template,
        language=language,
        article_content=article_content,
        extra_hooks=extra_hooks,
    )

    router = get_router()
    last_error: str = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = router.generate(prompt, template=template, expect_json=True)

            if not isinstance(result, dict):
                last_error = f"LLM returned {type(result).__name__}, expected dict"
                logger.warning(f"[ScriptWriter] Attempt {attempt}: {last_error}")
                continue

            result.setdefault("meta", {})
            result["meta"].setdefault("topic", topic)
            result["meta"].setdefault("niche", niche)
            result["meta"].setdefault("template", template)
            result["meta"].setdefault("language", language)

            valid, errors = validate(result)
            if valid:
                logger.info(f"[ScriptWriter] Valid script on attempt {attempt}")
                return fix_and_normalize(result, topic, niche, template)

            last_error = "; ".join(errors[:3])
            logger.warning(f"[ScriptWriter] Attempt {attempt} validation failed: {errors[:3]}")
            prompt += f"\n\nPREVIOUS ATTEMPT ERRORS (fix these):\n" + "\n".join(f"- {e}" for e in errors[:5])

        except RuntimeError:
            raise  # Gemini hard failure — propagate immediately
        except Exception as e:
            last_error = str(e)
            logger.error(f"[ScriptWriter] Attempt {attempt} exception: {e}")

    raise RuntimeError(f"Script generation failed after {MAX_RETRIES} attempts. Last error: {last_error}")


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


