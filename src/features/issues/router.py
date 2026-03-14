from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from requests import Session as http_session


# import requests
from src.database import get_db
from src.exceptions import DatabaseError
from src.features.issues.dependencies import get_http_session
from src.features.issues.service import IssuesService
from src.pagination import cursor_pagination_params


router = APIRouter(prefix="/issues", tags=["Issues"])


@router.get("/{repo_id}")
def get_repo_issues(
    repo_id: int,
    db: Session = Depends(get_db),
    http: http_session = Depends(get_http_session),
    pagination: dict[str, int | None] = Depends(cursor_pagination_params),
):
    issues_service = IssuesService(db_session=db, http_session=http, repo_id=repo_id)
    try:
        limit = pagination["limit"]
        cursor = pagination["cursor"]

        result = issues_service.get_repo_issues(
            limit=limit if limit else 10, cursor=cursor
        )
        return result
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail="Database Error") from e
