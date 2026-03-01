# type: ignore[all]
from celery import Celery
from kombu import Queue
from src.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_INCLUDE_TASKS
from src.core.embedder import get_embedder_model, get_tokenizer
from src.core.llm import get_llm_model, get_llm_tokenizer


def make_celery(include_task: bool):
    worker = Celery(__name__)

    worker.conf.update(
        broker_url=CELERY_BROKER_URL,
        result_backend=CELERY_RESULT_BACKEND,
        worker_send_task_events=True,
        task_send_sent_event=True,
        task_track_started=True,
        # if no queue defined, where the tasks should be routed?
        task_default_queue="queue1",
        task_default_routing_key="queue1",
        # what are the queues that handled with this worker?
        task_queues=(Queue("queue1", routing_key="queue1"),),
        # defining queues for tasks:
        task_routes={
            "features.indexer.tasks.*": {"queue": "queue1", "routing_key": "queue1"},
        },
    )

    if include_task:
        worker.autodiscover_tasks(
            [
                "src.features.indexer",
                "src.features.documentation_generator",
                "src.features.chatbot",
            ]
        )

    return worker


worker = make_celery(CELERY_INCLUDE_TASKS == "1")


if CELERY_INCLUDE_TASKS == "1":
    import torch, torchvision

    EMBEDDER = get_embedder_model()
    EMBEDDING_TOKENIZER = get_tokenizer()
    LLM_MODEL = get_llm_model()
    LLM_TOKENIZER = get_llm_tokenizer()

    print("torch:", torch.__version__)
    print("torchvision:", torchvision.__version__)
    print("CUDA available:", torch.cuda.is_available())
else:
    EMBEDDER = None
    EMBEDDING_TOKENIZER = None
    LLM_MODEL = None
    LLM_TOKENIZER = None
# for now we gonna work on solo pool (no concurrency), then we increase the throughput and scale processing
