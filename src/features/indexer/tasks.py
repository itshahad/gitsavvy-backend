from sqlalchemy.orm import Session
import requests
from pathlib import Path
from src.worker import worker
from src.database import SessionLocal
from src.features.indexer.service import *
from src.features.indexer.utils import get_repo_path
from src.features.indexer.embedder import get_embedder_model


@worker.task(bind = True)
def indexer(self, repo_owner:str, repo_name:str):
    db_session = SessionLocal()
    http = requests.session()
    embedder = get_embedder_model()

    try:
        repo_path = get_repo_path(repo_name=repo_name)
        
        self.update_state(state= "PROGRESS", meta={"step" : "metadata"})
        repo = get_repo_metadata(http=http, session=db_session, owner=repo_owner, repo_name=repo_name)

        self.update_state(state= "PROGRESS", meta={"step" : "download"})
        _, commit_sha = download_repo(http=http, owner=repo_owner, repo_name=repo_name)

        self.update_state(state= "PROGRESS", meta={"step" : "chunking"})
        chunks = chunk_repo_files(session=db_session, zip_file_path=repo_path, commit_sha=commit_sha, repo_id=repo.id, repo_name=repo_name)

        embeddings = embed_chunks(embedder=embedder, chunks=chunks, session=db_session)

        db_session.commit()
        
        return {
            "status": "ok",
            "repo_id": repo.id,
            "owner": repo_owner,
            "name": repo_name,
            "commit_sha": commit_sha,
            "chunks_created": len(embeddings) if embeddings is not None else 0,
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
        http.close()

