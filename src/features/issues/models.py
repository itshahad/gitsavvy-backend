from datetime import datetime
from typing import TYPE_CHECKING

from src.models import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, ForeignKey

if TYPE_CHECKING:
    from src.features.repositories.models import Repository


class Issue(BaseModel):
    __tablename__ = "issue"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repository.id", ondelete="CASCADE")
    )

    number: Mapped[int]
    title: Mapped[str]
    body: Mapped[str | None]
    state: Mapped[str]

    opened_at: Mapped[datetime]
    closed_at: Mapped[datetime | None]

    author_github_id: Mapped[int | None]
    author_username: Mapped[str | None]
    author_avatar_url: Mapped[str | None]

    repository: Mapped["Repository"] = relationship(back_populates="issues")
    assignees: Mapped[list["IssueAssignee"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"Issue(id={self.id!r}, repository_id={self.repository_id!r})"


class IssueAssignee(BaseModel):
    __tablename__ = "issue_assignee"

    id: Mapped[int] = mapped_column(primary_key=True)

    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id", ondelete="CASCADE"))

    github_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str]
    avatar_url: Mapped[str | None]

    issue: Mapped["Issue"] = relationship(back_populates="assignees")

    def __repr__(self):
        return f"issue_id(id={self.issue_id!r}, github_user_id={self.github_user_id!r}, avatar_url={self.avatar_url!r}, username={self.username!r})"


class RepoIssueSyncState(BaseModel):
    __tablename__ = "repo_issue_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repository.id", ondelete="CASCADE")
    )

    repository: Mapped["Repository"] = relationship(back_populates="issue_sync_state")

    # last_synced_at: Mapped[datetime | None]
    # last_full_sync_at: Mapped[datetime | None]
    next_cursor: Mapped[int | None] = mapped_column(default=1)
    is_fully_synced: Mapped[bool] = mapped_column(default=False)
    is_refreshing: Mapped[bool] = mapped_column(default=False)
    last_error: Mapped[str | None]
