from typing import TypedDict
from celery import Task  # type: ignore
import requests
from src.features.indexer.embedder import get_embedder_model, get_tokenizer
from src.features.indexer.service import ChunkingService, EmbeddingService, RepoService

from src.worker import worker
from src.database import SessionLocal
from src.features.indexer.utils import get_repo_path


class IndexerResult(TypedDict):
    status: str
    repo_id: int
    owner: str
    name: str
    commit_sha: str
    chunks_created: int
    encodings_created: int


@worker.task(bind=True)  # type: ignore
def indexer(self: Task, repo_owner: str, repo_name: str) -> IndexerResult:
    db_session = SessionLocal()
    http = requests.session()

    embedder = get_embedder_model()
    tokenizer = get_tokenizer()

    repo_service = RepoService(
        db_session=db_session, http_session=http, repo_name=repo_name
    )

    try:

        repo_path = get_repo_path(repo_name=repo_name)
        print(repo_path)
        self.update_state(state="PROGRESS", meta={"step": "metadata"})  # type: ignore

        repo = repo_service.get_repo_metadata(owner=repo_owner, repo_name=repo_name)

        self.update_state(state="PROGRESS", meta={"step": "download"})  # type: ignore

        _, commit_sha = repo_service.download_repo(
            owner=repo_owner, repo_name=repo_name
        )

        self.update_state(state="PROGRESS", meta={"step": "chunking"})  # type: ignore

        embedding_service = EmbeddingService(
            db_session=db_session,
            chunking_service=None,
            embedder=embedder,
            tokenizer=tokenizer,
        )

        chunking_service = ChunkingService(
            repo_service=repo_service,
            embedding_service=embedding_service,
            db_session=db_session,
            repo_id=repo.id,
            repo_name=repo_name,
        )

        embedding_service.chunking_service = chunking_service

        chunks = chunking_service.chunk_repo_files(
            zip_file_path=repo_path,
            commit_sha=commit_sha,
        )

        embeddings = embedding_service.embed_chunks(
            chunks=chunks, tokenizer=tokenizer, embedder=embedder
        )

        db_session.commit()

        return {
            "status": "ok",
            "repo_id": repo.id,
            "owner": repo_owner,
            "name": repo_name,
            "commit_sha": commit_sha,
            "chunks_created": len(chunks),
            "encodings_created": len(embeddings),
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
        http.close()
