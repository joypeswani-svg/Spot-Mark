"""
tasks/celery_app.py — Celery application for async ML jobs.
Used for heavy video/audio deepfake analysis that should not block the HTTP response.
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "truthlens",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.video_task", "app.tasks.audio_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_soft_time_limit=300,  # 5 min soft limit
    task_time_limit=360,       # 6 min hard limit
    worker_prefetch_multiplier=1,  # one task at a time per worker (ML models are heavy)
)
