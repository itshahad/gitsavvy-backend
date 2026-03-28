from celery import Task  # type: ignore

from src.worker import EMBEDDER, EMBEDDING_TOKENIZER, worker  # type: ignore
from src.database import SessionLocal

from src.features.profileInfo.services import UserProfileEmbeddingService


@worker.task(bind=True)  # type: ignore
def user_preferences_embedding_task(self: Task, user_id: int):
    print("running task")
    db_session = SessionLocal()

    service = UserProfileEmbeddingService(
        db_session=db_session,
        embedder=EMBEDDER,
        tokenizer=EMBEDDING_TOKENIZER,
    )
    try:
        service.embed_user_profile(user_id=user_id)
        return {"status": "ok"}
    finally:
        db_session.close()
