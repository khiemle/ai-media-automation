"""
Scraper orchestrator — run_scrape() coordinates all enabled sources.
Called by the daily pipeline and the console's manual scrape trigger.
"""
import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

SOURCES_YAML = Path(__file__).parent.parent / "config" / "scraper_sources.yaml"


def _load_sources() -> list[dict]:
    with open(SOURCES_YAML) as f:
        return yaml.safe_load(f).get("sources", [])


def run_scrape(source_ids: list[str] | None = None) -> dict:
    """
    Run all enabled scrapers (or only the specified source_ids).
    Then run trend analysis.
    Returns summary dict.
    """
    import importlib

    sources = _load_sources()
    to_run  = [
        s for s in sources
        if s.get("status") in ("active", "standby")
        and s.get("module") and s.get("function")
        and (source_ids is None or s["id"] in source_ids)
    ]

    total_inserted: int = 0
    all_inserted_ids: list[int] = []
    errors: list[str] = []

    for source in to_run:
        try:
            logger.info(f"[Scraper] Running source: {source['id']}")
            module = importlib.import_module(source["module"])
            fn     = getattr(module, source["function"])
            ids    = fn()
            total_inserted += len(ids)
            all_inserted_ids.extend(ids)
            logger.info(f"[Scraper] {source['id']} → {len(ids)} new records")
        except Exception as e:
            msg = f"[Scraper] {source['id']} failed: {e}"
            logger.error(msg)
            errors.append(msg)

    # Run trend analysis only for video sources (not news articles)
    video_inserted = any(s.get("type") != "news" for s in to_run)
    if all_inserted_ids and video_inserted:
        try:
            from scraper.trend_analyzer import analyze
            analyze()
            logger.info("[Scraper] Trend analysis complete")
        except Exception as e:
            logger.warning(f"[Scraper] Trend analysis failed: {e}")

    return {
        "sources_run":     len(to_run),
        "records_inserted": total_inserted,
        "inserted_ids":    all_inserted_ids,
        "errors":          errors,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run_scrape()
    print(result)
