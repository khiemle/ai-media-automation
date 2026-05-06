from celery import Celery, signals
from celery.schedules import crontab
from console.backend.config import settings

celery_app = Celery(
    "console",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "console.backend.tasks.scraper_tasks",
        "console.backend.tasks.script_tasks",
        "console.backend.tasks.production_tasks",
        "console.backend.tasks.upload_tasks",
        "console.backend.tasks.token_refresh",
        "console.backend.tasks.music_tasks",
        "console.backend.tasks.youtube_render_task",
        "console.backend.tasks.youtube_short_render_task",
        "console.backend.tasks.youtube_upload_task",
        "console.backend.tasks.runway_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_routes={
        "console.backend.tasks.scraper_tasks.*": {"queue": "scrape_q"},
        "console.backend.tasks.script_tasks.*": {"queue": "script_q"},
        "console.backend.tasks.production_tasks.*": {"queue": "render_q"},
        "console.backend.tasks.upload_tasks.*": {"queue": "upload_q"},
        "console.backend.tasks.token_refresh.*": {"queue": "scrape_q"},
        "console.backend.tasks.music_tasks.*": {"queue": "render_q"},
        "console.backend.tasks.youtube_render_task.*": {"queue": "render_q"},
        "console.backend.tasks.youtube_short_render_task.*": {"queue": "render_q"},
        "console.backend.tasks.youtube_upload_task.*": {"queue": "upload_q"},
        "console.backend.tasks.runway_task.*": {"queue": "render_q"},
        "tasks.animate_workflow": {"queue": "render_q"},
        "tasks.recover_pending_runway": {"queue": "render_q"},
    },
    beat_schedule={
        # Refresh expiring OAuth tokens every 30 minutes
        "token-refresh-every-30min": {
            "task": "console.backend.tasks.token_refresh.refresh_expiring_tokens",
            "schedule": crontab(minute="*/30"),
        },
        # Re-queue poll tasks for any Runway assets stuck in pending (e.g. after worker restart)
        "recover-pending-runway-every-5min": {
            "task": "tasks.recover_pending_runway",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "render_q"},
        },
    },
)


@signals.worker_process_init.connect
def _worker_process_init(**kwargs):
    """
    Dispose all engine connection pools after Celery forks a worker process.
    Without this, forked workers inherit the parent's pooled connections which
    PostgreSQL considers stale, and they accumulate as idle orphans.
    """
    try:
        from console.backend.database import engine as console_engine
        console_engine.dispose()
    except Exception:
        pass
    try:
        from database.connection import engine as pipeline_engine
        pipeline_engine.dispose()
    except Exception:
        pass
