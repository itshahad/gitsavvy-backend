from typing import Any

from fastapi import BackgroundTasks
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session, defer, selectinload
from src.core.validators import is_stale
from src.database import SessionLocal
from src.exceptions import raise_request_exception
from src.features.issues.constants import (
    ISSUE_COMMENTS_STALE_TIME,
    ISSUE_STALE_TIME,
)
from sqlalchemy.exc import NoResultFound

from src.features.issues.exceptions import IssueNotFoundError
from src.features.issues.models import Issue, IssueAssignee, RepoIssueSyncState
from src.features.issues.schemas import (
    IssueCommentFromApi,
    IssueCommentRead,
    IssueFromApi,
    IssueRead,
)
from src.features.issues.utils import extract_next_page_from_link
from src.features.repositories.config import API_URL, headers
from src.features.repositories.constants import REPOS_PATH
from src.features.repositories.models import Repository
from src.models_loader import IssueComment, IssueLabel


def refresh_issues_task(repo_id: int):
    db = SessionLocal()
    http = requests.session()
    try:
        service = IssuesService(db_session=db, http_session=http, repo_id=repo_id)
        service.refresh_repo_issues()
    finally:
        db.close()
        http.close()


def refresh_issue_comments_task(repo_id: int, issue_number: int):
    db = SessionLocal()
    http = requests.session()
    try:
        service = IssuesService(db_session=db, http_session=http, repo_id=repo_id)
        service.refresh_issue_comment(issue_number=issue_number)
    finally:
        db.close()
        http.close()


class IssuesService:
    def __init__(
        self, db_session: Session, http_session: requests.Session, repo_id: int
    ) -> None:
        self.db_session = db_session
        self.http_session = http_session
        self.repo_id = repo_id

    def _get_repo(self):
        repo = self.db_session.get(
            Repository,
            self.repo_id,
            options=[
                defer(Repository.readme_content),
            ],
        )
        if repo is None:
            raise ValueError(f"Repository with id {self.repo_id} was not found")
        return repo

    def _get_or_create_repo_sync_state(self) -> RepoIssueSyncState:
        repo_sync_state = self.db_session.scalar(
            select(RepoIssueSyncState).where(
                RepoIssueSyncState.repository_id == self.repo_id
            )
        )

        if repo_sync_state is None:
            repo_sync_state = RepoIssueSyncState(
                repository_id=self.repo_id,
                next_cursor=1,
                is_fully_synced=False,
                is_refreshing=False,
            )
            self.db_session.add(repo_sync_state)
            self.db_session.commit()

        return repo_sync_state

    def _get_repo_issues_from_db(
        self,
        limit: int = 10,
        cursor: int | None = None,
    ) -> list[Issue]:
        query = (
            select(Issue)
            .where(Issue.repository_id == self.repo_id)
            .options(
                selectinload(Issue.assignees),
                selectinload(Issue.issue_labels),
            )
            .order_by(Issue.number.desc())
            .limit(limit)
        )

        if cursor is not None:
            query = query.where(Issue.number < cursor)

        return list(self.db_session.scalars(query))

    def _store_or_update_issues(
        self,
        repo_id: int,
        issues: list[IssueFromApi],
    ) -> list[Issue]:
        if not issues:
            return []

        github_ids = [issue.github_id for issue in issues]

        existing_issues = list(
            self.db_session.scalars(
                select(Issue).where(
                    Issue.repository_id == repo_id,
                    Issue.github_id.in_(github_ids),
                )
            )
        )
        existing_by_github_id = {issue.github_id: issue for issue in existing_issues}

        stored_issues: list[Issue] = []

        for issue_data in issues:
            issue = existing_by_github_id.get(issue_data.github_id)

            if issue is None:
                issue = Issue(
                    repository_id=repo_id,
                    **issue_data.model_dump(exclude={"assignees", "labels"}),
                )
                self.db_session.add(issue)
            else:
                for field, value in issue_data.model_dump(
                    exclude={"assignees", "labels"}
                ).items():
                    setattr(issue, field, value)

                issue.assignees.clear()
                issue.issue_labels.clear()

            for assignee_data in issue_data.assignees:
                issue.assignees.append(
                    IssueAssignee(
                        issue_id=issue.id,
                        **assignee_data.model_dump(),
                    )
                )
            for label in issue_data.labels:
                issue.issue_labels.append(
                    IssueLabel(
                        issue_id=issue.id,
                        **label.model_dump(),
                    )
                )

            stored_issues.append(issue)

        self.db_session.flush()
        return stored_issues

    def _get_repo_issues_from_api(
        self, limit: int | None = 10, cursor: int | None = None
    ):
        try:
            repo = self._get_repo()

            r = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{repo.owner}/{repo.name}/issues",
                headers=headers(),
                params={
                    "per_page": limit,
                    "page": cursor,
                },
            )
            r.raise_for_status()

            link_header = r.headers.get("Link")

            next_cursor = None
            if link_header is not None:
                next_cursor = extract_next_page_from_link(link_header)

            data = r.json()
            issues: list[IssueFromApi] = []

            for i in data:
                if "pull_request" in i:
                    continue
                issues.append(IssueFromApi.model_validate(i))

            return issues, next_cursor
        except Exception as e:
            raise e

    def refresh_repo_issues(self, max_pages: int = 3) -> None:
        print("refreshing")
        repo_sync_state = self._get_or_create_repo_sync_state()

        if repo_sync_state.is_refreshing:
            return

        repo_sync_state.is_refreshing = True
        repo_sync_state.last_error = None
        self.db_session.commit()

        try:
            for page in range(1, max_pages + 1):
                fetched_issues, _ = self._get_repo_issues_from_api(
                    limit=100,
                    cursor=page,
                )

                if not fetched_issues:
                    break

                self._store_or_update_issues(
                    repo_id=self.repo_id,
                    issues=fetched_issues,
                )

                # if page came back with less than full size, no more recent pages
                if len(fetched_issues) < 100:
                    break

            self.db_session.commit()

        except Exception as e:
            repo_sync_state.last_error = str(e)
            self.db_session.commit()
            raise
        finally:
            repo_sync_state.is_refreshing = False
            self.db_session.commit()

    def get_repo_issues(
        self,
        limit: int = 10,
        cursor: int | None = None,
        background_tasks: BackgroundTasks | None = None,
    ):
        repo_sync_state = self._get_or_create_repo_sync_state()

        if is_stale(
            updated_at=repo_sync_state.updated_at, stale_after=ISSUE_STALE_TIME
        ):
            if background_tasks is not None:
                background_tasks.add_task(refresh_issues_task, self.repo_id)

        issues: list[Issue] = self._get_repo_issues_from_db(limit=limit, cursor=cursor)

        # DB already has enough data
        if len(issues) == limit:
            result: dict[str, Any] = {
                "data": issues,
                "next_cursor": issues[-1].number if issues else None,
            }
            return result

        # DB has all data and this is the end ---- hold your breath and count to ten :)
        if repo_sync_state.is_fully_synced:
            result: dict[str, Any] = {
                "data": issues,
                "next_cursor": None,
            }
            return result

        # Need to backfill from GitHub
        while len(issues) < limit and not repo_sync_state.is_fully_synced:
            fetched_issues, next_page = self._get_repo_issues_from_api(
                limit=100,
                cursor=repo_sync_state.next_cursor,
            )

            if not fetched_issues:
                repo_sync_state.is_fully_synced = True
                repo_sync_state.next_cursor = None
                self.db_session.commit()
                break

            self._store_or_update_issues(repo_id=self.repo_id, issues=fetched_issues)

            repo_sync_state.next_cursor = next_page
            if next_page is None:
                repo_sync_state.is_fully_synced = True

            self.db_session.commit()

            issues = self._get_repo_issues_from_db(limit=limit, cursor=cursor)

        result: dict[str, Any] = {
            "data": issues,
            "next_cursor": issues[-1].number if issues else None,
        }
        return result

    def get_issue(self, issue_number: int):
        stmt = (
            select(Issue)
            .where(Issue.repository_id == self.repo_id, Issue.number == issue_number)
            .options(
                selectinload(Issue.assignees),
                selectinload(Issue.issue_labels),
            )
        )

        try:
            issue = self.db_session.execute(stmt).scalar_one()
        except NoResultFound:
            raise IssueNotFoundError(issue_number)

        return IssueRead.model_validate(issue)

    def _get_issue_comments_from_api(self, issue_number: int):
        print("calling api")
        try:
            repo = self._get_repo()

            r = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{repo.owner}/{repo.name}/issues/{issue_number}/comments",
                headers=headers(),
            )
            r.raise_for_status()

            data = r.json()

            comments: list[IssueCommentFromApi] = [
                IssueCommentFromApi.model_validate(com) for com in data
            ]

            return comments
        except Exception as e:
            raise_request_exception(
                e=e, not_found_exception=IssueNotFoundError(issue_number=issue_number)
            )

    def _store_or_update_comments(
        self, issue_number: int, api_comments: list[IssueCommentFromApi]
    ):
        issue = self.get_issue(issue_number=issue_number)

        comments_from_db = self._get_issue_comments_from_db(issue_number=issue_number)

        existing_comment_by_number = {
            comment.github_comment_id: comment for comment in comments_from_db
        }

        api_comment_by_number = {
            comment.github_comment_id: comment for comment in api_comments
        }

        stored_comments: list[IssueComment] = []

        for db_comment in comments_from_db:
            if db_comment.github_comment_id not in api_comment_by_number:
                self.db_session.delete(db_comment)

        for com in api_comments:
            comment = existing_comment_by_number.get(com.github_comment_id)

            if comment is None:
                comment = IssueComment(issue_id=issue.id, **com.model_dump())
                self.db_session.add(comment)
            else:
                for field, value in com.model_dump().items():
                    setattr(comment, field, value)

            stored_comments.append(comment)

        self.db_session.commit()
        return stored_comments

    def _upsert_single_comment(self, issue_number: int, com: IssueCommentFromApi):
        issue = self.get_issue(issue_number=issue_number)

        comment = self.db_session.scalar(
            select(IssueComment).where(
                IssueComment.github_comment_id == com.github_comment_id
            )
        )

        if comment is None:
            comment = IssueComment(issue_id=issue.id, **com.model_dump())
            self.db_session.add(comment)
        else:
            for field, value in com.model_dump().items():
                setattr(comment, field, value)

        self.db_session.commit()
        return comment

    def _get_issue_comments_from_db(self, issue_number: int):
        issue = self.get_issue(issue_number=issue_number)

        query = (
            select(IssueComment)
            .where(IssueComment.issue_id == issue.id)
            .order_by(IssueComment.posted_at)
        )

        return list(self.db_session.scalars(query))

    def refresh_issue_comment(self, issue_number: int):
        print("refreshing")

        comments_from_api = self._get_issue_comments_from_api(issue_number=issue_number)

        self._store_or_update_comments(
            issue_number=issue_number, api_comments=comments_from_api
        )

    def get_issue_comments(
        self, issue_number: int, background_tasks: BackgroundTasks | None
    ):
        comments_from_db = self._get_issue_comments_from_db(issue_number=issue_number)
        print(len(comments_from_db))

        if len(comments_from_db) != 0:
            print("here")
            last_fetch_time = comments_from_db[0].updated_at

            if is_stale(
                updated_at=last_fetch_time, stale_after=ISSUE_COMMENTS_STALE_TIME
            ):
                if background_tasks is not None:
                    background_tasks.add_task(
                        refresh_issue_comments_task, self.repo_id, issue_number
                    )
            result = {
                "comments": [
                    IssueCommentRead.model_validate(com) for com in comments_from_db
                ]
            }
            return result
        else:
            comments_from_api = self._get_issue_comments_from_api(
                issue_number=issue_number
            )

            stored_comments = self._store_or_update_comments(
                issue_number=issue_number, api_comments=comments_from_api
            )

            result = {
                "comments": [
                    IssueCommentRead.model_validate(com) for com in stored_comments
                ]
            }
            return result

    # THE TOKEN OF THIS ENDPOINT SHOULD BE THE USER TOKEN, BUT FOR NOW IM USING MY OWN
    # def post_comment(self, comment_body: str, issue_number: int):
    #     try:
    #         repo = self._get_repo()

    #         print(headers(custom_token=CUSTOM_TOKEN))
    #         r = self.http_session.post(
    #             f"{API_URL}{REPOS_PATH}/{repo.owner}/{repo.name}/issues/{issue_number}/comments",
    #             headers=headers(custom_token=CUSTOM_TOKEN),
    #             json={"body": comment_body},
    #         )
    #         print(r.headers)
    #         print(r.status_code)
    #         print(r.text)
    #         r.raise_for_status()

    #         comment_data = IssueCommentFromApi.model_validate(r.json())
    #         print(comment_data)
    #         comment = self._upsert_single_comment(
    #             issue_number=issue_number,
    #             com=comment_data,
    #         )

    #         return IssueCommentRead.model_validate(comment)
    #     except:
    #         pass
