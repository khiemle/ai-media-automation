"""
Asset Resolver — 3-tier system: DB → Pexels → Veo.
Mode-based routing with write-back on every external fetch.
"""
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / "pipeline.env", override=False)
load_dotenv(_root / "console" / ".env", override=False)

logger = logging.getLogger(__name__)

RESOLVER_MODE = os.environ.get("ASSET_RESOLVER_MODE", "db_then_hybrid")
DB_MIN_SCORE  = float(os.environ.get("ASSET_DB_MIN_SCORE", "0.72"))

# Hybrid routing: which source handles each scene type
HYBRID_RULES = {
    "hook":       "veo",
    "cta":        "veo",
    "body":       "pexels",
    "transition": "pexels",
}


def resolve(
    scene: dict,
    meta:  dict,
    mode:  str | None = None,
) -> Path | None:
    """
    Resolve the best video clip for a scene.

    Tier 1: Video Asset DB  (free, instant, keyword-score ≥ DB_MIN_SCORE)
    Tier 2: Pexels or Veo  (based on mode + HYBRID_RULES)
    Write-back: every newly fetched clip is stored in the Asset DB.

    Returns local path to a 1080×1920 mp4 clip, or None on failure.
    """
    mode       = mode or RESOLVER_MODE
    scene_type = scene.get("type", "body")
    duration   = float(scene.get("duration", 5))

    # Extract keywords from visual_hint
    keywords = _extract_keywords(scene.get("visual_hint", ""))
    niche    = meta.get("niche", "lifestyle")
    topic    = meta.get("topic", "")
    scene_id = f"scene{scene.get('scene_number', 0)}"

    # ── Tier 1: Asset DB ──────────────────────────────────────────────────────
    if mode != "pexels" and mode != "veo":
        try:
            from pipeline.asset_db import search
            result = search(
                keywords=keywords,
                niche=niche,
                min_duration=duration,
                min_score=DB_MIN_SCORE,
            )
            if result:
                logger.info(f"[Resolver] {scene_id} → Asset DB hit (score={result.match_score:.2f})")
                return Path(result.file_path)
        except Exception as e:
            logger.warning(f"[Resolver] Asset DB search error: {e}")

    if mode == "db_only":
        logger.warning(f"[Resolver] {scene_id} → DB miss (db_only mode, no fallback)")
        return None

    # ── Tier 2: External source ────────────────────────────────────────────────
    source = _select_source(mode, scene_type)
    logger.info(f"[Resolver] {scene_id} → Tier 2: {source}")

    if source == "veo":
        result = _try_veo(scene, meta, scene_id, keywords, niche)
        if result:
            return result
        # Veo fallback → Pexels
        logger.info(f"[Resolver] {scene_id} → Veo failed, trying Pexels")
        source = "pexels"

    if source == "pexels":
        result = _try_pexels(keywords, niche, duration, scene_id)
        if result:
            return result
        logger.warning(f"[Resolver] {scene_id} → Pexels miss, using niche default")
        return _niche_default(niche)

    return None


def _select_source(mode: str, scene_type: str) -> str:
    if mode == "db_then_pexels":
        return "pexels"
    if mode == "db_then_veo":
        return "veo"
    if mode == "db_then_hybrid":
        return HYBRID_RULES.get(scene_type, "pexels")
    if mode == "pexels":
        return "pexels"
    if mode == "veo":
        return "veo"
    return "pexels"


def _extract_keywords(visual_hint: str) -> list[str]:
    """Extract meaningful keywords from visual_hint string."""
    stop = {"a", "an", "the", "and", "or", "with", "in", "on", "at", "of", "for", "to", "is", "are"}
    words = re.findall(r"\b[a-zA-Z]{3,}\b", visual_hint.lower())
    return [w for w in words if w not in stop][:8]


def _try_veo(scene: dict, meta: dict, scene_id: str, keywords: list[str], niche: str) -> Path | None:
    try:
        from pipeline.veo_client import get_client
        client = get_client()
        return client.generate_for_scene(scene, meta, scene_id, keywords, niche)
    except Exception as e:
        logger.error(f"[Resolver] Veo error: {e}")
        return None


def _try_pexels(keywords: list[str], niche: str, duration: float, scene_id: str) -> Path | None:
    try:
        from pipeline.pexels_client import search_and_download
        return search_and_download(keywords, niche, duration, scene_id)
    except Exception as e:
        logger.error(f"[Resolver] Pexels error: {e}")
        return None


def _niche_default(niche: str) -> Path | None:
    """Return a pre-stored niche default B-roll clip."""
    default_path = Path(os.environ.get("ASSET_DB_PATH", "./assets/video_db")) / "manual" / f"niche_default_{niche}.mp4"
    if default_path.exists():
        return default_path
    # Try generic default
    generic = Path(os.environ.get("ASSET_DB_PATH", "./assets/video_db")) / "manual" / "niche_default_lifestyle.mp4"
    if generic.exists():
        return generic
    logger.error(f"[Resolver] No default clip for niche '{niche}' — place one at {default_path}")
    return None
