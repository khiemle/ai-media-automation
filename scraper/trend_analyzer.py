"""
Trend analyzer — extracts viral content patterns from scraped videos.
Writes aggregated patterns to the viral_patterns table.
"""
import logging
import re
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Minimum views for a video to be considered "viral"
MIN_VIRAL_PLAY_COUNT = 100_000

# Vietnamese and English CTA trigger words
CTA_TRIGGERS = [
    "theo dõi", "follow", "comment", "bình luận", "share", "chia sẻ",
    "like", "thích", "subscribe", "đăng ký", "xem thêm", "link bio",
]

# Common scene type keywords
SCENE_KEYWORDS = {
    "hook":       ["bạn có biết", "bí quyết", "sự thật", "shock", "amazing", "wow"],
    "problem":    ["vấn đề", "khó khăn", "sai lầm", "mistake", "problem"],
    "solution":   ["giải pháp", "cách", "mẹo", "tip", "solution", "how to"],
    "transition": ["tiếp theo", "next", "và", "nhưng", "however"],
    "cta":        CTA_TRIGGERS,
}


def _extract_hook_template(text: str) -> str:
    """Normalize a hook text into a reusable template."""
    # Replace numbers with placeholder
    text = re.sub(r"\d+", "N", text)
    # Truncate to first clause
    for sep in [".", "!", "?", ",", "\n"]:
        if sep in text:
            text = text.split(sep)[0].strip()
            break
    return text[:100]


def _detect_scene_type(text: str) -> str:
    text_lower = text.lower()
    for scene_type, keywords in SCENE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return scene_type
    return "body"


def _extract_cta_phrases(texts: list[str]) -> list[str]:
    phrases = []
    for text in texts:
        text_lower = text.lower()
        for trigger in CTA_TRIGGERS:
            if trigger in text_lower:
                # Extract the sentence containing the CTA
                sentences = re.split(r"[.!?\n]", text)
                for s in sentences:
                    if trigger in s.lower():
                        phrases.append(s.strip()[:100])
                        break
    counter = Counter(phrases)
    return [phrase for phrase, _ in counter.most_common(10)]


def analyze(niche: str | None = None, region: str = "vn", min_videos: int = 5) -> list[dict]:
    """
    Analyze viral_videos for the given niche(s) and write viral_patterns.
    Returns list of pattern dicts written.
    """
    from database.connection import get_session
    from database.models import ViralVideo, ViralPattern
    from sqlalchemy import select, and_

    db = get_session()
    try:
        niches_to_analyze = [niche] if niche else ["health", "fitness", "lifestyle", "finance", "food"]
        written = []

        for n in niches_to_analyze:
            # Query top viral videos for this niche
            stmt = select(ViralVideo).where(
                and_(
                    ViralVideo.niche == n,
                    ViralVideo.region == region,
                    ViralVideo.play_count >= MIN_VIRAL_PLAY_COUNT,
                )
            ).order_by(ViralVideo.play_count.desc()).limit(200)

            videos = db.execute(stmt).scalars().all()
            if len(videos) < min_videos:
                logger.info(f"[TrendAnalyzer] niche={n}: only {len(videos)} viral videos, skipping")
                continue

            # Extract patterns
            hook_templates = Counter()
            scene_types    = Counter()
            cta_phrases    = []
            all_tags: list[str] = []
            durations: list[float] = []
            play_counts: list[int] = []

            for v in videos:
                if v.hook_text:
                    tmpl = _extract_hook_template(v.hook_text)
                    hook_templates[tmpl] += 1
                    scene_types[_detect_scene_type(v.hook_text)] += 1

                if v.tags:
                    all_tags.extend(v.tags)

                if v.duration_s:
                    durations.append(v.duration_s)

                play_counts.append(v.play_count or 0)

            cta_phrases = _extract_cta_phrases([v.hook_text or "" for v in videos])
            top_tags    = [t for t, _ in Counter(all_tags).most_common(20)]
            top_hooks   = [h for h, _ in hook_templates.most_common(10)]
            top_scenes  = [s for s, _ in scene_types.most_common(5)]
            avg_duration = round(sum(durations) / len(durations), 1) if durations else 30.0
            avg_plays    = int(sum(play_counts) / len(play_counts)) if play_counts else 0

            # Upsert pattern (update if exists, insert if not)
            existing = db.query(ViralPattern).filter(
                ViralPattern.niche == n,
                ViralPattern.region == region,
            ).first()

            if existing:
                existing.hook_templates   = top_hooks
                existing.scene_types      = top_scenes
                existing.cta_phrases      = cta_phrases
                existing.hashtag_clusters = top_tags
                existing.avg_duration_s   = avg_duration
                existing.avg_play_count   = avg_plays
                existing.sample_count     = len(videos)
                existing.updated_at       = datetime.now(timezone.utc)
                pattern = existing
            else:
                pattern = ViralPattern(
                    niche=n,
                    region=region,
                    hook_templates=top_hooks,
                    scene_types=top_scenes,
                    cta_phrases=cta_phrases,
                    hashtag_clusters=top_tags,
                    avg_duration_s=avg_duration,
                    avg_play_count=avg_plays,
                    sample_count=len(videos),
                )
                db.add(pattern)

            db.commit()
            written.append({"niche": n, "sample_count": len(videos)})
            logger.info(f"[TrendAnalyzer] niche={n}: wrote pattern from {len(videos)} videos")

        return written
    finally:
        db.close()
