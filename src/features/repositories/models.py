from typing import TYPE_CHECKING, List

from src.models import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, UniqueConstraint


if TYPE_CHECKING:
    from src.features.indexer.models import Chunk


class Repository(BaseModel):
    __tablename__ = "repository"

    __table_args__ = (UniqueConstraint("owner", "name", name="uq_repo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(nullable=True)
    url: Mapped[str]
    default_branch: Mapped[str] = mapped_column(String(30))
    avatar_url: Mapped[str] = mapped_column(nullable=True)
    stars_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    forks_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    open_issues_count: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

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

    readme_content: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self):
        return f"Repository(id={self.id!r}, owner={self.owner!r}, name={self.name!r}, description={self.description!r}, url={self.url!r}, forks_count={self.forks_count!r}, open_issues_count={self.open_issues_count!r}, default_branch={self.default_branch!r}, avatar_url={self.avatar_url!r})"


# --------------------------------------------------------------


class RepositoryTopic(BaseModel):
    __tablename__ = "repository_topic"

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repository.id", ondelete="CASCADE")
    )
    repository: Mapped["Repository"] = relationship(back_populates="topics")

    # UserId
    topic: Mapped[str]

    def __repr__(self):
        return f"RepositoryTopic(id={self.id!r}, repository_id={self.repository_id!r}, topic={self.topic!r})"


# --------------------------------------------------------------


class Module(BaseModel):
    __tablename__ = "module"

    __table_args__ = (UniqueConstraint("repository_id", "module_parent_id", "path"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repository.id", ondelete="CASCADE")
    )
    repository: Mapped["Repository"] = relationship(back_populates="modules")

    path: Mapped[str]

    files: Mapped[List["File"]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )

    module_parent_id: Mapped[int] = mapped_column(
        ForeignKey("module.id"), nullable=True
    )
    module_parent: Mapped["Module"] = relationship(
        back_populates="children_modules", remote_side=[id]
    )
    children_modules: Mapped[List["Module"]] = relationship(
        back_populates="module_parent", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"File(id={self.id!r}, repository_id={self.repository_id!r}, path={self.path!r})"


# --------------------------------------------------------------


class File(BaseModel):
    __tablename__ = "file"

    __table_args__ = (UniqueConstraint("repository_id", "file_path", name="uq_file"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repository.id", ondelete="CASCADE")
    )
    repository: Mapped["Repository"] = relationship(back_populates="files")

    module_id: Mapped[int] = mapped_column(ForeignKey("module.id"))
    module: Mapped["Module"] = relationship(back_populates="files")

    commit_sha: Mapped[str]
    file_path: Mapped[str]
    content_hash: Mapped[str] = mapped_column(nullable=True)

    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"File(id={self.id!r}, repository_id={self.repository_id!r}, commit_sha={self.commit_sha!r}, file_path={self.file_path!r}, content_hash={self.content_hash!r})"


# --------------------------------------------------------------
