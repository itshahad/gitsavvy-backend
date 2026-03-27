# from pydantic import BaseModel


# class PreferenceData(BaseModel):
#     languages: list[str]
#     interests: list[str]


# class UpdatePreferencesRequest(BaseModel):
#     languages: list[str]
#     interests: list[str]


# class UpdatePreferencesResponse(BaseModel):
#     message: str
#     preferences: PreferenceData


# class AccountProfileResponse(BaseModel):
#     id: int
#     username: str
#     name: str | None = None
#     avatar: str | None = None
#     github_id: int
#     role: str
#     points: int
#     level: int
#     github_connected: bool
#     preferences: PreferenceData
from pydantic import BaseModel
from src.features.badges.schemas import BadgeRead


class PreferenceData(BaseModel):
    languages: list[str]
    interests: list[str]


class UpdatePreferencesRequest(BaseModel):
    languages: list[str]
    interests: list[str]


class UpdatePreferencesResponse(BaseModel):
    message: str
    preferences: PreferenceData


class AccountProfileResponse(BaseModel):
    id: int
    username: str
    name: str | None = None
    avatar: str | None = None
    github_id: int
    role: str
    points: int
    level: int
    github_connected: bool
    badges: list[BadgeRead]
    preferences: PreferenceData