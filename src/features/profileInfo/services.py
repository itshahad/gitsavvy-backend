from sqlalchemy.orm import Session

from src.features.authentication.models import User, UserPreference
from src.features.userWork.services import sync_user_gamification


def get_or_create_user_preference(db: Session, user: User) -> UserPreference:
    preference = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == user.id)
        .first()
    )

    if not preference:
        preference = UserPreference(
            user_id=user.id,
            languages=[],
            interests=[],
        )
        db.add(preference)
        db.commit()
        db.refresh(preference)

    return preference


def build_account_profile(db: Session, user: User):
    user = sync_user_gamification(db, user)

    languages = []
    interests = []

    if user.preference:
        languages = user.preference.languages or []
        interests = user.preference.interests or []

    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "avatar": user.avatar_url,
        "github_id": user.github_id,
        "role": user.role,
        "points": user.points,
        "level": user.level,
        "github_connected": user.github_id is not None,
        "preferences": {
            "languages": languages,
            "interests": interests,
        },
    }


def update_user_preferences(
    db: Session,
    *,
    user: User,
    languages: list[str],
    interests: list[str],
) -> UserPreference:
    preference = get_or_create_user_preference(db, user)

    preference.languages = languages
    preference.interests = interests

    db.commit()
    db.refresh(preference)
    return preference