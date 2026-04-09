"""
Feedback Scorer — computes a quality score (0–100) from platform metrics.
Marks scripts as high_quality (≥70) or low_quality (<40).
"""
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REINDEX_THRESHOLD   = int(os.environ.get("FEEDBACK_REINDEX_THRESHOLD", "70"))
LOW_QUALITY_THRESHOLD = int(os.environ.get("FEEDBACK_LOW_QUALITY_THRESHOLD", "40"))

# Normalization denominators (benchmarks for "excellent" performance)
BENCHMARK_VIEWS  = 500_000
BENCHMARK_ER     = 10.0      # 10% ER = excellent
BENCHMARK_SHARES = 10_000


def compute_score(metrics) -> float:
    """
    Compute quality score 0–100 from a Metrics object.

    Formula:
      0.4 × (views / BENCHMARK_VIEWS)
    + 0.3 × (ER / BENCHMARK_ER)
    + 0.2 × (shares / BENCHMARK_SHARES)
    + 0.1 × (comments / (views * 0.01))   # comment ratio

    Capped at 100.
    """
    views   = getattr(metrics, "views", 0) or 0
    er      = getattr(metrics, "engagement_rate", 0) or 0
    shares  = getattr(metrics, "shares", 0) or 0
    comments = getattr(metrics, "comments", 0) or 0

    view_score    = min(views    / BENCHMARK_VIEWS, 1.0)  * 100
    er_score      = min(er       / BENCHMARK_ER,    1.0)  * 100
    share_score   = min(shares   / BENCHMARK_SHARES, 1.0) * 100
    comment_score = min(comments / max(views * 0.01, 1), 1.0) * 100

    score = (
        0.40 * view_score +
        0.30 * er_score   +
        0.20 * share_score +
        0.10 * comment_score
    )
    return round(min(score, 100.0), 2)


def score_all() -> dict:
    """
    Score all completed scripts and update their quality_score in the DB.
    Returns summary: {scored: N, high_quality: N, low_quality: N}
    """
    from database.connection import get_session
    from database.models import GeneratedScript
    from feedback.tracker import fetch_youtube, fetch_tiktok

    db = get_session()
    try:
        scripts = db.query(GeneratedScript).filter(
            GeneratedScript.status == "completed",
            GeneratedScript.platform_video_id.isnot(None),
        ).all()

        scored = high = low = 0
        for script in scripts:
            pid = script.platform_video_id or ""
            if pid.startswith("YT_"):
                m = fetch_youtube(pid[3:])
            elif pid.startswith("TT_"):
                m = fetch_tiktok(pid[3:])
            else:
                m = fetch_youtube(pid)

            if not m:
                continue

            score = compute_score(m)
            script.quality_score = score
            scored += 1

            if score >= REINDEX_THRESHOLD:
                high += 1
            elif score < LOW_QUALITY_THRESHOLD:
                low += 1

        db.commit()
        summary = {"scored": scored, "high_quality": high, "low_quality": low}
        logger.info(f"[Scorer] {summary}")
        return summary
    finally:
        db.close()
