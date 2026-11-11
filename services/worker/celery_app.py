from __future__ import annotations

import os

from celery import Celery

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
always_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() in {"1", "true", "yes"}

celery_app = Celery(
    "stock_assistant_worker",
    broker=broker_url,
    backend=result_backend,
    include=["services.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_track_started=True,
    task_always_eager=always_eager,
    task_eager_propagates=True,
)
