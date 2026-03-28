from sqlalchemy.orm import Session

from src.features.authentication.models import User, UserPreference
from src.features.userWork.services import sync_user_gamification

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.embedder import batch_encoding, embed_text, embed_texts  # type: ignore
from src.features.authentication.models import User, UserPreference
from src.features.authentication.schemas import (
    UserPreferencesEmbeddingCreate,
)
from src.features.authentication.utils import build_user_profile
from src.models_loader import UserPreferencesEmbedding


def get_or_create_user_preference(db: Session, user: User) -> UserPreference:
    preference = (
        db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
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


class UserProfileEmbeddingService:
    def __init__(
        self,
        db_session: Session,
        embedder: Any,
        tokenizer: Any,
    ) -> None:
        self.db_session = db_session
        self.embedder = embedder
        self.tokenizer = tokenizer

    def embed_user_profile(self, user_id: int):
        user = self.db_session.get(User, user_id)

        if user is None:
            raise ValueError("User is not found")

        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        user_preferences = self.db_session.execute(stmt).scalar_one_or_none()

        if user_preferences is None:
            raise ValueError("User has no preferences")

        user_profile = build_user_profile(pref=user_preferences)

        vec, _meta = self._create_embedding(user_profile=user_profile)

        self._store_embedding(preference_id=user_preferences.id, vec=vec)

    def _create_embedding(self, user_profile: str):
        device = next(self.embedder.parameters()).device

        vec, _meta = embed_text(
            text=user_profile,
            tokenizer=self.tokenizer,
            model=self.embedder,
            batch_encoding=batch_encoding,
            embed_texts=embed_texts,
            device=device,
        )

        return vec, _meta

    def _store_embedding(self, preference_id: int, vec: list[float]):
        embedding_data = UserPreferencesEmbeddingCreate.model_validate(
            {"preferences_id": preference_id, "embedding_vector": vec}
        )
        embedding_db = UserPreferencesEmbedding(**embedding_data.model_dump())
        self.db_session.add(embedding_db)
        self.db_session.commit()
