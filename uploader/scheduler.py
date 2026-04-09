"""
Upload Scheduler — determines optimal upload times per platform and niche.
Creates upload_targets rows with scheduled_at timestamps.
"""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Peak hours (local Vietnam time, UTC+7) per platform
PEAK_HOURS = {
    "youtube": [
        (8, 10),    # morning
        (12, 14),   # lunch
        (17, 20),   # evening primetime
    ],
    "tiktok": [
        (7, 9),     # morning commute
        (12, 13),   # lunch
        (19, 22),   # evening
    ],
}

# Niche-specific hour adjustments (delta from peak hour start)
NICHE_OFFSET = {
    "finance":   0,
    "health":    1,
    "fitness":   -1,   # gym crowd peaks slightly earlier
    "lifestyle": 0,
    "food":      -1,   # before meals
}

VIETNAM_UTC_OFFSET = 7  # UTC+7


def get_optimal_time(
    platform: str,
    niche:    str,
    base_date: datetime | None = None,
) -> datetime:
    """
    Return the next optimal upload datetime (UTC) for the given platform and niche.
    Picks the nearest upcoming peak hour window.
    """
    now = base_date or datetime.now(timezone.utc)
    vnow_h = (now.hour + VIETNAM_UTC_OFFSET) % 24

    peaks = PEAK_HOURS.get(platform, PEAK_HOURS["youtube"])
    offset = NICHE_OFFSET.get(niche, 0)

    # Find next peak window
    for start_h, end_h in sorted(peaks):
        target_vn_h = start_h + offset
        if target_vn_h >= vnow_h:
            # This window is today
            target_utc = now.replace(
                hour=(target_vn_h - VIETNAM_UTC_OFFSET) % 24,
                minute=0, second=0, microsecond=0,
            )
            if target_utc > now:
                return target_utc

    # All windows passed today → schedule for first window tomorrow
    first_h, _ = sorted(peaks)[0]
    target_vn_h = first_h + offset
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(
        hour=(target_vn_h - VIETNAM_UTC_OFFSET) % 24,
        minute=0, second=0, microsecond=0,
    )


def schedule_upload(
    script_id: int,
    channel_ids: list[int],
    niche: str = "lifestyle",
) -> list[dict]:
    """
    Create upload_targets rows for the given script and channels.
    Returns list of created target dicts.
    """
    from database.connection import get_session
    from console.backend.models.channel import Channel, UploadTarget

    db = get_session()
    try:
        targets = []
        for channel_id in channel_ids:
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                logger.warning(f"[Scheduler] Channel {channel_id} not found")
                continue

            scheduled_at = get_optimal_time(channel.platform, niche)
            existing = db.query(UploadTarget).filter(
                UploadTarget.video_id == str(script_id),
                UploadTarget.channel_id == channel_id,
            ).first()

            if existing:
                targets.append({"video_id": str(script_id), "channel_id": channel_id, "existing": True})
                continue

            target = UploadTarget(
                video_id=str(script_id),
                channel_id=channel_id,
                status="scheduled",
                scheduled_at=scheduled_at,
            )
            db.add(target)
            targets.append({
                "video_id":    str(script_id),
                "channel_id":  channel_id,
                "platform":    channel.platform,
                "scheduled_at": scheduled_at.isoformat(),
            })

        db.commit()
        logger.info(f"[Scheduler] Scheduled {len(targets)} upload targets for script {script_id}")
        return targets
    finally:
        db.close()
