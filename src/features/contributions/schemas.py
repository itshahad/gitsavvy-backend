from pydantic import BaseModel


class ClaimIssueResponse(BaseModel):
    message: str
    issue_id: int
    issue_number: int
    repository_id: int
    repository_name: str
    claimed_by_user_id: int
    claimed_by_username: str
    workflow_step: str
    status: str