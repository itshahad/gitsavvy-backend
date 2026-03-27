from pydantic import BaseModel


class MyWorkStatsResponse(BaseModel):
    in_progress: int
    completed: int
    total_points: int
    level: int
    badges: int
    next_level_at: int


# class MyWorkItemResponse(BaseModel):
#     issue_id: int
#     issue_number: int
#     title: str
#     description: str | None = None

#     repository_id: int
#     repository_name: str
#     repository_owner: str
#     repository_link: str | None = None

#     language: str | None = None
#     status: str
#     progress_percentage: int | None = None

#     opened_at: str | None = None
#     closed_at: str | None = None

#     points: int
#     comments_count: int
#     author_username: str | None = None

class MyWorkItemResponse(BaseModel):
    issue_id: int
    issue_number: int
    title: str
    description: str | None = None

    repository_id: int
    repository_name: str
    repository_owner: str
    repository_link: str | None = None
    repository_branch: str | None = None   

    language: str | None = None
    status: str
    progress_percentage: int | None = None

    opened_at: str | None = None
    closed_at: str | None = None

    points: int
    comments_count: int
    author_username: str | None = None

class MyWorkResponse(BaseModel):
    stats: MyWorkStatsResponse
    current_work: list[MyWorkItemResponse]
    completed_work: list[MyWorkItemResponse]