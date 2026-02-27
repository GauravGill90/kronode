from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "kronode",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.pipeline.task_queue"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "poll-pr-outcomes": {
        "task": "poll_pr_outcomes",
        "schedule": 60.0,  # every minute
    },
    "poll-clarifications": {
        "task": "poll_clarifications",
        "schedule": 30.0,  # every 30 seconds
    },
}
