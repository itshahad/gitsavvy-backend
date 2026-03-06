from typing import TypedDict
from celery import Task  # type: ignore
import requests

from src.features.repositories.service import RepoProcessingService
from src.features.repositories.utils import get_repo_path
from src.worker import worker  # type: ignore
from src.database import SessionLocal


class DownloadRepoResult(TypedDict):
    status: str
    repo_id: int
    owner: str
    name: str
    commit_sha: str
    num_of_selected_files: int


@worker.task(bind=True)  # type: ignore
def download_repo(self: Task, repo_owner: str, repo_name: str) -> DownloadRepoResult:
    db_session = SessionLocal()
    http = requests.session()

    repo_path = get_repo_path(repo_name=repo_name)

    repo_service = RepoProcessingService(
        db_session=db_session, http_session=http, repo_name=repo_name
    )

    try:
        self.update_state(state="PROGRESS", meta={"step": "metadata"})  # type: ignore

        repo = repo_service.get_repo_metadata(owner=repo_owner, repo_name=repo_name)

        self.update_state(state="PROGRESS", meta={"step": "download"})  # type: ignore

        _, commit_sha = repo_service.download_repo(
            owner=repo_owner, repo_name=repo_name
        )

        selected_files = repo_service.select_repo_files(
            repo=repo,
            zip_file_path=repo_path,
            repo_name=repo_name,
            commit_sha=commit_sha,
        )

        self.update_state(state="PROGRESS", meta={"step": "chunking"})  # type: ignore

        db_session.commit()

        return {
            "status": "ok",
            "repo_id": repo.id,
            "owner": repo_owner,
            "name": repo_name,
            "commit_sha": commit_sha,
            "num_of_selected_files": len(selected_files),
        }

    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
        http.close()
