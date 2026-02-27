from celery import Task  # type: ignore
import requests

from src.features.chatbot.service import ChatbotService
from src.features.documentation_generator.llm import get_llm_model, get_llm_tokenizer
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
    embedding_tokenizer = get_tokenizer()

    llm_model = get_llm_model()
    llm_tokenizer = get_llm_tokenizer()

    chatbot = ChatbotService(
        db_session=db_session,
        repo_id=repo_id,
        embedder=embedder,
        embedding_tokenizer=embedding_tokenizer,
        llm_model=llm_model,
        llm_tokenizer=llm_tokenizer,
    )

    try:
        query = "What is the use of fastapi"
        msg = chatbot.run_chatbot(query=query)
        return msg
    except Exception:
        raise
    finally:
        db_session.close()
        http.close()
