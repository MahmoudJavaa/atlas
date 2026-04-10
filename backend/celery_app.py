from celery import Celery
from backend.config import settings

celery_app = Celery(
    "atlas",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "backend.tasks.crawl_tasks",
        "backend.tasks.keyword_tasks",
        "backend.tasks.content_tasks",
        "backend.tasks.analytics_tasks",
        "backend.tasks.learning_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "backend.tasks.crawl_tasks.*": {"queue": "crawl"},
        "backend.tasks.keyword_tasks.*": {"queue": "keyword"},
        "backend.tasks.content_tasks.*": {"queue": "content"},
        "backend.tasks.analytics_tasks.*": {"queue": "analytics"},
        "backend.tasks.learning_tasks.*": {"queue": "learning"},
    },
    beat_schedule={
        "run-learning-loop-weekly": {
            "task": "backend.tasks.learning_tasks.run_learning_loop_all_sites",
            "schedule": 604800.0,  # 7 days
        },
    },
)
