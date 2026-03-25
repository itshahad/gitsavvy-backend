from datetime import datetime
from typing import TYPE_CHECKING

from src.models import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint

if TYPE_CHECKING:
    from src.features.repositories.models import Repository


class Issue(BaseModel):
    __tablename__ = "issue"

    __table_args__ = (
        UniqueConstraint("repository_id", "number", name="uq_repo_issue_number"),
    )

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
    num_of_comments: Mapped[int] = mapped_column(default=0, server_default="0")

    repository: Mapped["Repository"] = relationship(back_populates="issues")
    assignees: Mapped[list["IssueAssignee"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    issue_comments: Mapped[list["IssueComment"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    issue_labels: Mapped[list["IssueLabel"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"Issue(id={self.id!r}, repository_id={self.repository_id!r})"


class IssueAssignee(BaseModel):
    __tablename__ = "issue_assignee"

    __table_args__ = (
        UniqueConstraint("issue_id", "github_user_id", name="uq_issue_assignee_issue_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id", ondelete="CASCADE"))

    # github_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    github_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
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


class IssueComment(BaseModel):
    __tablename__ = "issue_comment"

    id: Mapped[int] = mapped_column(primary_key=True)

    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id", ondelete="CASCADE"))

    issue: Mapped["Issue"] = relationship(back_populates="issue_comments")

    github_comment_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    github_user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str]
    avatar_url: Mapped[str | None]

    posted_at: Mapped[datetime]

    body: Mapped[str]


class IssueLabel(BaseModel):
    __tablename__ = "issue_label"

    id: Mapped[int] = mapped_column(primary_key=True)

    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id", ondelete="CASCADE"))

    issue: Mapped["Issue"] = relationship(back_populates="issue_labels")

    name: Mapped[str]
    description: Mapped[str]
    color: Mapped[str]
