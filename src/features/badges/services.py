from sqlalchemy.orm import Session
from sqlalchemy import select

from src.features.authentication.models import User
from src.features.badges.constants import BADGES_SEED_DATA
from src.features.badges.models import Badge, UserBadge
from src.features.issues.models import Issue, IssueAssignee, IssueLabel


def seed_badges_if_missing(db: Session) -> None:
    for badge_data in BADGES_SEED_DATA:
        existing = db.query(Badge).filter(Badge.name == badge_data["name"]).first()
        if not existing:
            db.add(Badge(**badge_data))
    db.commit()


def get_badge_by_name(db: Session, badge_name: str) -> Badge | None:
    return db.query(Badge).filter(Badge.name == badge_name).first()


def user_has_badge(db: Session, user_id: int, badge_id: int) -> bool:
    existing = (
        db.query(UserBadge)
        .filter(
            UserBadge.user_id == user_id,
            UserBadge.badge_id == badge_id,
        )
        .first()
    )
    return existing is not None


def assign_badge_to_user(db: Session, user: User, badge_name: str) -> None:
    badge = get_badge_by_name(db, badge_name)
    if not badge:
        return

    if user_has_badge(db, user.id, badge.id):
        return

    db.add(UserBadge(user_id=user.id, badge_id=badge.id))
    db.commit()


def qualifies_for_first_contribution(user: User) -> bool:
    return user.points >= 25


def qualifies_for_code_master(user: User) -> bool:
    return user.level >= 5


def qualifies_for_monster(user: User) -> bool:
    return user.level >= 8


def qualifies_for_bug_hunter(db: Session, user: User) -> bool:
    """
    الشرط:
    المستخدم يكون assigned على issue
    وفي نفس الـ issue يوجد label اسمه يحتوي كلمة bug
    """
    issue_with_bug_label = (
        db.query(Issue)
        .join(IssueAssignee, IssueAssignee.issue_id == Issue.id)
        .join(IssueLabel, IssueLabel.issue_id == Issue.id)
        .filter(
            IssueAssignee.github_user_id == user.github_id,
            IssueLabel.name.ilike("%bug%"),
        )
        .first()
    )

    return issue_with_bug_label is not None


def check_and_assign_badges(db: Session, user: User) -> User:
    seed_badges_if_missing(db)

    if qualifies_for_first_contribution(user):
        assign_badge_to_user(db, user, "First Contribution")

    if qualifies_for_bug_hunter(db, user):
        assign_badge_to_user(db, user, "Bug Hunter")

    if qualifies_for_code_master(user):
        assign_badge_to_user(db, user, "Code Master")

    if qualifies_for_monster(user):
        assign_badge_to_user(db, user, "Monster")

    db.refresh(user)
    return user