from datetime import datetime

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class IssueModel(BaseModel):
    github_id: int = Field(validation_alias=AliasPath("id"))
    number: int
    title: str
    body: str | None
    state: str
    opened_at: datetime = Field(validation_alias=AliasPath("created_at"))
    closed_at: datetime | None
    author_github_id: int | None = Field(validation_alias=AliasPath("user", "id"))
    author_username: str | None = Field(validation_alias=AliasPath("user", "login"))
    num_of_comments: int = Field(validation_alias=AliasPath("comments"))
    author_avatar_url: str | None = Field(
        validation_alias=AliasPath("user", "avatar_url")
    )
    assignees: list["IssueAssigneeModel"] = Field(default=[])


class IssueFromApi(IssueModel):
    pass


class IssueCreate(IssueModel):
    repository_id: int
    pass


class IssueRead(IssueModel):
    model_config = ConfigDict(from_attributes=True)
    repository_id: int
    id: int
    github_id: int
    opened_at: datetime
    author_github_id: int | None
    author_username: str | None
    author_avatar_url: str | None
    num_of_comments: int


# =======================================================================


class IssueAssigneeModel(BaseModel):
    github_user_id: int = Field(validation_alias=AliasPath("id"))
    username: str = Field(validation_alias=AliasPath("login"))
    avatar_url: str | None


class IssueAssigneeFromApi(IssueAssigneeModel):
    pass


class IssueAssigneeCreate(IssueAssigneeModel):
    issue_id: int
    pass


class IssueAssigneeRead(IssueAssigneeModel):
    issue_id: int
    model_config = ConfigDict(from_attributes=True)
    id: int
    github_user_id: int
    username: str


# =======================================================================


class IssueCommentModel(BaseModel):
    github_user_id: int = Field(validation_alias=AliasPath("user", "id"))
    username: str = Field(validation_alias=AliasPath("user", "login"))
    avatar_url: str | None = Field(validation_alias=AliasPath("user", "avatar_url"))
    github_comment_id: int = Field(validation_alias=AliasPath("id"))
    posted_at: datetime = Field(validation_alias=AliasPath("created_at"))
    body: str


class IssueCommentFromApi(IssueCommentModel):
    pass


class IssueCommentCreate(IssueCommentModel):
    issue_id: int
    pass


class IssueCommentRead(IssueCommentModel):
    issue_id: int
    model_config = ConfigDict(from_attributes=True)
    id: int
    github_user_id: int
    username: str
    avatar_url: str | None
    posted_at: datetime
