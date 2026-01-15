from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from pydantic.aliases import AliasPath
import re

class RepositoryTopicModel(BaseModel):
    pass

class TopicRead(RepositoryTopicModel):
    #enables a model to be created from arbitrary class instances by reading their attributes:
    model_config = ConfigDict(from_attributes=True) 

    id: int
    repository_id: int
    topic: str

class RepositoryMetadataModel(BaseModel):
    owner: str = Field(validation_alias=AliasPath("owner", "login"))
    name: str
    description: str | None = None
    url: HttpUrl
    forks_count: int | None = None
    open_issues_count: int | None = None
    default_branch: str
    avatar_url: HttpUrl | None = Field(default=None, validation_alias=AliasPath("organization", "avatar_url"))


class RepoCreate(RepositoryMetadataModel):
    topics: list[str] = []
    language: str | None = None


class RepoRead(RepositoryMetadataModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner: str
    avatar_url: HttpUrl | None = None
    topics: list[TopicRead] = []

#====================================================================

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")

class RepoFileModel(BaseModel):
    repository_id : int
    commit_sha: str
    file_path: str
    content_hash: str | None = None

    @field_validator("commit_sha","content_hash", mode='after')
    @classmethod
    def validate_sha(cls, v: str) -> str:
        if not SHA1_RE.match(v):
            raise ValueError("commit_sha must be a 40-char hex SHA1")
        return v

class FileCreate(RepoFileModel):
    pass

class FileRead(RepoFileModel):
    model_config = ConfigDict(from_attributes=True) 

    id: int

#====================================================================

class Chunk(BaseModel): 
    pass