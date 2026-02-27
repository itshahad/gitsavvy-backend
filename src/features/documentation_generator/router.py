from typing import Any

from fastapi import APIRouter, Depends, HTTPException

# import requests
from sqlalchemy.orm import Session
from src.database import get_db
from src.exceptions import DatabaseError
from src.features.documentation_generator.exceptions import RepoNotFound
from src.features.documentation_generator.service import DocsService
from src.features.documentation_generator.tasks import docs_generator
from src.pagination import cursor_pagination_params


router = APIRouter(prefix="/documentation")


@router.get("/generate")
def test(session: Session = Depends(get_db)):
    try:
        repo_id = 2
        repo_name = "fastapi"
        # start_from_module = 607
        # start_from_file_id = 4609
        # start_from_chunk_id = 11590
        docs_generator.delay(  # type: ignore
            repo_id=repo_id,
            repo_name=repo_name,
            # start_from_module=start_from_module,
            # start_from_file=start_from_file_id,
            # start_from_chunk=start_from_chunk_id,
        )
        return {"meow": "meow"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{repo_id}/modules")
def get_repo_modules(
    repo_id: int,
    session: Session = Depends(get_db),
    pagination: dict[str, int | None] = Depends(cursor_pagination_params),
):
    docs_service = DocsService(db=session)

    try:
        modules = docs_service.get_modules(
            repo_id=repo_id, limit=pagination["limit"], cursor=pagination["cursor"]
        )
        next_cursor = modules[-1].id if modules else None
        result: dict[str, Any] = {"data": modules, "next_cursor": next_cursor}
        return result
    except RepoNotFound as e:
        raise HTTPException(status_code=404, detail="Repository not found") from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e
