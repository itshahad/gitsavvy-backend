import os

BROKER_URL = os.environ.get(
        "CELERY_BROKER_URL", "redis://localhost:6379")
RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379")
INCLUDE_TASKS= os.environ.get(
        "CELERY_INCLUDE_TASKS", "1")