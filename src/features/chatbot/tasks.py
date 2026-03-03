import json

from celery import Task  # type: ignore

from src.features.chatbot.constants import REDIS_SYNC
from src.features.chatbot.service import ChatbotService
from src.worker import EMBEDDER, EMBEDDING_TOKENIZER, LLM_MODEL, LLM_TOKENIZER, worker  # type: ignore
from src.database import SessionLocal


@worker.task(bind=True)  # type: ignore
def chatbot_task(self: Task, repo_id: int, query: str, channel: str):
    db_session = SessionLocal()
    try:
        delivered = REDIS_SYNC.publish(  # type: ignore
            channel=channel,
            message=json.dumps({"type": "started"}),
        )
        print(f"delivered to {delivered}")
        chatbot = ChatbotService(
            db_session=db_session,
            repo_id=repo_id,
            embedder=EMBEDDER,
            embedding_tokenizer=EMBEDDING_TOKENIZER,
            llm_model=LLM_MODEL,
            llm_tokenizer=LLM_TOKENIZER,
        )

        chatbot.run_chatbot(query=query, channel=channel)
        return {"status": "ok"}
    finally:
        db_session.close()
