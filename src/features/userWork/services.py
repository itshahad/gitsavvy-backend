from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.features.authentication.models import User
from src.features.issues.models import Issue, IssueAssignee
from src.features.repositories.models import Repository


POINTS_PER_CONTRIBUTION = 25
POINTS_PER_LEVEL = 200


def sync_user_gamification(db: Session, user: User) -> User:
    stmt = (
        select(Issue)
        .join(IssueAssignee, IssueAssignee.issue_id == Issue.id)
        .options(joinedload(Issue.repository).joinedload(Repository.topics))
        .where(IssueAssignee.github_user_id == user.github_id)
    )

    issues = list(db.scalars(stmt).unique())
    completed_count = sum(1 for issue in issues if issue.state == "closed")

    total_points = completed_count * POINTS_PER_CONTRIBUTION
    level = (total_points // POINTS_PER_LEVEL) + 1

    if user.points != total_points or user.level != level:
        user.points = total_points
        user.level = level
        db.commit()
        db.refresh(user)

    return user


class MyWorkService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def _get_language_from_topics(self, repo):
        topics = getattr(repo, "topics", None)

        if isinstance(topics, list) and topics:
            first_topic = topics[0]

            # إذا كان topic object
            if hasattr(first_topic, "topic"):
                return first_topic.topic

            # إذا كان string
            if isinstance(first_topic, str):
                return first_topic

        return None

    def _get_repo_link(self, repo):
        return getattr(repo, "url", None)

    def _format_status(self, state: str) -> str:
        if state == "open":
            return "In Progress"
        elif state == "closed":
            return "Merged"
        return "Unknown"

    def _progress(self, state: str):
        if state == "open":
            return 75
        elif state == "closed":
            return 100
        return None

    def _get_user_issues(self):
        stmt = (
            select(Issue)
            .join(IssueAssignee, IssueAssignee.issue_id == Issue.id)
            .options(joinedload(Issue.repository).joinedload(Repository.topics))
            .where(IssueAssignee.github_user_id == self.user.github_id)
        )

        return list(self.db.scalars(stmt).unique())

    def get_my_work(self):
        issues = self._get_user_issues()

        current = []
        completed = []

        for issue in issues:
            repo = issue.repository

            item = {
                "issue_id": issue.id,
                "issue_number": issue.number,
                "title": issue.title,
                "description": issue.body,
                "repository_id": repo.id,
                "repository_name": repo.name,
                "repository_owner": repo.owner,
                "repository_link": self._get_repo_link(repo),
                "language": self._get_language_from_topics(repo),
                "status": self._format_status(issue.state),
                "progress_percentage": self._progress(issue.state),
                "opened_at": issue.opened_at.isoformat() if issue.opened_at else None,
                "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                "points": POINTS_PER_CONTRIBUTION if issue.state == "closed" else 0,
                "comments_count": issue.num_of_comments,
                "author_username": issue.author_username,
            }

            if issue.state == "open":
                current.append(item)
            elif issue.state == "closed":
                completed.append(item)

        sync_user_gamification(self.db, self.user)

        badges = self.user.level // 2
        next_level_at = self.user.level * POINTS_PER_LEVEL

        return {
            "stats": {
                "in_progress": len(current),
                "completed": len(completed),
                "total_points": self.user.points,
                "level": self.user.level,
                "badges": badges,
                "next_level_at": next_level_at,
            },
            "current_work": current,
            "completed_work": completed,
        }