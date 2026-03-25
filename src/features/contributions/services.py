from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.features.authentication.models import User
from src.features.issues.models import Issue, IssueAssignee
from src.features.repositories.models import Repository


def claim_issue(db: Session, *, issue_id: int, user: User):
    issue = db.scalar(
        select(Issue)
        .options(joinedload(Issue.repository).joinedload(Repository.topics))
        .where(Issue.id == issue_id)
    )

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.state == "closed":
        raise HTTPException(status_code=400, detail="This issue is already closed")

    existing_claim = db.scalar(
        select(IssueAssignee).where(IssueAssignee.issue_id == issue.id)
    )

    if existing_claim:
        if existing_claim.github_user_id == user.github_id:
            return {
                "message": "Issue already claimed by you",
                "issue_id": issue.id,
                "issue_number": issue.number,
                "repository_id": issue.repository.id,
                "repository_name": issue.repository.name,
                "claimed_by_user_id": user.id,
                "claimed_by_username": user.username,
                "workflow_step": "claim_issue",
                "status": "already_claimed",
            }

        raise HTTPException(
            status_code=409,
            detail="Issue already claimed by another contributor",
        )

    assignee = IssueAssignee(
        issue_id=issue.id,
        github_user_id=user.github_id,
        username=user.username,
        avatar_url=user.avatar_url,
    )

    db.add(assignee)
    db.commit()
    db.refresh(issue)

    return {
        "message": "Issue claimed successfully",
        "issue_id": issue.id,
        "issue_number": issue.number,
        "repository_id": issue.repository.id,
        "repository_name": issue.repository.name,
        "claimed_by_user_id": user.id,
        "claimed_by_username": user.username,
        "workflow_step": "claim_issue",
        "status": "claimed",
    }