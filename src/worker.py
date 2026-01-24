from celery import Celery
import os

worker = Celery(__name__)

worker.conf.update(
    broker_url=os.environ.get(
        "CELERY_BROKER_URL", "redis://localhost:6379"),
    result_backend=os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379"),
)

worker.conf.worker_send_task_events = True
worker.conf.task_send_sent_event = True


worker.autodiscover_tasks([
    "features.indexer",
])