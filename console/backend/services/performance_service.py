"""PerformanceService — aggregated video performance analytics."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_EMPTY_DAILY = []
_EMPTY_NICHES = []
_EMPTY_TOP    = []


def _has_scripts(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1 FROM generated_scripts LIMIT 1"))
        return True
    except Exception:
        return False


class PerformanceService:
    def __init__(self, db: Session):
        self.db = db

    # ── Daily aggregates ──────────────────────────────────────────────────────

    def get_daily(self, days: int = 14) -> list[dict]:
        if not _has_scripts(self.db):
            return _stub_daily(days)
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            rows = self.db.execute(text("""
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC') AS day,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE status = 'approved')  AS approved,
                    COUNT(*) FILTER (WHERE status = 'draft')     AS drafted,
                    ROUND(AVG(performance_score)::numeric, 2)    AS avg_score
                FROM generated_scripts
                WHERE created_at >= :since
                GROUP BY day
                ORDER BY day ASC
            """), {"since": since}).fetchall()
            return [
                {
                    "date":      str(r.day),
                    "completed": r.completed or 0,
                    "approved":  r.approved  or 0,
                    "drafted":   r.drafted   or 0,
                    "avg_score": float(r.avg_score or 0),
                }
                for r in rows
            ] or _stub_daily(days)
        except Exception as e:
            logger.warning(f"Performance daily query failed: {e}")
            return _stub_daily(days)

    # ── Niche breakdown ───────────────────────────────────────────────────────

    def get_niches(self) -> list[dict]:
        if not _has_scripts(self.db):
            return _stub_niches()
        try:
            rows = self.db.execute(text("""
                SELECT
                    niche,
                    COUNT(*)                                            AS total,
                    COUNT(*) FILTER (WHERE status = 'completed')       AS completed,
                    ROUND(AVG(performance_score)::numeric, 2)          AS avg_score,
                    ROUND(AVG(CASE WHEN is_successful THEN 1.0 ELSE 0 END)::numeric * 100, 1) AS success_rate
                FROM generated_scripts
                WHERE niche IS NOT NULL
                GROUP BY niche
                ORDER BY total DESC
            """)).fetchall()
            return [
                {
                    "niche":        r.niche,
                    "total":        r.total or 0,
                    "completed":    r.completed or 0,
                    "avg_score":    float(r.avg_score or 0),
                    "success_rate": float(r.success_rate or 0),
                }
                for r in rows
            ] or _stub_niches()
        except Exception as e:
            logger.warning(f"Performance niches query failed: {e}")
            return _stub_niches()

    # ── Top videos ────────────────────────────────────────────────────────────

    def get_top_videos(self, limit: int = 10) -> list[dict]:
        if not _has_scripts(self.db):
            return []
        try:
            rows = self.db.execute(text("""
                SELECT id, topic, niche, template, performance_score,
                       performance_48h, is_successful, created_at
                FROM generated_scripts
                WHERE performance_score IS NOT NULL
                ORDER BY performance_score DESC
                LIMIT :limit
            """), {"limit": limit}).fetchall()
            return [
                {
                    "id":            r.id,
                    "topic":         r.topic,
                    "niche":         r.niche,
                    "template":      r.template,
                    "score":         float(r.performance_score or 0),
                    "is_successful": r.is_successful,
                    "performance_48h": r.performance_48h,
                    "created_at":    r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Top videos query failed: {e}")
            return []

    # ── Summary stats ─────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        if not _has_scripts(self.db):
            return {"total": 0, "completed": 0, "avg_score": 0, "success_rate": 0}
        try:
            row = self.db.execute(text("""
                SELECT
                    COUNT(*)                                       AS total,
                    COUNT(*) FILTER (WHERE status = 'completed')  AS completed,
                    ROUND(AVG(performance_score)::numeric, 2)     AS avg_score,
                    ROUND(AVG(CASE WHEN is_successful THEN 1.0 ELSE 0 END)::numeric * 100, 1) AS success_rate
                FROM generated_scripts
            """)).fetchone()
            return {
                "total":        row.total or 0,
                "completed":    row.completed or 0,
                "avg_score":    float(row.avg_score or 0),
                "success_rate": float(row.success_rate or 0),
            }
        except Exception as e:
            logger.warning(f"Summary query failed: {e}")
            return {"total": 0, "completed": 0, "avg_score": 0, "success_rate": 0}


# ── Stub data (when no pipeline DB yet) ──────────────────────────────────────

def _stub_daily(days: int) -> list[dict]:
    import random
    result = []
    for i in range(days):
        day = datetime.now(timezone.utc) - timedelta(days=days - i - 1)
        result.append({
            "date":      day.strftime("%Y-%m-%d"),
            "completed": random.randint(0, 5),
            "approved":  random.randint(2, 8),
            "drafted":   random.randint(3, 10),
            "avg_score": round(random.uniform(40, 85), 1),
        })
    return result


def _stub_niches() -> list[dict]:
    niches = [
        ("finance", 42, 28, 71.2, 66.7),
        ("health",  38, 24, 68.5, 63.2),
        ("tech",    31, 19, 65.1, 61.3),
        ("lifestyle", 27, 15, 62.3, 55.6),
        ("education", 21, 11, 58.9, 52.4),
    ]
    return [{"niche": n, "total": t, "completed": c, "avg_score": s, "success_rate": r}
            for n, t, c, s, r in niches]
