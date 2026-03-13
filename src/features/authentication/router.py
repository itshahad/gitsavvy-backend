from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.features.authentication.schemas import GitHubSyncRequest, UserRead
from src.features.authentication.services import sync_user_first_login
from src.features.authentication.dependencies import (
    get_current_claims,
    get_current_user,
    get_current_admin,
)

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


@router.get("/admin/test")
def admin_test(admin=Depends(get_current_admin)):
    return {"message": "Admin access granted"}


# @router.get("/admin/dashboard")
# def admin_dashboard(admin=Depends(get_current_admin)):
#     return {
#         "message": "Welcome admin",
#         "admin_username": admin.username
#     }
