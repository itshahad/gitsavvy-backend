import requests
from pathlib import Path
from zipfile import ZipFile, BadZipFile, LargeZipFile, ZipInfo
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.exceptions import ExternalServiceError, StorageError
from sqlalchemy.exc import IntegrityError

from src.features.indexer.utils import is_root_readme
from src.features.repositories.config import API_URL, headers
from src.features.repositories.constants import REPOS_PATH
from src.features.repositories.exceptions import raise_request_exception
from src.features.repositories.models import File, Module, Repository, RepositoryTopic
from src.features.repositories.schemas import (
    FileCreate,
    FileRead,
    ModuleCreate,
    ModuleRead,
    RepoCreate,
    RepoRead,
)
from src.features.repositories.utils import (
    get_item_from_db,
    get_repo_path,
    hash_file_content,
    is_binary,
    is_selected,
    is_skipped,
)


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
    ) -> None:
        self.db_session = db_session

    cached_repos: dict[int, RepoRead] = {}

    def get_repos(self):
        stmt = select(Repository).order_by(Repository.id)
        repos = self.db_session.execute(stmt).scalars().all()

        repos_list: list[RepoRead] = []
        for repo in repos:
            repo_read = RepoRead.model_validate(repo)
            repos_list.append(repo_read)
            self.cached_repos[repo.id] = repo_read
        return repos_list
