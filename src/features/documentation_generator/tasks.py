from typing import TypedDict
from celery import Task  # type: ignore
import requests
from src.features.documentation_generator.service import DocGenerateService

from src.features.indexer.tasks import IndexerResult
from src.worker import LLM_MODEL, LLM_TOKENIZER, worker  # type: ignore
from src.database import SessionLocal


class DocGeneratorResult(TypedDict):
    status: str
    repo_id: int
    files_len: int


@worker.task(bind=True)  # type: ignore
def docs_generator(
    self: Task,
    indexer_result: IndexerResult,
    start_from_module: int | None = None,
    start_from_file: int | None = None,
    start_from_chunk: int | None = None,
) -> DocGeneratorResult:
    db_session = SessionLocal()
    http = requests.session()

    repo_id = indexer_result["repo_id"]
    repo_name = indexer_result["name"]

    doc_generate_service = DocGenerateService(
        session=db_session,
        repo_id=repo_id,
        repo_name=repo_name,
        tokenizer=LLM_TOKENIZER,
        model=LLM_MODEL,
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
