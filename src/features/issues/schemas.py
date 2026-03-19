from datetime import datetime
from typing import Annotated

from pydantic import AliasPath, BaseModel, ConfigDict, Field

# ============================================================================


class IssueAssigneeFromApi(BaseModel):
    github_user_id: int = Field(validation_alias=AliasPath("id"))
    username: str = Field(validation_alias=AliasPath("login"))
    avatar_url: str | None = None


class IssueAssigneeCreate(BaseModel):
    issue_id: int
    github_user_id: int
    username: str
    avatar_url: str | None = None


class IssueAssigneeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    github_user_id: int
    username: str
    avatar_url: str | None = None


# ============================================================================


class IssueCommentFromApi(BaseModel):
    github_comment_id: int = Field(validation_alias=AliasPath("id"))
    github_user_id: int | None = Field(
        default=None, validation_alias=AliasPath("user", "id")
    )
    username: str | None = Field(
        default=None, validation_alias=AliasPath("user", "login")
    )
    avatar_url: str | None = Field(
        default=None, validation_alias=AliasPath("user", "avatar_url")
    )
    posted_at: datetime = Field(validation_alias=AliasPath("created_at"))
    body: str


class IssueCommentCreate(BaseModel):
    issue_id: int
    github_comment_id: int
    github_user_id: int | None = None
    username: str | None = None
    avatar_url: str | None = None
    posted_at: datetime
    body: str


class IssueCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    github_comment_id: int
    github_user_id: int | None = None
    username: str | None = None
    avatar_url: str | None = None
    posted_at: datetime
    body: str


class CommentCreate(BaseModel):
    body: str


# ============================================================================


class IssueLabelFromApi(BaseModel):
    name: str
    description: str | None = None
    color: str


class IssueLabelCreate(BaseModel):
    issue_id: int
    name: str
    description: str | None = None
    color: str


class IssueLabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    name: str
    description: str | None = None
    color: str


# ============================================================================


class IssueFromApi(BaseModel):
    github_id: int = Field(validation_alias=AliasPath("id"))
    number: int
    title: str
    body: str | None = None
    state: str
    opened_at: datetime = Field(validation_alias=AliasPath("created_at"))
    closed_at: datetime | None = None
    author_github_id: int | None = Field(
        default=None, validation_alias=AliasPath("user", "id")
    )
    author_username: str | None = Field(
        default=None, validation_alias=AliasPath("user", "login")
    )
    author_avatar_url: str | None = Field(
        default=None, validation_alias=AliasPath("user", "avatar_url")
    )
    num_of_comments: int = Field(validation_alias=AliasPath("comments"))

    assignees: Annotated[list[IssueAssigneeFromApi], Field(default_factory=list)]
    labels: Annotated[list[IssueLabelFromApi], Field(default_factory=list)]


class IssueCreate(BaseModel):
    github_id: int
    repository_id: int
    number: int
    title: str
    body: str | None = None
    state: str
    opened_at: datetime
    closed_at: datetime | None = None
    author_github_id: int | None = None
    author_username: str | None = None
    author_avatar_url: str | None = None
    num_of_comments: int = 0

    assignees: Annotated[list[IssueAssigneeCreate], Field(default_factory=list)]
    labels: Annotated[list[IssueLabelCreate], Field(default_factory=list)]


class IssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    github_id: int
    number: int
    title: str
    body: str | None = None
    state: str
    opened_at: datetime
    closed_at: datetime | None = None
    author_github_id: int | None = None
    author_username: str | None = None
    author_avatar_url: str | None = None
    num_of_comments: int = 0
    assignees: Annotated[list[IssueAssigneeRead], Field(default_factory=list)]
    labels: Annotated[
        list["IssueLabelRead"],
        Field(
            default_factory=list,
            validation_alias="issue_labels",
        ),
    ]
