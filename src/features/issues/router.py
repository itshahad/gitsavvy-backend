from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from requests import Session as http_session


# import requests
from src.database import get_db
from src.exceptions import DatabaseError
from src.features.issues.dependencies import get_http_session

# from src.features.issues.schemas import CommentCreate
from src.features.issues.service import IssueNotFoundError, IssuesService
from src.pagination import cursor_pagination_params


router = APIRouter(prefix="/issues", tags=["Issues"])


@router.get("/{repo_id}")
def get_repo_issues(
    repo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    http: http_session = Depends(get_http_session),
    pagination: dict[str, int | None] = Depends(cursor_pagination_params),
):
    issues_service = IssuesService(db_session=db, http_session=http, repo_id=repo_id)
    try:
        limit = pagination["limit"]
        cursor = pagination["cursor"]

        result = issues_service.get_repo_issues(
            limit=limit if limit else 10,
            cursor=cursor,
            background_tasks=background_tasks,
        )
        return result
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/{repo_id}/{issue_number}")
def get_issue(
    repo_id: int,
    issue_number: int,
    db: Session = Depends(get_db),
    http: http_session = Depends(get_http_session),
):
    issues_service = IssuesService(db_session=db, http_session=http, repo_id=repo_id)
    try:
        result = issues_service.get_issue(issue_number=issue_number)
        return result
    except IssueNotFoundError as e:
        raise HTTPException(status_code=404, detail="Issue Not Found") from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


@router.get("/{repo_id}/{issue_number}/comments")
def get_issue_comments(
    repo_id: int,
    issue_number: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    http: http_session = Depends(get_http_session),
):
    issues_service = IssuesService(db_session=db, http_session=http, repo_id=repo_id)
    try:
        result = issues_service.get_issue_comments(
            issue_number=issue_number, background_tasks=background_tasks
        )
        return result
    except IssueNotFoundError as e:
        raise HTTPException(status_code=404, detail="Issue Not Found") from e
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e


# @router.post("/{repo_id}/{issue_number}/comments")
# def post_comment(
#     repo_id: int,
#     issue_number: int,
#     data: CommentCreate,
#     db: Session = Depends(get_db),
#     http: http_session = Depends(get_http_session),
# ):
#     print(data.body)
#     issues_service = IssuesService(db_session=db, http_session=http, repo_id=repo_id)
#     try:
#         result = issues_service.post_comment(
#             issue_number=issue_number, comment_body=data.body
#         )
#         return result
#     except IssueNotFoundError as e:
#         raise HTTPException(status_code=404, detail="Issue Not Found") from e
#     except DatabaseError as e:
#         raise HTTPException(status_code=500, detail="Database Error") from e
