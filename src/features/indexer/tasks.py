from typing import TypedDict
from celery import Task  # type: ignore
import requests
from src.features.indexer.service import ChunkingService, EmbeddingService

from src.features.repositories.tasks import DownloadRepoResult
from src.worker import EMBEDDER, EMBEDDING_TOKENIZER, worker  # type: ignore
from src.database import SessionLocal


class IndexerResult(TypedDict):
    status: str
    repo_id: int
    name: str
    chunks_created: int
    encodings_created: int


@worker.task(bind=True)  # type: ignore
def index_repo(
    self: Task,
    download_repo_task_res: DownloadRepoResult,
) -> IndexerResult:
    db_session = SessionLocal()
    http = requests.session()

    print(download_repo_task_res)

    repo_id = download_repo_task_res["repo_id"]
    repo_name = download_repo_task_res["name"]

    try:
        embedding_service = EmbeddingService(
            db_session=db_session,
            chunking_service=None,
            embedder=EMBEDDER,
            tokenizer=EMBEDDING_TOKENIZER,
        )

        chunking_service = ChunkingService(
            embedding_service=embedding_service,
            db_session=db_session,
            repo_id=repo_id,
            repo_name=repo_name,
        )

        embedding_service.chunking_service = chunking_service

        selected_files = chunking_service.get_selected_files(repo_id=repo_id)

        self.update_state(state="PROGRESS", meta={"step": "chunking"})  # type: ignore
        chunks = chunking_service.chunk_repo_files(
            selected_files=selected_files,
        )

        self.update_state(state="PROGRESS", meta={"step": "embedding"})  # type: ignore
        embeddings = embedding_service.embed_chunks(chunks=chunks)

        db_session.commit()

        return {
            "status": "ok",
            "repo_id": repo_id,
            "name": repo_name,
            "chunks_created": len(chunks),
            "encodings_created": len(embeddings),
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
        http.close()
