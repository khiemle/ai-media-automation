"""
Batch Runner — cron entry point for the daily AI media pipeline.
Run: python batch_runner.py
     python batch_runner.py --run-now      (skip schedule check)
     python batch_runner.py --dry-run      (no LLM/render/upload)
     python batch_runner.py --scrape-only  (only scraper)
     python batch_runner.py --topics "topic1" "topic2"
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/pipeline.log", mode="a"),
    ],
)
logger = logging.getLogger("batch_runner")


def main():
    parser = argparse.ArgumentParser(description="AI Media Automation — Batch Runner")
    parser.add_argument("--run-now",     action="store_true", help="Run immediately, skip schedule")
    parser.add_argument("--dry-run",     action="store_true", help="Simulate without API calls")
    parser.add_argument("--scrape-only", action="store_true", help="Only run the scraper")
    parser.add_argument("--topics",      nargs="*",           help="Specific topics to generate")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"Batch Runner started at {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Options: dry_run={args.dry_run} scrape_only={args.scrape_only}")
    logger.info("=" * 60)

    os.makedirs("logs", exist_ok=True)

    if args.scrape_only:
        _run_scrape()
        return

    if args.run_now or _should_run():
        _run_pipeline(topics=args.topics, dry_run=args.dry_run)
    else:
        logger.info("Not scheduled to run now. Use --run-now to force.")


def _run_scrape():
    try:
        from scraper.main import run_scrape
        result = run_scrape()
        logger.info(f"Scrape complete: {result}")
    except Exception as e:
        logger.error(f"Scrape failed: {e}")


def _run_pipeline(topics=None, dry_run=False):
    try:
        from daily_pipeline import run_daily
        summary = run_daily(topics=topics, dry_run=dry_run)
        _log_summary(summary)
    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        sys.exit(1)


def _should_run() -> bool:
    """Check if pipeline should run based on config schedule (2am Vietnam time)."""
    try:
        import yaml
        from pathlib import Path
        cfg_path = Path(__file__).parent / "config" / "pipeline_config.yaml"
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            # Simple hour check: run between 2:00-2:59 Vietnam time (UTC+7)
            now_vn_h = (datetime.now(timezone.utc).hour + 7) % 24
            return now_vn_h == 2
    except Exception:
        pass
    return False


def _log_summary(summary: dict):
    steps = summary.get("steps", {})
    errors = summary.get("errors", [])

    logger.info("─" * 40)
    logger.info("PIPELINE SUMMARY")
    logger.info("─" * 40)

    if "scrape" in steps:
        s = steps["scrape"]
        logger.info(f"  Scrape: {s.get('videos_inserted', 0)} new videos")

    if "generate" in steps:
        g = steps["generate"]
        logger.info(f"  Generate: {g.get('scripts_created', 0)} scripts")

    if "produce" in steps:
        p = steps["produce"]
        logger.info(f"  Produce: {p.get('produced', 0)} videos (failed: {p.get('failed', 0)})")

    if "schedule" in steps:
        u = steps["schedule"]
        logger.info(f"  Schedule: {u.get('scheduled', 0)} uploads queued")

    logger.info(f"  Duration: {summary.get('duration_s', 0):.1f}s")

    if errors:
        logger.warning(f"  Errors ({len(errors)}):")
        for e in errors:
            logger.warning(f"    - {e}")

    logger.info("─" * 40)


if __name__ == "__main__":
    main()
