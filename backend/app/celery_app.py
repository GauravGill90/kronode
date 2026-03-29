from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "kronode",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.pipeline.task_queue", "app.orchestration.celery_integration"],
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

# Beat schedule — only enabled via env vars (all off by default)
beat_schedule = {}

if settings.enable_poll_pr:
    beat_schedule["poll-pr-outcomes"] = {
        "task": "poll_pr_outcomes",
        "schedule": 60.0,
    }

if settings.enable_poll_clarification:
    beat_schedule["poll-clarifications"] = {
        "task": "poll_clarifications",
        "schedule": 30.0,
    }

if settings.enable_convention_refresh:
    beat_schedule["weekly-convention-refresh"] = {
        "task": "refresh_conventions_all_orgs",
        "schedule": 604800.0,
    }

celery_app.conf.beat_schedule = beat_schedule
