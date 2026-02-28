

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from authentication.schemas import GitHubSyncRequest, UserRead
from authentication.services import sync_user_first_login
from authentication.dependencies import get_current_claims, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/github/sync", response_model=UserRead)
def github_sync(
    body: GitHubSyncRequest,
    claims=Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    firebase_uid = claims["uid"]

    try:
        user = sync_user_first_login(
            db,
            firebase_uid=firebase_uid,
            github_access_token=body.github_access_token,
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserRead)
def me(user=Depends(get_current_user)):
    return user