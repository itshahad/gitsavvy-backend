from celery import chain  # type: ignore
from fastapi import APIRouter

# import requests
from src.features.documentation_generator.tasks import docs_generator
from src.features.indexer.tasks import index_repo
from src.features.repositories.schemas import RepoRequest
from src.features.repositories.tasks import download_repo


router = APIRouter(prefix="/repo")


@router.post("/process")
def process_repo(data: RepoRequest):
    repo_owner = data.repo_owner
    repo_name = data.repo_name

    chain(
        download_repo.s(repo_owner=repo_owner, repo_name=repo_name),  # type: ignore
        index_repo.s(),  # type: ignore
        docs_generator.s(),  # type: ignore
    ).apply_async()
