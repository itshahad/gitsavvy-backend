from pydantic import BaseModel, Field, HttpUrl
from pydantic.aliases import AliasPath

class RepositoryMetadata(BaseModel):
    owner: str = Field(validation_alias=AliasPath("owner", "login"))
    name: str
    description: str
    url: HttpUrl
    forks_count: int
    open_issues_count: int
    default_branch: str
    avatar_url: HttpUrl = Field(validation_alias=AliasPath("organization", "avatar_url"))
    language: str
    topics: list[str]
