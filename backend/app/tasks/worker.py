"""Celery worker configuration."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "vaap_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.analysis_tasks.*": {"queue": "analysis"},
        "app.tasks.crawl_tasks.*": {"queue": "crawl"},
        "app.tasks.generation_tasks.*": {"queue": "generation"},
    },
    task_default_queue="default",
    beat_schedule={},
)

celery_app.autodiscover_tasks([
    "app.tasks.analysis_tasks",
    "app.tasks.crawl_tasks",
])
