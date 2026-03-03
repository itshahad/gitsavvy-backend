from typing import TYPE_CHECKING, List

from src.models import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, UniqueConstraint

if TYPE_CHECKING:
    from src.features.indexer.models import File, RepositoryTopic, Chunk, Module


class Repository(BaseModel):
    __tablename__ = "repository"

    __table_args__ = (UniqueConstraint("owner", "name", name="uq_repo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(nullable=True)
    url: Mapped[str]
    forks_count: Mapped[int] = mapped_column(nullable=True)
    open_issues_count: Mapped[int] = mapped_column(nullable=True)
    default_branch: Mapped[str] = mapped_column(String(30))
    avatar_url: Mapped[str] = mapped_column(nullable=True)

    files: Mapped[List["File"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

    topics: Mapped[List["RepositoryTopic"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

    modules: Mapped[List["Module"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"Repository(id={self.id!r}, owner={self.owner!r}, name={self.name!r}, description={self.description!r}, url={self.url!r}, forks_count={self.forks_count!r}, open_issues_count={self.open_issues_count!r}, default_branch={self.default_branch!r}, avatar_url={self.avatar_url!r})"
