from typing import Any

from fastapi import APIRouter, Depends, HTTPException

# import requests
from sqlalchemy.orm import Session
from src.database import get_db
from src.exceptions import DatabaseError
from src.features.documentation_generator.exceptions import RepoNotFound
from src.features.documentation_generator.pagination import children_pagination_params
from src.features.documentation_generator.service import (
    DocService,
    FileNotFound,
    ModuleNotFound,
)
from src.pagination import cursor_pagination_params


router = APIRouter(prefix="/documentation")


# @router.get("/generate")
# def test(session: Session = Depends(get_db)):
#     try:
#         repo_id = 2
#         repo_name = "fastapi"
#         # start_from_module = 607
#         # start_from_file_id = 4609
#         # start_from_chunk_id = 11590
#         docs_generator.delay(  # type: ignore
#             repo_id=repo_id,
#             repo_name=repo_name,
#             # start_from_module=start_from_module,
#             # start_from_file=start_from_file_id,
#             # start_from_chunk=start_from_chunk_id,
#         )
#         return {"meow": "meow"}
#     except Exception as e:
#         raise HTTPException(status_code=404, detail=str(e))


@router.get("/{repo_id}/children")
def get_repo_modules(
    repo_id: int,
    session: Session = Depends(get_db),
    pagination: dict[str, int | None] = Depends(children_pagination_params),
):
    docs_service = DocService(db=session)

    try:
        root_module = docs_service.get_module(repo_id=repo_id)

        limit = pagination["limit"]
        file_cursor = pagination["file_cursor"]
        module_cursor = pagination["module_cursor"]

        modules, next_module_cursor = docs_service.get_modules(
            repo_id=repo_id,
            module_parent_id=root_module.id,
            limit=limit if limit else 20,
            cursor=module_cursor,
        )
        files, next_file_cursor = docs_service.get_files(
            repo_id=repo_id,
            module_id=root_module.id,
            limit=limit if limit else 20,
            cursor=file_cursor,
        )
        result: dict[str, dict[str, Any]] = {
            "files": {"data": files, "next_cursor": next_file_cursor},
            "modules": {"data": modules, "next_cursor": next_module_cursor},
        }
        return result
    except RepoNotFound as e:
        raise HTTPException(status_code=404, detail="Repository not found") from e
    except ModuleNotFound as e:
        raise HTTPException(status_code=404, detail="Root module not found") from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/{repo_id}/modules/{module_id}/children")
def get_module_children(
    repo_id: int,
    module_id: int,
    session: Session = Depends(get_db),
    pagination: dict[str, int | None] = Depends(children_pagination_params),
):
    docs_service = DocService(db=session)

    try:
        limit = pagination["limit"]
        file_cursor = pagination["file_cursor"]
        module_cursor = pagination["module_cursor"]

        modules, next_module_cursor = docs_service.get_modules(
            repo_id=repo_id,
            module_parent_id=module_id,
            limit=limit if limit else 20,
            cursor=module_cursor,
        )
        files, next_file_cursor = docs_service.get_files(
            repo_id=repo_id,
            module_id=module_id,
            limit=limit if limit else 20,
            cursor=file_cursor,
        )
        result: dict[str, dict[str, Any]] = {
            "files": {"data": files, "next_cursor": next_file_cursor},
            "modules": {"data": modules, "next_cursor": next_module_cursor},
        }
        return result
    except ModuleNotFound as e:
        raise HTTPException(status_code=404, detail="Module not found") from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


# @router.get("/{repo_id}/modules/{module_id}/files")
# def get_module_file(
#     repo_id: int,
#     module_id: int,
#     session: Session = Depends(get_db),
#     pagination: dict[str, int | None] = Depends(cursor_pagination_params),
# ):
#     docs_service = DocService(db=session)

#     try:
#         limit = pagination["limit"]
#         cursor = pagination["cursor"]
#         files, next_cursor = docs_service.get_files(
#             module_id=module_id, limit=limit if limit else 20, cursor=cursor
#         )
#         result: dict[str, Any] = {"data": files, "next_cursor": next_cursor}
#         return result
#     except ModuleNotFound as e:
#         raise HTTPException(status_code=404, detail="Module not found") from e
#     except DatabaseError as e:
#         raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/{repo_id}/modules/{module_id}/files/{file_id}/docs")
def get_file_docs(
    repo_id: int,
    module_id: int,
    file_id: int,
    session: Session = Depends(get_db),
    pagination: dict[str, int | None] = Depends(cursor_pagination_params),
):
    docs_service = DocService(db=session)

    try:
        limit = pagination["limit"]
        cursor = pagination["cursor"]
        files, next_cursor = docs_service.get_chunk_documentation(
            file_id=file_id,
            limit=limit if limit else 20,
            cursor=cursor,
        )
        result: dict[str, Any] = {"data": files, "next_cursor": next_cursor}
        return result
    except FileNotFound as e:
        raise HTTPException(status_code=404, detail="File not found") from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e
