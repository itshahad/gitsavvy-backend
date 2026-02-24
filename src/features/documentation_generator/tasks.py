from typing import TypedDict
from annotated_types import Len
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
    files_len: int


@worker.task(bind=True)  # type: ignore
def docs_generator(
    self: Task,
    repo_id: int,
    repo_name: str,
    start_from_module: int | None = None,
    start_from_file: int | None = None,
    start_from_chunk: int | None = None,
) -> DocGeneratorResult:
    db_session = SessionLocal()
    http = requests.session()

    llm_model = get_llm_model()
    tokenizer = get_llm_tokenizer()
    # llm_model = None
    # tokenizer = None

    llm_service = LlmService(
        session=db_session, llm_model=llm_model, tokenizer=tokenizer
    )

    doc_generate_service = DocGenerateService(
        session=db_session,
        repo_id=repo_id,
        repo_name=repo_name,
        llm_service=llm_service,
        start_from_module_id=start_from_module,
        start_from_file_id=start_from_file,
        start_from_chunk_id=start_from_chunk,
    )

    try:
        files_doc = doc_generate_service.generate_docs()
        # db_session.commit()

        return {"status": "ok", "repo_id": repo_id, "files_len": len(files_doc)}
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
        http.close()
