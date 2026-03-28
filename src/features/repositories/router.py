from celery import chain  # type: ignore
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from requests import Session as http_session


# import requests
from src.database import get_db
from src.exceptions import DatabaseError
from src.features.documentation_generator.tasks import docs_generator
from src.features.indexer.tasks import IndexerResult, chunk_repo, index_repo
from src.features.repositories.dependencies import get_http_session
from src.features.repositories.schemas import RepoRequest
from src.features.repositories.service import ReposService
from src.features.repositories.tasks import download_repo


router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("/add-repo")
def process_repo(
    data: RepoRequest,
    repo_id: int | None = Query(None),
    doc_gen_from_module: int | None = Query(None),
    doc_gen_from_file: int | None = Query(None),
    doc_gen_from_chunk: int | None = Query(None),
):
    repo_owner = data.repo_owner
    repo_name = data.repo_name

    if repo_id is not None and (
        doc_gen_from_module is not None
        or doc_gen_from_file is not None
        or doc_gen_from_chunk is not None
    ):
        indexer_result: IndexerResult = {
            "name": repo_name,
            "status": "complete",
            "repo_id": repo_id,
        }
        docs_generator.delay(  # type: ignore
            indexer_result=indexer_result,
            start_from_module=doc_gen_from_module,
            start_from_file=doc_gen_from_file,
            start_from_chunk=doc_gen_from_chunk,
        )
        return {"status": "queued", "mode": "resume_docs"}

    chain(
        download_repo.s(repo_owner=repo_owner, repo_name=repo_name),  # type: ignore
        chunk_repo.s(),  # type: ignore
        index_repo.s(),  # type: ignore
        docs_generator.s(),  # type: ignore
    ).apply_async()
    return {"status": "queued", "mode": "full_pipeline"}


@router.get("")
def get_repositories(
    db: Session = Depends(get_db),
):
    repos_service = ReposService(db_session=db)
    try:
        repos = repos_service.get_repos()
        return {"data": repos}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/recommend")
def get_recommended_repositories(
    db: Session = Depends(get_db),
):
    repos_service = ReposService(db_session=db)
    try:
        repos = repos_service.get_recommended_repos(user_id=1)
        return {"data": repos}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/{repo_id}")
def get_repo_by_id(
    repo_id: int,
    db: Session = Depends(get_db),
):
    repos_service = ReposService(db_session=db)
    try:
        repo = repos_service.get_repo_by_id(repo_id=repo_id)
        return {"data": repo}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/{repo_id}/README")
def get_repository_readme(
    repo_id: int,
    db: Session = Depends(get_db),
):
    repos_service = ReposService(db_session=db)
    try:
        readme = repos_service.get_repo_readme(repo_id=repo_id)
        result: dict[str, str | int | None] = {"repo_id": repo_id, "readme": readme}
        return result
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/{repo_id}/stats")
def get_repository_stats(
    repo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    http: http_session = Depends(get_http_session),
):
    repos_service = ReposService(db_session=db, http_session=http)
    try:
        stats = repos_service.get_repo_stats(
            repo_id=repo_id, background_tasks=background_tasks
        )
        return stats
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e
