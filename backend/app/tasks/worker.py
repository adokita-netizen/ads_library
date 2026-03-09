"""Celery worker configuration."""

from types import SimpleNamespace

try:
    from celery import Celery
    from celery.schedules import crontab
except ModuleNotFoundError:
    Celery = None

    def crontab(*args, **kwargs):
        return {"args": args, "kwargs": kwargs}

    class _LocalTaskWrapper:
        def __init__(self, func, **task_options):
            self.func = func
            self.max_retries = task_options.get("max_retries", 0)
            self.default_retry_delay = task_options.get("default_retry_delay")
            self.request = SimpleNamespace(id=None, retries=0)

        def __call__(self, *args, **kwargs):
            return self.run(*args, **kwargs)

        def run(self, *args, **kwargs):
            previous_request = self.request
            self.request = SimpleNamespace(
                id=getattr(previous_request, "id", None),
                retries=getattr(previous_request, "retries", 0),
            )
            try:
                return self.func(self, *args, **kwargs)
            finally:
                self.request = previous_request

        def delay(self, *args, **kwargs):
            payload = self.run(*args, **kwargs)
            return SimpleNamespace(id=None, task_id=None, payload=payload)

        def apply_async(self, args=None, kwargs=None, **_options):
            payload = self.run(*(args or ()), **(kwargs or {}))
            return SimpleNamespace(id=None, task_id=None, payload=payload)

        def retry(self, exc=None):
            self.request.retries = getattr(self.request, "retries", 0) + 1
            raise exc or RuntimeError("Local task retry requested")

    class _LocalCelery:
        def __init__(self, *args, **kwargs):
            self.conf = SimpleNamespace(update=lambda *a, **k: None)

        def task(self, *decorator_args, **decorator_kwargs):
            def decorator(func):
                return _LocalTaskWrapper(func, **decorator_kwargs)

            return decorator

        def autodiscover_tasks(self, *args, **kwargs):
            return None

        def send_task(self, *args, **kwargs):
            raise RuntimeError("Celery is not installed in this environment")

from app.core.config import get_settings

settings = get_settings()

if Celery is None:
    celery_app = _LocalCelery(
        "vaap_worker",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
else:
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
    # Retry policy for transient errors (network, rate limits)
    task_autoretry_for=(ConnectionError, TimeoutError, OSError),
    task_retry_kwargs={"max_retries": 3},
    task_retry_backoff=True,
    task_retry_backoff_max=600,  # Max 10 minutes between retries
    task_routes={
        "app.tasks.analysis_tasks.*": {"queue": "analysis"},
        "app.tasks.crawl_tasks.*": {"queue": "crawl"},
        "app.tasks.generation_tasks.*": {"queue": "generation"},
        "app.tasks.lp_tasks.*": {"queue": "analysis"},
        "app.tasks.ranking_tasks.*": {"queue": "default"},
        "app.tasks.metrics_tasks.*": {"queue": "default"},
        "app.tasks.alert_tasks.*": {"queue": "default"},
        "app.tasks.freshness_tasks.*": {"queue": "default"},
        "app.tasks.meta_sync_tasks.*": {"queue": "default"},
        "app.tasks.optimization_tasks.*": {"queue": "default"},
    },
    task_default_queue="default",
    beat_schedule={
        "crawl-daily-all-platforms": {
            "task": "app.tasks.crawl_tasks.crawl_ads_task",
            "schedule": crontab(hour=3, minute=0),  # 毎日 03:00 JST
            "args": ["", ["youtube", "tiktok", "facebook", "instagram", "yahoo",
                          "x_twitter", "line", "pinterest", "smartnews",
                          "google_ads", "gunosy"], None, 50, True],
        },
        "collect-daily-metrics": {
            "task": "app.tasks.metrics_tasks.collect_daily_metrics_task",
            "schedule": crontab(hour=4, minute=0),  # 毎日 04:00 JST
        },
        "compute-daily-rankings": {
            "task": "app.tasks.ranking_tasks.compute_rankings_task",
            "schedule": crontab(hour=5, minute=0),  # 毎日 05:00 JST
        },
        "detect-daily-alerts": {
            "task": "app.tasks.alert_tasks.detect_alerts_task",
            "schedule": crontab(hour=6, minute=0),  # 毎日 06:00 JST
        },
        "refresh-data-freshness": {
            "task": "app.tasks.freshness_tasks.refresh_data_freshness_task",
            "schedule": crontab(hour=6, minute=30),  # 毎日 06:30 JST
        },
        # Meta Marketing API tasks
        "meta-token-health-check": {
            "task": "app.tasks.meta_sync_tasks.check_meta_token_health_task",
            "schedule": crontab(hour=1, minute=0),  # 毎日 01:00 JST
        },
        "meta-sync-all-accounts": {
            "task": "app.tasks.meta_sync_tasks.sync_all_meta_accounts_task",
            "schedule": crontab(hour=2, minute=0),  # 毎日 02:00 JST
        },
        "meta-generate-recommendations": {
            "task": "app.tasks.optimization_tasks.generate_recommendations_task",
            "schedule": crontab(hour=7, minute=0),  # 毎日 07:00 JST
        },
        "meta-update-ab-test-metrics": {
            "task": "app.tasks.optimization_tasks.update_ab_test_metrics_task",
            "schedule": crontab(minute=0, hour="*/4"),  # 4時間ごと
        },
    },
)

celery_app.autodiscover_tasks([
    "app.tasks.analysis_tasks",
    "app.tasks.crawl_tasks",
    "app.tasks.lp_tasks",
    "app.tasks.generation_tasks",
    "app.tasks.ranking_tasks",
    "app.tasks.metrics_tasks",
    "app.tasks.alert_tasks",
    "app.tasks.freshness_tasks",
    "app.tasks.meta_sync_tasks",
    "app.tasks.optimization_tasks",
])
