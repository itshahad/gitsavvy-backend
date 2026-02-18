from typing import TypedDict
from celery import Task  # type: ignore
import requests
from src.features.documentation_generator.llm import get_llm_model, get_llm_tokenizer
from src.features.documentation_generator.schemas import DocRead
from src.features.documentation_generator.service import DocGenerateService, LlmService

from src.worker import worker
from src.database import SessionLocal


class DocGeneratorResult(TypedDict):
    status: str
    repo_id: int
    num_of_docs: int


@worker.task(bind=True)  # type: ignore
def docs_generator(self: Task, repo_id: int) -> DocGeneratorResult:
    db_session = SessionLocal()
    http = requests.session()

    llm_model = get_llm_model()
    tokenizer = get_llm_tokenizer()

    llm_service = LlmService(
        session=db_session, llm_model=llm_model, tokenizer=tokenizer
    )

    doc_generate_service = DocGenerateService(
        session=db_session, repo_id=repo_id, llm_service=llm_service
    )

    try:
        files = doc_generate_service.load_files()

        docs_list: list[DocRead] = []
        for file in files:
            chunks_list = doc_generate_service.load_file_chunks(file)
            docs = doc_generate_service.generate_chunks_docs(chunks_list)
            docs_list.extend(docs)

        db_session.commit()

        return {"status": "ok", "repo_id": repo_id, "num_of_docs": len(docs_list)}
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
        http.close()
