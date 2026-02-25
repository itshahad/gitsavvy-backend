from celery import Task  # type: ignore
import requests

from src.features.chatbot.service import ChunkRetriever
from src.features.documentation_generator.llm import get_llm_model
from src.features.indexer.embedder import get_embedder_model, get_tokenizer
from src.worker import worker
from src.database import SessionLocal


@worker.task(bind=True)  # type: ignore
def chatbot_task(
    self: Task,
    repo_id: int,
):
    db_session = SessionLocal()
    http = requests.session()

    embedder = get_embedder_model()
    tokenizer = get_tokenizer()
    llm = get_llm_model()

    chatbot = ChunkRetriever(
        db_session=db_session,
        repo_id=2,
        embedder=embedder,
        tokenizer=tokenizer,
        llm=llm,
    )

    try:
        query = "What is the use of fastapi"

        msg = chatbot.run_chain(query=query)
        print(msg.content)
    except Exception:
        raise
    finally:
        db_session.close()
        http.close()
