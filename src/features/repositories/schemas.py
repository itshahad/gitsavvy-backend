from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from pydantic.aliases import AliasPath

from src.core.validators import validate_sha
from src.features.repositories.models import ContributorType


# ====================================================================


class RepositoryTopicModel(BaseModel):
    pass


class TopicRead(RepositoryTopicModel):
    # enables a model to be created from arbitrary class instances by reading their attributes:
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    topic: str


# ====================================================================
class RepositoryLanguageModel(BaseModel):
    pass


class LanguageRead(RepositoryLanguageModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    language: str


# ====================================================================


class RepositoryMetadataModel(BaseModel):
    owner: str = Field(validation_alias=AliasPath("owner", "login"))
    name: str
    description: str | None = None
    forks_count: int | None = None
    open_issues_count: int | None = None
    default_branch: str
    avatar_url: HttpUrl | None = Field(
        default=None, validation_alias=AliasPath("organization", "avatar_url")
    )
    stars_count: int | None = Field(validation_alias=AliasPath("stargazers_count"))
    url: HttpUrl = Field(validation_alias=AliasPath("html_url"))
    # readme_content: str | None = None


class RepoCreate(RepositoryMetadataModel):
    topics: list[str] = []
    language: str | None = None


class RepoRead(RepositoryMetadataModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner: str
    avatar_url: HttpUrl | None = None
    url: HttpUrl
    topics: list[TopicRead] = []
    languages: list[LanguageRead] = []
    stars_count: int | None


# ====================================================================


class ModuleModel(BaseModel):
    repository_id: int
    path: str
    module_parent_id: int | None = None


class ModuleCreate(ModuleModel):
    pass


class ModuleRead(ModuleModel):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ====================================================================


class RepoFileModel(BaseModel):
    repository_id: int
    module_id: int
    commit_sha: str
    file_path: str
    content_hash: str | None = None

    @field_validator("commit_sha", "content_hash", mode="after")
    @classmethod
    def validate_commit_content(cls, v: str) -> str:
        return validate_sha(v)


class FileCreate(RepoFileModel):
    pass


class FileRead(RepoFileModel):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ====================================================================


class RepoStatsModel(BaseModel):
    repository_id: int
    num_of_commits: int
    num_of_merged_pr: int
    num_of_closed_issues: int
    num_of_contributors: int


class RepoStatsCreate(RepoStatsModel):
    pass


class RepoStatsRead(RepoStatsModel):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ====================================================================


class TopRepoContributorsModel(BaseModel):
    avatar_url: HttpUrl | None = Field(default=None)
    num_of_contributions: int = Field(validation_alias=AliasPath("contributions"))
    type: ContributorType


class AnonContributorsCreate(TopRepoContributorsModel):
    name: str


class UserContributorsCreate(TopRepoContributorsModel):
    name: str = Field(validation_alias=AliasPath("login"))


class RepoContributorRead(TopRepoContributorsModel):
    name: str
    model_config = ConfigDict(from_attributes=True)
    id: int
    num_of_contributions: int


# ====================================================================


class RepoMonthlyActivityModel(BaseModel):
    month: str
    num_of_contributions: int = Field(default=0)


class MonthlyActivityCreate(RepoMonthlyActivityModel):
    pass


class MonthlyActivityRead(RepoMonthlyActivityModel):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ====================================================================


class RepoRequest(BaseModel):
    repo_owner: str
    repo_name: str
