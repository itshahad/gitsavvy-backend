import time
from typing import Any

import requests
from pathlib import Path
from zipfile import ZipFile, BadZipFile, LargeZipFile, ZipInfo
from sqlalchemy.orm import Session, defer
from sqlalchemy import select
from src.exceptions import ExternalServiceError, StorageError
from sqlalchemy.exc import IntegrityError

from src.features.indexer.utils import is_root_readme
from src.features.repositories.config import API_URL, headers
from src.features.repositories.constants import REPOS_PATH
from src.features.repositories.exceptions import raise_request_exception
from src.features.repositories.models import (
    File,
    Module,
    RepoMonthlyActivity,
    RepoStats,
    Repository,
    RepositoryTopic,
    TopRepoContributors,
)
from src.features.repositories.schemas import (
    AnonContributorsCreate,
    FileCreate,
    FileRead,
    ModuleCreate,
    ModuleRead,
    MonthlyActivityCreate,
    MonthlyActivityRead,
    RepoContributorRead,
    RepoCreate,
    RepoRead,
    RepoStatsCreate,
    RepoStatsRead,
    UserContributorsCreate,
)
from src.features.repositories.utils import (
    extract_last_page_count,
    get_item_from_db,
    get_repo_path,
    hash_file_content,
    is_binary,
    is_selected,
    is_skipped,
    weekly_to_monthly_commit_activity,
)
from src.models_loader import ContributorType


class RepoProcessingService:
    def __init__(
        self, db_session: Session, http_session: requests.Session, repo_name: str
    ) -> None:
        self.db_session = db_session
        self.http_session = http_session
        self.repo_path = get_repo_path(repo_name=repo_name)
        self.cashed_modules: dict[tuple[int | None, str], ModuleRead] = {}

    def get_repo_metadata(self, owner: str, repo_name: str, is_commit: bool = False):
        try:
            r = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}", headers=headers()
            )
            r.raise_for_status()
            repo_metadata = RepoCreate.model_validate(r.json())
            repo_data = Repository(
                **repo_metadata.model_dump(
                    exclude={"topics", "url", "avatar_url", "language"}
                ),
                url=str(repo_metadata.url),
                avatar_url=(
                    str(repo_metadata.avatar_url) if repo_metadata.avatar_url else None
                ),
            )

            self.db_session.add(repo_data)
            self.db_session.flush()  # to get an id
            self.db_session.add_all(
                [
                    RepositoryTopic(repository_id=repo_data.id, topic=t)
                    for t in repo_metadata.topics
                ]
            )
            self.db_session.refresh(repo_data)

            if is_commit:
                self.db_session.commit()

            return repo_data

        except IntegrityError as e:
            self.db_session.rollback()
            stmt = select(Repository).where(
                Repository.owner == owner, Repository.name == repo_name
            )
            repo_from_db = get_item_from_db(self.db_session, stmt)
            if repo_from_db is None:
                raise
            return repo_from_db

        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    def download_repo(self, owner: str, repo_name: str) -> tuple[str, str]:
        try:
            commits = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/commits", headers=headers()
            )
            commits.raise_for_status()
            latest_commit: str = commits.json()[0]["sha"]

            self.repo_path.parent.mkdir(parents=True, exist_ok=True)
            r = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/zipball/{latest_commit}",
                headers=headers(),
            )
            r.raise_for_status()
            with open(self.repo_path, mode="wb") as file:
                file.write(r.content)

            return str(self.repo_path), latest_commit
        except (PermissionError, FileNotFoundError, OSError) as e:
            msg = str(e) or "Storage write failed"
            raise StorageError(message=msg) from e
        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    # file selection: -----------------------------------------------------------------------------

    def select_repo_files(
        self,
        repo: Repository,
        zip_file_path: Path,
        repo_name: str,
        commit_sha: str,
        max_size: int = 200_000,
        is_commit: bool = False,
    ):  # 200KB per file
        try:
            selected_files: list[FileRead] = []
            extract_dir = Path(f"{REPOS_PATH}/{repo_name}")

            with ZipFile(zip_file_path, "r") as zip:
                for info in zip.infolist():
                    if info.is_dir() or info.file_size > max_size:
                        continue

                    if (
                        not is_skipped(info.filename)
                        and not is_binary(zip, info)
                        and is_selected(info.filename)
                    ):
                        path = Path(info.filename)
                        parents = path.parts[:-1]
                        parent: ModuleRead | None = None
                        for part in parents:
                            module = self.get_or_create_module(
                                repo_id=repo.id,
                                module=part,
                                parent_id=parent.id if parent else None,
                            )
                            parent = module

                        zip.extract(info.filename, extract_dir)
                        file = self.store_file_to_db(
                            repo.id,
                            commit_sha,
                            zip,
                            info,
                            parent.id if parent else None,
                        )

                        if is_root_readme(zip_entry=info.filename):
                            content = zip.read(info.filename).decode(
                                "utf-8", errors="ignore"
                            )
                            repo.readme_content = content
                            print(content)

                        selected_files.append(file)

                if is_commit:
                    self.db_session.commit()
            return selected_files

        except (BadZipFile, LargeZipFile) as e:
            raise ExternalServiceError(
                service="ZIP", message="invalid zip archive"
            ) from e

        except (PermissionError, FileNotFoundError, OSError) as e:
            msg = str(e) or "Storage read failed"
            raise StorageError(message=msg) from e

    def store_file_to_db(
        self,
        repo_id: int,
        commit_sha: str,
        zip_file: ZipFile,
        info: ZipInfo,
        module_id: int | None,
    ):
        content_hash = hash_file_content(zip_file, info)
        data: dict[str, str | int | None] = {
            "repository_id": repo_id,
            "commit_sha": commit_sha,
            "file_path": info.filename,
            "content_hash": content_hash,
            "module_id": module_id,
        }
        try:
            file_data = FileCreate.model_validate(data)
            file_db = File(**file_data.model_dump())
            self.db_session.add(file_db)
            self.db_session.flush()
            self.db_session.refresh(file_db)
            return FileRead.model_validate(file_db)
        except IntegrityError:
            self.db_session.rollback()
            stmt = select(File).where(
                File.repository_id == data["repository_id"],
                File.commit_sha == data["commit_sha"],
                File.file_path == data["file_path"],
            )
            file_from_db = get_item_from_db(self.db_session, stmt)
            if file_from_db is None:
                raise
            return FileRead.model_validate(file_from_db)

    def get_or_create_module(
        self,
        repo_id: int,
        module: str | None,
        parent_id: int | None = None,
    ):
        if module is None:
            return None

        key = (parent_id, module)

        if key not in self.cashed_modules:
            data = ModuleCreate(
                repository_id=repo_id,
                path=module,
                module_parent_id=parent_id,
            )
            module_db = Module(**data.model_dump())
            self.db_session.add(module_db)
            self.db_session.flush()
            self.db_session.refresh(module_db)
            module_read = ModuleRead.model_validate(module_db)
            self.cashed_modules[key] = module_read

        return self.cashed_modules[key]


class ReposService:
    def __init__(
        self,
        db_session: Session,
        http_session: requests.Session | None = None,
    ) -> None:
        self.db_session = db_session
        self.http_session = http_session

    cached_repos: dict[int, RepoRead] = {}

    def get_repos(self):
        stmt = (
            select(Repository)
            .options(defer(Repository.readme_content))
            .order_by(Repository.id)
        )
        repos = self.db_session.execute(stmt).scalars().all()

        repos_list: list[RepoRead] = []
        for repo in repos:
            repo_read = RepoRead.model_validate(repo)
            repos_list.append(repo_read)
            self.cached_repos[repo.id] = repo_read
        return repos_list

    def get_repo_readme(self, repo_id: int) -> str | None:
        stmt = select(Repository.readme_content).where(Repository.id == repo_id)

        readme = self.db_session.execute(stmt).scalar_one_or_none()

        return readme

    def get_repo_stats(self, repo_id: int):
        try:
            repo = self.cached_repos.get(repo_id, None)
            if repo is None:
                repo = self.db_session.get(Repository, repo_id)

            if repo is None:
                raise ValueError(f"Repository with id {repo_id} was not found")

            num_of_commits = self.compute_num_of_commits(
                owner=repo.owner, repo_name=repo.name
            )
            num_of_merged_pr = self.compute_num_of_merged_pr(
                owner=repo.owner, repo_name=repo.name
            )
            num_of_closed_issues = self.compute_num_of_closed_issues(
                owner=repo.owner, repo_name=repo.name
            )
            num_of_contributors = self.compute_num_of_contributors(
                owner=repo.owner, repo_name=repo.name
            )

            stats_create = RepoStatsCreate(
                repository_id=repo.id,
                num_of_closed_issues=num_of_closed_issues,
                num_of_commits=num_of_commits if num_of_commits is not None else 0,
                num_of_contributors=(
                    num_of_contributors if num_of_contributors is not None else 0
                ),
                num_of_merged_pr=num_of_merged_pr,
            )

            stats = RepoStats(**stats_create.model_dump())
            self.db_session.add(stats)

            monthly_activity = self.compute_monthly_commit_activity(
                owner=repo.owner, repo_name=repo.name
            )

            monthly_rows: list[RepoMonthlyActivity] = []
            if monthly_activity is not None:
                monthly_rows = [
                    RepoMonthlyActivity(repository_id=repo.id, **item.model_dump())
                    for item in monthly_activity
                ]
                self.db_session.add_all(monthly_rows)

            top_contributors = self.get_top_contributors(
                owner=repo.owner, repo_name=repo.name
            )

            contributor_rows: list[TopRepoContributors] = []
            if len(top_contributors) != 0:
                contributor_rows = [
                    TopRepoContributors(
                        repository_id=repo.id,
                        **item.model_dump(exclude={"avatar_url"}),
                        avatar_url=str(item.avatar_url),
                    )
                    for item in top_contributors
                ]
                self.db_session.add_all(contributor_rows)

            self.db_session.commit()

            self.db_session.refresh(stats)
            for row in monthly_rows:
                self.db_session.refresh(row)
            for row in contributor_rows:
                self.db_session.refresh(row)

            res: dict[str, Any] = {
                "stats": RepoStatsRead.model_validate(stats),
                "monthly_activity": [
                    MonthlyActivityRead.model_validate(act) for act in monthly_rows
                ],
                "top_contributors": [
                    RepoContributorRead.model_validate(cont)
                    for cont in contributor_rows
                ],
            }

            return res

        except Exception:
            self.db_session.rollback()
            raise

    def compute_num_of_commits(self, owner: str, repo_name: str):
        if self.http_session is None:
            raise ValueError("HTTP Session is not initialized")
        try:
            r = self.http_session.get(
                f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/commits",
                headers=headers(),
                params={"per_page": 1},
            )
            r.raise_for_status()

            link = r.headers.get("Link")

            if not link:
                return len(r.json())

            count = extract_last_page_count(link_header=link)
            return count
        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    def compute_num_of_merged_pr(self, owner: str, repo_name: str):
        if self.http_session is None:
            raise ValueError("HTTP Session is not initialized")
        try:
            r = self.http_session.get(
                f"{API_URL}/search/issues",
                params={"q": f"repo:{owner}/{repo_name} is:pr is:merged"},
                headers=headers(),
            )
            r.raise_for_status()

            data = r.json()
            return int(data["total_count"])
        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    def compute_num_of_closed_issues(self, owner: str, repo_name: str):
        if self.http_session is None:
            raise ValueError("HTTP Session is not initialized")
        try:
            r = self.http_session.get(
                f"{API_URL}/search/issues",
                params={"q": f"repo:{owner}/{repo_name} is:issue is:closed"},
                headers=headers(),
            )
            r.raise_for_status()

            data = r.json()
            return int(data["total_count"])
        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    def compute_num_of_contributors(self, owner: str, repo_name: str):
        if self.http_session is None:
            raise ValueError("HTTP Session is not initialized")
        try:
            r = self.http_session.get(
                f"{API_URL}/repos/{owner}/{repo_name}/contributors",
                headers=headers(),
                params={"per_page": 1, "anon": "true"},
            )
            r.raise_for_status()

            link = r.headers.get("Link")

            if not link:
                return len(r.json())

            count = extract_last_page_count(link_header=link)
            return count
        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    def compute_monthly_commit_activity(
        self, owner: str, repo_name: str
    ) -> list[MonthlyActivityCreate] | None:
        if self.http_session is None:
            raise ValueError("HTTP Session is not initialized")

        try:
            url = f"{API_URL}/repos/{owner}/{repo_name}/stats/commit_activity"

            weekly_activity: list[Any] = []

            for _ in range(5):
                r = self.http_session.get(url, headers=headers())

                if r.status_code == 202:
                    time.sleep(2)
                    continue

                if r.status_code == 204:
                    weekly_activity = []

                r.raise_for_status()
                weekly_activity = r.json()

            if len(weekly_activity) != 0:
                monthly_activity = weekly_to_monthly_commit_activity(weekly_activity)
                return monthly_activity

            return None

        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)

    def get_top_contributors(self, owner: str, repo_name: str, limit: int = 5):
        if self.http_session is None:
            raise ValueError("HTTP Session is not initialized")
        try:
            r = self.http_session.get(
                f"{API_URL}/repos/{owner}/{repo_name}/contributors",
                headers=headers(),
                params={"per_page": limit, "anon": "true"},
            )
            r.raise_for_status()

            contributors: list[UserContributorsCreate | AnonContributorsCreate] = []

            data = r.json()

            for cont in data:
                type = (
                    ContributorType.User
                    if cont["type"] == "User"
                    else ContributorType.Anonymous
                )
                if type == ContributorType.User:
                    contributors.append(
                        UserContributorsCreate.model_validate({**cont, "type": type})
                    )
                else:
                    contributors.append(
                        AnonContributorsCreate.model_validate({**cont, "type": type})
                    )

            return contributors
        except Exception as e:
            raise_request_exception(e=e, owner=owner, repo_name=repo_name)
