from typing import Any, Generator
from pathlib import Path
import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.exceptions import StorageError
from src.features.indexer.schemas import FileRead
from src.features.indexer.service import (
    chunk_text_files,
    download_repo,
    get_repo_metadata,
)
import src.features.indexer.service as service

from src.database import Base

TEST_DB_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, Any, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize(
    "owner, repo, expected_exception",
    [
        ("", "repo", Exception),
        ("owner", "", Exception),
        ("octocat", "Hello-World", None),
        ("octocat", "Hello-World", None),
        ("psf", "requests", None),
    ],
)
def test_get_repo_metadata_cases(
    owner: str,
    repo: str,
    expected_exception: type[BaseException] | None,
    db_session: Session,
):
    http = requests.Session()

    if expected_exception is not None:
        with pytest.raises(expected_exception):
            get_repo_metadata(
                http=http, owner=owner, repo_name=repo, session=db_session
            )
    else:
        out = get_repo_metadata(
            http=http, owner=owner, repo_name=repo, session=db_session
        )
        assert out != None
        assert out.owner == owner
        assert out.name.lower() == repo.lower()


# ==============================================================================


@pytest.mark.parametrize(
    "owner, repo, expected_exception",
    [
        ("", "repo", Exception),
        ("owner", "", Exception),
        ("octocat", "THIS_REPO_SHOULD_NOT_EXIST_123", Exception),
        ("octocat", "Hello-World", None),
        ("psf", "requests", None),
    ],
)
def test_download_repo_cases(
    owner: str,
    repo: str,
    expected_exception: type[BaseException] | None,
    tmp_path: Path,
):
    http = requests.Session()

    # same idea as your manual test, but safe path
    def fake_get_repo_path(repo_name: str) -> Path:
        return tmp_path / f"{repo_name}.zip"

    # only redirect the file path (NOT mocking logic)
    service.get_repo_path = fake_get_repo_path  # simple assignment, no magic

    if expected_exception is not None:
        with pytest.raises(expected_exception):
            download_repo(http=http, owner=owner, repo_name=repo)
    else:
        res = download_repo(http=http, owner=owner, repo_name=repo)

        assert res != None
        file_path, commit_sha = res

        assert file_path is not None
        assert commit_sha is not None
        assert Path(file_path).exists()


# ==============================================================================


@pytest.mark.parametrize(
    "chunk_size, overlapping, expected_exception",
    [
        (10, 2, None),  # normal
        (10, 10, ValueError),  # overlapping >= chunk_size -> ValueError
    ],
)
def test_chunk_text_files_cases(
    db_session: Session,
    tmp_path: Path,
    chunk_size: int,
    overlapping: int,
    expected_exception: type[BaseException] | None,
):
    # Create a real text file (like your manual test)
    repo_name = "test"
    rel_file_path = "Git-Savvy-test-26c69dc/sample.toml"

    # Put it in a temp folder so we don't touch real repos/
    full_path = tmp_path / rel_file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Write a file with multiple lines so chunking happens
    lines = [f"line {i}\n" for i in range(1, 31)]
    full_path.write_text("".join(lines), encoding="utf-8")

    # Build FileRead like you do manually
    file: FileRead = FileRead(
        repository_id=2,
        commit_sha="26c69dcc6b74480cfd3dbb73ecb942ad91ec5147",
        content_hash="97c74f376096d6bbe4e0dad56a9f77be235597c3",
        file_path=rel_file_path,
        id=26,
    )

    # IMPORTANT: make get_file_complete_path resolve into tmp_path
    # This is not “mocking the logic”, it just points the code to our temp test folder.
    def _fake_get_file_complete_path(file_path: str, repo_name_: str):
        return tmp_path / file_path

    service.get_file_complete_path = _fake_get_file_complete_path

    if expected_exception is not None:
        with pytest.raises(expected_exception):
            chunk_text_files(
                session=db_session,
                repo_id=2,
                file=file,
                repo_name=repo_name,
                chunk_size=chunk_size,
                overlapping=overlapping,
            )
    else:
        out = chunk_text_files(
            session=db_session,
            repo_id=2,
            file=file,
            repo_name=repo_name,
            chunk_size=chunk_size,
            overlapping=overlapping,
        )
        assert out is not None
        assert len(out) > 0
        # minimal sanity
        assert out[0].file_id == file.id


def test_chunk_text_files_missing_file_raises_storage_error(
    db_session: Session, tmp_path: Path
):
    repo_name = "test"
    rel_file_path = "missing/sample.toml"

    file = FileRead(
        repository_id=2,
        commit_sha="26c69dcc6b74480cfd3dbb73ecb942ad91ec5147",
        content_hash="97c74f376096d6bbe4e0dad56a9f77be235597c3",
        file_path=rel_file_path,
        id=26,
    )

    def _fake_get_file_complete_path(file_path: str, repo_name_: str) -> Path:
        return tmp_path / file_path  # but we never create it

    service.get_file_complete_path = _fake_get_file_complete_path

    with pytest.raises(StorageError):
        chunk_text_files(session=db_session, repo_id=2, file=file, repo_name=repo_name)


# ==============================================================================
