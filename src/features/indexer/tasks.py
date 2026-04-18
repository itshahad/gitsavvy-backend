from typing import TypedDict
from celery import Task  # type: ignore
import requests
from src.features.indexer.service import ChunkingService, EmbeddingService

from src.features.repositories.tasks import DownloadRepoResult
from src.worker import EMBEDDER, EMBEDDING_TOKENIZER, worker  # type: ignore
from src.database import SessionLocal


class ChunkerResult(TypedDict):
    status: str
    repo_id: int
    name: str


@worker.task(bind=True)  # type: ignore
def chunk_repo(
    self: Task,
    download_repo_task_res: DownloadRepoResult,
) -> ChunkerResult:
    db_session = SessionLocal()
    http = requests.session()

    repo_id = download_repo_task_res["repo_id"]
    repo_name = download_repo_task_res["name"]

    try:
        chunking_service = ChunkingService(
            db_session=db_session,
            repo_id=repo_id,
            repo_name=repo_name,
        )

        selected_files = chunking_service.get_selected_files(repo_id=repo_id)

        self.update_state(state="PROGRESS", meta={"step": "chunking"})  # type: ignore
        chunking_service.chunk_repo_files(
            selected_files=selected_files,
        )

        db_session.commit()

        return {
            "status": "ok",
            "repo_id": repo_id,
            "name": repo_name,
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
        http.close()


class IndexerResult(TypedDict):
    status: str
    repo_id: int
    name: str


@worker.task(bind=True)  # type: ignore
def index_repo(
    self: Task,
    chunker_result: ChunkerResult,
) -> IndexerResult:
    db_session = SessionLocal()

    repo_id = chunker_result["repo_id"]
    repo_name = chunker_result["name"]

    embedding_service = EmbeddingService(
        repo_id=repo_id,
        db_session=db_session,
        embedder=EMBEDDER,
        tokenizer=EMBEDDING_TOKENIZER,
    )

    try:
        self.update_state(state="PROGRESS", meta={"step": "embedding"})  # type: ignore
        embedding_service.create_repo_profile_embedding()
        embedding_service.embed_chunks()
        db_session.commit()

        return {
            "status": "ok",
            "repo_id": repo_id,
            "name": repo_name,
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
