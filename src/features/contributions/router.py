from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.features.authentication.dependencies import get_current_user
from src.features.authentication.models import User
from src.features.contributions.schemas import ClaimIssueResponse
from src.features.contributions.services import claim_issue

router = APIRouter(prefix="/contributions", tags=["contributions"])


@router.post("/issues/{issue_id}/claim", response_model=ClaimIssueResponse)
def claim_issue_endpoint(
    issue_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return claim_issue(db, issue_id=issue_id, user=user)