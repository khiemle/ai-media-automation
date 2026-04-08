import importlib
import logging
from pathlib import Path

import yaml

from console.backend.celery_app import celery_app

logger = logging.getLogger(__name__)

SOURCES_YAML = Path(__file__).parent.parent.parent.parent / "config" / "scraper_sources.yaml"


@celery_app.task(bind=True, name="console.backend.tasks.scraper_tasks.run_scrape_task", queue="scrape_q")
def run_scrape_task(self, source_id: str):
    """Load the source config, dynamically import the scraper module, and run it."""
    with open(SOURCES_YAML) as f:
        sources = yaml.safe_load(f).get("sources", [])

    source = next((s for s in sources if s["id"] == source_id), None)
    if not source:
        raise ValueError(f"Source '{source_id}' not found")
    if source["status"] not in ("active", "standby"):
        raise ValueError(f"Source '{source_id}' is not active (status: {source['status']})")
    if not source.get("module") or not source.get("function"):
        raise ValueError(f"Source '{source_id}' has no module/function configured")

    logger.info(f"Running scrape for source: {source_id}")
    self.update_state(state="PROGRESS", meta={"step": "importing", "source": source_id})

    module = importlib.import_module(source["module"])
    fn = getattr(module, source["function"])
    result = fn()

    logger.info(f"Scrape complete for {source_id}: {len(result) if result else 0} items")
    return {"source_id": source_id, "count": len(result) if result else 0}
