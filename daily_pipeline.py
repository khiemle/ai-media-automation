"""
Daily Pipeline Orchestrator — runs the full content production cycle.
Called by batch_runner.py on cron schedule.

Flow:
  1. Scrape TikTok trends (optional, if enabled)
  2. Analyze trends → update viral_patterns
  3. Generate scripts (one per topic/niche combo)
  4. Compose + render each approved script
  5. Schedule uploads to configured channels
  6. Return summary report
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config" / "pipeline_config.yaml"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def run_daily(topics: list[str] | None = None, dry_run: bool = False) -> dict:
    """
    Run the full daily pipeline.

    Args:
        topics:   List of specific topics to generate. If None, auto-selects from trends.
        dry_run:  If True, skip actual LLM/render/upload — just log actions.

    Returns: Summary dict with counts and errors.
    """
    cfg      = _load_config()
    started  = datetime.now(timezone.utc)
    summary  = {"started_at": started.isoformat(), "errors": [], "steps": {}}

    niches    = cfg.get("pipeline", {}).get("niches", ["health", "fitness", "lifestyle"])
    template  = cfg.get("pipeline", {}).get("default_template", "tiktok_viral")
    target_n  = cfg.get("pipeline", {}).get("daily_video_target", 5)

    # ── Step 1: Scrape ────────────────────────────────────────────────────────
    scrape_enabled = cfg.get("scraper", {}).get("enabled", True)
    if scrape_enabled and not dry_run:
        try:
            from scraper.main import run_scrape
            scrape_result = run_scrape()
            summary["steps"]["scrape"] = scrape_result
            logger.info(f"[Pipeline] Scrape: {scrape_result.get('records_inserted', 0)} new records")
        except Exception as e:
            msg = f"Scrape failed: {e}"
            logger.error(f"[Pipeline] {msg}")
            summary["errors"].append(msg)

    # ── Step 2: Determine topics ──────────────────────────────────────────────
    if not topics:
        topics = _select_topics(niches, target_n)
    logger.info(f"[Pipeline] Generating {len(topics)} scripts: {topics}")

    # ── Step 3: Generate scripts ──────────────────────────────────────────────
    script_ids: list[int] = []
    if not dry_run:
        from database.connection import get_session
        from database.models import GeneratedScript

        for i, topic_str in enumerate(topics):
            niche = niches[i % len(niches)]
            try:
                from rag.script_writer import generate_script
                script_json = generate_script(topic=topic_str, niche=niche, template=template)

                db = get_session()
                try:
                    script = GeneratedScript(
                        topic=topic_str,
                        niche=niche,
                        template=template,
                        script_json=script_json,
                        status="approved",  # auto-approved in batch mode
                        llm_used=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                    )
                    db.add(script)
                    db.commit()
                    db.refresh(script)
                    script_ids.append(script.id)
                    logger.info(f"[Pipeline] Script {script.id} generated: '{topic_str}'")
                finally:
                    db.close()

            except Exception as e:
                msg = f"Script generation failed for '{topic_str}': {e}"
                logger.error(f"[Pipeline] {msg}")
                summary["errors"].append(msg)

    summary["steps"]["generate"] = {"scripts_created": len(script_ids), "script_ids": script_ids}

    # ── Step 4: Produce (compose + render) ────────────────────────────────────
    produced: list[int] = []
    failed_render: list[int] = []

    for script_id in script_ids:
        if dry_run:
            logger.info(f"[Pipeline] [dry-run] Would render script {script_id}")
            continue
        try:
            from pipeline.composer import compose_video
            from pipeline.renderer import render_final
            from pipeline.caption_gen import generate_captions
            from pipeline.quality_validator import validate

            raw_path   = compose_video(script_id)
            srt_path   = generate_captions(
                os.path.join(os.path.dirname(raw_path), "audio_0.wav")
            )
            final_path = render_final(raw_path, srt_path=srt_path)

            valid, report = validate(final_path)
            if valid:
                produced.append(script_id)
                logger.info(f"[Pipeline] Script {script_id} → {final_path}")
            else:
                logger.warning(f"[Pipeline] Script {script_id} quality check failed: {report['errors']}")
                failed_render.append(script_id)

        except Exception as e:
            msg = f"Render failed for script {script_id}: {e}"
            logger.error(f"[Pipeline] {msg}")
            summary["errors"].append(msg)
            failed_render.append(script_id)

    summary["steps"]["produce"] = {
        "produced": len(produced),
        "failed":   len(failed_render),
        "script_ids": produced,
    }

    # ── Step 5: Schedule uploads ──────────────────────────────────────────────
    if produced and not dry_run:
        try:
            from uploader.scheduler import schedule_upload
            from database.connection import get_session
            from console.backend.models.channel import Channel

            db = get_session()
            try:
                all_channels = db.query(Channel).filter(Channel.status == "active").all()
                default_channel_ids = [c.id for c in all_channels[:2]]  # first 2 active channels
            finally:
                db.close()

            for script_id in produced:
                niche = niches[script_ids.index(script_id) % len(niches)] if script_id in script_ids else "lifestyle"
                schedule_upload(script_id, default_channel_ids, niche=niche)

            summary["steps"]["schedule"] = {"scheduled": len(produced)}
        except Exception as e:
            msg = f"Upload scheduling failed: {e}"
            logger.error(f"[Pipeline] {msg}")
            summary["errors"].append(msg)

    summary["completed_at"] = datetime.now(timezone.utc).isoformat()
    summary["duration_s"]   = (datetime.now(timezone.utc) - started).total_seconds()

    logger.info(f"[Pipeline] Daily run complete: {summary}")
    return summary


def _select_topics(niches: list[str], count: int) -> list[str]:
    """Auto-select topics from viral patterns if no topics provided."""
    topics: list[str] = []
    try:
        from database.connection import get_session
        from database.models import ViralVideo

        db = get_session()
        try:
            # Use most-viewed recent videos as topic inspiration
            recent = db.query(ViralVideo).order_by(
                ViralVideo.play_count.desc()
            ).limit(count * 2).all()

            for v in recent:
                if v.hook_text and len(topics) < count:
                    # Truncate hook to ~50 chars as topic
                    topics.append(v.hook_text[:60].strip())
        finally:
            db.close()
    except Exception:
        pass

    # Fill remaining with niche defaults
    DEFAULT_TOPICS = {
        "health":    ["5 thói quen sống khỏe mỗi ngày", "Bí quyết tăng sức đề kháng tự nhiên"],
        "fitness":   ["Bài tập giảm cân hiệu quả tại nhà", "5 động tác gym cho người mới bắt đầu"],
        "lifestyle": ["Cách xây dựng thói quen tốt trong 21 ngày", "Bí quyết sống tối giản"],
        "finance":   ["Cách tiết kiệm 10 triệu mỗi tháng", "5 sai lầm tài chính người trẻ hay mắc"],
    }
    while len(topics) < count:
        niche = niches[len(topics) % len(niches)]
        niche_topics = DEFAULT_TOPICS.get(niche, ["Nội dung hữu ích cho cuộc sống"])
        topics.append(niche_topics[len(topics) % len(niche_topics)])

    return topics[:count]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    dry = "--dry-run" in sys.argv
    result = run_daily(dry_run=dry)
    print(result)
