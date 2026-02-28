# from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
# from pydantic.aliases import AliasPath
# import re
# from .models import ChunkType
# from .utils import validate_sha

# class RepositoryTopicModel(BaseModel):
#     pass

# class TopicRead(RepositoryTopicModel):
#     #enables a model to be created from arbitrary class instances by reading their attributes:
#     model_config = ConfigDict(from_attributes=True) 

#     id: int
#     repository_id: int
#     topic: str

# class RepositoryMetadataModel(BaseModel):
#     owner: str = Field(validation_alias=AliasPath("owner", "login"))
#     name: str
#     description: str | None = None
#     url: HttpUrl
#     forks_count: int | None = None
#     open_issues_count: int | None = None
#     default_branch: str
#     avatar_url: HttpUrl | None = Field(default=None, validation_alias=AliasPath("organization", "avatar_url"))


# class RepoCreate(RepositoryMetadataModel):
#     topics: list[str] = []
#     language: str | None = None


# class RepoRead(RepositoryMetadataModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: int
#     owner: str
#     avatar_url: HttpUrl | None = None
#     topics: list[TopicRead] = []

# #====================================================================


# class RepoFileModel(BaseModel):
#     repository_id : int
#     commit_sha: str
#     file_path: str
#     content_hash: str | None = None

#     @field_validator("commit_sha","content_hash", mode='after')
#     @classmethod
#     def validate_commit_content(cls, v: str) -> str:
#        return validate_sha(v)

# class FileCreate(RepoFileModel):
#     pass

# class FileRead(RepoFileModel):
#     model_config = ConfigDict(from_attributes=True) 
#     id: int

# #====================================================================

# class ChunkModel(BaseModel): 
#     file_id: int
#     chunk_parent_id : int | None = None
#     start_line : int | None = None
#     end_line: int | None = None
#     type : ChunkType
#     content : str
#     embedding_vector: list[int] | None = None
#     content_hash: str | None = None

#     @field_validator("content_hash", mode='after')
#     @classmethod
#     def validate_commit_content(cls, v: str) -> str:
#        return validate_sha(v)
    
# class ChunkCreate(ChunkModel):
#     pass 

# class ChunkRead(ChunkModel):
#     model_config = ConfigDict(from_attributes=True)

#     id: int