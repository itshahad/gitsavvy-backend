from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.features.authentication.dependencies import get_current_user
from src.features.profileInfo.schemas import (
    AccountProfileResponse,
    UpdatePreferencesRequest,
    UpdatePreferencesResponse,
)
from src.features.profileInfo.services import (
    build_account_profile,
    update_user_preferences,
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/", response_model=AccountProfileResponse)
def get_account_profile(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_account_profile(db, user)


@router.put("/preferences", response_model=UpdatePreferencesResponse)
def update_preferences(
    body: UpdatePreferencesRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preference = update_user_preferences(
        db,
        user=user,
        languages=body.languages,
        interests=body.interests,
    )

    return {
        "message": "Preferences updated successfully",
        "preferences": {
            "languages": preference.languages,
            "interests": preference.interests,
        },
    }