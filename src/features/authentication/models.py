from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from src.models import BaseModel
from pgvector.sqlalchemy import Vector  # type: ignore


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Firebase identity (ثابت)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    github_id: Mapped[int] = mapped_column(Integer, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    github_access_token_enc: Mapped[str | None] = mapped_column(
        String(2048), nullable=True
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")

    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    preference: Mapped["UserPreference | None"] = relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    user_badges: Mapped[list["UserBadge"]] = relationship(
        "UserBadge",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    badges: Mapped[list["Badge"]] = relationship(
        "Badge",
        secondary="user_badges",
        viewonly=True,
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    languages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    interests: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    user: Mapped["User"] = relationship("User", back_populates="preference")

    user_preferences_embedding: Mapped["UserPreferencesEmbedding"] = relationship(
        back_populates="user_preference",
        cascade="all, delete-orphan",
        uselist=False,
    )


class UserPreferencesEmbedding(BaseModel):
    __tablename__ = "user_preferences_embedding"

    id: Mapped[int] = mapped_column(primary_key=True)
    embedding_vector: Mapped[list[float]] = mapped_column(Vector(1536))

    preferences_id: Mapped[int] = mapped_column(
        ForeignKey("user_preferences.id", ondelete="CASCADE"), unique=True
    )
    user_preference: Mapped["UserPreference"] = relationship(
        back_populates="user_preferences_embedding"
    )

    def __repr__(self):
        return f"UserPreferencesEmbedding(id={self.id!r}, preferences_id={self.preferences_id!r}, embedding_vector={self.embedding_vector!r})"
