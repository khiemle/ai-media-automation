from celery import Celery
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
    },
    beat_schedule={
        # Refresh expiring OAuth tokens every 30 minutes
        "token-refresh-every-30min": {
            "task": "console.backend.tasks.token_refresh.refresh_expiring_tokens",
            "schedule": crontab(minute="*/30"),
        },
    },
)
