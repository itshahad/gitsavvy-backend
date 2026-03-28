from pydantic import BaseModel, ConfigDict, Field


class GitHubUser(BaseModel):
    username: str = Field(alias="login", max_length=100)
    github_id: int = Field(alias="id")
    name: str | None = Field(default=None, alias="name")
    avatar_url: str | None = Field(default=None, alias="avatar_url")

    model_config = ConfigDict(populate_by_name=True)


class UserBase(BaseModel):
    username: str
    github_id: int
    name: str | None = None
    role: str
    points: int
    level: int


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class GitHubSyncRequest(BaseModel):
    github_access_token: str


# ====================================================================


class UserPreferencesEmbeddingModel(BaseModel):
    preferences_id: int
    embedding_vector: list[float]


class UserPreferencesEmbeddingCreate(UserPreferencesEmbeddingModel):
    pass


class UserPreferencesEmbeddingRead(UserPreferencesEmbeddingModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
