import importlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from console.backend.celery_app import celery_app

SOURCES_YAML = Path(__file__).parent.parent.parent.parent / "config" / "scraper_sources.yaml"


class _ListHandler(logging.Handler):
    """Captures log records into a list for task progress reporting."""
    def __init__(self, log_list: list):
        super().__init__()
        self.log_list = log_list

    def emit(self, record):
        try:
            self.log_list.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "msg": self.format(record),
            })
        except Exception:
            pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@celery_app.task(bind=True, name="console.backend.tasks.scraper_tasks.run_scrape_task", queue="scrape_q")
def run_scrape_task(self, source_id: str):
    """Load the source config, dynamically import the scraper module, and run it.
    Emits granular PROGRESS states with accumulated log lines for live UI streaming."""
    logs: list[dict] = []

    handler = _ListHandler(logs)
    handler.setFormatter(logging.Formatter("%(name)s — %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    def _progress(step: str, extra: dict | None = None):
        meta = {"step": step, "source": source_id, "logs": list(logs)}
        if extra:
            meta.update(extra)
        self.update_state(state="PROGRESS", meta=meta)

    try:
        logs.append({"ts": _now(), "level": "INFO", "msg": f"Starting scrape for source: {source_id}"})
        _progress("loading_config")

        with open(SOURCES_YAML) as f:
            sources = yaml.safe_load(f).get("sources", [])

        source = next((s for s in sources if s["id"] == source_id), None)
        if not source:
            raise ValueError(f"Source '{source_id}' not found")
        if source["status"] not in ("active", "standby"):
            raise ValueError(f"Source '{source_id}' is not runnable (status: {source['status']})")
        if not source.get("module") or not source.get("function"):
            raise ValueError(f"Source '{source_id}' has no module/function configured")

        logs.append({"ts": _now(), "level": "INFO",
                     "msg": f"Config OK — module: {source['module']} · fn: {source['function']}"})
        _progress("importing_module")

        module = importlib.import_module(source["module"])
        fn = getattr(module, source["function"])

        logs.append({"ts": _now(), "level": "INFO", "msg": "Module imported — running scraper…"})
        _progress("scraping")

        result = fn()

        count = len(result) if result else 0
        logs.append({"ts": _now(), "level": "INFO", "msg": f"Done — {count} item(s) saved to database"})
        _progress("done", {"count": count})

        return {"source_id": source_id, "count": count, "logs": list(logs)}

    except Exception as exc:
        logs.append({"ts": _now(), "level": "ERROR", "msg": f"Scrape failed: {exc}"})
        _progress("error", {"error": str(exc)})
        raise
    finally:
        root_logger.removeHandler(handler)
